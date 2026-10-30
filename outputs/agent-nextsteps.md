# Angry Miao：由 Agent 完成的 Next Step、TODO 与交付

更新：2026-10-30（北京时间）。这是上一版方案的执行改版：抓取、分析、写稿、改代码、测试、后台操作与报告都分配给执行 Agent。缺少连接或原始证据时，只阻塞依赖它的动作，其他任务继续；不把“找开发、找编辑、等运营审核”设为默认流程。

**本轮已经由 Agent 完成 7 个本地产物任务，生成 11 条产品事实记录、13 项可回滚的离线页面修改、中英各一份修订稿，并通过 87 项机器检查。线上网站未改动，真实 GEO 题库尚未调用。**

## 1. 今天可采用的开源执行方案

2026-10-30 北京时间 01:43 只读复核 GitHub API；下列星数为该时点快照。pushed_at 含分支活动，不等于默认分支的实质功能更新；结合 10 月 29 日保留的提交与源码核查判断能力，不以星数推断 SEO 效果。

### 首选：现有 Agent 执行；独立部署选 OpenHands SDK

**[OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk)**：MIT，1,319 stars，最近 push 为北京时间 10 月 30 日。它提供带文件编辑、终端和任务跟踪工具的 coding agent，可读仓库、修改代码、运行验证、迭代修复；支持本地或隔离工作区。当前主仓库 OpenHands/OpenHands 是上层界面，真正的执行组件应看 SDK。模型与基础设施另计费。本轮使用当前会话的 Agent 已完成本地交付，没有安装或启动 OpenHands 服务。

