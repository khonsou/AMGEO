# Angry Miao：用 Agent 执行中英双市场 SEO / GEO

公开站点研究日期：2026 年 10 月 29 日；Agent 执行改版与新增开源组件复核：2026 年 10 月 30 日，Asia/Shanghai。适用范围：Angry Miao / 怒喵的品牌站、海外商店、中文商城及支持内容。英文先以美国作为试点地区假设，实际国家优先级应由订单与搜索数据决定；中文以中国大陆为起点。

**2026-10-30 更新：Next Step、TODO 与交付现由 Agent 执行。已完成 11 条事实记录、13 项离线修改、双语换电修订及 87 项验证；详见 [Agent 执行方案](agent-nextsteps.md) 与 [执行包入口](agent-kit/RUN-AGENT.md)。未接入源站、后台和真实 AI 采样，线上未改动。**

**建议：先用 30 天跑通“抓取与事实治理 → 原创证据内容 → 小批发布 → 双市场测量”的闭环，再决定扩展规模。** Agent 的主要价值是发现问题、交叉核对产品事实、准备修改和持续评估。内容数量、开源星数和工具的 GEO 自评分均不能代表销量或真实 AI 引用效果。

本研究已完成公开网页核查、低频 HTTP 请求及开源项目核验；未获取 GSC、百度搜索资源平台、Bing Webmaster Tools、GA4、商城后台、日志和真实 AI 问答基线。因此下面的优先级是研究判断，业务收益、关键词搜索量和当前 AI 可见度均未测得。所有路线图数量属于建议产能，不是增长预测。

## 1. 对 Angry Miao 的判断：先解决事实与交付，再扩大内容

