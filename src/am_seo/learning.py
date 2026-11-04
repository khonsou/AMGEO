"""Deterministic process lessons from recorded evidence, with no model call."""
import json
import hashlib
import re
from copy import deepcopy


def runtime_failure(message):
    if not isinstance(message, str):
        return None
    lower = message.lower()
    if any(word in lower for word in ("usage limit", "quota exceeded", "insufficient_quota")):
        return {"kind": "usage_limit", "label": "模型账号额度受限", "message": "模型调用返回额度限制。已有成果可继续查看、人工核验和本地证据复盘；恢复额度后可明确重试。", "detail": message[-4000:]}
    if any(word in lower for word in ("unauthorized", "authentication failed", "not logged in")):
        return {"kind": "authentication", "label": "模型登录需恢复", "message": "执行器认证失败。已有证据与本地检查不受影响。", "detail": message[-4000:]}
    return None


def process_lessons(cycle, project, brand_context=None):
    tasks = cycle.get("tasks", [])
    metrics = cycle.get("metrics") or {}
    lessons = []

    def add(finding, change, evidence):
        lessons.append({"finding": finding, "change": change, "evidence": evidence,
                        "scope": "process", "cycle_id": cycle["id"],
                        "status": "adopted_process_candidate", "method": "local_evidence_rules_v1"})

    errors = [cycle.get("error", "")] + [r.get("error", "") for r in metrics.get("geo", {}).get("observations", [])]
    if any(runtime_failure(error) for error in errors):
        add("本轮模型调用遇到额度或认证限制，搜索表现不能据此判零。",
            "同一执行器硬失败后停止自动重复调用；保留结果与错误，继续独立本地工作，恢复后由明确重试接续。",
            f"{cycle['id']}.error; metrics.geo.observations errors")
    capability_noted = False
    for task in tasks:
        review = task.get("independent_review", {})
        if review.get("blocked_claims") and review.get("criteria") and all(c.get("passed") for c in review["criteria"]):
            add("核验记录中全部条件通过，却同时列出阻塞主张，验收协议存在语义冲突。",
                "阻塞项仅记录产物实际断言且无支持的主张；明确排除或保留未知的主张不算失败。保持逐项核验及哈希检查。",
                f"{task['id']}.independent_review")
        if task.get("capability_resolution", {}).get("resolved") and not capability_noted:
            add("模型子进程只读与宿主保存产物的能力不同。",
                "由服务保存结构化任务产物；已有本地保存能力不再作为缺失授权阻塞研究和写稿。",
                f"{task['id']}.capability_resolution")
            capability_noted = True
    if metrics.get("seo", {}).get("score") is None and metrics.get("seo", {}).get("technical"):
        add("本轮只有网页技术诊断，缺少真实搜索表现数据。",
            "技术分单列并保留采集覆盖；排名、展现与点击维持待测，不从资料验收或技术分推导效果。",
            "metrics.seo.score=null; metrics.seo.technical")
    current_brand = brand_context or {}
    adopted_lines = (current_brand.get("context") or {}).get("user_direction", {}).get("adopted_product_lines", [])
    categories = adopted_lines or project.get("brand", {}).get("product_categories", [])
    content = json.dumps([{k: t.get(k) for k in ("title", "instruction")} for t in tasks], ensure_ascii=False)
    if not adopted_lines and any("键盘" in value for value in categories) and tasks and not re.search(r"键盘|keyboard|cyberboard|hatsu", content, re.I):
        add("项目范围包含鼠标与键盘，本轮任务集中于鼠标，覆盖不完整。",
            "下一轮按目标补充键盘的公开评测、社区和产品事实；本轮鼠标结果不外推为整个品牌的结论。",
            f"{cycle['id']}.tasks; config.project.brand.product_categories")
    used_brand = cycle.get("brand_context_snapshot") or {}
    if current_brand.get("configured") and used_brand.get("sha256") != current_brand.get("sha256"):
        add("本轮品牌与人群输入未采用当前版本，旧任务不能追认为已使用新资料。",
            "下一轮冻结品牌资料来源版本，按核心人群、需求阶段与渠道生成任务；历史记录保留，并将人群画像视为待验证的规划依据。",
            f"{cycle['id']}.brand_context_snapshot; config/brand-context.json sha256={current_brand.get('sha256')}")
    if not lessons:
        add("当前记录没有足够证据证明搜索或 AI 表现提升。",
            "保留任务、来源、固定面板和未完成依赖，在取得可比观测后再判断效果。",
            f"{cycle['id']}.tasks; metrics.comparison")
    # One local review per exact evidence snapshot, avoiding version inflation on repeated clicks.
    evidence = {"cycle_id": cycle["id"], "tasks": [{k: t.get(k) for k in ("id", "status", "review", "independent_review", "capability_resolution")} for t in tasks],
                "measurement_id": metrics.get("measurement_id"), "error": cycle.get("error"), "categories": categories, "used_brand_sha256": used_brand.get("sha256"), "current_brand_sha256": current_brand.get("sha256")}
    fingerprint = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return lessons, fingerprint


def rebase_brand_direction(strategy, brand_context):
    """Retire only category-bound instructions when an explicit direction changes."""
    lessons = deepcopy(strategy.get("lessons", []))
    priorities = list(strategy.get("priorities", []))
    direction = (brand_context.get("context") or {}).get("user_direction", {})
    lines = direction.get("adopted_product_lines", [])
    if not isinstance(lines, list) or not lines:
        return lessons, priorities, []
    previous_lines = strategy.get("adopted_product_lines", [])
    if lines != previous_lines:
        for lesson in lessons:
            if "config.project.brand.product_categories" not in str(lesson.get("evidence", "")):
                continue
            lesson.update(status="superseded_brand_direction", superseded_by_brand_context_sha256=brand_context.get("sha256"),
                          superseded_reason="此前品类假设未绑定当前用户明确采用的产品方向；保留历史，不继续作为执行优先级。")
    retired = {lesson.get("change") for lesson in lessons if lesson.get("status") == "superseded_brand_direction"}
    priorities = [priority for priority in priorities if priority not in retired]
    if strategy.get("brand_context_sha256") == brand_context.get("sha256"):
        return lessons, priorities, []
    adoption = [{"finding": "当前用户已明确更新品牌核心产品方向，旧品类假设不能覆盖这次指令。",
                 "change": "下一轮以 user_direction.adopted_product_lines 为优先：" + "；".join(lines) + "；旧参考与历史经验仅在不冲突时复用。",
                 "evidence": "config/brand-context.json user_direction.adopted_product_lines; sha256=" + str(brand_context.get("sha256")),
                 "scope": "process", "status": "adopted_process_candidate", "method": "local_evidence_rules_v1",
                 "brand_context_sha256": brand_context.get("sha256")}]
    return lessons, priorities, adoption
