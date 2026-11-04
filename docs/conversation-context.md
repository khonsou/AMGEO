# 从当前聊天继续 AM SEO

用户希望为 Angry Miao / 怒喵建设中英双市场 SEO/GEO 方案，并要求 Next Step、TODO 和交付由 Agent 执行。2026-10-30 用户进一步授权拉取建议的 GitHub 开源项目，把当前对话升级为 AM SEO 项目。

## 已形成的决策

- 2026-11-01 用户明确修正当前品牌核心：电竞鼠标 AM Infinity Mouse 与 AI device（如 CYBERBOARD R6）。这一方向优先于旧品牌资料中的“机械键盘为核心”。物理形态、历史品类与当前战略分开；具体 AI 功能仍须匹配型号与版本证据。不能因同店销售就推断 Dry Studio 的正式品牌关系。
- 中英共用产品事实源，价格、渠道、售后、选题和测量按市场分开。
- Agent 负责采集、分析、修订、代码修改、验证和已授权范围内的后台操作。
- 数值冲突只阻塞对应 claim。AM Infinity .97 的有线37g/39g尚未裁决；现有修订不发布争议数值。
- Google/Bing SEO、AI搜索引用、实际订单分开观察；API、自建回答、消费端不能混为一组“排名”。

## 本地已有证据与产物

公开站点观察于2026-10-29：主站部分路径及robots/sitemap返回同一SPA壳；.97同页参数、换电表达、预售日期和占位文案需治理。证据只代表对应请求环境，未验证真实Googlebot、GSC Live Test或多地区WAF。

`outputs/agent-kit/`有11条事实记录、13项可逆的公开HTML离线修改、中英换电稿、48题、校验器和指标计算器。87项本地产物检查通过；任务图的7项completed仅指本地产物完成。

当前工程已拉取7个官方上游并锁定commit。没有安装/运行其全部依赖，没有接入真实网站源代码、Shopify、GSC/GA4或AI消费端会话，没有生产修改或真实GEO基线。

## 当前继续入口

2026-10-31 用户明确要求以可执行循环为产品入口：分析按钮 → 动态任务（Agent / 人类）→ 执行与验收 → 分开评估 SEO / GEO → 版本化策略经验 → 再分析。网页不再以文档目录或仅记录待执行请求作为主流程。

已实现本机浏览器工作流，运行记录在 `outputs/runtime/console/workflow/state.json`，任务产物、来源轨迹、观测和策略历史在对应轮次目录。继续时先读取此记录，不要把旧 A00–A12 列表当作全部当前任务。`./am-seo status` 同时展示动态轮次摘要与初始产物任务。

执行器为本机已登录的 Codex CLI，分析与写稿读取锁定的 marketingskills 方法参考；其余 vendor 项目尚不能声称已投入执行。只读的模型子进程返回结构化正文，由服务实际保存到任务目录；不能再将模型本身不能写文件误判为本地任务缺少产物保存能力。

评分口径见 `docs/measurement.md`：搜索表现待真实平台数据；原始 HTML 技术诊断单列；GEO 固定小题组的独立 Agent/API 试运行与消费端区分。没有观测则 null，不造零分；策略候选更新不是效果提升结论。

先运行 `./am-seo status`、`./am-seo doctor`、`./am-seo deps verify`、`./am-seo run --offline`。读取当前动态轮次与 `outputs/agent-kit/tasks.json`，从可运行分支继续。

待接入资源是实际网站仓库、搜索/电商连接、明确的写入范围及真实采样会话或provider。项目仓库本身是研究和执行工作台，不应误认为它就是www.angrymiao.com的源站仓库。

以 `README.md`、`AGENTS.md`、`config/project.json` 与实际命令为准。保留已有用户授权，不反复询问相同范围；也不把项目初始化当作任意生产发布或外联授权。

## 2026-11-01 品牌与 TA 更新

用户指定 CyberboardR6MarketingPlan/am-marketing-planner/references 为品牌与 TA 资料来源。五份 Markdown 固定至 4396097272fe7d7455baf85404e594f98d22efb9，原文与哈希保存在 outputs/brand-context/，采纳解释在 config/brand-context.json。三类 TA 与 Future Art Community 用作策划基础，不冒充消费者实测；最新用户方向优先。每轮冻结资料快照，旧轮不追认为已使用新版。独立 GEO 评估不注入品牌/TA资料，原48题与固定协议保持独立。
