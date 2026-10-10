# 开发文档盘点与维护职责

日期：2026-10-10；基线 main `c6a5e1f`。基线跟踪 **159 份 Markdown**，本轮新增3份，共 **162份**。以下逐路径登记；“盘点全部”不代表逐条英雄技能已获7.41f语义认证。

## 权威入口与冲突规则

| 问题 | 唯一职责 |
|---|---|
| 当前做什么、先后顺序 | [主线开发流程](development-mainline.md) |
| 当前任务状态与出口 | [roadmap](roadmap.md)，M主线与旧编号并存 |
| 实际交付了什么 | [project-status](project-status.md) |
| 当前结构/目标依赖约束 | [engineering-design](engineering-design.md) / [module-boundaries](module-boundaries.md) |
| 已实现接口 | [data-contracts](data-contracts.md)；新推荐契约在模块边界中明确标为规划 |
| 使用与恢复 | [coach-workflow](coach-workflow.md) / [workflow](workflow.md) |
| 测试与证据范围 | [validation-and-delivery](validation-and-delivery.md) |
| 来源及知识维护 | [knowledge-maintenance](knowledge-maintenance.md) |
| 学习状态 | [learning roadmap](../learning/docs/roadmap.md)，不替代产品排期 |

优先核对实现和最新用户目标；历史证据不重写为当前结论。代码中的通用patch字符串与旧数据格式保留兼容，文档固定7.41f不表示运行代码已增加版本门禁。

## 审阅范围与本轮修正

- 全文审阅根文档、docs工程文档、learning说明/流程/模板、knowledge说明/评估/来源、单事件课程与证据README；保留旧任务编号和历史验收记录。
- 生成英雄档案127份及索引纳入路径清单，核对生成方式与版本警示，抽读档案；**未逐技能核验734条机制**。不手改生成页，不把来源JSON、注册表、候选数据重标成7.41f。
- 跟随文档核对CLI、Schema导出、数据集excluded、负观测时间、Gem版本、模块导入、学习生成器和三份CI工作流。验收JSON/依赖清单仅检查结构与历史范围；不重新解析demo、下载制品或认定语义通过。
- 修正仍指向旧功能分支的克隆步骤；区分学习未完成与清洗/样本代码已经实现。
- 修正Gem已精确锁0.10.0、导出版本3.0、6份Schema、excluded已持久化、负观测时间已拒绝、已有features/samples契约等陈旧说明。
- 将未标版本官网优先的旧计划替换为7.41f；移除规划中的命石输入，来源残留保留为待核验历史文本。
- 只调整导航/状态/约束与事实描述，不删除文档、不修改代码、来源快照、已冻结JSON/JSONL和验收收据。

## 非 Markdown 开发资料

| 文件/目录 | 本轮处理 |
|---|---|
| [pyproject.toml](../pyproject.toml) | 核对0.4.0、可选依赖与Gem精确版本，不改配置 |
| [.github/workflows](../.github/workflows) 三份YAML | 阅读触发条件；纯文档不触发两份真实数据工作流 |
| [docs/acceptance](acceptance) 的3份JSON与依赖TXT | 核对历史范围与索引，不逐行重新认证数据 |
| [knowledge/maintenance-verification.json](../knowledge/maintenance-verification.json) | 历史迁入检查，不覆盖为本轮结果 |
| [learning/assets/catalog.json](../learning/assets/catalog.json) | 文档消费者依赖；本轮保持旧组件/学习地图，构建测试验证兼容 |
| [knowledge/hero-capabilities](../knowledge/hero-capabilities) JSON/JSONL及sources | 冻结来源与候选保持不变；文档明确与7.41f目标之间的缺口 |

## 全量 Markdown 清单

