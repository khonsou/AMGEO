"use strict";
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
