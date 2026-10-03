# 验证与交付

基线：v0.3，2026-10-02。验证分为工程运行、真实回放语义和模型效果三层，不能相互替代。

## 1. 当前证据

| 层级 | 已有结果 | 结论范围 |
|---|---|---|
| 工程测试 | 全量 47 项通过，其中工作流 22 项 | 测试覆盖的契约、失败路径与文件操作通过 |
| 静态检查 | Ruff check、format --check 通过 | 风格与静态规则通过 |
| Linux CI | Python 3.11 / 3.12，安装 dev + replay，pytest、两个报告路径及 doctor 通过 | 这些环境可安装并运行现有测试/合成示例 |
| Windows CI | Python 3.12，安装 dev，工作流测试和 demo 通过 | 不含真实 Gem 回放解析或 GPU |
| 安装产物 | 本地 wheel 和 CLI 冒烟已通过 | 包入口可运行 |
| 历史真实回放 | v0.2 的 8822520406：10 玩家、362 购买事件及引用核对 | 历史购买解析证据，非本次重新解析 |
| 新位置/经济语义 | 尚未完成真实对照 | 不宣称新时序已通过真实数据验收 |
| 模型效果 | 尚无模型和独立评估 | 不报告准确率、胜率或决策改善 |

工程基线：[364d9ad](https://github.com/xrfc/dota2-item-timing/commit/364d9adf07373e925c9d420b5804403f866c432e)，[成功 CI](https://github.com/xrfc/dota2-item-timing/actions/runs/36997970952)。本次文档整理不会把历史验证写成新的实测结果。

本轮文档核验：14 份 Markdown、99 个仓库相对链接、7 个 JSON 契约示例通过检查；24 次 CLI 调用通过，覆盖帮助、重复 demo、doctor/status、数据集构建、JSON 导入/去重/标注/事实复盘和旧报告入口。检查在临时工作区使用现有 Python 依赖执行，没有重新安装 Gem 或解析真实 demo。运行代码与上述基线一致。

## 2. 开发者复现命令

仓库根目录，Python 3.11+：

```bash
python scripts/bootstrap.py --replay --dev
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/python -m dota_items.cli report examples/match.synthetic.json --player-slot 0 --output reports/smoke
python coach.py --workspace coach-workspace/validation demo
python coach.py --workspace coach-workspace/validation doctor
python coach.py --workspace coach-workspace/validation status
```

Windows 的解释器路径为 `.venv/Scripts/python.exe`。只核对 JSON 工作流可省略 --replay；真实 demo 测试另需 Gem 和合法可用的回放文件。

期望结果：pytest 无失败；demo 的 dataset.split_matches 为 train=4、validation=1、test=1，report 路径存在，doctor.ok 为 true。重复 demo 应复用相同数据集 ID 并生成新的报告。实际源码与 CI 配置发生变化时，以当次检查为准。

## 3. 自动测试覆盖

| 测试文件 | 主要覆盖 | 没有证明的内容 |
|---|---|---|
| [test_pipeline.py](../tests/test_pipeline.py) | 首次购买、重复/赛前事件、缺失与非法值、HTML 转义、事实指纹 | 装备实际可用时间、统计建议质量 |
| [test_source.py](../tests/test_source.py) | 原响应缓存、错误 match_id、重试等待、错误不暴露 key | OpenDota 实时可用性和缓存完整性策略 |
| [test_replay_ingestion.py](../tests/test_replay_ingestion.py) | 压缩/头部/zip、购买适配、索引、缓存、批次继续 | 全补丁的真实 Gem 语义与解析性能 |
| [test_coach_workflow.py](../tests/test_coach_workflow.py) | 合成闭环、标签/筛选/比赛划分、去重冲突、搬迁/损坏、写锁、时序与证据、训练/登记/预测协议、超时/失败、未来引用拒绝 | 真正训练、全流程故障恢复、模型内部无未来泄漏 |

模型测试通过临时脚本生成受控产物和预测，仅用于验证协议。没有深度学习训练，也不能把接口桩指标用于报告效果。当前自动测试不能替代真实 demo 的固定回归集。

## 4. 真实回放验收矩阵

每个样本至少记录原文件/demo/raw/normalized 哈希、parser/adapter/代码版本、补丁、平台、角色来源、核验记录。此矩阵区分“有导出”与“已人工确认语义”：

| 能力 | 当前状态 | 所需证据 |
|---|---|---|
| 购买 key/tick/引用 | 一场历史样本已核对 | 固定回放集重跑与人工游戏事件对照 |
| 购买漏检/合成/送达 | 未完成 | 独立人工事件集合，误检/漏检分母与语义分类 |
| 暂停感知时钟 | 受控测试通过；真实待验 | 暂停前/中/后的 tick 和游戏时间对照 |
| 位置与坐标语义 | 导出/受控测试通过；真实待验 | 坐标、时间、死亡/复活与采样覆盖对照 |
| gold / net_worth / 补刀反补 / xp_progress | 导出/受控测试通过；真实待验 | UI/原始值、单位、等级变化与缺失片段 |
| 截断/不完整回放 | 部分提示；资格规则未实现 | 完整/缺失/截断样本和训练排除结果 |
| 跨补丁/平台 Gem 能力 | 未形成矩阵 | 精确版本和范围逐项记录 |
| 真实模型复盘 | 未实现 | 独立评估、错误案例与适用范围 |

模板见[操作指南](workflow.md)。先选择有权使用的少量固定回放发现问题，再扩样本；“看了 20 条没有异常”不能作为总体准确率或完整性结论。

## 5. 交付验收

2026-10-03 新增的数据准备学习任务见 [L01–L12](roadmap.md)，逐场/逐样本的正反例要求见[开发流程验收矩阵](development-workflow.md)。这些是后续任务的完成条件，不包含在当前 47 项测试已通过的声明中；填写模板也不代表执行了验收。

### 当前基础设施交付

- 快速开始在干净环境能复现，输出明确标为 synthetic。
- 导入失败保留逐文件结果，重复比赛不增加新工作区逻辑样本数。
- 固定数据集保持比赛级 split 与文件指纹；修改源标签不改变旧快照。
- 训练/预测未实现时模板失败并说明原因；不能伪造成功产物。
- 运行失败保留配置/日志，失败 run 不允许登记。
- 预测引用不得来自另一玩家、整局汇总或决策之后。
- 文档标明 doctor、旧缓存和模型适用性检查的边界。

### 下一轮可靠性出口

还需完成：真实字段验收、质量覆盖与完整性状态、完整来源/环境清单、解析限额、故障注入、陈旧任务识别、备份恢复演练。细化任务见 D01–D11、V01–V04。

### 模型阶段出口

定义任务和数据窗口后，保存同一快照上的基线比较、独立测试、校准/缺失子组表现和按比赛计算的不确定性。模型产物登记成功不能代替这一出口。

## 6. 文档和变更检查

纯文档变更核对以下内容即可，不为文字增加镜像实现的测试：

1. 所有仓库相对链接和代码路径存在；历史外部链接明确版本。
2. 非占位命令在临时工作区运行，预期输出字段与退出码正确。
3. JSON 格式示例与 Pydantic 契约或导入校验器一致。
4. 标清真实数据、适配器路径、dataset/run/model ID 等必须替换的占位值。
5. 完成度、任务状态、接口版本、CI 证据保持一致；已知缺口不写成已实现。

运行行为变更时按相关风险增加有意义的正反例测试，并执行项目要求的静态/自动检查。数据/schema 变化需说明迁移与回退；提交到开发分支，不把 CI 通过等同自动发布或合并。
