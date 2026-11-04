"""Question -> concrete artifact -> public check, with separately attributed traffic."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import re
import threading
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .measurement import ALLOWED_HOSTS, BrandRedirects, diagnose_html
from .workflow import atomic, load

ORIGINS = ("https://www.angrymiao.com", "https://store.angrymiao.com")
PRODUCT = ORIGINS[1] + "/products/am-infinity-97-wireless-gaming-mouse"
AI_HOSTS = {"chatgpt.com": "ChatGPT", "chat.openai.com": "ChatGPT", "perplexity.ai": "Perplexity", "www.perplexity.ai": "Perplexity", "gemini.google.com": "Gemini", "claude.ai": "Claude", "copilot.microsoft.com": "Copilot", "chat.deepseek.com": "DeepSeek", "doubao.com": "豆包", "www.doubao.com": "豆包", "kimi.com": "Kimi", "www.kimi.com": "Kimi", "kimi.moonshot.cn": "Kimi"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_public(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("只能检查品牌公开 HTTPS 页面。")
    request = Request(url, headers={"User-Agent": "AMSEO/0.4 public verification"})
    try:
        response = build_opener(BrandRedirects()).open(request, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("页面超过 2 MiB 检查上限。")
        return {"url": url, "final_url": response.geturl(), "status": response.status,
                "body": raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace"),
                "content_type": response.headers.get_content_type(), "captured_at": now(),
                "sha256": hashlib.sha256(raw).hexdigest()}


def robots_allows(body, agent, path):
    """Specific agent groups, wildcard and longest path rule; Allow wins ties."""
    groups, agents, rules = [], [], []
    for raw in body.splitlines() + ["User-agent: __end__"]:
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key.lower() == "user-agent":
            if rules:
                groups.append((agents, rules)); agents, rules = [], []
            agents.append(value.lower())
        elif key.lower() in {"allow", "disallow"} and agents and value:
            rules.append((key.lower(), value))
    applicable = [(max((len(a) for a in aa if a != "*" and a in agent.lower()), default=0), aa, rr) for aa, rr in groups]
    specificity = max((n for n, _, _ in applicable), default=0)
    selected = [rr for n, aa, rr in applicable if (specificity and n == specificity) or (not specificity and "*" in aa)]
    matches = []
    for rr in selected:
        for kind, pattern in rr:
            terminal = pattern.endswith("$")
            regex = re.escape(pattern[:-1] if terminal else pattern).replace(r"\*", ".*")
            if re.match("^" + regex + ("$" if terminal else ""), path):
                matches.append((len(pattern.replace("*", "").rstrip("$")), kind == "allow"))
    return max(matches, default=(0, True))[1]


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(); self.schemas = []; self.text = []; self._json = None; self._skip = 0; self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1": self.h1 += 1
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json": self._json = []
        elif tag in {"script", "style"}: self._skip += 1

    def handle_endtag(self, tag):
        if tag == "script" and self._json is not None:
            self.schemas.append("".join(self._json)); self._json = None
        elif tag in {"script", "style"}: self._skip = max(0, self._skip - 1)

    def handle_data(self, value):
        if self._json is not None: self._json.append(value)
        elif not self._skip: self.text.append(value)


def schema_types(value):
    if isinstance(value, list): return set().union(*(schema_types(v) for v in value)) if value else set()
    if not isinstance(value, dict): return set()
    types = value.get("@type", [])
    return set(types if isinstance(types, list) else [types]) | schema_types(value.get("@graph", []))


def traffic_report(text, start, end, property_host):
    if property_host not in {"www.angrymiao.com", "store.angrymiao.com", "mall.angrymiao.com"}:
        raise ValueError("请选择这份报表对应的品牌站点。")
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last: raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("请填写有效的报表起止日期。")
    if not isinstance(text, str) or len(text.encode()) > 24000: raise ValueError("CSV 需小于 24 KiB。")
    lines = [line for line in text.lstrip("\ufeff").splitlines() if line.strip() and not line.startswith("#")]
    reader = csv.DictReader(lines)
    aliases = {"Session source / medium": "combined", "会话来源 / 媒介": "combined", "sessionSourceMedium": "combined", "source": "source", "Session source": "source", "会话来源": "source", "medium": "medium", "Session medium": "medium", "会话媒介": "medium", "sessions": "sessions", "Sessions": "sessions", "会话数": "sessions", "key_events": "key_events", "Key events": "key_events", "关键事件": "key_events"}
    headers = reader.fieldnames or []
    if not headers or len(set(headers)) != len(headers) or any(h not in aliases for h in headers):
        raise ValueError("仅支持聚合列：Session source / medium、Sessions、Key events（可选）；请移除用户、订单及其他明细列。")
    fields = [aliases[h] for h in headers]
    if len(set(fields)) != len(fields) or "sessions" not in fields or not ("combined" in fields or "source" in fields) or ("combined" in fields and ("source" in fields or "medium" in fields)):
        raise ValueError("CSV 缺少来源或会话数，或包含重复含义列。")
    totals, total_sessions, total_events, rows, seen = {}, 0, 0, 0, set()
    for raw in reader:
        if None in raw or any(v is None for v in raw.values()): raise ValueError("CSV 列数不一致。")
        row = {aliases[k]: v.strip() for k, v in raw.items()}
        source, medium = row.get("source", ""), row.get("medium", "")
        if "combined" in row:
            if " / " not in row["combined"]: raise ValueError("来源/媒介须以 ‘ / ’ 分隔。")
            source, medium = row["combined"].rsplit(" / ", 1)
        source, medium = source.lower(), medium.lower()
        if not re.fullmatch(r"[a-z0-9.()_-]{1,100}", source) or not re.fullmatch(r"[a-z0-9() _-]{0,60}", medium):
            raise ValueError("仅接受来源主机名和媒介；不要上传 URL、查询参数或个人信息。")
        if (source, medium) in seen: raise ValueError("存在重复来源/媒介，请先在报表中聚合。")
        seen.add((source, medium))
        try:
            sessions = int(row["sessions"].replace(",", ""))
            events = float(row["key_events"].replace(",", "")) if "key_events" in row else None
            if sessions < 0 or (events is not None and (events < 0 or not math.isfinite(events))): raise ValueError()
        except ValueError: raise ValueError("会话数须为非负整数，关键事件须为非负数值。")
        total_sessions += sessions; rows += 1
        if rows > 250: raise ValueError("一次最多导入 250 个聚合来源。")
        platform = AI_HOSTS.get(source)
        # Native GA4 attribution is retained; ordinary Google/Direct is never guessed as AI.
        if medium == "ai-assistant" and not platform: platform = "其他 AI（GA4 已分类）"
        if platform:
            item = totals.setdefault(platform, {"platform": platform, "sessions": 0, "key_events": 0 if "key_events" in fields else None})
            item["sessions"] += sessions
            if events is not None: item["key_events"] += events; total_events += events
    if not rows: raise ValueError("CSV 没有数据行。")
    ai_sessions = sum(item["sessions"] for item in totals.values())
    return {"status": "imported", "start_date": start, "end_date": end, "property_host": property_host, "imported_at": now(),
            "ai_sessions": ai_sessions, "ai_key_events": total_events if "key_events" in fields else None,
            "report_sessions": total_sessions, "sources": list(totals.values()), "rows": rows,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "scope": "用户导入的聚合报表；显示当前这份报表，不跨文件累加。无来源的 Direct 与 Google AI 搜索不能完整识别。"}


class GeoWorkspace:
    def __init__(self, root, fetcher=None, page_runner=None):
        self.root = Path(root).resolve(); self.directory = self.root / "outputs/geo-workspace"
        self.path = self.directory / "state.json"; self.lock = threading.RLock(); self.fetcher = fetcher or read_public
        self.page_runner = page_runner
        self.data = load(self.path, {"tasks": [], "traffic": None, "history": []})

    def playbook(self):
        book = load(self.root / "config/geo-playbook.json", {"questions": [], "intents": {}, "guidance_sources": []})
        if self.data.get("generated_questions"):
            book["questions"] = deepcopy(self.data["generated_questions"])
            book["panel_id"] = self.data.get("question_panel_id")
        return book

    def adopt_questions(self, questions, panel_id):
        with self.lock:
            if self.data.get("generated_questions"):
                self.data["history"].append({"question_panel_id": self.data.get("question_panel_id"), "questions": self.data["generated_questions"]})
            self.data["generated_questions"] = deepcopy(questions)
            self.data["question_panel_id"] = panel_id
            self.data["selected_questions"] = [q["id"] for q in questions if q.get("selected")]
            self.save()

    def link_test_evidence(self, question_ids, run):
        with self.lock:
            for task in self.data['tasks']:
                if task.get('question', {}).get('id') in question_ids:
                    task['test_evidence'] = {'run_id': run['id'], 'panel_id': run['panel_id'], 'provider': run['protocol']['provider'], 'model': run['protocol']['model'], 'mode': run['protocol']['mode'], 'reason': 'API 问题未命中；生成对应内容优化候选，不声称优化已经生效。'}
            self.save()

    def state(self):
        with self.lock:
            data = deepcopy(self.data)
            for task in data["tasks"]:
                task.setdefault("execution_done", False)
                task["group"] = {"page": "content", "robots": "foundation", "schema": "foundation", "traffic": "attribution"}.get(task["kind"], "other")
                task["validation_status"] = "passed" if task.get("check_status") == "passed" else "failed" if task.get("check_status") == "needs_work" else "not_checked"
            return {**data, "playbook": self.playbook()}

    def save(self):
        atomic(self.path, self.data)

    def task(self, task_id):
        result = next((t for t in self.data["tasks"] if t["id"] == task_id), None)
        if not result: raise ValueError("优化任务不存在。")
        return result

    def toggle(self, task_id, done):
        if not isinstance(done, bool): raise ValueError("执行勾选状态必须为布尔值。")
        with self.lock:
            task = self.task(task_id)
            if task.get("execution_done", False) != done:
                self.data["history"].append({"task_id": task_id, "execution_done": task.get("execution_done", False), "changed_at": now()})
                task.update(execution_done=done, execution_updated_at=now(), completion_source="ui_checkbox")
                self.save()
            return deepcopy(task)

    def generate(self, selected):
        questions = self.playbook()["questions"]; known = {q["id"] for q in questions}
        if not isinstance(selected, list) or not selected or any(not isinstance(q, str) or q not in known for q in selected) or len(selected) != len(set(selected)):
            raise ValueError("请选择有效且不重复的问题。")
        with self.lock:
            existing = {t["id"]: t for t in self.data["tasks"]}
            for task in self.base_tasks(): existing.setdefault(task["id"], task)
            for question in questions:
                if question["id"] not in selected: continue
                task_id = "page-" + question["id"]
                existing.setdefault(task_id, {"id": task_id, "kind": "page", "title": question["prompt"], "question": question,
                    "target_url": ORIGINS[1] + question["path"], "status": "ready", "artifacts": [], "checks": [],
                    "steps": ["先给出直接答案，再提供可操作的选择器或步骤。", "加入适用场景、限制、来源和对应产品内链。", "发布到目标 URL 后重新检查正文与工具；固定评分题组保持不变。"],
                    "acceptance": ["页面可访问且问题出现在 H1", "正文有直接答案、来源与限制", "工具输入能产生有用结果", "人工复核事实并完成真实站点发布"]})
            self.data["tasks"] = list(existing.values()); self.data["selected_questions"] = list(dict.fromkeys(self.data.get("selected_questions", []) + selected))
            self.data["updated_at"] = now(); self.save()
        return self.state()

    @staticmethod
    def base_tasks():
        return [
            {"id": "ai-crawlers", "kind": "robots", "title": "确认 AI 搜索爬虫能访问公开页面", "status": "ready", "artifacts": [], "checks": [],
             "steps": ["检查官网与商城 robots.txt 的 OAI-SearchBot、PerplexityBot、bingbot 规则。", "只放行需公开的产品与工具页；保留后台、购物车等限制。", "用真实爬虫日志确认 CDN 放行；搜索放行与训练授权分别决定。"], "acceptance": ["两站点公开路径未被 robots 规则阻止", "CDN / WAF 的真实爬虫访问证据"]},
            {"id": "answer-schema", "kind": "schema", "title": "核对直接答案、FAQ 和匹配正文的结构化数据", "target_url": PRODUCT, "status": "ready", "artifacts": [], "checks": [],
             "steps": ["在型号对应页直接回答价格、尺寸、重量、兼容性，字段须有来源。", "添加与可见正文一致的 Product / WebPage 数据；价格库存取商城实时值。", "校验 JSON 并与页面逐字段核对；冲突字段继续省略。"], "acceptance": ["JSON-LD 可解析且包含 Product", "价格、型号与页面可见内容逐字段一致", "不把 FAQ 标记当作 AI 推荐保证"]},
            {"id": "ai-traffic", "kind": "traffic", "title": "单独记录 AI 带来的访问与关键事件", "status": "ready", "artifacts": [], "checks": [],
             "steps": ["GA4 流量获取选择会话维度，查看 AI Assistant 渠道。", "按来源/媒介导出 Sessions、Key events 聚合报表和日期范围。", "点击本任务的“设置 AI 流量来源”导入；核对 ChatGPT、Perplexity 等来源，保留未归因访问。"], "acceptance": ["已导入有站点与时间范围的真实聚合报表", "会话与关键事件分开记录"]},
        ]

    def _write_artifact(self, task, filename, content):
        directory = self.directory / "artifacts" / task["id"]; directory.mkdir(parents=True, exist_ok=True)
        target = directory / filename; target.write_text(content, encoding="utf-8")
        return {"filename": filename, "path": str(target.relative_to(self.root)), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    def prepare(self, task_id):
        from .geo_pages import page_files
        with self.lock:
            snapshot = deepcopy(self.task(task_id))
        if snapshot['kind'] == 'page' and snapshot['question'].get('basis') == 'skill_generated':
            from .question_content import question_page_files
            files = question_page_files(self.root, snapshot['question'], snapshot['target_url'], runner=self.page_runner)
            with self.lock:
                task = self.task(task_id)
                task['artifacts'] = [self._write_artifact(task, name, content) for name, content in files.items()]
                task.update(prepared_at=now(), status='prepared', completion_scope='local_artifact_not_published')
                self.save(); return deepcopy(task)
        with self.lock:
            task = self.task(task_id)
            if task["kind"] == "page": files = page_files(task["question"], task["target_url"])
            elif task["kind"] == "schema":
                files = {"product-jsonld.json": json.dumps({"@context": "https://schema.org", "@type": "Product", "name": "AM INFINITY MOUSE .97", "brand": {"@type": "Brand", "name": "Angry Miao"}, "url": PRODUCT}, ensure_ascii=False, indent=2),
                         "apply.md": "将最小 Product 身份数据合并到实际产品模板；核对已有 JSON-LD，避免重复。仅身份数据不满足全部商品富结果要求。价格、库存、图片从实时产品记录绑定；不添加冲突重量、虚构评分或评论。正文 FAQ 按型号和市场核对。\n"}
            elif task["kind"] == "robots":
                files = {"crawl-policy.json": json.dumps({"search_agents": ["OAI-SearchBot", "PerplexityBot", "bingbot"], "origins": ORIGINS,
                        "public_paths": ["/products/am-infinity-97-wireless-gaming-mouse", "/products/am-infinity-mouse"] + [q["path"] for q in self.playbook()["questions"]],
                        "merge_rule": "先读取实际 robots.txt；已有规则放行时无需改动。合并特定 UA 组时继承已有私有路径限制，只增加目标公开路径的精确 Allow，不替换整份文件。", "training_policy": "GPTBot、Google-Extended 等训练/其他用途另行决策；本任务不自动放行。"}, ensure_ascii=False, indent=2),
                        "check.md": "点击检查线上，查看两站点 robots.txt 的实际结果。规则检查不证明真实爬虫 IP 已通过 CDN/WAF；需要访问日志。未连接真实站点源码时不输出冒充源码补丁的文件。\n"}
            else:
                files = {"tracking.md": "GA4 → 报告 → 获取 → 流量获取。按会话来源/媒介查看 AI Assistant 渠道，导出聚合 CSV：Session source / medium,Sessions,Key events（可选）。在工作台指定报表站点与起止日期后导入。不要导出用户、订单或完整 URL。\n\n按导入报表口径显示会话、关键事件和来源，不跨文件求和以免重复。Direct 及 Google AI 搜索不能全部识别。当前 GA4 原生 AI Assistant 渠道已可用；自定义规则只用于补充并放在 Referral 之前。\n",
                         "source-rules.json": json.dumps({"native_medium": "ai-assistant", "exact_source_hosts": AI_HOSTS, "do_not_infer": ["direct", "google organic", "bot requests"], "documentation": "https://support.google.com/analytics/answer/9756891?hl=en"}, ensure_ascii=False, indent=2)}
            task["artifacts"] = [self._write_artifact(task, name, content) for name, content in files.items()]
            task["prepared_at"] = now(); task["status"] = "prepared"; task["completion_scope"] = "local_artifact_not_published"; self.save()
            return deepcopy(task)

    def artifact(self, task_id, filename):
        with self.lock:
            task = self.task(task_id); record = next((a for a in task["artifacts"] if a["filename"] == filename), None)
            if not record: raise ValueError("产物不存在。")
            path = (self.root / record["path"]).resolve()
            if not path.is_relative_to((self.directory / "artifacts").resolve()): raise ValueError("产物路径无效。")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record["sha256"]: raise ValueError("产物已变化，请重新准备后查看。")
            return raw

    def check(self, task_id):
        with self.lock: task = deepcopy(self.task(task_id))
        checks, captures = [], []
        if task["kind"] == "traffic":
            checks.append({"title": "真实聚合报表已导入", "passed": bool(self.data.get("traffic")), "detail": "未连接时不填零。"})
        else:
            targets = [origin + "/robots.txt" for origin in ORIGINS] if task["kind"] == "robots" else [task["target_url"]]
            for url in targets:
                try:
                    capture = self.fetcher(url); captures.append(capture); body = capture["body"]
                    ok = 200 <= capture["status"] < 300
                    checks.append({"title": f"{urlsplit(url).hostname} · HTTP 成功", "passed": ok, "detail": str(capture["status"])})
                    if not ok: continue
                    if task["kind"] == "robots":
                        text_ok = capture.get("content_type", "text/plain").startswith("text/") and "<html" not in body.lower()
                        checks.append({"title": "取得 robots 规则文本", "passed": text_ok, "detail": url})
                        if not text_ok: continue
                        paths = ["/products/am-infinity-97-wireless-gaming-mouse", "/products/am-infinity-mouse"]
                        paths += [t["question"]["path"] for t in self.data["tasks"] if t["kind"] == "page"]
                        for agent in ("OAI-SearchBot", "PerplexityBot", "bingbot"):
                            blocked = [p for p in paths if not robots_allows(body, agent, p)]
                            checks.append({"title": f"{urlsplit(url).hostname} · {agent} 公开路径", "passed": not blocked, "detail": ", ".join(blocked) if blocked else f"{len(paths)} 条目标路径未被规则阻止"})
                    else:
                        parser = Markup(); parser.feed(body)
                        if task["kind"] == "schema":
                            parsed = []
                            for block in parser.schemas:
                                try: parsed.append(json.loads(block))
                                except ValueError: pass
                            checks.append({"title": "页面 JSON-LD 均可解析", "passed": bool(parsed) and len(parsed) == len(parser.schemas), "detail": f"{len(parsed)} / {len(parser.schemas)} 块"})
                            types = set().union(*(schema_types(p) for p in parsed)) if parsed else set()
                            checks.append({"title": "包含 Product 类型", "passed": "Product" in types, "detail": "只检查类型与语法，不自动确认商品事实一致。"})
                        else:
                            text = " ".join(parser.text)
                            checks.append({"title": "问题正文与 H1 可见", "passed": parser.h1 > 0 and task["question"]["prompt"] in text, "detail": "原始 HTML 检查；工具实际交互仍需浏览器验收。"})
                            diagnosis = diagnose_html(body, http_status=capture["status"])
                            checks.append({"title": "未发现页面显式 noindex", "passed": next(c["passed"] for c in diagnosis["checks"] if c["id"] == "no_explicit_noindex"), "detail": "未发现不等于已收录；响应头与实际索引另行核对。"})
                            checks.append({"title": "canonical 指向目标页面", "passed": diagnosis["canonical"] == [task["target_url"]], "detail": task["target_url"]})
                except (OSError, ValueError) as error:
                    checks.append({"title": "采集成功", "passed": False, "error": True, "detail": str(error)[:240]})
        # Technical success never claims publication, content review or actual bot access.
        with self.lock:
            current = self.task(task_id); previous = current.get("verification")
            if previous: self.data["history"].append({"task_id": task_id, "verification": previous})
            directory = self.directory / "checks" / task_id / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            evidence = []
            for i, capture in enumerate(captures):
                directory.mkdir(parents=True, exist_ok=True); path = directory / f"{i}.txt"; path.write_text(capture["body"], encoding="utf-8")
                evidence.append({k: v for k, v in capture.items() if k != "body"} | {"path": str(path.relative_to(self.root)), "saved_text_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            current["checks"] = checks; current["verification"] = {"checked_at": now(), "scope": "public_rule_or_html_diagnostic_only", "evidence": evidence}
            current["check_status"] = "passed" if checks and all(c["passed"] for c in checks) else "needs_work"
            if task["kind"] == "robots":
                invalid = [c["detail"] for c in checks if c["title"] == "取得 robots 规则文本" and not c["passed"]]
                current["next_action"] = ("先修复返回 HTML 的 robots.txt 路由：" + "、".join(invalid)) if invalid else ("规则检查已通过；接着核对真实爬虫的 CDN / WAF 访问日志。" if current["check_status"] == "passed" else "展开未通过项，按目标公开路径修正规则后复查。")
            elif task["kind"] == "schema" and current["check_status"] == "passed":
                current["title"] = "核对现有 Product 数据、直接答案与 FAQ"
                current["next_action"] = "页面已有 Product 标记，避免重复添加；下一步核对字段与可见正文一致。"
            self.save(); return deepcopy(current)

    def import_traffic(self, payload):
        report = traffic_report(payload.get("csv"), payload.get("start_date"), payload.get("end_date"), payload.get("property_host"))
        with self.lock:
            if self.data.get("traffic"): self.data["history"].append({"traffic": self.data["traffic"]})
            self.data["traffic"] = report; self.save()
        return report
