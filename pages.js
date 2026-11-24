"use strict";
const byId = id => document.getElementById(id);
const marketName = {"both": "中英双市场", "zh-CN": "中文市场", "en-US": "英文市场"};
const languageName = {"zh-CN": "中文", "en-US": "English"};
const checks = {passed: "验证通过", failed: "验证不通过", not_checked: "待验证"};
let snapshot;

function element(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}

function recordDate(value) {
  if (!value) return "日期未记录";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "日期未记录";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  return timestamp.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  }) + "（上海）";
}

function navigate() {
  const requested = location.hash.slice(1);
  const view = ["todo", "questions", "settings"].includes(requested) ? requested : "todo";
  document.querySelectorAll("[data-view]").forEach(panel => { panel.hidden = panel.id !== view; });
  document.querySelectorAll(".nav-link").forEach(link => {
    const current = link.hash === "#" + view;
    link.classList.toggle("active", current);
    if (current) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function renderOverview() {
  const tasks = snapshot.tasks;
  const finished = tasks.filter(task => task.done).length;
  const passed = tasks.filter(task => task.check === "passed").length;
  const failed = tasks.filter(task => task.check === "failed").length;
  const cycle = snapshot.cycle;
  const heading = byId("guide-status");
  if (cycle) {
    byId("guide-round").textContent = [
      "第 " + cycle.number + " 轮", marketName[cycle.market], cycle.strategy_version != null ? "策略 v" + cycle.strategy_version : ""
    ].filter(Boolean).join(" · ");
    heading.replaceChildren(element("span", cycle.ready, "guide-quantity"), "项 Agent 任务可执行");
    byId("guide-progress").textContent = "本轮验收 " + cycle.verified + " / " + cycle.total + " 项 · 轮次快照 " + recordDate(cycle.updated_at);
  } else {
    heading.replaceChildren(element("span", tasks.length, "guide-quantity"), "项优化 Todo");
    byId("guide-progress").textContent = "验证通过 " + passed + " 项 · 验证不通过 " + failed + " 项";
  }
  const rows = [["已勾选", finished + " / " + tasks.length, ""], ["验证通过", passed, "check-passed"], ["验证不通过", failed, "check-pending"]];
  byId("task-counts").replaceChildren(...rows.map(([label, count, style]) => {
    const row = element("div", undefined, style);
    row.append(element("span", label), element("b", count));
    return row;
  }));
  byId("review-tasks").disabled = false;
}

function taskCard(task) {
  const card = element("details", undefined, "public-task");
  const head = element("summary");
  const status = Object.hasOwn(checks, task.check) ? task.check : "not_checked";
  head.append(element("strong", task.title), element("small", task.done ? "已勾选 · 查看详情" : "未勾选 · 查看详情"),
    element("span", checks[status], "todo-validation " + status));
  card.append(head);
  const content = element("div", undefined, "public-instructions");
  for (const [title, values, tag] of [["操作步骤", task.steps, "ol"], ["验收条件", task.acceptance, "ul"]]) {
    if (!values.length) continue;
    const list = element(tag);
    list.append(...values.map(value => element("li", value)));
    content.append(element("h4", title), list);
  }
  if (!content.childElementCount) content.append(element("p", "这项任务的详细说明待补充。"));
  card.append(content);
  return card;
}

function renderTasks() {
  const filter = byId("task-filter").value;
  const matching = snapshot.tasks.filter(task =>
    filter === "all" || filter === task.check || (filter === "done" && task.done) || (filter === "pending" && !task.done));
  const sections = new Map([["网站基础", []], ["内容与工具页", []], ["AI 流量归因", []]]);
  for (const task of matching) {
    const section = task.kind === "page" ? "内容与工具页" : task.kind === "traffic" ? "AI 流量归因" : "网站基础";
    sections.get(section).push(task);
  }
  const container = byId("task-list");
  container.replaceChildren();
  for (const [label, tasks] of sections) {
    if (!tasks.length) continue;
    const group = element("section", undefined, "todo-group");
    group.append(element("h2", label + " · " + tasks.length), ...tasks.map(taskCard));
    container.append(group);
  }
  if (!matching.length) container.append(element("p", "当前筛选没有任务记录。", "snapshot-meta"));
}

function renderQuestions() {
  const locale = byId("question-locale").value;
  const intent = byId("question-intent").value;
  const questions = snapshot.questions.filter(q => (locale === "all" || q.locale === locale) && (intent === "all" || q.intent === intent));
  byId("question-count").textContent = questions.length + " 个问题 · 种子题库更新于 " + recordDate(snapshot.question_updated_date);
  byId("question-list").replaceChildren(...questions.map(q => {
    const row = element("li");
    row.append(element("strong", q.prompt), element("small", [languageName[q.locale] || q.locale, snapshot.intents[q.intent] || q.intent].join(" · ")));
    return row;
  }));
  if (!questions.length) byId("question-list").append(element("li", "当前筛选没有种子问题。"));
}

function renderScores() {
  const geo = snapshot.geo;
  const source = byId("score-source-summary");
  const container = byId("score-groups");
  container.replaceChildren();
  if (!geo || !geo.groups.length) {
    source.textContent = "本次公开快照暂无 GEO 评分。";
    return;
  }
  source.textContent = [geo.provider, geo.model, "采样记录 " + recordDate(geo.verified_at)].filter(Boolean).join(" · ");
  for (const group of geo.groups) {
    const card = element("article", undefined, "focus-score-card");
    const label = (languageName[group.locale] || group.locale) + " · " + (group.test_group === "discovery" ? "发现题" : "品牌题");
    const measured = Number.isFinite(group.score);
    const score = element("div", measured ? String(group.score) : "待测", "focus-score-number");
    if (measured) score.append(element("small", " / 100"));
    card.append(element("h3", label, "focus-score-label"), score,
      element("p", "命中 " + group.hits + " / 已完成 " + group.successful_tests + " · 计划 " + group.planned),
      element("p", "调用错误 " + group.errors + " · 未运行 " + group.not_run));
    container.append(card);
  }
}

async function loadSnapshot() {
  byId("reload-data").disabled = true;
  try {
    const response = await fetch("./snapshot.json", {credentials: "omit", cache: "no-cache"});
    if (!response.ok) throw new Error("snapshot");
    const data = await response.json();
    if (!Array.isArray(data.tasks) || !Array.isArray(data.questions) || !data.intents) throw new Error("snapshot");
    snapshot = data;
    const intent = byId("question-intent");
    intent.replaceChildren(new Option("全部类型", "all"), ...Object.entries(snapshot.intents).map(([key, label]) => new Option(label, key)));
    renderOverview();
    renderTasks();
    renderQuestions();
    renderScores();
    byId("todo-record-date").textContent = "任务记录更新于 " + recordDate(snapshot.todo_updated_at);
    byId("load-error").hidden = true;
  } catch {
    byId("load-error").hidden = false;
    byId("guide-status").textContent = "任务快照暂不可用";
    byId("score-source-summary").textContent = "暂时无法读取采样记录。";
  } finally {
    byId("reload-data").disabled = false;
  }
}

function setScoreOpen(open) {
  byId("score-float-panel").hidden = !open;
  byId("score-float-toggle").setAttribute("aria-expanded", String(open));
  (open ? byId("score-float-close") : byId("score-float-toggle")).focus();
}

byId("review-tasks").addEventListener("click", () => {
  byId("task-filter").focus({preventScroll: true});
  byId("task-board").scrollIntoView();
});
byId("task-filter").addEventListener("change", () => { if (snapshot) renderTasks(); });
for (const id of ["question-locale","question-intent"]) {
  byId(id).addEventListener("change", () => { if (snapshot) renderQuestions(); });
}
byId("score-float-toggle").addEventListener("click", () => setScoreOpen(byId("score-float-panel").hidden));
byId("score-float-close").addEventListener("click", () => setScoreOpen(false));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !byId("score-float-panel").hidden) setScoreOpen(false);
});
byId("reload-data").addEventListener("click", loadSnapshot);
document.querySelector(".skip-workspace").addEventListener("click", event => {
  event.preventDefault();
  byId("workspace-main").focus();
});
window.addEventListener("hashchange", navigate);
navigate();
loadSnapshot();
