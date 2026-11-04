# 控制台维护

人的入口是 [AM SEO 优化循环](http://127.0.0.1:8787/)，完整流程见 [使用指南](usage.md)。

## 启动

在工程根目录运行 `./am-seo serve`，默认只监听 `127.0.0.1:8787`。可用 `--port` 更改端口，不支持公网绑定。服务停止或电脑重启后需要恢复；没有安装登录启动项。

## 运行结构

- `workflow.py`：轮次、任务、执行、核验、评估与策略版本。调用已安装的 Codex CLI，使用 `--search`、只读 sandbox、结构化输出和固定超时；不安装或运行 vendor 代码。
- `measurement.py`：公开 HTML 诊断和独立中英 API 答案试运行面板。固定问题、模型与口径；不把检索结果当消费端回答，不合成跨语言分数。
- `server.py`：loopback、Host/Origin/会话令牌保护的本机 API。
- `web/`：浏览器操作界面；用户无需编辑 JSON 或复制全文。

`POST /api/workflow` 支持 analyze、execute、verify、evaluate、improve、next-cycle、run-cycle、handoff、review、technical-check、local-review、retry-runtime。普通文本仅作为限定范围内的任务数据，不拼接为 shell。`run-cycle` 可按顺序执行一批已支持动作，不是无限循环。

生成产物正文通过 `/api/workflow/artifacts/<cycle>/<task>/<index>` 按已记录 ID 和 SHA256 读取。禁止任意文件路径。旧交付物仍按静态白名单读取为文本，不执行采集的 HTML。

## 数据与恢复

轮次和策略保存在被 Git 忽略的 `outputs/runtime/console/workflow/`，包含 state、来源轨迹、任务产物、评分样本和策略历史。进程重启时将未确认的活动轮次标记中断，不假定旧任务完成。

同一服务实例最多一个活动工作流；每批最多执行 3 个 Agent 任务。每次模型调用有超时；不同额度或网络失败会保留错误。不读取、复制或保存登录凭证。Codex 使用现有登录态，消耗该账号可用额度；额度问题不通过切换账号、模型或 API 计费通道绕过。

服务只准备公开研究和本地产物。实际站点源代码、CMS、搜索账号及发布范围仍须按任务接入；Agent 核验、人工提交或勾选验收不创建新的账号访问权限，也不证明生产写入或业务效果。

## 验证

```bash
python3 -m unittest discover -s tests -v
./am-seo run --offline
node --check src/am_seo/web/app.js
```

测试使用临时项目和注入运行器，不能用模拟样本作为项目基线。API 测试需要本机临时端口权限。实际流程另通过浏览器验收并保留来源与执行证据。评分口径见 [测量说明](measurement.md)，底层旧 CLI 见 [高级参考](agent-cli.md)。

## 故障隔离

已记录的模型额度/认证硬失败保存在 runtime_block，阻塞模型动作，但不阻塞本地规则复盘、人工核验、资料检查和独立公开 HTML 诊断。连接恢复需要用户明确触发一次健康检查，不自动轮询或换模型。失败历史与已有采样保留。local-review 仅根据实际记录生成有来源的过程候选，同一证据不重复增加版本；它不是模型复盘或效果证明。

技术解析 v1.1 只读取文档标题，排除 SVG 图标的可访问性标题。新技术检查使用新采集时间和版本，旧评估与 GEO 原始时间仍保留。

当前聊天 Agent 也可经 `submit-result` 写回已授权且前置任务已验收的 Agent 任务。接口校验原任务条件、逐项检查、正文和来源，保存真实文件与哈希后进入待核验；提交不会直接完成任务，也不扩展任何外部访问权限。这个通道供 Agent 使用，不要求日常用户编辑 JSON 或复制文档。
