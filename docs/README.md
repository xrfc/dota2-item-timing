# 文档索引

**先读：[主线开发流程](development-mainline.md) → [模块与耦合约束](module-boundaries.md) → [任务清单](roadmap.md)。** 全量文件职责、审阅边界及本轮修正见[文档盘点](documentation-inventory.md)。

文档更新：**2026-10-10**；包版本 **0.4.0**，实现核对基线 **main / c6a5e1f**。全部开发分支已整合，包括真实数据验收、上下文、训练准入与缓存/身份追踪修复。本文索引工程文档；全部学习资料与可视化入口见 [learning/](../learning/README.md)。实际模型训练仍为下一阶段。

## 按任务阅读

| 你要做什么 | 文档 |
|---|---|
| 先判断项目做到了哪里 | [完成度与验证证据](project-status.md) |
| 查看全英雄机制资料与选人评估范围 | [英雄能力知识](../knowledge/README.md) |
| 判断知识如何用于冷启动训练 | [知识与训练候选](knowledge-cold-start.md) |
| 查资料迁移、外部证据与仓库维护路径 | [知识维护与路径清单](knowledge-maintenance.md) |
| 安装、导入、标注、固定数据集、预留模型接入 | [教练工作流](coach-workflow.md) |
| 日常操作、旧命令迁移、备份、故障恢复、人工核验 | [操作指南](workflow.md) |
| 了解模块边界和数据流 | [工程设计](engineering-design.md) |
| 一份 demo 到清洗、特征、标签与训练数组 | [数据管线](data-pipeline.md) |
| 采集 7.41f 高分候选、复现真实回放验收 | [真实数据准入](real-data-acceptance.md) |
| 核对视野、装备、技能、战斗字段及教练任务缺口 | [教练字段核查](coach-field-audit.md) |
| 使用新增上下文、玩家视角与真实重解析检查 | [上下文接入](observer-context.md) |
| 核对真实训练准入及桌面交接 | [训练准入](training-admission.md) |
| 实现训练器或预测器 | [数据契约](data-contracts.md) |
| 理解技术选择和后续性能优化 | [技术选型与优化路线](long-term-roadmap.md) |
| 安排下一轮开发 | [任务清单](roadmap.md) |
| 复核已知限制与历史问题 | [风险复核](project-review.md) |
| 重现检查、区分工程验证和模型效果 | [验证与交付](validation-and-delivery.md) |
| 修改代码或文档 | [贡献指南](../CONTRIBUTING.md) |
| 查版本变化 | [变更记录](../CHANGELOG.md) |

## 文档职责

- `project-status.md` 统一回答完成度，不使用缺乏分母的完成百分比。
- `data-contracts.md` 描述代码当前接受和输出的格式；规划中的格式单独注明。
- `coach-workflow.md` 维护命令和适配器用法；`workflow.md` 维护运营与恢复。
- `long-term-roadmap.md` 解释选择、成本和升级条件；`roadmap.md` 维护任务状态与验收要求。
- `validation-and-delivery.md` 维护测试证据及其边界；合成数据通过不等于真实回放语义通过。

出现冲突时，先核对[实现](../src/dota_items/workflow/)和[测试](../tests/)，修正文档并注明验证范围。生成到工作区的 JSON Schema 来自代码；部分运行清单只有版本字段和程序校验，并没有对应的完整 Pydantic Schema。
