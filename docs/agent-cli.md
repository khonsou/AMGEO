# Agent 与维护者操作参考

本文面向执行 Agent 与维护者。人的日常入口是浏览器控制台，见 [使用指南](usage.md)。以下保留底层任务指令、CLI、观测格式及接入细节；持续监控与线上优化仍取决于真实执行连接。

## 1. 第一次使用

本地需要 Python 3.11+ 和 Git。已有目录可直接运行，不必先安装全部上游组件或购买模型调用。

```bash
cd /Users/linan/Desktop/AMSEO
./am-seo status
./am-seo doctor
./am-seo deps verify
./am-seo run --offline
```

这四步分别回答：当前有哪些任务；本地运行条件与连接声明是什么；7个上游是否与锁定版本一致；已有证据与离线修改能否通过验收。

成功的离线运行会刷新：

- [`outputs/agent-kit/qa-results.json`](../outputs/agent-kit/qa-results.json)：实际检查、通过情况、原文匹配和回滚结果。
- [`outputs/project-status.json`](../outputs/project-status.json)：本轮离线状态、任务统计与执行范围。

`status` 和 `doctor` 本身只输出信息。`doctor` 不读取密钥值，也不实际验证后台登录；`pending` 不是所有任务都失败。`run --offline` 需要明确传入 `--offline`，不会自动发出真实 AI 请求或修改网站。

从另一个工程副本恢复时，`vendor/` 可能因被 Git 忽略而缺失。可在具有网络访问的环境运行：

```bash
python3 scripts/sync_upstreams.py sync
./am-seo deps verify
```

这会拉取锁定源码，保留许可证；不会安装依赖或启动其服务，也不会重置已有脏仓库。若 `./am-seo` 因执行权限不能启动，可使用 `python3 am-seo`。

## 2. 让 Agent 开始一轮工作

在当前项目聊天中直接描述目标。下面是可复制的任务指令，不是终端命令。

### 运行一轮品牌监测与优化

> 为 Angry Miao 执行一轮中英 SEO/GEO 工作。读取 AGENTS.md、README、事实库和任务图，检查本轮可用工具与连接。先采样真实选购需求并追踪引用来源，按搜索与AI回答、第三方评测/视频/社区、商品渠道、自有资料组织发现。完成有证据、有权限的改进并验证，保存本轮原始来源、产物与结果；只阻塞缺少必要输入的分支，不把旧快照当作新观测。

没有采集工具、登录会话或provider时，Agent应明确记录未运行的观测，继续已有资料核验、内容准备和其他可执行任务。不能把离线题库、自建回答或搜索候选列表写成消费端基线。

### 继续未完成任务

> 继续当前任务图。先核对真实状态和依赖，完成可运行分支；有新连接或反馈就恢复相应任务。每项交付附来源、版本、验收和范围，汇总本轮完成、失败、等待输入的事项及产物路径。

任务状态在 [`tasks.json`](../outputs/agent-kit/tasks.json)。已有的 `completed` 指对应本地产物完成，不表示网站已上线或业务效果已经验证；`waiting_access`、`waiting_data`、`blocked_claim` 分别表示缺连接、缺观测或局部事实冲突。

### 查看结果与下一轮决策

> 汇总本轮真实观测与执行结果，区分已验证事实、优化假设和未测量事项。解释哪些改动值得保留、回滚或继续试验，保留失败记录和归因限制，并生成下一轮可执行任务。

Agent应给出实际存在的文件和证据。尚无真实数据时，输出准备情况与缺口，不编造趋势、提升比例或未来收入。

## 3. 任务开始前提供什么

Angry Miao 的初始上下文已保存在 [品牌配置](../config/project.json)、[事实库](../outputs/agent-kit/product-facts.json)、[题库](../outputs/agent-kit/query-seeds.json) 与 [项目决策](conversation-context.md)。每轮只需补充变化的目标、市场、产品、资料和允许的动作范围。

不同任务按需接入资源，不必一次把所有账号都配置好：

- **公开研究**：提供可访问的页面、评测、视频/图文或原始资料；Agent使用当前实际可用的采集工具。
- **真实AI采样**：提供允许使用的消费端会话，或已配置的联网provider及调用额度；UI、API回答和纯检索分别存档。
- **搜索与转化分析**：连接对应GSC、百度、Bing、分析或电商数据源，明确目标站点、市场、时间与业务口径；已有导出也可作为输入。
- **源站或CMS修改**：接入真实网站仓库或可编辑对象，说明可修改范围；Agent先定位实际结构和当前版本，再生成、应用与验证修改。
- **硬件与政策事实**：提供对应型号/版本的原始记录、测量或有效政策；无法确认的数字只冻结相应断言。

凭证通过运行环境或连接管理提供，不放进README、普通输出文件或聊天正文。项目中的 `.env.example` 仅预留配置名称；当前CLI不会读取它来自动连接后台或启动模型。

当前实现以Angry Miao为实例，部分品牌名、官方域名判定、事实、题库和任务仍固定于该实例。切换品牌时，让Agent同步适配这些内容并验证；仅修改 `config/project.json` 不能完成全项目品牌切换。

## 4. 导入真实观测并计算GEO指标

### 准备输入

由采集Agent把真实结果写成UTF-8 JSONL，每行一个JSON对象，例如 `outputs/observations/<批次>/observations.jsonl`。原始回答、provider响应或截图证据应另存并可追溯，避免把账号和客户资料混入结果。

每条记录必需的身份字段是：`run_id`、`query_id`、`surface`、`platform`、`locale`、`mode`、`status`。重复运行使用不同的 `run_id`，保留题库中的 `query_id`。

