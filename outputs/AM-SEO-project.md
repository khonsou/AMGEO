# AM SEO 项目已建立

当前聊天已归入应用侧的 **AMSEO** 项目，聊天名为 **AM SEO**。

实际工程目录：`/Users/linan/Desktop/AMSEO`。

## 已完成

- 初始化本地Git仓库，配置项目README、AGENTS、事实与执行约定。
- 实际拉取7个官方开源仓库并固定完整commit、来源和许可证：OpenHands SDK、gh-aw、Crawl4AI、marketingskills、promptfoo、browser-use、Playwright。
- 接入原研究、11条事实、13项离线修改、双语稿与48题。
- 提供可从任意目录调用的 `am-seo` CLI。
- 工程迁入新目录后，7/7上游核验、29项行为测试与87项离线产物检查全部通过。

## 立即使用

```bash
cd /Users/linan/Desktop/AMSEO
./am-seo status
./am-seo doctor
./am-seo deps verify
./am-seo run --offline
python3 -m unittest discover -s tests -v
```

README与docs/conversation-context.md保留本次对话的项目决策；AGENTS.md指导后续Agent连续执行。

本次拉取源码未安装/运行所有上游依赖，没有付费模型调用、网站部署或商品修改。源站仓库、搜索/商城连接与真实AI采样能力仍按任务图接入。

原研究目录的文件保留，已有链接继续可用。后续工程修改以Desktop/AMSEO为准。