品牌有两条适合分别承接的需求：鼠标的竞技性能、形状与换电体验；键盘的设计、结构、声音与客制化。商店同时展示 Dry Studio 产品，需保留真实 vendor 及正式品牌关系。不能把所有机械键盘写成磁轴、Rapid Trigger 或同一品牌系列。可从[键盘类目](https://store.angrymiao.com/collections/keyboard)、[AM RGB 65](https://store.angrymiao.com/products/am-rgb-65)及[Dry Studio HE 商品](https://store.angrymiao.com/products/dry-studio-battleye-75-he-r2)核对实体。

### P0-A：主站的爬取入口与初始 HTML 需要优先复验

公开请求中，[首页](https://www.angrymiao.com/)、[英文首页](https://www.angrymiao.com/en/)、[英文产品目录](https://www.angrymiao.com/en/products/)、[robots.txt](https://www.angrymiao.com/robots.txt)与[sitemap.xml](https://www.angrymiao.com/sitemap.xml)均返回 HTTP 200 的同一份 HTML 应用壳。后两项没有交付预期的纯文本 / XML；初始 HTML 的 lang 为空，未发现页面独有的 canonical、hreflang 或产品结构化数据。

2026-10-29 北京时间 18:43 的轻量复核，对四个关键路径分别采用默认 UA 与 Googlebot 字符串，共 8 次请求，均为 14,570 bytes，SHA256 相同：`45e034e5fcdbfdd0cfa47d8d91f1a86a25a35c44c2c05ea6271031d8e76f85cc`。这是本次请求环境下可复现的交付问题；UA 字符串不是经过验证的真实 Googlebot，尚未排除 CDN、地区、WAF 配置差异。

**行动：**工程 Agent 接入真实仓库后自动定位并核对静态文件路由是否被 SPA fallback 吞掉；再用 GSC Live URL Inspection、渲染 DOM 与服务器日志复验核心产品页。必要时采用 SSR / SSG / 稳定预渲染，交付正文、内链及页面独有元数据，用户与爬虫看到一致内容。Google 可以处理 JavaScript，当前证据不足以断言“全站无法收录”。[Google JS SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)、[robots 规范](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt)、[站点地图规范](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)。

**验收：**robots 为可解析纯文本，sitemap 为有效站图且列出真实规范 URL；抽样重点页面初始 HTML 有独立标题、H1、正文、链接和准确语言；完成真实搜索工具的抓取 / 渲染复核。验收这些技术条件不等于保证索引。

### P0-B：.97 商品页有具体的事实与交易说明冲突

[AM Infinity .97 商品页](https://store.angrymiao.com/products/am-infinity-97-wireless-gaming-mouse)营销区域写有线 37g，Specifications 写 39g；同时存在把换电描述成“1.2 秒充满”的表达。事实 Agent 自动检索匹配型号的权威资料，无法裁决则省略争议重量字段并继续修订其他内容；不可自行选一个数，更不可把 USB 回报间隔当端到端延迟。

同页 Shipping Policy 还包含预售、KS 和从 May 分批发货的无年份表述；商业信息 Agent 读取当前市场政策与履约数据验证适用性；无可信数据时仅移除具体时效承诺并链接已观察到的有效政策入口。Need help 的四项说明保留主题占位句。应改为真实、按市场与 SKU 生效的发货、客服及购买说明。页面源码同时包含 Add to cart / Sold Out 模板，不能据此判断真实库存。

**验收：**同一型号的每项参数只有一个经过批准的口径，所有测试条件和日期完整；页面、schema、商品 feed 与后台的价格 / 变体 / 库存同步；占位文本清零。当前正确重量和实时库存不由本报告推断。

### P1：保留已有基础，做一致性检查和内容整合

海外商店的 [robots](https://store.angrymiao.com/robots.txt) 与 [sitemap](https://store.angrymiao.com/sitemap.xml)正常交付；.97 的 collection 上下文路径已有指向 `/products/` 的 canonical，原始 HTML 已有 ProductGroup、变体、Offer 与评论数据。优先验证语义、数据同步和重复实体，配合 Rich Results Test，不能把建议写成“从零添加 schema”。[Google 商品变体规范](https://developers.google.com/search/docs/appearance/structured-data/product-variants)。

商店已有相邻意图的[鼠标榜单一](https://store.angrymiao.com/blogs/insider-stories/best-fps-gaming-mouse)、[鼠标榜单二](https://store.angrymiao.com/blogs/insider-stories/best-gaming-mouse-recommendations)及[键盘选购内容](https://store.angrymiao.com/blogs/insider-stories/best-gaming-keyboard-for-every-player)。先看 GSC 的 query → page，确定更新、合并与内链分工；标题相似只是复核线索，不能单凭标题认定严重流量内耗。

中文侧还包括 [mall 商品页](https://mall.angrymiao.com/products/1313) 与 [m 移动商品页](https://m.angrymiao.com/products/1536)。前者公开抽取仍可见 2023 年发货说明，后者有售罄 / 参考价说明。它们是生命周期治理候选；尚未确认当前交易入口以及 mall / m 的重复关系，不能直接决定下线或重定向。

## 2. SEO 与 GEO 的实践边界

SEO 解决搜索发现、索引与高意图到站；GEO 在此基础上关注回答中的提及、引用、推荐和事实准确性。两者共同依赖可靠资料与可访问页面。Google 官方明确，AI 搜索仍遵循 SEO 基础，没有专用的 GEO schema；llms.txt 不影响 Google 搜索可见度。[Google AI 优化指南](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)。

适合 Angry Miao 的最佳实践是：把原创测试、设计解释、版本区别、适配边界和售后事实做成可持续维护的资料；用清晰的标题、对比与图示帮助用户选择。结论段或 FAQ 可以提高阅读效率，但不存在“固定字数答案块必然被 AI 引用”的保证。

避免把同一文章改写成几百个手型、游戏名、价格词页面。Google 的 scaled content abuse 政策针对主要为操纵排名而大量生产、缺乏增量价值的内容；AI 辅助内容及元数据也需发布前核验。[Spam policies](https://developers.google.com/search/docs/essentials/spam-policies)、[使用生成式 AI 内容](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)。

需要纠正三类常见旧建议：

- Google FAQ 富结果已于 2026-05-07 停止展示；保留真实 FAQ 是为了用户与支持，不应据此承诺富结果。[官方更新记录](https://developers.google.com/search/updates)。
- IndexNow 是参与引擎的更新通知，当前参与列表不含 Google；普通商品页也不适用 Google 的 JobPosting / BroadcastEvent Indexing API。[参与方](https://www.indexnow.org/searchengines.json)、[Indexing API 范围](https://developers.google.com/search/apis/indexing-api/v3/quickstart)。
- GEO 论文在特定基准上的最高提升，不能转写为 Angry Miao 的销售或流量预期。[原始 GEO 研究](https://arxiv.org/abs/2311.09735)。

搜索 bot 与训练 bot 应分别配置：OAI-SearchBot 与 GPTBot 用途不同；PerplexityBot 另有官方规则。核对 robots、CDN / WAF 和官方来源验证；允许抓取并不保证被引用。[OpenAI bots](https://developers.openai.com/api/docs/bots)、[Perplexity crawlers](https://docs.perplexity.ai/docs/resources/perplexity-crawlers)。

## 3. 开源选型：采用最小组合，按证据评估活跃度

核验方法：2026-10-29 查询 GitHub 仓库 API、默认分支提交、release、README 和 LICENSE。以下星数是当日快照；30 日提交从 2026-09-29 00:00 UTC 起统计，首次最多取 100 条，因此 ≥100 只是下限，包含文档、合并与依赖更新。pushed_at 不是默认分支最近实质代码更新；热度不等于优化效果。

### 核心组合

**Crawl4AI：采集与页面差异层。**86,502 stars，30 日 75 次提交；10 月 20 日有安装处理修复，10 月 14 日发布 v0.9.5。用于保存 HTTP、原始 HTML、渲染正文、商品字段及页面差异。自托管不要求购买云服务，但仍有机器、浏览器维护与可选模型费用。许可 Apache-2.0，部署保留适用 LICENSE / NOTICE。[仓库](https://github.com/unclecode/crawl4ai)、[维护提交](https://github.com/unclecode/crawl4ai/commit/129a950ca6cc39107676daae666f54ac4ebba698)。

**marketingskills：策略、选题与转化工作流。**57,207 stars，30 日 ≥100 次提交；10 月 27 日 UTC 有证据校验相关实现与 v2.13.9 发布。支持多类 agent 环境，选取审计、AI 搜索、内容、竞品和分析相关技能，再叠加 Angry Miao 事实库。MIT；模型与数据服务另计。其关于 llms.txt、schema 等建议仍须与平台官方指南校准，不照单全收。[仓库](https://github.com/coreyhaines31/marketingskills)、[证据校验提交](https://github.com/coreyhaines31/marketingskills/commit/3c849a245b5d07a596c48d5e43b26586b97ae036)。

**promptfoo：可复现评估层。**26,580 stars，30 日 ≥100 次提交；10 月 25 日发布 0.125.1，近期持续维护模型依赖。它是通用评测底座，需要定制联网调用、原始回答、引用 URL、品牌实体和事实断言；不是开箱即用的 GEO 排名工具。MIT，API / 搜索调用另计；新测量需避开旧响应缓存。[仓库](https://github.com/promptfoo/promptfoo)、[联网搜索配置](https://www.promptfoo.dev/docs/providers/openai/#web-search)。

### 有条件增加或替换

**claude-seo：团队已有 Claude Code 时增加专项审计。**23,663 stars，30 日 55 次提交，10 月 22 日发布 v2.5.0 并有代码修复。适合电商、技术 SEO、结构化数据和国际化审计。原生为 Claude Code 插件，不能假定 `/seo` 原样适用于所有 agent；只用其他平台的团队可采用经适配的审计清单。MIT，模型与可选外部数据服务有成本。[仓库](https://github.com/AgriciDaniel/claude-seo)、[release](https://github.com/AgriciDaniel/claude-seo/releases/tag/v2.5.0)。

**Firecrawl：采集层替代选择。**196,559 stars，30 日 ≥100 次提交，近期有 agent 与 API 修复。若团队想减少采集运维，可与 Crawl4AI 二选一。服务端核心 AGPL-3.0，部分 SDK 为 MIT；云与自托管能力不能假设完全相同，云调用另计费。[仓库](https://github.com/firecrawl/firecrawl)、[自托管说明](https://docs.firecrawl.dev/contributing/self-host)。

### 实验观察名单

**eGEOagents**：211 stars，30 日 14 次提交，10 月发布 v2.3.0。可试验少量诊断 / 改写草稿，但其[评测说明](https://github.com/mverab/eGEOagents/blob/main/docs/evaluation.md)是固定候选的 LLM 重排代理指标，不能当线上搜索引用；部分 fix-gaps 功能[仍标记 experimental](https://github.com/mverab/eGEOagents/commit/8f58dda0d9fed42e732ef748f0c3ebe0b09ce052)。

**geo-aeo-tracker**：311 stars，30 日 13 次提交；实时监测依赖 Bright Data 等服务，无 key 可展示样例数据。只能在确认真数据、保存原始输出和算清成本后试点。**aeo-platform**：13 stars，30 日 28 次提交，可关注其 API 采样与原文归档方法，尚不能叫成熟高热度项目。[tracker](https://github.com/danishashko/geo-aeo-tracker)、[aeo-platform](https://github.com/webappski/aeo-platform)。

**选型决策：**起步只用 Crawl4AI + marketingskills + promptfoo；现有 agent 负责调度，数据库 / 文件保存证据。首月不另建复杂多 agent 平台。依据运行环境决定是否增加 claude-seo；Firecrawl 替换采集层，而非重复采购。上线时固定版本 / commit，先验证样例与外部数据依赖。本次只读研究，未安装或执行这些项目。

## 4. 中英双市场：共享事实，分别运营

### 共同的实体与页面底座

建立“产品型号 → 硬件版本 → SKU / 变体 → 市场 → 语言 → 规范 URL”映射。AM Infinity 与 .97 分别维护；真实颜色 / 套装变体再按商品模型组织。Angry Miao、怒喵、怒喵科技及用户常用写法映射到品牌实体；实体 Agent 从官方原始资料验证 Dry Studio 关系；证据不足则保留 vendor，不发布母子品牌断言。

www 负责设计研发、品牌与产品故事；store 承接海外交易；实体 Agent 根据导航、跳转与真实后台配置验证 mall / m 的中文交易与移动端分工，未验证前不改重定向。叙事与交易页面保留各自意图，跨域 canonical 只用于真实重复且要合并的页面，不做全站相互指向。中英等价页设置准确 lang 和双向 hreflang；人民币 / 美元、国内 / 海外配送与保修分开。[Google 本地化页面规范](https://developers.google.com/search/docs/specialty/international/localized-versions)。

### 英文市场

- 搜索渠道：Google、Bing；购物信息用真实商品 feed、Product / Offer 和 Merchant Center 维护。先按已售市场确认币种、运费、关税说明及退货政策，不能只优化标题。[Google 商家商品规范](https://developers.google.com/search/docs/appearance/structured-data/merchant-listing)。
- AI 渠道：固定测试 Google AI Mode、ChatGPT Search、Perplexity 的消费端表现；AI Overview 如需观察另建面板，API 的联网评估也另列。不要把 Gemini API grounding 直接叫作 Google AI Mode 排名。
- 内容主轴：`hot swappable battery gaming mouse`、`AM Infinity vs .97`、握姿与尺寸、8K 的收益与限制、设计与机械客制化、软件和保修。以上是待验证意图假设，没有伪造搜索量。
- 外部证据：向合适的硬件评测者提供可复现测法和产品资料，由其独立形成结论；本站链接真实原评测。合作与内容分发属于后续计划，本研究未联系任何第三方。

### 中文市场

- 搜索渠道：百度为独立基线，Bing 中文可作补充；先确认站点验证、抓取与站图 / 链接提交能力。国内购买、发货、授权渠道和售后要有稳定 HTML 页，不能仅埋在 PDF 或历史活动里。[百度搜索资源平台](https://ziyuan.baidu.com/)。
- AI 渠道：以豆包、DeepSeek、Kimi 建立第一批消费端观察面板；根据真实引用来源决定是否增加百度 AI 搜索、元宝等。选择依据应是受众与可观测性，不假设所有平台使用同一排名逻辑。
- 内容主轴：“小手抓握游戏鼠标怎么选”“8K 鼠标为什么卡顿”“换电鼠标续航怎么算”“怒喵机械键盘与磁轴怎么选”“AM Master 固件 / 驱动”“现货、预售与售后”。避免逐字翻译英文榜单。
- 外部证据：原创中文评测、B 站视频配套的公开图文 / 测试方法、客制化社区的一手体验。是否优先某平台，应由实际引用日志和客户来源决定；不自动灌水或制造第三方背书。
- 中文自动测量可研究 [DeepSeek Search / Fetch](https://api-docs.deepseek.com/zh-cn/guides/search/)及 [Kimi Web Search](https://platform.kimi.ai/docs/guide/best-practices-for-web-search)。这些提供检索 / 内容接口，自己拼装的回答不等于它们消费端的推荐；需要独立标为 API 检索覆盖 / API 回答实验。

中文平台公开 GEO 规则和站长可观测性并不统一；本报告不编造“专用爬虫白名单”“保证引用提交入口”。百度 AI 流量相关能力须登录账号核实实际开放情况，不能作为已拿到的基线或承诺 API。

## 5. Agent 直接执行、核验并交付

运行链路：采集 / 事实 / 实体 Agent 并行 → 内容与 Patch Agent → QA Agent 自动测试 → 工程 / 发布 Agent 应用允许的改动 → 浏览器 / API Agent 采样 → 分析 Agent 更新任务。

不把例行抓取、后台导出、写稿、翻译、改代码、测试和上线后核对分配给人。已有访问与授权范围内连续执行；缺仓库、连接、可信原始数据时仅阻塞相应动作，其他分支继续。

1. **采集 / 诊断 Agent**交付时间戳、响应、HTML/DOM、差异与机器验收。接入实际仓库后定位路由、修改真实文件、构建并生成补丁。无仓库时清楚标记“修复未应用”，不猜框架。
2. **事实 / 实体 Agent**把型号、版本、市场、单位与逐条证据组成事实账本。37g/39g 等冲突无法裁决时冻结该字段并从待发布稿中省略；本次已执行该降级。
3. **内容 / 本地化 Agent**产出有依据的中英文正文、元数据和修改操作。当前已生成两份换电说明与13项离线修改，不把尚无实测的数据写进稿件。
4. **QA Agent**校验来源片段、hash、数值、实体、语言、修改前置条件与回滚，并在实际工程环境中运行链接/schema/渲染回归。独立核验与确定性检查配合；不把模型自评分当事实证明。
5. **发布 Agent**读取当前源对象，映射到真实CMS字段或源码，按已有范围写入并read-back；失败回滚。离线公开HTML修改不等于Shopify mutation；当前未接入CMS和源站，无实际发布。
6. **测量 / 分析 Agent**用已授权浏览器采样消费端，以官方API运行独立实验；原文、来源、费用和版本全部归档，自动计算结果并生成下一批任务。

执行层新增推荐：独立服务用 [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk)；GitHub仓库内用 [gh-aw](https://github.com/github/gh-aw)。需要UI操作时用 [browser-use](https://github.com/browser-use/browser-use)，稳定回归用 [Playwright](https://github.com/microsoft/playwright)。实际组件边界、今日快照和完整任务契约见 [Agent执行方案](agent-nextsteps.md)。

每条事实保存产品/版本、SKU、市场/语言、数值/单位、测试条件、来源、证据日期和支持状态。公开页面中的品牌参数标为source_claim，不冒充独立物理测量。价格、库存与政策以真实业务数据为输入。

可复用入口：[RUN-AGENT.md](agent-kit/RUN-AGENT.md)。任务图和验收：[tasks.json](agent-kit/tasks.json)。已完成：[qa-results.json](agent-kit/qa-results.json)。

## 6. 内容计划：先建设 8 类可引用资产

以下按主题立项；已有同意图内容优先升级。中英文作为同一资料的本地化版本维护，市场政策独立。实际 URL 由现有 CMS 和 query → page 映射决定，本报告不强制改路径。

1. **Infinity 与 .97 选型**：形状尺寸、真实手型 / 握姿照片、重量条件、模块与适用人群；整合现有 PDP 对比，连到正确 SKU。先解决参数冲突，不公开未经测试的手长推荐区间。
2. **换电与续航机制**：说明更换已充电电池的过程、接收器充电方式、单电池测试及中断；明确“infinite”的机制边界。加入图示与测试日期。
3. **1K / 4K / 8K 测试与设置**：公开固件、CPU、系统、游戏、连接、测法与误差；同时说明 CPU 负载、兼容与续航取舍。不得用回报率倒数冒充完整延迟。
4. **形状 / 握姿 / Hatchback 适配**：真实照片、尺寸图、不同握姿边界与选择建议。帮助用户选择，不为每种手长生成重复页面。
5. **机械客制化与 HE 选型**：设计、声音、手感和竞技功能分别解释；准确区分 AM 与 Dry Studio 型号，竞品参数引用其官方资料并注明日期。
6. **AM Master / 固件 / 手册中心**：基于现有[软件入口](https://store.angrymiao.com/pages/software)和[手册入口](https://store.angrymiao.com/pages/user-manual)，提供型号级 HTML 快速指南、兼容性、发布日期、变更和已知问题，PDF 保留。
7. **独立评测证据索引与研发记录**：链接原始评测、视频及方法；品牌自己的数据明确标为品牌测试，不包装成第三方结论。声音视频固定录制条件。
8. **购买 / 发售 / 售后事实页**：中文国内与英文海外分别给出当前渠道、完整日期、发货状态和保修；缺货保留有用页面与通知入口，永久停售说明替代型号及历史身份，继续提供支持资料。

首批建议交付：4 个主题 × 中英两版＝8 个升级 / 新建页面，外加 4 个关键商品 / 支持页修订。优先主题为选型、换电、8K 测试、购买支持；若测试证据未完成，先发布已核验的事实 / 设置内容，性能结论等待测试。

## 7. 怎么测量：分别看搜索、回答与生意

### 第一层：搜索与商品发现

- 英文：GSC 非品牌点击、重点页面覆盖、查询 → 页面、国家与设备；Bing 的对应搜索数据。中英文品牌词表分别维护，并归并 Angry Miao / angrymiao / 怒喵等别名。
- 中文：百度资源平台可获得的抓取、索引、搜索数据，以及固定关键词观察；以账号实际功能为准，不能直接套用 GSC 的报表字段。
- Google 的独立 **Generative AI performance report** 已于 2026-08-31 全球推出，包含 AI Overviews / AI Mode 曝光，可按页面、国家、设备与日期查看；曝光不足可能不显示。当前文档不支持承诺独立 AI clicks / CTR 或可用 API。[官方报告](https://support.google.com/webmasters/answer/16984139)。
- 同时检查 GSC Settings 的 Search generative AI Include / Exclude / Inherit 及属性继承。[官方控制说明](https://support.google.com/webmasters/answer/16908024)。Bing AI Performance 只解释其支持场景的数据，不外推全部 LLM。[Bing AI Performance](https://blogs.bing.com/webmaster/2026/2/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview/)。

### 第二层：固定问题面板

随附 48 条未运行种子题：每语言 24 条，含 12 鼠标、8 键盘、4 购买 / 支持；每语言 18 条非品牌与 6 条品牌。先用客户问题与搜索数据复核，锁定版本，不能每周只保留品牌表现好的题。

消费端建议：英文 Google AI Mode / ChatGPT Search / Perplexity；中文豆包 / DeepSeek / Kimi。Google AI Overview 另建面板，不能与 AI Mode 混算。每周固定 8 条哨兵题 × 2 语言 × 3 平台 × 2 次＝96 次测试；每月完整 24 条 × 2 语言 × 3 平台 × 2 次＝288 次。使用新会话、稳定地区 / 语言 / 联网模式；原始输出、来源、搜索是否触发和时间全部保留。Google 未触发 AI 回答单列，不隐藏。

API 另设实验表：英文可用联网 provider 做 24 题 × 3 provider × 3 次＝216 次 / 轮；中文可接明确支持 Search / Fetch 的官方接口，记录检索与最终生成步骤。预算不足先缩减 provider 数量，保持固定题组。API 测量不与消费端合并，不把自建 RAG 回答当平台推荐份额。

四个核心指标分别计算，不汇成神秘总分：

- **品牌提及率**＝包含品牌 / 正确产品实体的测试次数 ÷ 成功完成的固定题测试次数。
- **官网引用率**＝引用已确认官方域名的测试次数 ÷ 成功完成的固定题测试次数；引用第三方对品牌的评测另列。
- **适配推荐率**＝明确将正确产品作为适合该需求选项的测试次数 ÷ 成功完成的固定题测试次数。无依据的“最强”不算优质结果。
- **事实正确率**＝抽查正确且有依据的关键事实断言数 ÷ 被抽查关键事实断言数；关键参数冲突、错型号、过期发货和错误价格另设错误清单。

网络错误 / 限流等排除出成功测试分母但单报失败率；成功完成测试但未出现 AI 回答计零并单列。未联网、无引用和未触发搜索的答案也保留在端到端分母，另报“有 AI 回答条件下”的比例，避免挑样本。非品牌测试不向 system prompt 注入品牌或官网。多次生成不是独立消费者；需要区间时按问题聚类估计，不虚报统计显著性。

### 第三层：到站与转化

看已识别的自然搜索 / AI referrer 的产品浏览、加购、净支付订单、候补名单和售后自助完成。购买与候补分开，退款与重复订单按统一口径去重。保留实际 referrer / UTM，不把全部 Direct 归为 AI；bot 抓取不能当人类访问。高端限量产品记录发售、售罄、促销与媒体曝光，避免把库存变化误认成 SEO 成效。

### 小规模对照实验

前两周建立基线，选择同语言、类似意图与曝光的页面分批上线。每轮只改一个主要机制，例如初始 HTML、经过批准的规格 / 适用边界，或重复文章整合。4–6 周比较处理与可比页面，记录重新抓取、发布会、补货、价格与促销等变化。小站样本不够时采用分批准实验，报告方向与不确定性，不承诺某个百分比提升。

## 8. Next Step 与执行顺序

**现在已完成的本地任务：**能力记录、路由证据重放、11条产品事实、实体URL映射、中英换电修订、13项可回滚离线修改、87项QA验证。7个任务完成指本地产物，不代表线上效果完成。

**接入即执行的任务：**工程Agent取得网站仓库后生成真实路由补丁与构建/回归记录；数据Agent读取已授权GSC/GA4/百度/Bing；发布Agent映射实际字段，写入允许的CMS/生产范围并验证；浏览器/评估Agent取得会话或provider后跑真实题库。当前4项任务waiting_access。

**只等待必要数据的任务：**上线后的效果分析waiting_data；争议重量/时长只对应blocked_claim。未确认数值可省略，其他内容不排队等待。

30天目标是运行并验证完整闭环；31–60天由分析Agent用真实观测判断有效机制；61–90天由同一套Agent扩展已经有效的模板。4–6周成效依赖自然时间与实际数据；不会用合成数据提前填结果。

每个任务记录Agent、依赖、输入、输出与验收；短暂失败最多重试3次，保存证据并继续独立分支。不设置例行的“交给某个人处理”作为终点。

## 9. 运行能力与成本

无需把雇用增长、开发和中英编辑列为执行前置条件。已有Agent可直接做单轮任务；需要独立服务时选择OpenHands SDK，需要仓库工作流时选择gh-aw，按现有环境二选一。LangGraph仅在需要复杂持久编排时加入。

待接入输入：实际网站仓库/部署连接、搜索与分析property、商城可编辑对象、允许的写入字段和动作范围、AI采样会话或provider额度。Agent通过API/浏览器自动读取，免去人手动导出与整理；凭证保存在运行环境，不写进产物包。当前未配置无人值守后台或定期任务。

费用按模型token、搜索/API、浏览器时间、机器/存储与真实实验设备计算。先用一小批真实运行记录单次费用，再设置每轮上限。开源软件不代表外部数据和模型调用免费。

硬件实测有原始日志或可控制的真实测试设备时由Agent分析或调度；缺实物/仪器时只输出协议，不生成测试结论。其他可靠事实与设置解释继续完成。

## 10. 证据说明与交付物

本报告将观察事实、研究建议和待验证事项分别表述。没有推测当前流量、收入、转化率、搜索量、AI 引用率或竞品性能；本次没有修改官网、发布内容、采购服务或发送外部消息。

随附文件：交互阅读版 `angrymiao-seo-geo-plan.html`；未运行题库 `angrymiao-query-seeds.json`；去除原网页正文的 HTTP 证据 `angrymiao-http-evidence.json`；开源活跃度快照 `angrymiao-oss-snapshot.json`。技术证据仅代表记录时间与请求环境；当前业务事实由Agent读取可信后台或原始资料核验；无法获取的字段局部阻塞，不以模型猜测补齐。新增交付见 [Agent执行方案](agent-nextsteps.md)、[任务图](agent-kit/tasks.json) 与 [执行包](angrymiao-agent-kit.zip)。