- `surface`：`consumer`（消费端）、`api_answer`（API回答）或 `search_retrieval`（纯检索）。
- `status`：`completed`（完成）、`no_ai_answer`（测试完成但无AI回答）或 `error`（请求失败）。
- 完成的回答还需要非空 `answer_text`、布尔值 `brand_mentioned` / `suitable_recommendation`，以及实际最终回答引用的URL数组 `citations`。
- 每条实际采样还应记录 `captured_at`、具体模式与证据位置。当前计算器未强制校验这些追溯字段，由采集Agent保证完整。

下面**仅演示结构，不是真实观测**。原文、标签、时间和引用必须由采集与核验Agent按实际结果填写，不能直接将示例写入正式基线。

```json
{
  "run_id": "EXAMPLE_ONLY_REPLACE_WITH_REAL_RUN",
  "query_id": "EN-M-01",
  "surface": "consumer",
  "platform": "ChatGPT Search",
  "locale": "en-US",
  "mode": "web-search",
  "status": "completed",
  "captured_at": "替换为实际采集时间",
  "answer_text": "替换为未经改写的实际回答原文",
  "brand_mentioned": false,
  "suitable_recommendation": false,
  "citations": []
}
```

这是便于阅读的单条对象展示；实际JSONL需将每个对象写在独立一行。`no_ai_answer` 和 `error` 仍须保留身份字段，但不要求填写不存在的回答原文或标签。

可选 `fact_checks` 是逐条事实核验结果：`verdict` 为 `supported` 或 `incorrect` 的断言进入事实正确率分母，其他状态单列为未决。没有已判定断言时，正确率为 `null`。这些判断由核验Agent依据来源完成，计算器不会自动判断推荐适配性或事实真伪。

### 运行计算

将下例路径替换为已有的真实批次文件：

```bash
./am-seo score outputs/observations/2026-10-30/observations.jsonl outputs/observations/2026-10-30/geo-metrics.json
```

所有相对路径按项目根解析，即使从其他目录调用也一样；也接受绝对路径。显式指定每批输出可保留历史结果。省略输出参数时，默认写入并覆盖 `outputs/geo-metrics.json`；已有的同名结果文件也会被覆盖，但不允许用输入文件本身作为输出。

### 阅读结果

- 按 `surface / platform / locale / mode` 分组，消费端、API与检索数据不合并。
- 无AI回答按零计入成功测试分母；网络等错误排除并单报失败率。
- 空输入是 `not_run`，不是一组品牌表现为零的测量。
- 提及、官网引用、适配推荐与事实正确性分别解释。纯检索只标记检索范围，不当成答案引用。

当前计算器只识别预设官方域名的引用率，没有完整的第三方品牌证据质量或全渠道商业归因评分；这些由Agent保留来源、另行分析，不能把官网引用率作为总成绩。

## 5. 与团队交接并接回执行

直接给Agent具体的交接目标，例如：

> 将需要团队执行的这项工作整理为任务包：给出目标、已完成分析、原始证据、可直接使用的内容/修改/实验协议、待决定事项、验收条件和Agent恢复位置。保留任务ID，交接不等于完成。

当前可约定保存在 `outputs/handoffs/<任务ID>/`，由Agent生成实际文件；这只是文件组织约定，没有专用 `handoff` 命令或团队系统自动同步。

团队回传文档、测量、决定或修改结果后，将文件提供给当前项目Agent，例如：

> 读取 outputs/team-feedback/<任务ID>.md 中的团队反馈，核对来源与适用范围，更新事实或决策记录；完成必要验证后恢复该任务，汇总本轮新增产物和状态。

Agent应将反馈关联回同一任务，保留分歧、版本和验证结果；不能把“收到反馈”直接当成事实已验证或任务已完成。Issue、PR或团队工作系统的双向同步尚需连接适配。

## 6. 怎样使用持续监控与自我优化

当前主要从浏览器启动分析、动态任务执行、评估、策略复盘与下一轮；具体使用见 [使用指南](usage.md)。聊天也可以读取同一轮次记录接续工作。尚无持续调度、自动线上发布或执行器代码经评估后自主晋升的服务。

需要检验某个优化方法时，可要求：

> 为这次改动建立试验记录，锁定问题面板、基线、主要假设与验收口径，保存策略和执行版本；真实数据到齐后比较结果，报告失败与不确定性，再提出保留、回滚或下一轮修改。

Agent可以准备方案与可用执行材料；实际采样、发布、观测和定期运行仍按本轮可用连接及授权推进。不要把CLI中的 `run --offline` 当作启动自主监控的开关。

## 7. 命令与常见问题

当前命令可用 `./am-seo --help` 查看，包含：

```bash
./am-seo --version
./am-seo serve
./am-seo status --json
./am-seo doctor --json
./am-seo validate
./am-seo score INPUT.jsonl OUTPUT.json
./am-seo run --offline
./am-seo deps verify
python3 scripts/sync_upstreams.py verify --json
```

- **`doctor` 有pending但退出成功**：表示本地工作台仍能使用，指定上游或线上连接尚需接入；它不证明账号认证有效。
- **上游核验失败**：让Agent检查缺失、版本差异或工作区改动。缺失checkout可按锁文件恢复；已有改动先保留，不能为了过检而删除或强制重置。
- **`score` 报错**：检查输入是否存在、JSONL是否每行合法、字段/枚举是否正确、运行身份是否重复、输入与输出是否同一路径。失败以非零退出码返回。
- **希望自动发布或定期运行**：当前没有 `init`、`monitor`、`optimize`、`schedule`、`publish` 或 `handoff` 子命令；应作为具体接入/实现任务交给Agent，不能靠填一个环境变量宣称已经启用。

查看本轮产物时，以任务验收及实际文件为准。[交互阅读版](../outputs/angrymiao-seo-geo-plan.html)是静态研究页面，不会自动刷新成实时监控看板。
