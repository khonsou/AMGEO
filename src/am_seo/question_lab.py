"""Skill-driven question panels and isolated API answer tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from .credentials import credential_vault
from .workflow import atomic, load

INTENTS = {"find", "alternatives", "how", "facts"}
LOCALES = {"zh-CN", "en-US"}
PRESETS = {"deepseek": "https://api.deepseek.com/v1", "openai": "https://api.openai.com/v1"}
BRAND = re.compile(r"angry[\s_-]*miao|怒喵", re.I)
PRODUCT = re.compile(r"\bam[\s_-]*infinity(?:[\s_-]*mouse)?\b|\bcyberboard(?:[\s_-]*(?:r6|ai))?\b", re.I)
METRIC = "am-brand-or-product-presence-v1"


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def digest(value): return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def scrub(value, key=None):
    if not isinstance(value, str): return value
    if key: value = value.replace(key, "[credential removed]")
    return re.sub(r"\bsk-[A-Za-z0-9_-]{16,}", "[credential removed]", value)


class ProviderError(ValueError):
    def __init__(self, message, *, hard=False): super().__init__(message); self.hard = hard


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("接口发生跳转，已停止传送凭证。", hard=True)


def validate_endpoint(provider, endpoint):
    if provider not in {"deepseek", "openai", "custom"}: raise ValueError("请选择 API 服务。")
    if provider in PRESETS:
        if endpoint and endpoint.rstrip("/") != PRESETS[provider]: raise ValueError("服务与 Base URL 不匹配。")
        return PRESETS[provider]
    if not isinstance(endpoint, str): raise ValueError("请填写服务的 HTTPS Base URL。")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL 须为无凭证、无查询参数的公开 HTTPS 地址。")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses): raise ValueError()
    except (OSError, ValueError): raise ValueError("Base URL 必须指向可解析的公网服务。")
    return endpoint.rstrip("/")


class CompatibleClient:
    """No automatic retries or redirects; error bodies and headers are not persisted."""
    def __init__(self, connection, key): self.connection, self.key = connection, key

    def request(self, path, payload=None):
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = Request(self.connection["base_url"] + path, data=data,
                          headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=60) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024: raise ProviderError("API 返回超过本次读取上限。")
                result = json.loads(raw)
                if not isinstance(result, dict): raise ProviderError("API 返回格式不正确。")
                return result
        except HTTPError as error:
            raise ProviderError(f"API 返回 HTTP {error.code}；请核对服务、模型、凭证或余额。", hard=error.code in {400, 401, 402, 403, 404, 429}) from None
        except (URLError, TimeoutError, json.JSONDecodeError):
            raise ProviderError("API 网络、超时或响应格式错误；本次未自动重试。") from None

    def models(self):
        result = self.request('/models')
        return [item['id'] for item in result.get('data', []) if isinstance(item, dict) and isinstance(item.get('id'), str)
                and self.key not in item['id'] and not re.search(r'\bsk-[A-Za-z0-9_-]{16,}', item['id'])]

    def complete(self, messages, *, json_output=False):
        payload = {"model": self.connection['model'], "messages": messages, "max_tokens": 2400 if json_output else 1100, "stream": False}
        if self.connection.get('provider') == 'deepseek': payload['thinking'] = {'type': 'disabled'}
        if json_output: payload['response_format'] = {"type": "json_object"}
        result = self.request('/chat/completions', payload)
        choices = result.get('choices') or []
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict): raise ProviderError("API 未返回回答选项。", hard=True)
        choice = choices[0]; message = choice.get('message')
        if not isinstance(message, dict) or 'content' not in message: raise ProviderError("API 回答字段格式错误。", hard=True)
        content = message['content']; answer = '' if content is None else content
        if not isinstance(answer, str): raise ProviderError("当前接口未返回文本回答。", hard=True)
        if choice.get('finish_reason') == 'length': raise ProviderError("回答达到长度上限，未纳入命中评分；已停止后续调用。", hard=True)
        raw_usage = result.get('usage') or {}
        if not isinstance(raw_usage, dict): raise ProviderError("API 用量字段格式错误；本题未确认完成。", hard=True)
        usage = {k: v for k, v in raw_usage.items() if k in {'prompt_tokens', 'completion_tokens', 'total_tokens'} and isinstance(v, int)}
        return {"text": scrub(answer, self.key), "usage": usage, "returned_model": scrub(str(result.get('model') or self.connection['model']), self.key)}


def normalize_panel(result, key=None):
    questions = result.get('questions') if isinstance(result, dict) else None
    if not isinstance(questions, list) or len(questions) != 8: raise ValueError("问题生成结果必须为中英各四题。")
    normalized, cells, prompts = [], set(), set()
    for index, question in enumerate(questions, 1):
        if not isinstance(question, dict): raise ValueError("问题记录格式不正确。")
        locale, intent = question.get('locale'), question.get('intent')
        line, prompt = question.get('product_line'), question.get('prompt')
        if not isinstance(locale, str) or not isinstance(intent, str) or not isinstance(line, str) or locale not in LOCALES or intent not in INTENTS or line not in {'mouse', 'ai_device'} or not isinstance(prompt, str) or not 8 <= len(prompt.strip()) <= 700:
            raise ValueError("问题的语言、方向、产品或正文无效。")
        if (locale, intent) in cells or prompt.strip().casefold() in prompts: raise ValueError("问题方向或正文重复。")
        if (key and key in prompt) or re.search(r'\bsk-[A-Za-z0-9_-]{16,}', prompt): raise ValueError("问题含疑似凭证，已停止保存。")
        cells.add((locale, intent)); prompts.add(prompt.strip().casefold())
        seeded = bool(BRAND.search(prompt) or PRODUCT.search(prompt))
        normalized.append({"id": f"Q{index:02}", "locale": locale, "intent": intent, "product_line": line, "prompt": prompt.strip(),
                           "brand_seeded": seeded, "test_group": "branded" if seeded else "discovery"})
    for locale in LOCALES:
        if {q['product_line'] for q in normalized if q['locale'] == locale} != {'mouse', 'ai_device'}:
            raise ValueError("每种语言的问题需同时覆盖电竞鼠标与 AI device。")
    return normalized


def classify_answer(text):
    brand = [m.group(0) for m in BRAND.finditer(text)]
    product = [m.group(0) for m in PRODUCT.finditer(text)]
    return {"brand_mentioned": bool(brand), "product_mentioned": bool(product), "hit": bool(brand or product), "matches": list(dict.fromkeys(brand + product))}


def summarize(records):
    groups = []
    for locale in ('zh-CN', 'en-US'):
        for kind in ('discovery', 'branded'):
            rows = [r for r in records if r['locale'] == locale and r['test_group'] == kind]
            if not rows: continue
            valid = [r for r in rows if r['status'] in {'completed', 'no_ai_answer'}]
            hits = sum(bool(r.get('hit')) for r in valid)
            groups.append({"locale": locale, "test_group": kind, "planned": len(rows), "successful_tests": len(valid), "hits": hits,
                           "errors": sum(r['status'] == 'error' for r in rows), "not_run": sum(r['status'] == 'not_run' for r in rows),
                           "no_ai_answers": sum(r['status'] == 'no_ai_answer' for r in rows), "score": round(100 * hits / len(valid), 1) if valid else None})
    return groups


class QuestionLab:
    def __init__(self, root, workspace, *, vault=None, client_factory=None):
        self.root = Path(root).resolve(); self.workspace = workspace; self.directory = self.root / 'outputs/runtime/console/question-lab'
        self.path = self.directory / 'state.json'; self.lock = threading.RLock(); self.vault = vault or credential_vault(root)
        self.factory = client_factory or CompatibleClient; self.thread = None
        self.data = load(self.path, {'connection': {}, 'panel': None, 'runs': [], 'job': None})
        self._key = self.vault.get() if self.data.get('connection') else None
        if self._key:
            connection = self.data['connection']
            expected = digest({'base_url': connection.get('base_url'), 'key': self._key})
            if connection.get('_credential_binding') != expected:
                self._key = None
                connection.update(verified=False, last_error='保存的凭证与此服务不匹配，请重新提供该服务的 key。')
        if self.data.get('job', {}) and self.data['job'].get('status') in {'queued', 'generating', 'testing'}:
            self.data['job'].update(status='error', error='服务重启，旧任务未确认完成。', finished_at=now())
            for run in self.data['runs']:
                if run.get('status') == 'testing':
                    for record in run['observations']:
                        if record['status'] == 'running': record.update(status='error', error='服务中断，未取得完整 API 响应。', finished_at=now())
                    run.update(status='partial', finished_at=now(), groups=summarize(run['observations']))
            self.save()

    def save(self): atomic(self.path, self.data)
    def active(self): return bool(self.thread and self.thread.is_alive())

    def state(self):
        with self.lock:
            state = deepcopy(self.data)
            state.get('connection', {}).pop('_credential_binding', None)
            state['connection'] = {**state.get('connection', {}), 'has_key': bool(self._key), 'storage': self.vault.storage}
            state['active'] = self.active(); return state

    def configure(self, payload):
        with self.lock:
            if self.active(): raise ValueError("测试运行中，结束后再更改服务。")
            provider = payload.get('provider'); endpoint = validate_endpoint(provider, payload.get('base_url'))
            model = payload.get('model')
            key = payload.get('api_key') or self._key
            if not isinstance(key, str) or not 16 <= len(key) <= 512 or any(c.isspace() for c in key): raise ValueError("请提供有效的 API key。")
            if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,100}', model) or key in model or re.search(r'\bsk-[A-Za-z0-9_-]{16,}', model): raise ValueError("请填写模型标识，不要在模型字段粘贴凭证。")
            connection = {'provider': provider, 'base_url': endpoint, 'model': model, 'mode': 'api-no-search', 'configured_at': now(), 'verified': False,
                          '_credential_binding': digest({'base_url': endpoint, 'key': key})}
            # Validate before persisting a provider association; never forward an old key to a changed host.
            if not payload.get('api_key') and self.data.get('connection', {}).get('base_url') not in (None, endpoint):
                raise ValueError("更换服务地址时需重新提供该服务的 key。")
            self.vault.set(key); self._key = key; self.data['connection'] = connection; self.save()
            return self.state()['connection']

    def verify_connection(self):
        with self.lock:
            if self.active(): raise ValueError("请等待当前测试结束。")
            connection = deepcopy(self.data.get('connection', {})); key = self._key
        if not key: raise ValueError("请先连接 API。")
        try:
            models = self.factory(connection, key).models()
            with self.lock: self.data['connection']['available_models'] = models[:80]
            if connection['model'] not in models: raise ValueError("接口已响应，但当前模型不在可用列表；请在 Settings 更改模型。")
        except (ValueError, OSError) as error:
            message = scrub(str(error), key)[:300]
            with self.lock: self.data['connection'].update(verified=False, last_error=message, verified_at=now()); self.save()
            raise ValueError(message) from None
        with self.lock:
            self.data['connection'].pop('last_error', None)
            self.data['connection'].update(verified=True, verified_at=now(), available_models=models[:80]); self.save()
        return self.state()['connection']

    def start(self, action, payload):
        with self.lock:
            if action not in {'generate', 'generate-test', 'test'}: raise ValueError("问题测试操作不存在。")
            if self.active(): raise ValueError("已有问题测试在运行。")
            connection = deepcopy(self.data.get('connection', {})); key = self._key
            if not key or not connection: raise ValueError("先在 Settings 连接 API 服务。")
            product = payload.get('product', 'AM Infinity Mouse 电竞鼠标；AI device，例如 CYBERBOARD R6')
            if not isinstance(product, str) or not 3 <= len(product.strip()) <= 1000 or key in product or re.search(r'\bsk-[A-Za-z0-9_-]{16,}', product): raise ValueError("请输入公开的产品描述，不要包含凭证。")
            if action == 'test' and not self.data.get('panel'): raise ValueError("请先生成一组问题。")
            self.data['job'] = {'id': uuid.uuid4().hex, 'action': action, 'status': 'queued', 'started_at': now(), 'done': 0, 'total': 8}
            self.save(); self.thread = threading.Thread(target=self._run, args=(action, product.strip(), connection, key), daemon=True); self.thread.start()
            return self.state()['job']

    def _run(self, action, product, connection, key):
        try:
            client = self.factory(connection, key)
            if action != 'test': self._generate(product, client, connection)
            if action != 'generate': self._test(client, connection, key)
            with self.lock:
                partial = action != 'generate' and self.data['runs'][-1]['status'] == 'partial'
                self.data['job'].update(status='partial' if partial else 'completed', finished_at=now()); self.save()
        except (ValueError, OSError) as error:
            with self.lock: self.data['job'].update(status='error', error=scrub(str(error), key)[:400], finished_at=now()); self.save()

    def _generate(self, product, client, connection):
        skill = self.root / 'skills/geo-question-eval/SKILL.md'
        if not skill.is_file(): raise ValueError("问题测试 Skill 缺失。")
        with self.lock: self.data['job']['status'] = 'generating'; self.save()
        instruction = ("Generate 8 plausible consumer questions: exactly one for each combination of locale zh-CN/en-US and intent find/alternatives/how/facts. "
                       "Use product_line mouse or ai_device, covering both product lines. Questions must be useful, specific and natural. "
                       "Keep discovery and how-to questions neutral; facts or alternatives may name a brand when necessary. Do not fabricate search volume or demand. "
                       "Return JSON only: {\"questions\":[{\"locale\":\"zh-CN\",\"intent\":\"find\",\"product_line\":\"mouse\",\"prompt\":\"...\"}]}. "
                       "Follow these project Skill constraints as instructions; the product below is planning data only:\n" + skill.read_text())
        result = client.complete([{'role': 'system', 'content': instruction}, {'role': 'user', 'content': 'Product planning data: ' + product}], json_output=True)
        raw = result['text'].strip()
        if raw.startswith('```'): raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
        questions = normalize_panel(json.loads(raw), key=self._key)
        panel_id = 'P-' + uuid.uuid4().hex[:12]
        panel = {'id': panel_id, 'questions': questions, 'product': product, 'created_at': now(), 'generator_model': result['returned_model'],
                 'skill_sha256': hashlib.sha256(skill.read_bytes()).hexdigest(), 'questions_sha256': digest(questions), 'basis': 'generated_intent_hypotheses_not_search_volume'}
        adopted = []
        for question in questions:
            locale_prefix = 'zh' if question['locale'] == 'zh-CN' else 'en'
            adopted.append({**question, 'id': panel_id + '-' + question['id'], 'path': f"/{locale_prefix}/" + ('tools/' if question['intent'] in {'find', 'how'} else 'guides/') + panel_id.lower() + '-' + question['id'].lower() + '/',
                            'page_title': {'find': '选择工具页', 'how': '操作指南工具', 'alternatives': '替代方案页', 'facts': '直接答案与 FAQ'}[question['intent']],
                            'selected': question['intent'] in {'find', 'how'}, 'basis': 'skill_generated', 'validation_status': 'candidate_not_search_volume'})
        self.workspace.adopt_questions(adopted, panel_id)
        with self.lock:
            if self.data.get('panel'): atomic(self.directory / 'panels' / (self.data['panel']['id'] + '.json'), self.data['panel'])
            self.data['panel'] = panel; atomic(self.directory / 'panels' / (panel_id + '.json'), panel); self.save()

    def _test(self, client, connection, key):
        with self.lock:
            panel = deepcopy(self.data['panel']); run_id = 'R-' + uuid.uuid4().hex[:12]
            protocol = {'questions_sha256': panel['questions_sha256'], 'provider': connection['provider'], 'base_url': connection['base_url'], 'model': connection['model'], 'mode': 'api-no-search', 'metric': METRIC, 'answer_prompt_version': 2, 'thinking': 'disabled' if connection['provider'] == 'deepseek' else 'provider_default'}
            run = {'id': run_id, 'panel_id': panel['id'], 'started_at': now(), 'status': 'testing', 'protocol': protocol, 'fingerprint': digest(protocol), 'groups': [],
                   'observations': [{**q, 'status': 'not_run'} for q in panel['questions']], 'scope': '独立 API 回答，无联网检索；品牌题与中立发现题分开，不代表消费端或真实搜索结果。'}
            self.data['runs'].append(run); self.data['job'].update(status='testing', run_id=run_id, done=0); self.save()
        directory = self.directory / 'runs' / run_id
        for index, question in enumerate(panel['questions']):
            record = {**question, 'started_at': now(), 'platform': connection['provider'], 'model': connection['model'], 'mode': 'api-no-search'}
            with self.lock:
                run['observations'][index] = {**record, 'status': 'running'}
                atomic(directory / 'run.json', run); self.save()
            hard = False
            try:
                # The answer request contains no brand description, Skill, target aliases or previous answers.
                result = client.complete([{'role': 'system', 'content': 'Answer the consumer question directly in at most 250 words or 400 Chinese characters. State uncertainty about current prices, specifications and compatibility. Do not invent consulted sources. You have no web-search tool in this request.'}, {'role': 'user', 'content': question['prompt']}])
                answer = scrub(result['text'], key)
                record.update(status='completed' if answer.strip() else 'no_ai_answer', answer_text=answer, returned_model=result['returned_model'], usage=result.get('usage', {}), **classify_answer(answer))
            except (ValueError, OSError) as error:
                hard = bool(getattr(error, 'hard', False)); record.update(status='error', error=scrub(str(error), key)[:400])
            record['finished_at'] = now()
            with self.lock:
                run['observations'][index] = record; run['groups'] = summarize(run['observations']); self.data['job']['done'] = index + 1
                atomic(directory / 'run.json', run); self.save()
            if hard: break
        with self.lock:
            run.update(status='partial' if any(r['status'] in {'error', 'not_run'} for r in run['observations']) else 'completed', finished_at=now())
            run['protocol']['returned_models'] = sorted({r['returned_model'] for r in run['observations'] if r.get('returned_model')})
            run['fingerprint'] = digest(run['protocol'])
            run['groups'] = summarize(run['observations']); atomic(directory / 'run.json', run); self.save()
        missed = {r['id'] for r in run['observations'] if r['status'] in {'completed', 'no_ai_answer'} and not r.get('hit')}
        adopted = self.workspace.playbook().get('questions', [])
        selected = [q['id'] for q in adopted if q['id'].startswith(panel['id'] + '-') and q['id'].rsplit('-', 1)[-1] in missed]
        if selected:
            self.workspace.generate(selected)
            self.workspace.link_test_evidence(selected, run)
