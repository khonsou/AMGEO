"""Small useful bilingual tools; factual gaps remain explicit in the draft."""
from html import escape
import json

PRODUCT = "https://store.angrymiao.com/products/am-infinity-97-wireless-gaming-mouse"
AI_SOURCE = "https://store.angrymiao.com/pages/cyberboard-ai-kickstarter-coming-soon"


def page_files(question, target_url):
    zh = question["locale"] == "zh-CN"
    mouse = question["product_line"] == "mouse"
    intent = question["intent"]
    if mouse:
        answer = ("先比较握姿、带电池重量、补电方式与备用电池条件，再看与游戏和桌面习惯的匹配。可换电池并不等于电池能瞬间充满。" if zh else
                  "Compare grip fit, weight with the battery installed, charging workflow and spare-battery requirements. Replacing a battery does not mean charging it instantly.")
        inputs = [("grip", "主要握姿" if zh else "Grip", [("palm", "趴握" if zh else "Palm"), ("claw", "抓握" if zh else "Claw"), ("tip", "指握" if zh else "Fingertip")]),
                  ("cable", "能否接受插线使用" if zh else "Can you use a charging cable?", [("avoid", "尽量不插线" if zh else "Prefer no cable"), ("ok", "可以接受" if zh else "Cable is fine")]),
                  ("spare", "能否维护备用电池" if zh else "Can you maintain a charged spare?", [("yes", "可以" if zh else "Yes"), ("no", "不方便" if zh else "Not conveniently")])]
        steps = (["核对具体型号的电池规格和充电方式。", "在非对局时确认备用电池已充电。", "按照产品说明换电，检查连接恢复，再继续使用。", "记录本次使用与补电情况；不要用宣传续航代替自己的使用记录。"] if zh else
                 ["Check the exact model's battery and charging instructions.", "Check that the spare is charged before a session.", "Replace the battery following the manual; verify reconnection before continuing.", "Record use and charging in your own setup rather than treating advertised runtime as a measurement."])
        limitation = ("本工具不预测具体鼠标手感、延迟或续航。AM Infinity 原版与 .97 分开核对；.97 有线重量存在来源冲突，未采用。" if zh else
                      "This tool does not predict grip comfort, latency or runtime. Verify the original AM Infinity and .97 separately. The conflicting .97 wired-weight field is omitted.")
        faq = [("换电和充电是一回事吗？" if zh else "Is swapping the same as charging?", "不是。换电使用已充电的备用电池，另一块仍需正常充电。" if zh else "No. A swap uses an already charged spare; the other battery still needs charging."),
               (".97 的有线重量是多少？" if zh else "What is the .97 wired weight?", "现有记录存在冲突，等待对应型号的权威更正或测量。" if zh else "The stored sources conflict. A model-specific correction or measurement is needed.")]
    else:
        answer = ("把语音转文字、应用控制和设备控制分开评估。先确认软件集成、系统兼容和失败时的手动退路，再决定是否需要独立硬件。" if zh else
                  "Evaluate voice transcription, app control and device control separately. Confirm integrations, operating-system compatibility and a manual fallback before choosing dedicated hardware.")
        inputs = [("need", "首要用途" if zh else "Primary task", [("dictation", "语音转文字" if zh else "Voice dictation"), ("apps", "控制应用" if zh else "App control"), ("devices", "控制设备" if zh else "Device control")]),
                  ("cloud", "是否允许上传工作内容" if zh else "Can work content leave the device?", [("no", "不允许 / 未确认" if zh else "No / unconfirmed"), ("yes", "已确认允许" if zh else "Approved")]),
                  ("integration", "目标系统是否已确认兼容" if zh else "Are exact integrations confirmed?", [("no", "尚未确认" if zh else "Not yet"), ("yes", "已实际验证" if zh else "Verified in practice")])]
        steps = (["选一个真实任务，写清输入、目标应用和成功结果。", "用已有系统或软件做一次基线测试。", "核对麦克风、权限、网络、模型或服务和目标设备接口。", "比较完成时间与人工接管次数，再决定是否增加硬件。"] if zh else
                 ["Choose one real task and specify its input, target app and successful outcome.", "Run a baseline with existing software or operating-system tools.", "Check microphone, permissions, network, model/service and device integrations.", "Compare completion time and manual recoveries before adding hardware."])
        limitation = ("此工具给出验证路径，不宣称 CYBERBOARD R6 已支持你的应用或设备。AI/R6 命名、软件依赖及具体能力须按当前版本资料核对。" if zh else
                      "This tool proposes a validation workflow. It does not claim CYBERBOARD R6 supports your apps or equipment. Verify naming, version and software dependencies against current documentation.")
        faq = [("有语音输入就能控制全部软件吗？" if zh else "Does voice input imply control of every app?", "不能。转写、命令执行与具体应用集成是不同能力。" if zh else "No. Transcription, command execution and app integrations are separate capabilities."),
               ("R6 能否离线运行？" if zh else "Can R6 run offline?", "需确认具体功能、软件和型号版本；本页没有可验证的离线承诺。" if zh else "Verify the function, software and model version. This page has no verified offline-operation claim.")]
    # Alternatives/facts get a direct-answer draft rather than a fake interactive product claim.
    if intent == "alternatives":
        answer = ("先按能否解决同一个任务比较替代方案，再逐项核对型号、成本、兼容性与限制。这里未编造竞品排名或实时价格。" if zh else
                  "Compare alternatives by the same job to be done, then verify model, cost, compatibility and limitations. No competitor ranking or live price is invented here.")
    if intent == "facts":
        answer = ("先确认具体型号与销售市场。价格和库存以当前商城为准；缺少匹配来源的参数保持待确认，不把家族其他型号的参数移用。" if zh else
                  "Confirm the exact model and sales market. Use the current store for price and availability. Leave unsupported specifications unconfirmed rather than copying another variant.")
    if intent == "how" and mouse:
        answer = ("先确认备用电池已经充好，安排在非对局时更换；更换后检查连接，再为取下的电池补电。备用电池未就绪时，改用型号支持的插线方式或暂停补电。" if zh else
                  "Confirm a charged spare and schedule the swap outside a match. Verify reconnection, then recharge the removed battery. If no spare is ready, use a model-supported cable or pause to recharge.")
        inputs = [("ready", "备用电池状态" if zh else "Spare battery status", [("yes", "已确认充好" if zh else "Confirmed charged"), ("no", "未确认" if zh else "Unconfirmed")]),
                  ("window", "计划更换时机" if zh else "Planned swap window", [("before", "对局 / 工作开始前" if zh else "Before a session"), ("break", "休息时" if zh else "During a break")]),
                  ("fallback", "备用电池不可用时" if zh else "If the spare is unavailable", [("cable", "按说明使用充电线" if zh else "Use a cable if supported"), ("pause", "暂停并补电" if zh else "Pause and recharge")])]
    elif intent == "how":
        answer = ("选一个真实任务，明确语音输入、目标应用和设备控制接口；先用已有软件完成基线，再核对权限、数据去向与失败时的人工接管方式。" if zh else
                  "Choose one real task and identify voice input, the target app and the device-control integration. Establish a baseline with existing software, then verify permissions, data handling and manual recovery.")
    source = PRODUCT if mouse else AI_SOURCE
    h = escape
    controls = "".join(f'<label>{h(label)}<select name="{key}">' + "".join(f'<option value="{v}">{h(t)}</option>' for v, t in options) + '</select></label>' for key, label, options in inputs)
    schema = {"@context": "https://schema.org", "@type": "WebPage", "name": question["prompt"], "url": target_url, "inLanguage": question["locale"], "description": answer}
    tool = intent in {"find", "how"}
    if tool: schema["mainEntity"] = {"@type": "WebApplication", "name": question["page_title"], "applicationCategory": "UtilitiesApplication", "operatingSystem": "Web browser", "description": answer}
    encoded_schema = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
    html = f'''<!doctype html><html lang="{question['locale']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>{h(question['prompt'])} · Angry Miao</title><meta name="description" content="{h(answer, quote=True)}"><link rel="canonical" href="{h(target_url, quote=True)}"><link rel="stylesheet" href="./page.css"><script src="./tool.js" defer></script></head><body><main>
<p class="draft">{'本地草稿 · 待核对与发布' if zh else 'Local draft · review before publishing'}</p><h1>{h(question['prompt'])}</h1><p class="answer">{h(answer)}</p>
{('<form id="tool" data-intent="'+intent+'" data-product="'+question['product_line']+'" data-locale="'+question['locale']+'">'+controls+'<button type="submit">'+('生成我的检查清单' if zh else 'Build my checklist')+'</button></form><section id="result" aria-live="polite"><h2>'+('你的下一步' if zh else 'Your next step')+'</h2><p>'+('选择条件后生成建议。' if zh else 'Choose your conditions to build a checklist.')+'</p></section>') if tool else ''}
<h2>{'操作步骤' if zh else 'Steps'}</h2><ol>{''.join('<li>'+h(s)+'</li>' for s in steps)}</ol>
<h2>{'适用范围与限制' if zh else 'Scope and limitations'}</h2><p>{h(limitation)}</p>
<h2>FAQ</h2>{''.join('<details><summary>'+h(q)+'</summary><p>'+h(a)+'</p></details>' for q,a in faq)}
<h2>{'来源与进一步核对' if zh else 'Sources and further checks'}</h2><p><a href="{source}">{'对应产品公开资料' if zh else 'Model-specific public source'}</a> · {'产品表述并非独立性能测量。' if zh else 'Product statements are not independent performance measurements.'}</p>
<p>{'品牌方向采用用户 2026-11-01 更新。事实库来源采集于 2026-10-29，当前参数与政策需发布前复核。' if zh else 'Brand direction follows the user update of 2026-11-01. The stored facts were captured on 2026-10-29; verify current specs and policies before publishing.'}</p>
<script type="application/ld+json">{encoded_schema}</script></main></body></html>'''
    js = '''"use strict";
const form=document.querySelector("#tool");
if(form)form.addEventListener("submit",event=>{event.preventDefault();const values=Object.fromEntries(new FormData(form)),zh=form.dataset.locale==="zh-CN",items=[];
if(form.dataset.product==="mouse"&&form.dataset.intent==="how"){
 items.push(values.ready==="yes"?(zh?"备用电池已确认有电：按产品说明核对触点、方向与安装。":"A charged spare is confirmed: check contacts, orientation and installation in the manual."):(zh?"先为备用电池补电并确认状态，暂不把它安排进轮换。":"Charge the spare and confirm its state before including it in the rotation."));
 items.push(values.window==="before"?(zh?"在开始前完成更换并验证连接，避免在对局中首次尝试。":"Swap before starting and verify reconnection; avoid the first attempt during a match."):(zh?"在休息时暂停输入，再更换并验证连接。":"Pause input during a break, then swap and verify reconnection."));
 items.push(values.fallback==="cable"?(zh?"备用不可用时，核对型号是否支持插线使用；按说明补电。":"If no spare is ready, verify whether the exact model supports wired use and follow its charging instructions."):(zh?"备用不可用时暂停使用并补电，不假设存在无需补电的无限续航。":"If no spare is ready, pause and recharge; do not assume unlimited operation without charging."));
 items.push(zh?"将取下的电池按正确方式充电，并记录何时可作为下一块备用。":"Recharge the removed battery correctly and record when it is ready as the next spare.");
}else if(form.dataset.product==="mouse"){
 items.push(zh?"按你的握姿实际试握；尺寸或重量不能单独预测舒适度。":"Try the mouse with your grip; dimensions or weight alone do not predict comfort.");
 if(values.cable==="avoid"&&values.spare==="yes")items.push(zh?"优先比较可换电池方案：确认电池兼容、备件供应和接收器补电方式。":"Compare swappable-battery designs: verify compatibility, spare availability and receiver charging.");
 else if(values.cable==="avoid")items.push(zh?"你不希望插线，又不方便维护备用电池；先安排可接受的补电窗口，再选产品。":"You prefer no cable but cannot maintain a spare. Establish an acceptable charging window before choosing hardware.");
 else items.push(zh?"插线可接受：同时比较内置电池方案，避免为不使用的换电能力增加维护。":"A cable is acceptable: include built-in-battery options and compare maintenance needs.");
 items.push(zh?"轮换检查：确认备用电池已充电 → 非对局时更换 → 验证连接恢复 → 为取下的电池补电。":"Rotation check: confirm a charged spare → replace outside a match → verify reconnection → recharge the removed battery.");
}else{
 const task={dictation:zh?"转写准确率与目标文本框输入":"transcription and input into the target text field",apps:zh?"具体应用接口、权限和撤销机制":"the exact app integration, permissions and undo behavior",devices:zh?"设备型号、协议和控制权限":"device models, protocols and control permissions"}[values.need];
 items.push((zh?"先验证：":"Verify first: ")+task+"。");
 items.push(values.cloud==="no"?(zh?"先确定本地处理与数据政策；未确认前不上传工作内容。":"Establish local processing and data policy before sending work content."):(zh?"记录已允许使用的服务与数据范围。":"Record the approved services and data scope."));
 items.push(values.integration==="yes"?(zh?"用同一真实任务比较现有方案与新硬件的完成时间和人工接管次数。":"Compare the same real task with existing tools and proposed hardware, including time and manual recovery."):(zh?"先完成一次端到端演示，再购买硬件；不要把语音能力当作所有设备兼容。":"Complete an end-to-end demonstration before buying hardware; voice capability does not imply universal compatibility."));
}
const out=document.querySelector("#result"),heading=document.createElement("h2"),list=document.createElement("ol");heading.textContent=zh?"你的下一步":"Your next step";items.forEach(value=>{const li=document.createElement("li");li.textContent=value;list.append(li);});out.replaceChildren(heading,list);});
'''
    css = 'body{font:16px/1.8 system-ui;color:#253226;background:#f5f6f0;margin:0}main{max-width:780px;margin:40px auto;padding:30px;background:white;border-radius:18px}h1{font-size:30px;line-height:1.4}h2{font-size:20px;margin-top:32px}.draft{font-size:13px;color:#807a57}.answer{font-size:19px}form{display:grid;gap:16px;background:#eef3e6;padding:24px;border-radius:12px}label{display:grid;gap:7px}select,button{font:inherit;padding:10px;border:1px solid #ccd6c2;border-radius:6px}button{background:#293e27;color:white;cursor:pointer}a{color:#476b35}#result{padding:8px 20px;background:#fafbf6}details{margin:12px 0}@media(max-width:600px){main{margin:10px;padding:20px}h1{font-size:25px}}'
    return {"index.html": html, "tool.js": js, "page.css": css, "schema.json": json.dumps(schema, ensure_ascii=False, indent=2),
            "publish-checklist.md": f"目标：{target_url}\n问题：{question['prompt']}\n\n- [ ] 在本地预览实际操作工具并核对输出\n- [ ] 按型号/市场复核事实、来源和 FAQ\n- [ ] 映射真实站点模板；配置可访问的工具脚本与样式\n- [ ] 发布前移除草稿 noindex 与草稿提示，设置实际 canonical\n- [ ] 加入站内链接和 sitemap，验证 robots/CDN\n- [ ] 在工作台检查线上，再使用原固定 GEO 题组复测\n\n这是本地内容包；不是已应用的网站源码补丁。\n"}
