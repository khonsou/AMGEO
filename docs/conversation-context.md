# 从当前聊天继续 AM SEO

用户希望为 Angry Miao / 怒喵建设中英双市场 SEO/GEO 方案，并要求 Next Step、TODO 和交付由 Agent 执行。2026-10-30 用户进一步授权拉取建议的 GitHub 开源项目，把当前对话升级为 AM SEO 项目。

## 已形成的决策

- 品牌方向是高端游戏鼠标与设计/客制化键盘；不能把普通机械键盘混成 HE/Rapid Trigger，也不能因同店销售就推断 Dry Studio 的正式品牌关系。
- 中英共用产品事实源，价格、渠道、售后、选题和测量按市场分开。
- Agent 负责采集、分析、修订、代码修改、验证和已授权范围内的后台操作。
- 数值冲突只阻塞对应 claim。AM Infinity .97 的有线37g/39g尚未裁决；现有修订不发布争议数值。
- Google/Bing SEO、AI搜索引用、实际订单分开观察；API、自建回答、消费端不能混为一组“排名”。

## 本地已有证据与产物

公开站点观察于2026-10-29：主站部分路径及robots/sitemap返回同一SPA壳；.97同页参数、换电表达、预售日期和占位文案需治理。证据只代表对应请求环境，未验证真实Googlebot、GSC Live Test或多地区WAF。

`outputs/agent-kit/`有11条事实记录、13项可逆的公开HTML离线修改、中英换电稿、48题、校验器和指标计算器。87项本地产物检查通过；任务图的7项completed仅指本地产物完成。

当前工程已拉取7个官方上游并锁定commit。没有安装/运行其全部依赖，没有接入真实网站源代码、Shopify、GSC/GA4或AI消费端会话，没有生产修改或真实GEO基线。

## 当前继续入口

先运行 `./am-seo status`、`./am-seo doctor`、`./am-seo deps verify`、`./am-seo run --offline`。读取 `outputs/agent-kit/tasks.json`，从可运行分支继续。

待接入资源是实际网站仓库、搜索/电商连接、明确的写入范围及真实采样会话或provider。项目仓库本身是研究和执行工作台，不应误认为它就是www.angrymiao.com的源站仓库。

以 `README.md`、`AGENTS.md`、`config/project.json` 与实际命令为准。保留已有用户授权，不反复询问相同范围；也不把项目初始化当作任意生产发布或外联授权。