**[github/gh-aw](https://github.com/github/gh-aw)**：MIT，5,519 stars，最近 push 为北京时间 10 月 30 日。适合网站源码在 GitHub 的情况，把任务说明编译为 Actions 工作流，调用 coding engine，并通过 safe outputs 创建 PR 等产物。自动构建与确定性测试继续由普通 CI 执行。[工作流说明](https://github.github.com/gh-aw/introduction/how-they-work/)、[PR 输出能力](https://github.github.com/gh-aw/reference/safe-outputs-pull-requests/)。需要实际仓库、引擎认证及 Actions 配置；不是装上就拥有源站写权限。

两种运行方式二选一：已有仓库与 CI 优先 gh-aw；独立服务用 OpenHands SDK。当前单轮执行可直接沿用现有 Agent，无需先搭一个新平台。

### 给执行 Agent 接上实际工具

- **采集**：[Crawl4AI](https://github.com/unclecode/crawl4ai) 获取原始 HTML、浏览器正文与商品字段；[marketingskills](https://github.com/coreyhaines31/marketingskills)提供 SEO / 内容任务方法。这两者沿用上一轮核验，不冒称本轮重新安装运行。
- **搜索数据与审计**：[houtini-ai/seo-audit](https://github.com/houtini-ai/seo-audit)，Apache-2.0，86 stars，最近 push 10 月 26 日；结合 GSC 与抓取数据输出审计和修复资料。源码核查显示 `fix_finding` 生成 remediation artifact，后续需 coding agent 把它落实为实际代码和测试。小型项目，接入前固定版本并验证；不把它描述为高热度或已验证商业效果的系统。
- **轻量 GSC 连接**：[saurabhsharma2u/search-console-mcp](https://github.com/saurabhsharma2u/search-console-mcp)，MIT，315 stars，最近 push 10 月 21 日，可作为 GSC 数据连接备选；接入工具与 property 授权必须实际验证。
- **站点分析**：[googleanalytics/google-analytics-mcp](https://github.com/googleanalytics/google-analytics-mcp)，Google 官方仓库，Apache-2.0，3,590 stars，最近 push 为北京时间 10 月 30 日。由数据 Agent 直接读已授权 GA 数据，替代要求人导出表格；账户权限仍是必要输入。
- **后台与消费端操作**：[browser-use/browser-use](https://github.com/browser-use/browser-use)，MIT，119,475 stars，最近 push 10 月 27 日；用于已授权会话中的后台读取、报表下载和问答采样。[microsoft/playwright](https://github.com/microsoft/playwright)，Apache-2.0，98,813 stars，最近 push 为北京时间 10 月 30 日；用于 DOM / 网络断言、截图、回归和证据。当前已有可用浏览器工具时直接使用，不重复安装。账号会话不是开源库能凭空提供的资源。
- **GEO 评估**：[promptfoo](https://github.com/promptfoo/promptfoo)连接真实联网 provider；本次另交付零依赖结果计算脚本，消费端、API 回答与纯检索分组统计。没有真实调用时输出 `not_run`，不填一组零分冒充基线。
- **复杂编排备选**：[LangGraph](https://github.com/langchain-ai/langgraph)，MIT，44,106 stars，最近 push 为北京时间 10 月 30 日。仅在需要持久状态、分支与恢复时增加；它需要接入执行工具，不会自己读取后台或修改源站。

执行框架开源不等于模型、联网搜索、代理和托管浏览器免费。`citeworthyio/seo-agent` 当前只有 54 stars，上轮核验最近 push 为 8 月；未列入高活跃核心。专用 GEO 工具仍按真实联网与引用结果验收。

## 2. Next Step：输入、动作、自动验收、产物

### 第一步：采集 / 事实 / 实体 Agent 并行执行

输入：公开页面、已有 HTTP 快照、说明书与可读商品资料。

Agent 自动生成抓取异常、型号与 URL 映射、逐字段事实账本和冲突。数值、单位、型号、硬件版本与证据定位一起保存。37g / 39g 无法自动裁决时只冻结该字段；本次稿件已省略争议重量和未确认时长，其余可证实内容继续生成。

交付：`routing-audit.json`、`entity-url-map.json`、`product-facts.json`。本轮已完成；HTTP 原始观察来自 10 月 29 日，本轮为证据重放，未伪装成 10 月 30 日重新抓站。

### 第二步：内容 / Patch Agent 直接写成可应用修改

输入：事实账本、目标页原文及当前内容。

Agent 产出中英换电说明，移除“换电即充满”的误导表述；去掉没有当前依据的无年份预售说明，改用已观察到的政策入口；替换主题占位句。每个修改携带源文本 hash、定位、替换内容和回滚方法。

交付：`battery-mechanism.en.md`、`battery-mechanism.zh-CN.md`、`am-infinity-97.operations.json`。本轮已完成 13 项精确修改指令。它们针对抓取时的公开 HTML，不是网站源码 patch，也不是已经映射到 Shopify Admin 的 mutation。

### 第三步：QA Agent 执行机器门禁与失败重试

自动验证原文 SHA256、事实片段、修改不重叠、证据 ID、完整离线应用、逆向回滚、禁用未确认数字、题库分组和任务输出。失败只回退对应修改并重跑；不会输出“请编辑检查全文”作为完成结果。

交付：`validate_batch.py`、`qa-results.json`。本轮 87 项通过，完整回滚与原始字节一致。检查范围是离线产物完整性与来源定位；不代表独立硬件实测、线上 SEO 成效或 Google 富结果认证。

### 第四步：工程 / 数据 / 发布 Agent 在连接就绪后执行

网站源码接入后，工程 Agent 定位真实 SPA / 静态文件规则，改路由、构建、跑页面回归并提交实际补丁；不能在没有仓库时猜一份 nginx 配置冒充修复。

GSC / GA4 / 百度 / Bing 接入后，数据 Agent 自动读取基线、property 设置与索引状态。GSC URL Inspection API 查询的是索引版本，Live Test 由已授权浏览器操作，结果分开保存。[GSC API](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)、[Live Test](https://support.google.com/webmasters/answer/9012289)。

发布 Agent 根据允许范围写入 CMS、PR 或生产，读取当前版本并防止覆盖新修改；写后验收，失败回滚。已有商品的 `productUpdate` 直接影响商品，不可把商品改成 DRAFT 来暂存内容修订；主题修改也有独立权限条件。[Shopify productUpdate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/productUpdate)、[themeFilesUpsert](https://shopify.dev/docs/api/admin-graphql/latest/mutations/themeFilesUpsert)。

交付终点必须是实际 `routing-fix.patch`、构建 / 回归记录、PR URL 或 CMS 对象 ID、发布与回滚记录。当前尚未接入这些资源，因此不声称源站已经修好或已经发布。

### 第五步：浏览器 / 评估 / 分析 Agent 完成测量闭环

有授权会话后，浏览器 Agent 运行固定消费端面板并保存答案、引用和截图；API Agent 运行联网 provider，分别存档；分析 Agent 自动计算提及、引用、适配推荐与事实错误，再决定下一轮修改。

交付：真实 `observations.jsonl`、`geo-metrics.json`、`weekly-report.html`、`next-batch.json`。没有会话或 API 时只交付运行契约与计算器，不生成假答案。四至六周成效需要真实时间与数据，不能靠 Agent 现在编出来。

## 3. TODO 已改为机器任务图

`agent-kit/tasks.json` 包含 13 个任务，每项都有 Agent、依赖、输入、输出与验收条件。

- **7 项 completed**：能力记录、路由证据、事实提取、实体映射、双语修订、离线修改、QA。这里 completed 指本地产物完成。
- **4 项 waiting_access**：源码修复、后台基线、真实 AI 采样、线上发布。阻塞项是对应连接与动作范围。
- **1 项 waiting_data**：上线后的效果分析，等待真实观测。
- **1 项 blocked_claim**：有争议数值的权威来源或物理数据，只影响相应断言。

Agent 从可运行任务开始，完成后更新状态；遇到短暂失败最多重试三次，保存证据并继续独立任务。未确认信息不填 0，不按模型置信度“投票”解决。

## 4. 实际交付 Output

执行包位于 `agent-kit/`，其中：

1. `RUN-AGENT.md`：给执行 Agent 的入口任务；读取 manifest 后继续执行。
2. `tasks.json` / `capabilities.json`：任务状态与当前会话可用能力。
3. `product-facts.json`：11 条有定位证据的事实及冲突记录。
4. `battery-mechanism.en.md` / `battery-mechanism.zh-CN.md`：已生成的中英修订稿。
5. `am-infinity-97.operations.json`：13 项离线修改与回滚；源内容变化即需重新生成。
6. `validate_batch.py` / `qa-results.json`：可重复执行的 87 项校验及本次结果。
7. `query-seeds.json` / `geo-run-plan.json`：48 题与浏览器 / API 运行契约。
8. `score_observations.py`：对真实采样计算指标；UI、API、纯检索分别统计，无 AI 回答计零，网络错误单报。
9. `routing-audit.json` / `route-repair-task.json` / `release-manifest.json`：技术证据、待接入的工程任务和未发布状态。
10. `open-source-snapshot.json`：今天复核的 8 个仓库元数据。`evidence/` 的公开 HTML 以 `.txt` 保存用于重放，不作为网页执行。

执行包不含密钥、登录 cookies 或用户订单资料；没有安装后台服务、创建定期自动化、联系第三方或修改线上站点。

## 5. 剩余依赖只需接入一次

需要的输入是：正确的网站仓库 / 部署连接、目标搜索与商城账号的可用连接、允许的目标字段及写入范围、真实 AI 采样会话或 provider 额度。由 Agent 通过 API / 浏览器读取和处理，免去人手动导出、整理、改稿与逐页测试。

发布授权若已在后续会话明确给出，Agent 在范围内连续执行，不再默认每篇等人审核。缺少权威产品数值时，先省略该断言；必须发布该数值才需要原始资料或可控制的真实测试设备。

本轮完成的是“开源组件选型 + 实际本地产物执行 + 可机器验收的接续任务”，尚未部署一个无人值守的线上服务。
