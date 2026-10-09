# 验证与交付

## 当前主干验证（2026-10-09）

代码基线：[main / 725f35c](https://github.com/xrfc/dota2-timing/commit/725f35c25d74243a8ca52b17e7956107fd9dfa40)。PR #2 → #1 → [#3](https://github.com/xrfc/dota2-timing/pull/3) 依次合并，主干文件树与已验证的修复提交 `942ebfd` 一致；包版本仍为 0.4.0。

| 验证 | 结果与证据 | 边界 |
|---|---|---|
| 本地完整检查 | `python scripts/check.py`：122 项 pytest、10 项学习 Python、6 项 JS 全通过，Ruff 检查/格式通过 | 测试中的训练器是协议桩，不是实际模型 |
| 本地工作区 | doctor 检查 6 场 synthetic 比赛通过；4/1/1 观察快照，无模型或训练运行 | 合成闭环，不证明真实语义 |
| main 工程 CI | [37926671655](https://github.com/xrfc/dota2-timing/actions/runs/37926671655)：Linux Python 3.11/3.12、Chromium 浏览器检查、Windows portable 全通过 | Windows 不含真实 Gem 解析 |
| main 保存回放回归 | [37926671611](https://github.com/xrfc/dota2-timing/actions/runs/37926671611) 成功并保存回归制品 | 复用原 raw 导出，不是二进制重解析；绿色不解除训练 held |
| 固定证据留存 | 4 个原始制品 SHA-256/大小/ZIP CRC，8 场 demo 与 raw 哈希核验通过；8 场保存结果通过新身份校验 | 本地副本，不是异机备份；[留存清单](acceptance/7.41f-2026-10-06-preservation.json) |
| 合并触发的新比赛采集 | [37926671670](https://github.com/xrfc/dota2-timing/actions/runs/37926671670) 已主动取消 | 不属于本次分支整合验收，不用其结果代替固定样本 |

缓存修复先增加回归用例，最初 12 项中的 10 项在修复前失败；最终新增 18 项检查，覆盖 normalized 改动、清单缺失/旧版本、来源返回、跨玩家引用及合法/伪造英雄别名。更广的来源合并、迁移、资源管理并未因此完成。

真实数据仍为原固定批次 3 场机械审计通过、5 场隔离，完整训练准入保持 held；游戏画面对照和实际模型未完成。下一步是当前 main 对八场原 demo 在新工作区重解析并比较，再进行人工语义核验。以下 47、66、75、87 等数量及旧环境描述仅属于其注明日期的历史验证，不能当作当前结果。

## 1. 历史基线证据

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

工程基线：[364d9ad](https://github.com/xrfc/dota2-item-timing/commit/364d9adf07373e925c9d420b5804403f866c432e)，[成功 CI](https://github.com/xrfc/dota2-item-timing/actions/runs/36997970952)。这是原基础设施基线的验证记录；后续修改的验证单独列出。

2026-10-02 文档核验：14 份 Markdown、99 个仓库相对链接、7 个 JSON 契约示例通过检查；24 次 CLI 调用通过，覆盖帮助、重复 demo、doctor/status、数据集构建、JSON 导入/去重/标注/事实复盘和旧报告入口。检查在临时工作区使用现有 Python 依赖执行，没有重新安装 Gem 或解析真实 demo。当时运行代码与上述基线一致。

2026-10-03 仓库整理核验：共享存储模块迁移后，工程 47 项测试及 Ruff 检查通过；学习生成器 10 项标准库测试和教学/个人记录规则 6 项 JavaScript 测试通过。所有当前 Markdown 相对链接与组件源码路径存在，正式包不包含学习代码。学习测试详见 [learning/](../learning/README.md)；该次云端环境禁止浏览器所需的进程通信，本地未完成真实浏览器核验；独立 Chromium 检查由 Ubuntu CI 执行，其结果以当次工作流为准。

## 2. 开发者复现命令

仓库根目录，Python 3.11+：

```bash
python scripts/bootstrap.py --replay --data --dev
python scripts/check.py
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

新增工程测试范围：

- [缓存与身份](../tests/test_cache_identity.py)：双输出完整性、热缓存来源、新 catalog 追踪、raw 玩家与别名绑定。
- [数据准备](../tests/test_data_preparation.py)：清洗、缺失与任务 mask、样本快照和 train-only 预处理。
- [真实验收](../tests/test_real_acceptance.py)：采集/审计规则与隔离；不能替代独立游戏画面对照。
- [观察上下文](../tests/test_observer_context.py)：上下文引用、可见性与截止时间边界。
- [训练准入](../tests/test_training_admission.py)：默认 held、样本/玩家/特征/任务绑定及拒绝路径。

模型测试通过临时脚本生成受控产物和预测，仅用于验证协议。没有深度学习训练，也不能把接口桩指标用于报告效果。当前自动测试不能替代真实 demo 的固定回归集。

## 4. 真实回放验收矩阵

每个样本至少记录原文件/demo/raw/normalized 哈希、parser/adapter/代码版本、补丁、平台、角色来源、核验记录。此矩阵区分“有导出”与“已人工确认语义”：

| 能力 | 当前状态 | 所需证据 |
|---|---|---|
| 购买 key/tick/引用 | 8 场 raw 引用审计；一场 346 条与 OpenDota 完全一致 | 其他比赛事件对照和人工游戏事件核验 |
| 购买漏检/合成/送达 | 未完成 | 独立人工事件集合，误检/漏检分母与语义分类 |
| 暂停感知时钟 | 真实导出与 Gem 转换一致；发现暂停边界状态冲突 | 暂停前/中/后的游戏画面核验及冲突处理规则 |
| 位置与坐标语义 | 导出/受控测试通过；真实待验 | 坐标、时间、死亡/复活与采样覆盖对照 |
| gold / net_worth / 补刀反补 / xp_progress | 已有真实分钟对照，存在数值差异与 XP 语义冲突 | 采样边界、游戏 UI、XP 语义及缺失片段 |
| 截断/不完整回放 | 部分提示；资格规则未实现 | 完整/缺失/截断样本和训练排除结果 |
| 跨补丁/平台 Gem 能力 | 未形成矩阵 | 精确版本和范围逐项记录 |
| 真实模型复盘 | 未实现 | 独立评估、错误案例与适用范围 |

模板见[操作指南](workflow.md)。先选择有权使用的少量固定回放发现问题，再扩样本；“看了 20 条没有异常”不能作为总体准确率或完整性结论。

## 5. 交付验收

2026-10-03 新增的数据准备学习任务见 [L01–L12](../learning/docs/roadmap.md)，逐场/逐样本的正反例要求见[开发流程验收矩阵](../learning/docs/development-workflow.md)。这些是学习任务的完成条件，不包含在历史 47 项或当前 122 项工程测试通过的声明中；填写模板也不代表执行了验收。

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
