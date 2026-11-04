"""Validate attributed browser SERP captures and score only complete top-ten panels.

This module performs no network or model calls. Submitted observations are
agent-attributed readings of preserved evidence, not search-account analytics.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit


METRIC = "official_domain_presence_top10_rate_x100"
OFFICIAL_HOSTS = {"angrymiao.com", "www.angrymiao.com", "store.angrymiao.com",
                  "mall.angrymiao.com", "m.angrymiao.com", "cdn-www.angrymiao.com",
                  "diy.angrymiao.com", "ammaster.angrymiao.com"}


def _text(value, field, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} requires non-empty bounded text")
    return value.strip()


def _timestamp(value):
    value = _text(value, "captured_at_utc", 100)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ValueError("Search capture time requires an ISO timestamp with timezone")
    return value


def _public_url(value, field):
    value = _text(value, field, 4096)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{field} requires a public HTTP(S) URL")
    host = parsed.hostname.lower()
    if "." not in host or host.endswith((".localhost", ".local", ".internal")) or host == "localhost":
        raise ValueError(f"{field} cannot point to a local service")
    import ipaddress
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError(f"{field} cannot point to a private address")
    return value


def _evidence(root, directory, relative, expected_sha, image=False):
    relative = _text(relative, "capture path", 1000)
    if Path(relative).is_absolute():
        raise ValueError("Capture paths must be project-relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError("Search capture must exist within this cycle's searchcaptures directory")
    size_limit = 20 * 1024 * 1024 if image else 2 * 1024 * 1024
    if not 0 < path.stat().st_size <= size_limit:
        raise ValueError("Search capture has an invalid size")
    content = path.read_bytes()
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or hashlib.sha256(content).hexdigest() != expected_sha:
        raise ValueError("Search capture hash mismatch")
    if image and not (content.startswith(b"\x89PNG\r\n\x1a\n") or content.startswith(b"\xff\xd8\xff")):
        raise ValueError("Search screenshot must be a captured PNG or JPEG")
    if not image:
        try:
            if not content.decode("utf-8").strip():
                raise ValueError("Search text evidence cannot be empty")
        except UnicodeError:
            raise ValueError("Search text evidence must be UTF-8")
    return str(path.relative_to(root)), hashlib.sha256(content).hexdigest()


def validate_search_measurement(root, cycle_id, payload):
    """Return scored observations after all fixed-panel and local evidence checks."""
    root = Path(root).resolve()
    if payload.get("executor") != "current_chat_agent":
        raise ValueError("Search measurement import requires the current authorized chat agent")
    plan_path = root / "config/search-panel.json"
    try:
        plan_bytes = plan_path.read_bytes()
        plan = json.loads(plan_bytes)
    except (OSError, ValueError):
        raise ValueError("A fixed config/search-panel.json is required before sampling")
    panel_sha = hashlib.sha256(plan_bytes).hexdigest()
    if payload.get("panel_sha256") != panel_sha or payload.get("panel") != plan:
        raise ValueError("Submitted search panel differs from the fixed pre-sampling plan")
    if not isinstance(plan, dict) or plan.get("engine") != "bing" or not plan.get("id") or not plan.get("version") or not isinstance(plan.get("settings"), dict):
        raise ValueError("Search panel needs identity, version, Bing engine and fixed settings")
    queries = plan.get("queries")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 12:
        raise ValueError("Search panel requires 1–12 fixed queries")
    by_id = {}
    for query in queries:
        if not isinstance(query, dict) or query.get("locale") not in {"en-US", "zh-CN"}:
            raise ValueError("Search query locale must be fixed before sampling")
        identifier = _text(query.get("id"), "query id", 100)
        _text(query.get("prompt"), "query prompt", 1500)
        if identifier in by_id:
            raise ValueError("Duplicate fixed search query")
        by_id[identifier] = query
    raw = payload.get("observations")
    if not isinstance(raw, list) or len(raw) != len(queries):
        raise ValueError("Every fixed query needs exactly one observation, including errors")
    captures = root / "outputs/runtime/console/workflow" / cycle_id / "searchcaptures"
    observations, seen = [], set()
    for item in raw:
        if not isinstance(item, dict) or item.get("query_id") not in by_id or item["query_id"] in seen:
            raise ValueError("Unknown or duplicate search observation")
        query = by_id[item["query_id"]]
        seen.add(item["query_id"])
        if item.get("platform") != "bing" or item.get("locale") != query["locale"] or item.get("status") not in {"completed", "error"}:
            raise ValueError("Search platform, locale and status must match the fixed panel")
        page_url = _public_url(item.get("page_url"), "page_url")
        parsed = urlsplit(page_url)
        if parsed.scheme != "https" or parsed.hostname not in {"www.bing.com", "bing.com", "cn.bing.com"} or parsed.path.rstrip("/") != "/search":
            raise ValueError("Search evidence URL must be the observed Bing search page")
        actual_query = parse_qs(parsed.query).get("q", [None])[0]
        if not isinstance(actual_query, str) or " ".join(actual_query.split()).casefold() != " ".join(query["prompt"].split()).casefold():
            raise ValueError("Observed search URL query differs from the fixed query")
        evidence, evidence_sha = _evidence(root, captures, item.get("evidence_path"), item.get("evidence_sha256"))
        screenshot, screenshot_sha = _evidence(root, captures, item.get("screenshot_path"), item.get("screenshot_sha256"), image=True)
        results = item.get("results", [])
        if not isinstance(results, list) or len(results) > 20:
            raise ValueError("Search results must be an ordered bounded organic-result list")
        normalized, result_urls = [], set()
        for rank, result in enumerate(results, 1):
            if not isinstance(result, dict) or isinstance(result.get("rank"), bool) or result.get("rank") != rank:
                raise ValueError("Organic result ranks must be consecutive from one")
            url = _public_url(result.get("url"), "organic result URL")
            identity = url.split("#", 1)[0]
            if identity in result_urls:
                raise ValueError("Duplicate result URL cannot stand in for another organic position")
            result_urls.add(identity)
            normalized.append({"rank": rank, "title": _text(result.get("title"), "result title", 1000), "url": url})
        status = item["status"]
        error = _text(item.get("error"), "search error", 2000) if status == "error" else None
        if status == "completed" and len(normalized) < 10:
            status, error = "error", "incomplete_top10: fewer than ten ordered organic results were captured; positive partial views are not scored"
        top10 = normalized[:10]
        official_ranks = [r["rank"] for r in top10 if urlsplit(r["url"]).hostname.lower() in OFFICIAL_HOSTS]
        observations.append({"query_id": query["id"], "query_text": query["prompt"], "locale": query["locale"],
                             "platform": "bing", "surface": "search_serp", "mode": "organic-top10",
                             "status": status, "reported_status": item["status"], "captured_at_utc": _timestamp(item.get("captured_at_utc")),
                             "page_url": page_url, "evidence_path": evidence, "evidence_sha256": evidence_sha,
                             "screenshot_path": screenshot, "screenshot_sha256": screenshot_sha,
                             "results": normalized, "organic_results_observed": len(normalized),
                             "capture_note": _text(item["capture_note"], "capture note", 3000) if item.get("capture_note") else None,
                             "screenshot_captured_at_utc": _timestamp(item["screenshot_captured_at_utc"]) if item.get("screenshot_captured_at_utc") else None,
                             "official_domain_present_top10": bool(official_ranks) if status == "completed" else None,
                             "official_domain_ranks_top10": official_ranks if status == "completed" else [],
                             "error": error, "classification_method": "Agent-attributed ordered organic results; exact allowlisted official-domain matching, not brand mentions in third-party text."})
    groups = []
    for locale in sorted({o["locale"] for o in observations}):
        subset = [o for o in observations if o["locale"] == locale]
        valid = [o for o in subset if o["status"] == "completed"]
        rate = sum(o["official_domain_present_top10"] for o in valid) / len(valid) if valid else None
        groups.append({"locale": locale, "platform": "bing", "surface": "search_serp", "mode": "organic-top10",
                       "score": round(rate * 100, 1) if rate is not None else None,
                       "attempted": len(subset), "completed": len(valid), "successful_tests": len(valid),
                       "errors": len(subset) - len(valid), "official_domain_presence_top10_rate": rate})
    measured = sum(g["successful_tests"] for g in groups)
    return {"status": "measured" if measured else "error", "score": None, "source_type": "browser_serp",
            "metric": METRIC, "metric_version": "exact-official-host-organic-top10-v1", "panel_id": plan["id"],
            "panel_version": plan["version"], "panel_sha256": panel_sha, "panel_fingerprint": panel_sha,
            "protocol": deepcopy(plan), "comparable_protocol": plan["settings"].get("comparison_controls_verified") is True,
            "comparability_reason": "只有在实际地区、登录/个性化及采样设置已验证一致时，才标为可比；固定查询或请求地区参数本身不足以证明可比。",
            "groups": groups, "observations": observations,
            "attempted": len(observations), "completed": measured, "errors": len(observations) - measured,
            "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": "按语言分别报告固定 Bing 查询的官方域名前十出现率；不生成跨语种总分。" if measured else "本轮搜索采样均未形成完整前十证据，错误单报，分数保持待测。",
            "scope": "实际浏览器 Bing 自然结果前十的官方域名出现率；非通用 SEO 分、流量或账号展现/点击。请求语种/地区不代表实际位置已验证。",
            "limitations": "小样本、单次浏览器与搜索环境；排除广告和非自然模块。全部固定查询均保留，缺少完整前十即报错；不证明优化造成变化。",
            "attribution": {"executor": "current_chat_agent", "independently_verified": False,
                            "scope": "Submitted browser observations and retained evidence; hash checks do not certify SERP extraction truth."}}


def preserve_search_measurement(previous, current):
    """A new GEO/technical run cannot silently erase or re-date a SERP capture."""
    old_search = (previous or {}).get("seo", {})
    fresh_search = current.get("seo", {})
    if old_search.get("source_type") != "browser_serp" or fresh_search.get("source_type") == "browser_serp":
        return current
    current["seo"] = deepcopy(old_search)
    if "technical" in fresh_search:
        current["seo"]["technical"] = fresh_search["technical"]
    current["seo_reused_from_search_measurement_id"] = old_search.get("measurement_id")
    current["search_measurement_id"] = old_search.get("measurement_id")
    return current
