"""Observed diagnostics and a small, explicitly API-only answer panel.

No ranking score is inferred from HTML, and no consumer UI is simulated.
The answer sampler sees only a neutral question in an empty working directory.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


PANEL_VERSION = "bilingual-discovery-pilot-v1"
RUBRIC_VERSION = "raw-html-technical-v1.1"
PANEL_IDS = ("EN-M-02", "EN-K-04", "ZH-M-02", "ZH-K-04")
PANEL_MODEL = "gpt-6.1-sol"
PAGES = (
    ("brand-home", "needs_language_check", "https://www.angrymiao.com/"),
    ("en-product", "en-US", "https://store.angrymiao.com/products/am-infinity-97-wireless-gaming-mouse"),
    ("zh-product", "zh-CN", "https://mall.angrymiao.com/products/1313"),
)
ALLOWED_HOSTS = {"angrymiao.com", "www.angrymiao.com", "store.angrymiao.com", "mall.angrymiao.com", "m.angrymiao.com", "cdn-www.angrymiao.com"}
ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["status", "answer_text", "citations"],
    "properties": {
        "status": {"type": "string", "enum": ["completed", "no_ai_answer"]},
        "answer_text": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.h1 = []
        self.description = []
        self.canonical = []
        self.robots = []
        self.lang = ""
        self._title = self._h1 = False
        self._document_title_seen = False
        self._svg_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang", "")
        if tag == "svg":
            self._svg_depth += 1
        if tag == "title" and not self._svg_depth and not self._document_title_seen:
            self._title = True
        if tag == "h1":
            self._h1 = True
        if tag == "meta":
            name = attrs.get("name", "").lower()
            if name == "description":
                self.description.append(attrs.get("content", ""))
            if name in {"robots", "googlebot"}:
                self.robots.append(attrs.get("content", ""))
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonical.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            if self._title:
                self._document_title_seen = True
            self._title = False
        if tag == "svg":
            self._svg_depth = max(0, self._svg_depth - 1)
        if tag == "h1":
            self._h1 = False

    def handle_data(self, text):
        if self._title:
            self.title.append(text)
        if self._h1:
            self.h1.append(text)


def diagnose_html(body, *, http_status=200, headers=None):
    """Six equal-weight, project-owned checks; not a search engine's score."""
    parser = PageParser()
    parser.feed(body)
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    robots = ",".join(parser.robots + [headers.get("x-robots-tag", "")]).lower()
    checks = [
        ("http_ok", "HTTP 返回成功", 200 <= http_status < 300),
        ("title", "原始 HTML 含非空标题", bool("".join(parser.title).strip())),
        ("description", "含非空描述", any(x.strip() for x in parser.description)),
        ("canonical", "含唯一且有效的绝对 canonical", len(parser.canonical) == 1 and urlsplit(parser.canonical[0]).scheme in {"http", "https"} and bool(urlsplit(parser.canonical[0]).hostname)),
        ("h1", "原始 HTML 含非空 H1", bool("".join(parser.h1).strip())),
        ("no_explicit_noindex", "未发现显式 noindex / none", not re.search(r"(?:^|[,\s])(?:noindex|none)(?:$|[,\s])", robots)),
    ]
    if not 200 <= http_status < 300:
        checks = [(key, title, False) for key, title, _ in checks]
    return {"checks": [{"id": key, "title": title, "passed": bool(passed)} for key, title, passed in checks],
            "title": "".join(parser.title).strip(), "canonical": parser.canonical, "lang": parser.lang,
            "note": "未发现 noindex 不代表 robots 允许抓取、已收录或获得排名；不执行 JavaScript。"}


class BrandRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.hostname not in ALLOWED_HOSTS or target.username or target.password or target.port not in (None, 443):
            raise ValueError("站点跳转超出品牌公开域名，停止跟随。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url):
    request = Request(url, headers={"User-Agent": "AMSEO/0.3 public technical diagnostic", "Accept": "text/html"})
    opener = build_opener(BrandRedirects())
    try:
        response = opener.open(request, timeout=25)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("公开页面超过本轮 2 MiB 采集上限。")
        if "html" not in response.headers.get_content_type():
            raise ValueError("返回内容不是 HTML，无法按当前诊断规则评估。")
        return {"url": url, "final_url": response.geturl(), "http_status": response.status,
                "headers": {k: v for k, v in response.headers.items() if k.lower() in {"content-type", "x-robots-tag", "last-modified"}},
                "body": raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace"),
                "sha256": hashlib.sha256(raw).hexdigest(), "captured_at_utc": now()}


def technical_panel(directory, fetcher=fetch_page):
    directory.mkdir(parents=True, exist_ok=True)
    observations = []
    for page_id, locale, url in PAGES:
        try:
            capture = fetcher(url)
            body = capture.pop("body")
            source = directory / f"{page_id}.html.txt"
            source.write_text(body, encoding="utf-8")
            diagnosis = diagnose_html(body, http_status=capture["http_status"], headers=capture.get("headers"))
            observations.append({"id": page_id, "locale": locale, "status": "measured", **capture, **diagnosis, "evidence_file": str(source), "evidence_sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        except (OSError, URLError, ValueError) as error:
            observations.append({"id": page_id, "locale": locale, "url": url, "status": "error", "captured_at_utc": now(), "error": str(error)[:500]})
    checks = [check for item in observations for check in item.get("checks", [])]
    passed = sum(check["passed"] for check in checks)
    result = {"status": "measured" if checks else "error", "score": round(100 * passed / len(checks), 1) if checks else None,
              "checks_passed": passed, "checks_total": len(checks), "pages_planned": len(PAGES),
              "pages_measured": sum(item["status"] == "measured" for item in observations),
              "errors": sum(item["status"] == "error" for item in observations),
              "rubric_version": RUBRIC_VERSION, "observations": observations,
              "scope": "原始 HTML 技术诊断；6 项等权内部检查，非排名、收录或流量分数。"}
    (directory / "technical.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def summarize_answers(records):
    groups = []
    for locale in sorted({record["locale"] for record in records}):
        subset = [record for record in records if record["locale"] == locale]
        valid = [record for record in subset if record["status"] != "error"]
        mentions = sum(record.get("brand_mentioned", False) for record in valid)
        official = sum(record.get("official_citation", False) for record in valid)
        groups.append({"locale": locale, "surface": "api_answer", "platform": "codex-cli-search", "mode": "web-search",
                       "score": round(100 * mentions / len(valid), 1) if valid else None,
                       "attempted": len(subset), "successful_tests": len(valid), "errors": len(subset) - len(valid),
                       "no_ai_answers": sum(record["status"] == "no_ai_answer" for record in valid),
                       "brand_mention_rate": mentions / len(valid) if valid else None,
                       "official_citation_rate": official / len(valid) if valid else None})
    return {"status": "measured" if any(group["successful_tests"] for group in groups) else "error",
            "score": None, "groups": groups, "panel_version": PANEL_VERSION, "observation_count": len(records),
            "reason": "中英文分别报告固定题组的品牌出现率，不合并成跨市场总分。",
            "scope": "联网 Agent/API 回答试验；不是 ChatGPT/Gemini/豆包消费端表现，不衡量推荐适配或事实正确率。",
            "limitations": "每市场仅 2 题的试运行；模型与搜索结果存在波动，无因果提升结论。错误另报，无 AI 回答计入分母。"}


def validate_answer_panel(plan):
    """Freeze a neutral mouse/AI-device panel before any sampling or fetching.

    This is a separate topic panel, not a rewrite of the historical seed file.
    Its complete input is part of the measurement fingerprint.
    """
    if not isinstance(plan, dict):
        raise ValueError("回答面板配置必须是对象。")
    identifier = plan.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,99}", identifier) or identifier == PANEL_VERSION:
        raise ValueError("回答面板需要有效的固定版本 ID。")
    version = plan.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("回答面板版本必须是正整数。")
    if plan.get("model") != PANEL_MODEL:
        raise ValueError("回答面板必须使用固定模型，不能静默更换测量模型。")
    if plan.get("surface", "api_answer") != "api_answer" or plan.get("platform", "codex-cli-search") != "codex-cli-search":
        raise ValueError("本采样器只支持独立 Agent/API 联网回答。")
    title = plan.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 300:
        raise ValueError("回答面板需要具体标题。")
    raw_queries = plan.get("queries")
    if not isinstance(raw_queries, list) or len(raw_queries) != 4:
        raise ValueError("核心回答面板需要中英文各两题。")
    identities, cells, queries = set(), set(), []
    for item in raw_queries:
        if not isinstance(item, dict):
            raise ValueError("回答面板题目格式无效。")
        query_id, locale, line, prompt = (item.get(key) for key in ("id", "locale", "product_line", "prompt"))
        if not isinstance(query_id, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,99}", query_id) or query_id in identities:
            raise ValueError("回答面板题目 ID 必须唯一且不能包含路径。")
        if not isinstance(locale, str) or not isinstance(line, str) or locale not in {"en-US", "zh-CN"} or line not in {"mouse", "ai_device"} or (locale, line) in cells:
            raise ValueError("每个语言必须各有电竞鼠标和 AI device 一题。")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise ValueError("回答面板需要有效的中立问题。")
        if re.search(r"angry\s*miao|怒喵|cyberboard|am\s+infinity", prompt, re.I):
            raise ValueError("发现面板不得在问题中预置品牌或产品名称。")
        identities.add(query_id)
        cells.add((locale, line))
        queries.append({"id": query_id, "language": locale, "prompt": prompt, "product_line": line})
    snapshot = json.loads(json.dumps(plan, ensure_ascii=False))
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"id": identifier, "title": title.strip(), "version": version, "model": PANEL_MODEL,
            "queries": queries, "snapshot": snapshot, "sha256": hashlib.sha256(encoded).hexdigest()}


def answer_panel(root, cycle, directory, runner_factory=None, *, panel_plan=None):
    from .workflow import CodexRunner
    selected = validate_answer_panel(panel_plan) if panel_plan is not None else None
    if selected:
        queries = selected["queries"]
    else:
        queries = json.loads((root / "outputs/agent-kit/query-seeds.json").read_text(encoding="utf-8"))["queries"]
        queries = [query for query in queries if query["id"] in PANEL_IDS]
    queries = [query for query in queries if cycle.get("market", "both") == "both" or query["language"] == cycle["market"]]
    if not queries:
        raise ValueError("固定题组缺失，不能用临时换题生成分数。")
    panel_version = selected["id"] if selected else PANEL_VERSION
    directory.mkdir(parents=True, exist_ok=True)
    if selected:
        (directory / "panel-plan.json").write_text(json.dumps(selected["snapshot"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def sample(query):
        record = {"run_id": cycle["id"], "query_id": query["id"], "locale": query["language"],
                  "surface": "api_answer", "platform": "codex-cli-search", "mode": "web-search", "prompt": query["prompt"],
                  "panel_version": panel_version, "captured_at_utc": now()}
        if "product_line" in query:
            record["product_line"] = query["product_line"]
        try:
            # Empty cwd and fresh process prevent brand files/previous answers from priming this query.
            with tempfile.TemporaryDirectory(prefix="amseo-neutral-") as neutral:
                runner = runner_factory(Path(neutral)) if runner_factory else CodexRunner(Path(neutral), model=PANEL_MODEL)
                prompt = ("Answer the following shopper question using live web search. Use only public sources. "
                          "Do not read local files or any brand project. Answer naturally in the question's language. "
                          "Include only URLs actually cited in your final answer in citations, not a list of search results. "
                          "If unable to produce an answer set no_ai_answer. Recommend products only when helpful for the question.\n\n" + query["prompt"])
                raw = runner(prompt, ANSWER_SCHEMA, directory / query["id"], search=True)
            result = raw.get("result", raw)
            if not raw.get("trace", {}).get("web_search_events"):
                raise ValueError("没有实际联网搜索轨迹，不能计作本轮联网答案样本。")
            if result.get("status") not in {"completed", "no_ai_answer"} or not isinstance(result.get("answer_text"), str) or not isinstance(result.get("citations"), list):
                raise ValueError("采样返回格式不符合固定协议。")
            if result["status"] == "completed" and not result["answer_text"].strip():
                raise ValueError("空回答不能作为完成的样本。")
            citations = []
            for url in result["citations"]:
                if not isinstance(url, str):
                    raise ValueError("引用必须为 URL。")
                parsed = urlsplit(url)
                if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
                    citations.append(url)
            record.update(status=result["status"], answer_text=result["answer_text"], citations=citations)
            record["brand_mentioned"] = result["status"] == "completed" and bool(re.search(r"angry\s*miao|怒喵", result["answer_text"], re.I))
            record["official_citation"] = result["status"] == "completed" and any(urlsplit(url).hostname in ALLOWED_HOSTS for url in citations)
            record["trace"] = raw.get("trace", {})
            record["classification_method"] = "正文品牌词匹配，仅计算出现，不推断适配推荐或事实正确性。"
        except Exception as error:
            record.update(status="error", error=str(error)[:1000])
        record["finished_at_utc"] = now()
        return record

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(sample, queries))
    (directory / "observations.jsonl").write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    result = summarize_answers(records)
    versions = sorted({record.get("trace", {}).get("cli_version") for record in records if record.get("trace", {}).get("cli_version")})
    protocol = {"panel_version": panel_version, "queries": [{"id": q["id"], "locale": q["language"], "prompt": q["prompt"], **({"product_line": q["product_line"]} if "product_line" in q else {})} for q in queries],
                "model": PANEL_MODEL, "surface": "api_answer", "platform": "codex-cli-search", "mode": "live-web-search", "neutral_cwd": True,
                "metric": "brand_mention_rate_x100", "metric_version": "literal-brand-presence-v1", "cli_versions": versions}
    result["panel_version"] = panel_version
    if selected:
        coverage = {locale: sorted({q["product_line"] for q in queries if q["language"] == locale}) for locale in sorted({q["language"] for q in queries})}
        protocol.update(panel_plan_sha256=selected["sha256"], plan_hash_method="canonical-json-sha256", panel_config_version=selected["version"], topic_coverage=coverage)
        result.update(panel_title=selected["title"], panel_plan_sha256=selected["sha256"], topic_coverage=coverage,
                      baseline_rule="独立的新主题面板；历史试运行与原始题库保持留存，跨主题分数不可比较。")
    result.update(protocol=protocol, panel_fingerprint=hashlib.sha256(json.dumps(protocol, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                  model=PANEL_MODEL, metric_version=protocol["metric_version"], metric=protocol["metric"], comparable_protocol=len(versions) == 1)
    result["observations_file"] = str(directory / "observations.jsonl")
    result["observations"] = records
    (directory / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def measure(root, cycle, runner=None):
    plan_path = root / "config/answer-panel.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else None
    # Validate before even the independent HTML fetch, so malformed plans never
    # consume model calls or leave a misleading partially executed measurement.
    if plan is not None:
        validate_answer_panel(plan)
    measurement_id = uuid.uuid4().hex
    directory = root / "outputs/runtime/console/workflow" / cycle["id"] / "measurement" / measurement_id
    technical = technical_panel(directory / "seo")
    geo = answer_panel(root, cycle, directory / "geo", panel_plan=plan)
    tasks = cycle.get("tasks", [])
    return {"measurement_id": measurement_id, "artifact_dir": str(directory.relative_to(root)), "measured_at_utc": now(),
            "seo": {"status": "waiting_data", "score": None, "reason": "真实搜索表现需接入 GSC / Bing / 百度数据；技术检查分单列。", "technical": technical},
            "geo": geo,
            "execution": {"verified": sum(task.get("status") == "completed" for task in tasks), "total": len(tasks),
                          "prepared": sum(task.get("status") in {"needs_review", "prepared"} for task in tasks)},
            "production_writes": 0}


def measure_technical_only(root, cycle):
    from copy import deepcopy
    measurement_id = uuid.uuid4().hex
    directory = root / "outputs/runtime/console/workflow" / cycle["id"] / "measurement" / measurement_id
    technical = technical_panel(directory / "seo")
    previous = cycle.get("metrics") or {}
    geo = deepcopy(previous.get("geo") or {"status": "not_measured", "score": None, "groups": [], "reason": "本次仅做技术诊断，没有调用 AI 采样。"})
    return {"measurement_id": measurement_id, "artifact_dir": str(directory.relative_to(root)), "evaluated_at": now(),
            "seo": {"status": "waiting_data", "score": None, "reason": "只有技术诊断；真实搜索表现仍待数据。", "technical": technical},
            "geo": geo, "geo_reused_from_measurement_id": previous.get("measurement_id"),
            "scope": "技术检查为本次新请求；GEO 若有则保留原始时间和原始结果，未重新采样。", "production_writes": 0}
