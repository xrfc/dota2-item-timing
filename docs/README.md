# 文档索引

文档更新：**2026-10-03**；运行代码基线 **0.3.0**。当前学习主线是数据清洗、时间对齐、样本与预处理；实际模型训练仍为下一阶段。

## 按任务阅读

| 你要做什么 | 文档 |
|---|---|
| 先判断项目做到了哪里 | [完成度与验证证据](project-status.md) |
| 安装、导入、标注、固定数据集、预留模型接入 | [教练工作流](coach-workflow.md) |
| 日常操作、旧命令迁移、备份、故障恢复、人工核验 | [操作指南](workflow.md) |
| 了解模块边界和数据流 | [工程设计](engineering-design.md) |
| 实现训练器或预测器 | [数据契约](data-contracts.md) |
| 理解技术选择和后续性能优化 | [技术选型与优化路线](long-term-roadmap.md) |
| 安排下一轮开发 | [任务清单](roadmap.md) |
| 按学习计划执行数据准备任务 | [开发流程](development-workflow.md) |
| 记录目标、验收与学习复盘 | [任务记录模板](templates/task-record.md) |
| 核对字段、缺失、时间边界和样本来源 | [数据审计模板](templates/data-audit.md) |
| 复核已知限制与历史问题 | [风险复核](project-review.md) |
| 重现检查、区分工程验证和模型效果 | [验证与交付](validation-and-delivery.md) |
| 修改代码或文档 | [贡献指南](../CONTRIBUTING.md) |
| 查版本变化 | [变更记录](../CHANGELOG.md) |

## 文档职责

- `project-status.md` 统一回答完成度，不使用缺乏分母的完成百分比。
- `data-contracts.md` 描述代码当前接受和输出的格式；规划中的格式单独注明。
- `coach-workflow.md` 维护命令和适配器用法；`workflow.md` 维护运营与恢复。
- `long-term-roadmap.md` 解释选择、成本和升级条件；`roadmap.md` 维护任务状态与验收要求。
- `development-workflow.md` 维护 L01–L12 的执行流程、验收示例和开发边界；`templates/` 只提供待填写模板，不作为已完成证据。
- `validation-and-delivery.md` 维护测试证据及其边界；合成数据通过不等于真实回放语义通过。

出现冲突时，先核对[实现](../src/dota_items/workflow/)和[测试](../tests/)，修正文档并注明验证范围。生成到工作区的 JSON Schema 来自代码；部分运行清单只有版本字段和程序校验，并没有对应的完整 Pydantic Schema。

历史入口 [engineering-design-v0.1.md](engineering-design-v0.1.md) 仅用于兼容旧链接。旧文档中尚未实现的设计不能视为当前功能。