| 路径 | 职责 | 本轮处理/边界 |
|---|---|---|
| [CHANGELOG.md](../CHANGELOG.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [README.md](../README.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/README.md](README.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/coach-field-audit.md](coach-field-audit.md) | 历史字段审查 | 全文审阅，保留历史基线及到当前实现的链接 |
| [docs/coach-workflow.md](coach-workflow.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/data-contracts.md](data-contracts.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/data-pipeline.md](data-pipeline.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/development-mainline.md](development-mainline.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/documentation-inventory.md](documentation-inventory.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/engineering-design.md](engineering-design.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/knowledge-cold-start.md](knowledge-cold-start.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/knowledge-maintenance.md](knowledge-maintenance.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/long-term-roadmap.md](long-term-roadmap.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/module-boundaries.md](module-boundaries.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/observer-context.md](observer-context.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/project-review.md](project-review.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/project-status.md](project-status.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/real-data-acceptance.md](real-data-acceptance.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/roadmap.md](roadmap.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/training-admission.md](training-admission.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/validation-and-delivery.md](validation-and-delivery.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [docs/workflow.md](workflow.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [knowledge/README.md](../knowledge/README.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [knowledge/evidence/7.41f-2026-10-06/README.md](../knowledge/evidence/7.41f-2026-10-06/README.md) | 历史教学/证据 | 全文审阅，保留原日期、哈希与结论 |
| [knowledge/hero-capabilities/ASSESSMENT.md](../knowledge/hero-capabilities/ASSESSMENT.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [knowledge/hero-capabilities/HEROES.md](../knowledge/hero-capabilities/HEROES.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/README.md](../knowledge/hero-capabilities/README.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [knowledge/hero-capabilities/SOURCES.md](../knowledge/hero-capabilities/SOURCES.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [knowledge/hero-capabilities/heroes/1.md](../knowledge/hero-capabilities/heroes/1.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/10.md](../knowledge/hero-capabilities/heroes/10.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/100.md](../knowledge/hero-capabilities/heroes/100.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/101.md](../knowledge/hero-capabilities/heroes/101.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/102.md](../knowledge/hero-capabilities/heroes/102.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/103.md](../knowledge/hero-capabilities/heroes/103.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/104.md](../knowledge/hero-capabilities/heroes/104.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/105.md](../knowledge/hero-capabilities/heroes/105.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/106.md](../knowledge/hero-capabilities/heroes/106.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/107.md](../knowledge/hero-capabilities/heroes/107.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/108.md](../knowledge/hero-capabilities/heroes/108.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/109.md](../knowledge/hero-capabilities/heroes/109.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/11.md](../knowledge/hero-capabilities/heroes/11.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/110.md](../knowledge/hero-capabilities/heroes/110.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/111.md](../knowledge/hero-capabilities/heroes/111.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/112.md](../knowledge/hero-capabilities/heroes/112.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/113.md](../knowledge/hero-capabilities/heroes/113.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/114.md](../knowledge/hero-capabilities/heroes/114.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/119.md](../knowledge/hero-capabilities/heroes/119.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/12.md](../knowledge/hero-capabilities/heroes/12.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/120.md](../knowledge/hero-capabilities/heroes/120.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/121.md](../knowledge/hero-capabilities/heroes/121.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/123.md](../knowledge/hero-capabilities/heroes/123.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/126.md](../knowledge/hero-capabilities/heroes/126.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/128.md](../knowledge/hero-capabilities/heroes/128.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/129.md](../knowledge/hero-capabilities/heroes/129.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/13.md](../knowledge/hero-capabilities/heroes/13.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/131.md](../knowledge/hero-capabilities/heroes/131.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/135.md](../knowledge/hero-capabilities/heroes/135.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/136.md](../knowledge/hero-capabilities/heroes/136.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/137.md](../knowledge/hero-capabilities/heroes/137.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/138.md](../knowledge/hero-capabilities/heroes/138.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/14.md](../knowledge/hero-capabilities/heroes/14.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/145.md](../knowledge/hero-capabilities/heroes/145.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/15.md](../knowledge/hero-capabilities/heroes/15.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/155.md](../knowledge/hero-capabilities/heroes/155.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/16.md](../knowledge/hero-capabilities/heroes/16.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/17.md](../knowledge/hero-capabilities/heroes/17.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/18.md](../knowledge/hero-capabilities/heroes/18.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/19.md](../knowledge/hero-capabilities/heroes/19.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/2.md](../knowledge/hero-capabilities/heroes/2.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/20.md](../knowledge/hero-capabilities/heroes/20.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/21.md](../knowledge/hero-capabilities/heroes/21.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/22.md](../knowledge/hero-capabilities/heroes/22.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/23.md](../knowledge/hero-capabilities/heroes/23.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/25.md](../knowledge/hero-capabilities/heroes/25.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/26.md](../knowledge/hero-capabilities/heroes/26.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/27.md](../knowledge/hero-capabilities/heroes/27.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/28.md](../knowledge/hero-capabilities/heroes/28.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/29.md](../knowledge/hero-capabilities/heroes/29.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/3.md](../knowledge/hero-capabilities/heroes/3.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/30.md](../knowledge/hero-capabilities/heroes/30.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/31.md](../knowledge/hero-capabilities/heroes/31.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/32.md](../knowledge/hero-capabilities/heroes/32.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/33.md](../knowledge/hero-capabilities/heroes/33.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/34.md](../knowledge/hero-capabilities/heroes/34.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/35.md](../knowledge/hero-capabilities/heroes/35.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/36.md](../knowledge/hero-capabilities/heroes/36.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/37.md](../knowledge/hero-capabilities/heroes/37.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/38.md](../knowledge/hero-capabilities/heroes/38.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/39.md](../knowledge/hero-capabilities/heroes/39.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/4.md](../knowledge/hero-capabilities/heroes/4.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/40.md](../knowledge/hero-capabilities/heroes/40.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/41.md](../knowledge/hero-capabilities/heroes/41.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/42.md](../knowledge/hero-capabilities/heroes/42.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/43.md](../knowledge/hero-capabilities/heroes/43.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/44.md](../knowledge/hero-capabilities/heroes/44.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/45.md](../knowledge/hero-capabilities/heroes/45.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/46.md](../knowledge/hero-capabilities/heroes/46.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/47.md](../knowledge/hero-capabilities/heroes/47.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/48.md](../knowledge/hero-capabilities/heroes/48.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/49.md](../knowledge/hero-capabilities/heroes/49.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/5.md](../knowledge/hero-capabilities/heroes/5.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/50.md](../knowledge/hero-capabilities/heroes/50.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/51.md](../knowledge/hero-capabilities/heroes/51.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/52.md](../knowledge/hero-capabilities/heroes/52.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/53.md](../knowledge/hero-capabilities/heroes/53.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/54.md](../knowledge/hero-capabilities/heroes/54.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/55.md](../knowledge/hero-capabilities/heroes/55.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/56.md](../knowledge/hero-capabilities/heroes/56.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/57.md](../knowledge/hero-capabilities/heroes/57.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/58.md](../knowledge/hero-capabilities/heroes/58.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/59.md](../knowledge/hero-capabilities/heroes/59.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/6.md](../knowledge/hero-capabilities/heroes/6.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/60.md](../knowledge/hero-capabilities/heroes/60.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/61.md](../knowledge/hero-capabilities/heroes/61.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/62.md](../knowledge/hero-capabilities/heroes/62.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/63.md](../knowledge/hero-capabilities/heroes/63.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/64.md](../knowledge/hero-capabilities/heroes/64.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/65.md](../knowledge/hero-capabilities/heroes/65.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/66.md](../knowledge/hero-capabilities/heroes/66.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/67.md](../knowledge/hero-capabilities/heroes/67.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/68.md](../knowledge/hero-capabilities/heroes/68.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/69.md](../knowledge/hero-capabilities/heroes/69.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/7.md](../knowledge/hero-capabilities/heroes/7.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/70.md](../knowledge/hero-capabilities/heroes/70.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/71.md](../knowledge/hero-capabilities/heroes/71.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/72.md](../knowledge/hero-capabilities/heroes/72.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/73.md](../knowledge/hero-capabilities/heroes/73.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/74.md](../knowledge/hero-capabilities/heroes/74.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/75.md](../knowledge/hero-capabilities/heroes/75.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/76.md](../knowledge/hero-capabilities/heroes/76.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/77.md](../knowledge/hero-capabilities/heroes/77.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/78.md](../knowledge/hero-capabilities/heroes/78.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/79.md](../knowledge/hero-capabilities/heroes/79.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/8.md](../knowledge/hero-capabilities/heroes/8.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/80.md](../knowledge/hero-capabilities/heroes/80.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/81.md](../knowledge/hero-capabilities/heroes/81.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/82.md](../knowledge/hero-capabilities/heroes/82.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/83.md](../knowledge/hero-capabilities/heroes/83.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/84.md](../knowledge/hero-capabilities/heroes/84.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/85.md](../knowledge/hero-capabilities/heroes/85.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/86.md](../knowledge/hero-capabilities/heroes/86.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/87.md](../knowledge/hero-capabilities/heroes/87.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/88.md](../knowledge/hero-capabilities/heroes/88.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/89.md](../knowledge/hero-capabilities/heroes/89.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/9.md](../knowledge/hero-capabilities/heroes/9.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/90.md](../knowledge/hero-capabilities/heroes/90.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/91.md](../knowledge/hero-capabilities/heroes/91.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/92.md](../knowledge/hero-capabilities/heroes/92.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/93.md](../knowledge/hero-capabilities/heroes/93.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/94.md](../knowledge/hero-capabilities/heroes/94.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/95.md](../knowledge/hero-capabilities/heroes/95.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/96.md](../knowledge/hero-capabilities/heroes/96.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/97.md](../knowledge/hero-capabilities/heroes/97.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/98.md](../knowledge/hero-capabilities/heroes/98.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [knowledge/hero-capabilities/heroes/99.md](../knowledge/hero-capabilities/heroes/99.md) | 生成英雄资料/索引 | 目录及版本警示核对；不逐技能认证、不手改生成页 |
| [learning/README.md](../learning/README.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [learning/docs/development-workflow.md](../learning/docs/development-workflow.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [learning/docs/roadmap.md](../learning/docs/roadmap.md) | 工程/知识/学习开发文档 | 全文审阅或本轮新增；按职责统一主线，历史记录保留 |
| [learning/exercises/event-lineage/9031371970/README.md](../learning/exercises/event-lineage/9031371970/README.md) | 历史教学/证据 | 全文审阅，保留原日期、哈希与结论 |
| [learning/templates/data-audit.md](../learning/templates/data-audit.md) | 学习记录模板 | 全文审阅，保留独立学习用途 |
| [learning/templates/task-record.md](../learning/templates/task-record.md) | 学习记录模板 | 全文审阅，保留独立学习用途 |
