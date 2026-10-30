# AM SEO

Angry Miao / 怒喵的中英双市场 SEO、GEO Agent 项目。这里保留本次对话的研究、事实证据、48 条题库、双语修订稿和可重复运行的本地验收；同时固定官方开源上游，供后续 Agent 接入真实网站仓库与后台继续执行。

## 本地开始

需要 Python 3.11+、Git；离线命令没有第三方 Python 依赖，也不需要 API key。

```bash
./am-seo status
./am-seo doctor
./am-seo deps verify
./am-seo run --offline
python3 -m unittest discover -s tests -v
```

其他命令：

```bash
./am-seo --help
./am-seo status --json
./am-seo doctor --json
./am-seo validate
./am-seo score observations.jsonl metrics.json
python3 scripts/sync_upstreams.py sync
```

`run --offline` 重放现有真实证据、验证修改与回滚，更新本地状态；它不会启动模型调用、生成假问答、修改官网或发布商品。

## 开源组件

精确版本、来源和许可在 `config/upstreams.lock.json`，实际 checkout 在被 Git 忽略的 `vendor/`。

- OpenHands Software Agent SDK：独立 coding agent 执行组件。
- GitHub gh-aw：仓库内的 Agent 工作流与 PR 产物。
- Crawl4AI：公开页面抓取、渲染与结构化采集。
- marketingskills：SEO/GEO、内容和分析任务方法。
- promptfoo：联网答案评估底座。
- browser-use：需要浏览器规划的已授权 UI 任务。
- Playwright：DOM/网络检查、截图和回归。

拉取源码不等于安装、运行全部组件。本项目先固定实际 commit，保留上游 LICENSE，再按需要在隔离环境接入。OpenHands 与 gh-aw 是可选的执行模式；现有聊天中的 Agent 也可直接操作本项目。模型、搜索和云服务的费用与开源许可分开。

`sync_upstreams.py verify` 离线核对 URL、commit、工作区与许可证；`sync` 按锁文件恢复缺失 checkout，不重置或删除已有脏仓库。

## 从本次对话继续

1. 读取 `AGENTS.md`、`outputs/agent-kit/RUN-AGENT.md` 和 `outputs/agent-kit/tasks.json`。
2. 检查本地能力与上游固定版本，执行可运行分支。
3. 接入真实网站仓库后，工程 Agent 定位真实路由、修改源代码并运行构建和页面回归。
4. 搜索/电商连接就绪后，由 Agent 直接读数据、映射 CMS 对象及执行允许的修改。
5. 消费端会话或联网 provider 就绪后，保存真实观测并分别计算 UI、API、纯检索指标。

不设置例行的“交给某个人处理”作为任务终点。缺少权威数值时只冻结相应断言，不妨碍其他内容和技术任务。

## 当前可用产物

- `outputs/agent-nextsteps.md`：Agent 执行方案。
- `outputs/angrymiao-seo-geo-strategy.md`：完整中英 SEO/GEO 研究。
- `outputs/angrymiao-seo-geo-plan.html`：交互阅读版。
- `outputs/agent-kit/`：11 条事实、13 项离线修改、两份修订稿、48 条题库、验证器和指标计算器。
- `outputs/agent-kit/qa-results.json`：已执行的离线检查。
- `outputs/project-status.json`：项目集成命令生成的本地运行状态。

公开产品证据采集于 2026-10-29；项目与执行组件升级于 2026-10-30。两种时间分别记录。

## 目录

```text
am-seo                  本地 CLI 入口
AGENTS.md               全项目 Agent 约定
config/                 上游版本锁
src/am_seo/             CLI 与集成
scripts/                可重复的依赖同步
tests/                  隔离的行为测试
vendor/                 实际上游源码，忽略提交
outputs/                可交付成果与证据
work/                   研究和临时文件，忽略提交
```

当前项目是本地工作台；真实网站源码、搜索/商城授权和线上发布范围仍需作为连接接入。没有把离线产物冒充生产修改，也没有配置收费调用或定期后台服务。
