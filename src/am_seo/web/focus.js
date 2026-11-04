"use strict";
let focusBusy=false,labPosting=false,questionSelection=null,questionPanelId=null,activeFocusHash=null,scoreSourceChosen=false;
const TODO_GROUPS={foundation:"网站基础",content:"内容与工具页",attribution:"AI 流量归因",other:"其他优化"};
function focusWorkspace(){return state?.geo_workspace||{tasks:[],playbook:{questions:[],intents:{}}};}
function questionLab(){return state?.question_lab||{connection:{},panel:null,runs:[],active:false,job:null};}
function latestGeoCycle(){return cycles().slice().reverse().find(item=>(item.metrics?.geo?.groups||[]).some(group=>typeof group.score==="number"));}
function latestApiRun(){return questionLab().runs.at(-1);}
function focusButton(text,callback,cls="button secondary"){const button=node("button",text,cls);button.type="button";button.dataset.focusAction="true";button.disabled=focusBusy;button.addEventListener("click",callback);return button;}
async function focusAction(action,payload={}){
  if(focusBusy)return false;focusBusy=true;renderFocusControls();
  try{await api("/api/geo",{action,...payload});state=await api("/api/state");render();if(action!=="toggle")toast(({generate:"Todo 已生成。",prepare:"产物已保存。","prepare-all":"产物已准备。",check:"验证结果已保存。","import-traffic":"AI 流量报表已导入。"})[action]);return true;}
  catch(error){toast(error.message);if(action==="import-traffic")$("#traffic-import-result").textContent=error.message;return false;}
  finally{focusBusy=false;renderFocusControls();}
}
async function labAction(action,payload={}){
  if(labPosting)return false;labPosting=true;renderFocusControls();
  try{await api("/api/question-lab",{action,...payload});state=await api("/api/state");render();return true;}
  catch(error){toast(error.message);$("#api-config-status").textContent=error.message;$("#lab-status").textContent=error.message;return false;}
  finally{labPosting=false;renderFocusControls();}
}
function renderFocusControls(){
  const lab=questionLab(),active=lab.active||labPosting,connected=lab.connection.has_key;
  $("#focus-generate").disabled=focusBusy||!questionSelection?.size||lab.active;
  $("#focus-prepare-all").disabled=focusBusy||!focusWorkspace().tasks.some(task=>task.status==="ready");
  $("#lab-generate-test").disabled=active||!connected;$("#lab-generate").disabled=active||!connected;$("#lab-retest").disabled=active||!connected||!lab.panel;
  $("#api-verify").disabled=active||!connected;
  document.querySelectorAll('#api-config-form button,#api-config-form input,#api-config-form select').forEach(el=>{el.disabled=active;});
  $("#api-verify").disabled=active||!connected;
  const apiSource=$("#score-source").value==="api",runtime=workflow().runtime||{};
  $("#focus-evaluate").disabled=apiSource?(active||!connected||!lab.panel):(busy()||runtime.blocked||runtime.available===false||!cycles().length);
  $("#focus-evaluate").textContent=apiSource?"重测原题组 API":busy()?"联网采样中…":"重测联网 Agent";
  document.querySelectorAll('[data-focus-action],.todo-checkbox,#traffic-import-form button').forEach(button=>{button.disabled=focusBusy;});
}
function renderFocusScore(){
  const lab=questionLab(),apiRun=latestApiRun(),measured=latestGeoCycle();
  const apiOption=$("#score-source").querySelector('option[value="api"]');apiOption.disabled=!apiRun;
  apiOption.textContent=apiRun?`API · ${apiRun.protocol.provider} / ${apiRun.protocol.model}`:"问题测试 API（未测）";
  if(apiRun&&!scoreSourceChosen)$("#score-source").value="api";
  const isApi=$("#score-source").value==="api",metric=isApi?apiRun:measured?.metrics?.geo,groups=metric?.groups||[];
  $("#focus-geo-score").replaceChildren(...(groups.length?groups.map(group=>{const card=node("article",undefined,"focus-score-card"),has=typeof group.score==="number"&&Number.isFinite(group.score);
    card.append(node("span",`${metricLocale(group.locale)}${isApi?(group.test_group==="branded"?" · 品牌题":" · 发现题"):""}`,"focus-score-label"));
    const value=node("div",has?Math.round(group.score*10)/10:"待测","focus-score-number");if(has)value.append(node("small","/ 100"));
    card.append(value,node("p",`有效 ${group.successful_tests??0} · 错误 ${group.errors??0}${isApi?` · 未运行 ${group.not_run??0}`:""}`));return card;
  }):[node("p","暂无有效测试结果。","empty-panel")]));
  const visible=groups.filter(group=>!isApi||group.test_group==="discovery");
  const compact=['zh-CN','en-US'].map(locale=>{const group=visible.find(item=>item.locale===locale);return `${locale==="zh-CN"?"中":"英"} ${typeof group?.score==="number"?Math.round(group.score*10)/10:"待测"}`;}).join(" · ");
  $("#score-float-summary").textContent=`${isApi?"API":"联网"} ${compact}`;
  const job=lab.job;
  $("#score-run-status").textContent=job?.status==="error"?`最近 Skill 运行失败：${job.error}`:job?.status==="partial"?"最近一轮有调用错误或未运行项，已保留在分母说明中。":lab.active?"Skill 正在运行，浮窗结果会自动更新。":"";
  $("#focus-score-scope").textContent=isApi&&apiRun?`品牌 / 产品命中率 · API 未联网 · ${date(apiRun.finished_at||apiRun.started_at)}。发现题与品牌题分别计分。`:metric?`固定题组品牌出现率 · 联网 Agent/API · ${measurementWindow(metric)}。与其他模型或题组分数分别记录。`:"先在问题测试页运行 Skill。";
  $("#focus-evidence").disabled=!metric;
}
function renderFocusQuestions(){
  const workspace=focusWorkspace(),book=workspace.playbook,lab=questionLab(),locale=$("#question-locale").value,intent=$("#question-intent").value;
  const panelId=book.panel_id||"seed";
  if(questionSelection===null||questionPanelId!==panelId){questionSelection=new Set(workspace.selected_questions||book.questions.filter(q=>q.selected).map(q=>q.id));questionPanelId=panelId;}
  $("#question-intents").replaceChildren(...Object.entries(book.intents||{}).map(([id,value])=>{const button=focusButton(value.label,()=>{$("#question-intent").value=id;renderFocusQuestions();},"intent-card");button.append(node("span",`→ ${value.page}`));return button;}));
  const run=latestApiRun(),recordMap=new Map(run?.panel_id===lab.panel?.id?run.observations.map(record=>[record.id,record]):[]);
  $("#focus-questions").replaceChildren(...book.questions.filter(q=>(locale==="all"||q.locale===locale)&&(intent==="all"||q.intent===intent)).map(question=>{
    const card=node("article",undefined,"question-result-card"),label=node("label",undefined,"question-card"),check=node("input"),record=recordMap.get(question.id.split('-').at(-1));
    check.type="checkbox";check.checked=questionSelection.has(question.id);check.setAttribute("aria-label",`选择问题：${question.prompt}`);
    check.addEventListener("change",()=>{if(check.checked)questionSelection.add(question.id);else questionSelection.delete(question.id);renderQuestionSelection();});
    const copy=node("span",undefined,"question-copy");copy.append(node("strong",question.prompt),node("small",`${book.intents[question.intent]?.label} · ${question.locale==="zh-CN"?"中文":"English"}${question.brand_seeded?" · 品牌题":""}`));label.append(check,copy);
    const status=record?(record.status==="error"?"调用错误":record.status==="not_run"?"未运行":record.hit?"命中":"未命中"):"待测";
    label.append(node("span",status,`question-hit ${record?.status==="error"?"error":record?.hit?"hit":"miss"}`));card.append(label);
    if(record){const details=node("details",undefined,"question-answer");details.append(node("summary","回答与命中证据"),node("pre",record.answer_text||record.error||"本题未产生回答。","code-output"));if(record.matches?.length)details.append(node("p",`匹配：${record.matches.join("、")}`,"form-note"));details.append(node("small",`${record.model||run.protocol.model} · API 未联网 · ${date(record.finished_at)}`));card.append(details);}
    return card;
  }));renderQuestionSelection();
}
function renderQuestionSelection(){$("#question-selection").textContent=`已选 ${questionSelection?.size||0} 题 · ${questionLab().panel?"Skill 生成题组":"当前为种子问题，尚未用 API 测试"}`;renderFocusControls();}
function openTraffic(){const dialog=$("#traffic-dialog");if(!dialog.open)dialog.showModal();}
function focusTaskCard(task){
  const card=node("article",undefined,`todo-item${task.execution_done?" is-done":""}`),head=node("div",undefined,"todo-head"),check=node("input");
  check.type="checkbox";check.className="todo-checkbox";check.checked=task.execution_done===true;check.setAttribute("aria-label",`执行完成：${task.title}`);
  check.addEventListener("change",async()=>{if(!await focusAction("toggle",{task_id:task.id,done:check.checked}))check.checked=task.execution_done===true;});
  const title=node("div",undefined,"todo-title");title.append(node("h3",task.title));
  if(task.next_action)title.append(node("p",task.next_action,"todo-next"));
  if(task.kind==="traffic")title.append(node("p",focusWorkspace().traffic?`${focusWorkspace().traffic.ai_sessions} 个 AI 来源会话 · ${focusWorkspace().traffic.start_date} — ${focusWorkspace().traffic.end_date}`:"等待真实访问报表","todo-next"));
  const status=task.validation_status||"not_checked",label={passed:"验证通过",failed:"验证不通过",not_checked:"待验证"}[status];
  head.append(check,title,node("span",label,`todo-validation ${status}`));card.append(head);
  const details=node("details",undefined,"todo-details");details.dataset.taskId=task.id;details.append(node("summary","操作、产物与验证详情"));
  const controls=node("div",undefined,"focus-task-actions");controls.append(focusButton(task.question?.basis==="skill_generated"?"Agent 生成对应页面":task.artifacts?.length?"重新准备产物":"准备产物",()=>focusAction("prepare",{task_id:task.id})),focusButton("验证",()=>focusAction("check",{task_id:task.id})));
  if(task.kind==="traffic")controls.append(focusButton("设置 AI 流量来源",openTraffic));
  const artifact=(task.artifacts||[]).find(a=>a.filename==="index.html")||task.artifacts?.[0];if(artifact){const link=node("a",artifact.filename==="index.html"?"预览页面 ↗":"查看配置产物 ↗","text-button");link.href=`/api/geo/files/${encodeURIComponent(task.id)}/${encodeURIComponent(artifact.filename)}`;link.target="_blank";link.rel="noopener noreferrer";controls.append(link);}details.append(controls);
  if(task.target_url)details.append(node("p",`目标：${task.target_url}`,"focus-target"));
  if(task.question?.basis==="skill_generated")details.append(node("p","此题使用现有 Agent 公开检索并生成对应内容，不套用固定换电模板；消耗该执行器的模型额度。","form-note"));
  const steps=node("ol",undefined,"simple-steps");task.steps.forEach(step=>steps.append(node("li",step)));details.append(steps,node("strong","完成条件","small-label"));
  const acceptance=node("ul",undefined,"simple-steps");task.acceptance.forEach(value=>acceptance.append(node("li",value)));details.append(acceptance);
  if(task.checks?.length){task.checks.forEach(item=>details.append(node("p",`${item.passed?"✓":"✕"} ${item.title}${item.detail?` · ${item.detail}`:""}`,item.passed?"check-passed":"check-pending")));details.append(node("p",`验证于 ${date(task.verification?.checked_at)} · 公开规则 / HTML 基础检查，发布与内容事实另按完成条件核对。`,"form-note"));}
  else details.append(node("p","尚未验证。勾选不会改写验证结果。","form-note"));
  card.append(details);return card;
}
function renderFocusTasks(){
  const tasks=focusWorkspace().tasks,filter=$("#focus-task-filter").value,done=tasks.filter(t=>t.execution_done).length,passed=tasks.filter(t=>t.validation_status==="passed").length,failed=tasks.filter(t=>t.validation_status==="failed").length;
  $("#todo-progress").replaceChildren(node("span",`已勾选 ${done} / ${tasks.length}`),node("span",`验证通过 ${passed}`,"check-passed"),node("span",`验证不通过 ${failed}`,"check-pending"));
  const shown=tasks.filter(t=>filter==="all"||(filter==="pending"?!t.execution_done:filter==="done"?t.execution_done:t.validation_status==="failed"));
  const opened=new Set([...document.querySelectorAll('#focus-tasks details[open]')].map(el=>el.dataset.taskId)),groups=[];
  for(const [id,label] of Object.entries(TODO_GROUPS)){const rows=shown.filter(t=>(t.group||"other")===id);if(!rows.length)continue;const group=node("section",undefined,"todo-group");group.append(node("h2",`${label} · ${rows.length}`));rows.forEach(t=>group.append(focusTaskCard(t)));groups.push(group);}
  $("#focus-tasks").replaceChildren(...(groups.length?groups:[node("p","当前筛选没有 Todo。","empty-panel")]));
  document.querySelectorAll('#focus-tasks details').forEach(el=>{el.open=opened.has(el.dataset.taskId);});
  $("#focus-download").hidden=!tasks.some(t=>t.artifacts?.length);
  $("#focus-publish-note").textContent="工具与配置在本地准备；真实站点发布仍需对应源码 / CMS 连接。";
}
function renderFocusTraffic(){
  const report=focusWorkspace().traffic,wrap=$("#focus-traffic");if(!report){wrap.replaceChildren(node("p","尚无真实访问数据。导入带站点与日期范围的 GA4 聚合报表后统计。","focus-scope"));return;}
  const summary=node("div",undefined,"focus-stat-grid");[[report.ai_sessions,"AI 来源会话"],[report.ai_key_events??"未导入","关键事件"]].forEach(([value,label])=>{const item=node("div");item.append(node("strong",value),node("span",label));summary.append(item);});const rows=node("div");report.sources.forEach(source=>{const row=node("p",`${source.platform} · ${source.sessions} 会话 · ${source.key_events??"—"} 关键事件`);rows.append(row);});wrap.replaceChildren(node("p",`${report.property_host} · ${report.start_date} — ${report.end_date}`,"focus-report-range"),summary,rows,node("p",report.scope,"focus-scope"));
}
function renderLab(){
  const lab=questionLab(),connection=lab.connection,job=lab.job;
  $("#lab-connection-link").textContent=connection.has_key?`${connection.provider} · ${connection.model}${connection.verified?" · 已验证":" · 待验证"}`:"连接 API ↗";
  const messages={queued:"已开始。",generating:"Skill 正在生成 8 个中英问题…",testing:`独立回答测试中：${job?.done??0} / ${job?.total??8}`,completed:"本轮已完成，可展开各题回答与命中证据。",partial:"部分测试失败，错误和未运行项已分别记录。",error:`本次未完成：${job?.error||"接口错误"}`};
  $("#lab-status").textContent=!connection.has_key?"等待确认 API 服务并接入凭证。":job?messages[job.status]:"连接已配置。点击生成并测试，或先仅生成问题。";
  if(changed("api-config",connection)){
    const focused=document.activeElement;if(!$("#api-config-form").contains(focused)||!['INPUT','SELECT'].includes(focused?.tagName)){
      $("#api-provider").value=connection.provider||"";$("#api-base-url").value=connection.base_url||"";$("#api-model").value=connection.model||"";
    }
    $("#api-model-options").replaceChildren(...(connection.available_models||[]).map(model=>{const option=node("option");option.value=model;return option;}));
    $("#api-config-status").textContent=connection.has_key?`${connection.verified?"连接已验证":"已保存，待验证"} · ${connection.storage==="keychain"?"凭证在本机 Keychain":"凭证仅保留于当前进程"}${connection.last_error?` · ${connection.last_error}`:""}`:"尚未配置连接。";
  }
  if(changed('lab-history',lab.runs))$("#lab-history").replaceChildren(...lab.runs.slice().reverse().map(run=>{const row=node('div',undefined,'history-row'),errors=run.observations.filter(r=>r.status==='error').length;row.append(node('span',`${date(run.finished_at||run.started_at)} · ${run.status} · ${errors} 个错误`),focusButton('查看本轮回答与参数',()=>openContent(`问题测试 ${run.id}`,JSON.stringify(run,null,2)),'text-button'));return row;}));
}
function renderFocus(){
  const workspace=focusWorkspace(),lab=questionLab();
  if(changed("focus-todos",[workspace.tasks,workspace.traffic]))renderFocusTasks();
  if(changed("focus-questions",[workspace.playbook,workspace.selected_questions,lab.panel,lab.runs]))renderFocusQuestions();
  if(changed("focus-traffic",workspace.traffic))renderFocusTraffic();
  if(changed("focus-scores",[cycles().map(c=>[c.id,c.metrics]),lab]))renderFocusScore();
  renderLab();renderFocusControls();
  if(changed("focus-sources",workspace.playbook.guidance_sources))$("#focus-method-sources").replaceChildren(...(workspace.playbook.guidance_sources||[]).map(source=>{const p=node("p");p.append(safeLink(source.url,source.title));return p;}));
  routeFocus();
}
function routeFocus(){
  const raw=location.hash.slice(1)||"todo",alias={overview:"todo",tasks:"todo",traffic:"todo"},hash=alias[raw]||raw,views=['todo','questions','settings'],route=views.includes(hash)?hash:'settings';
  const moved=hash!==activeFocusHash;activeFocusHash=hash;document.querySelectorAll('[data-view]').forEach(view=>{view.hidden=view.dataset.view!==route;});document.querySelectorAll('.nav-link').forEach(link=>link.classList.toggle('active',link.hash===`#${route}`));
  if(route==='settings'&&hash!=='settings'){const target=document.getElementById(hash);if(target){let parent=target.tagName==='DETAILS'?target:target.parentElement;while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}if(moved)target.scrollIntoView();}}
  else if(moved)document.getElementById(route)?.scrollIntoView({block:'start'});
}
function labPayload(){return {product:$("#lab-product").value.trim()};}
$("#question-lab-form").addEventListener('submit',event=>{event.preventDefault();labAction('generate-test',labPayload());});
$("#lab-generate").addEventListener('click',()=>labAction('generate',labPayload()));$("#lab-retest").addEventListener('click',()=>labAction('test',labPayload()));
$("#api-config-form").addEventListener('submit',async event=>{event.preventDefault();const form=event.target;const success=await labAction('configure',{provider:form.elements.provider.value,base_url:form.elements.base_url.value,model:form.elements.model.value,api_key:form.elements.api_key.value});if(success)$("#api-key").value='';});
$("#api-verify").addEventListener('click',()=>labAction('verify-connection'));
$("#api-provider").addEventListener('change',()=>{const provider=$("#api-provider").value;$("#api-base-url").value=({deepseek:'https://api.deepseek.com/v1',openai:'https://api.openai.com/v1'})[provider]||'';$("#api-model").value=provider==='deepseek'?'deepseek-flash':'';});
$("#focus-evaluate").addEventListener('click',()=>$("#score-source").value==='api'?labAction('test',labPayload()):action('evaluate',{cycle_id:cycles().at(-1)?.id}));
$("#focus-evidence").addEventListener('click',()=>{if($("#score-source").value==='api')location.hash='questions';else{const measured=latestGeoCycle();if(measured){selectedCycleId=measured.id;render();location.hash='evaluation';}}routeFocus();});
$("#score-source").addEventListener('change',()=>{scoreSourceChosen=true;renderFocusScore();renderFocusControls();});
$("#score-float-toggle").addEventListener('click',()=>{const panel=$("#score-float-panel");panel.hidden=!panel.hidden;$("#score-float-toggle").setAttribute('aria-expanded',String(!panel.hidden));});
$("#score-float-close").addEventListener('click',()=>{$("#score-float-panel").hidden=true;$("#score-float-toggle").setAttribute('aria-expanded','false');});
$("#focus-generate").addEventListener('click',async()=>{if(await focusAction('generate',{question_ids:[...questionSelection]})){location.hash='todo';routeFocus();}});
$("#focus-prepare-all").addEventListener('click',()=>focusAction('prepare-all'));
$("#question-locale").addEventListener('change',renderFocusQuestions);$("#question-intent").addEventListener('change',renderFocusQuestions);$("#focus-task-filter").addEventListener('change',renderFocusTasks);
$("#traffic-close").addEventListener('click',()=>$("#traffic-dialog").close());
$("#traffic-import-form").addEventListener('submit',async event=>{event.preventDefault();const form=event.target,file=form.elements.report.files[0];if(!file)return;if(file.size>24000){$("#traffic-import-result").textContent='请导入小于 24 KiB 的聚合 CSV。';return;}const success=await focusAction('import-traffic',{csv:await file.text(),start_date:form.elements.start_date.value,end_date:form.elements.end_date.value,property_host:form.elements.property_host.value});if(success)$("#traffic-import-result").textContent='已导入。请在 Todo 中验证这项设置。';});
window.addEventListener('hashchange',routeFocus);routeFocus();if(state)renderFocus();
