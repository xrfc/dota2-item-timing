# 训练准入与桌面核验交接

**文档定位（2026-10-10）**：本页维护既有回放/训练基础设施或其历史证据；当前开发优先级统一见[7.41f 主线](development-mainline.md)，新推荐模块约束见[模块边界](module-boundaries.md)。既有通用格式不因此改成仅支持7.41f；历史核验与 held 状态不变。

更新：2026-10-09。当次代码基线为 `main / 725f35c`（本轮实现核对c6a5e1f，门禁不变）；训练门禁首次实现于 `5ac0566`，现已合入主干，不代表真实数据已通过核验。

## 本轮边界

`prepare`、`build-dataset`、`build-samples` 继续允许生成待审材料，方便定位问题。
普通 `train` 对真实数据默认拒绝；必须提供绑定**样本快照 ID、manifest 哈希、特征版本、全部比赛与所选玩家**的人工审查记录。
旧观察快照和没有审查的旧样本仍可读、可检查，但不能直接用于真实训练。
明确 `synthetic_only` 且全部比赛标注 synthetic 的快照保留接口测试路径；这不是训练资格或真实性鉴定。

当前只接受 `coach-features/1` 的 item/route 模仿任务。两种任务都使用相同 X，故仅申请 item 也必须核验位置、经济等全部输入域。
observer JSONL、新视野/库存/血魔通道、gank/反制模型不在获准范围，不能偷偷拼入 X。
门禁校验声明与证据完整性，不签名、不自动判断截图真实性，也不能审计任意训练脚本内部是否遵守权限。
`register-model` 的历史运行兼容路径未改造；这不是所有入口的统一质量系统，D01/D05 仍只部分完成。

## 生成与检查

先按现有流程生成观察快照和样本快照。下列 `SAMPLE_DATASET_ID` 必须替换为 `build-samples` 返回的 ID：

```bash
python coach.py --workspace coach-workspace/real admission-template SAMPLE_DATASET_ID
python coach.py --workspace coach-workspace/real check-admission SAMPLE_DATASET_ID --admission data/review/admission.json
python coach.py --workspace coach-workspace/real train SAMPLE_DATASET_ID --trainer path/to/train.py --admission data/review/admission.json
```

第一条命令只输出 JSON，所有检查默认 held。可将输出保存为 UTF-8 JSON；不要将终端报错写入文件。`init` 同时导出 `contracts/admission.schema.json`。
第三条仅说明未来接口，本轮不训练，仓库仍没有实际训练器。

记录 `coach-training-admission/1` 的字段：

| 字段 | 要求 |
|---|---|
| dataset_id / manifest_sha256 / feature_schema | 模板生成，不得借用其他快照；数据、参数或预处理变化后重新核验 |
| tasks | 非空且无重复的 item/route 子集，不表示决策正确率 |
| status / reviewer / reviewed_at / limitations | 总状态；真实审查人、日期、抽查覆盖范围和未覆盖边界 |
| evidence_files | 相对 admission.json 所在目录的文件路径 → SHA-256；禁止越出该目录 |
| matches | 精确覆盖快照中的全部比赛和所选 player_slots，不可遗漏 validation/test |
| checks | 每场固定 pipeline、clock、positions、economy、purchases、labels_and_masks 六域 |
| 每域 status / compared / mismatched / missing | 默认 held；passed 需 compared > 0、错误/缺失均为 0。分母是事先约定的核验点，不是全场准确率 |
| 每域 evidence / notes | 引用 evidence_files 中的文件；写清时间点、玩家、核验方法、分母和结论 |

未观察到、无法打开回放、没有独立对照均保持 held。当前使用严格零错误规则；不能删掉失败核验点来通过。
发现问题应修复或重新定义更窄的特征契约并重新构建，不能把 missing 改成 0。
单个核验点满足格式检查不代表足够的科学证据；人工必须在 limitations 和报告中说明抽样充分性。
训练启动前冻结核验 JSON 与证据副本到运行目录，退出后复验哈希，并检查模型声明的特征和任务没有超出核验范围。

## 两个账号的分工

| 当前账号 A | 桌面账号 B |
|---|---|
| 准入契约、CLI、训练入口检查、回归测试、工程文档 | 游戏画面对照、固定回放恢复、Windows 复现、核验记录 |
| 统一基线 `main`（本次核对 `725f35c`） | 从核对后的 main 新建 `audit/desktop-semantic-review`；该名称是建议，不代表远端已有此分支 |
| 不宣称已做客户端核验 | 不修改 A 的 admission.py、jobs.py、cli.py 或测试来绕过门禁 |

B 先读取 README、project-status、observer-context、real-data-acceptance 及本文件，确认 Git 提交与工作区是否有未提交改动。
先复现 demo/doctor/status；需要解析时安装 replay/data/dev 依赖。
固定八场已在当前 OpenClaw 工作区本地留存，位置、清单及恢复限制见[证据留存](real-data-acceptance.md#固定证据留存与缓存修复2026-10-09)；桌面端不自动共享这些文件。优先恢复并校验固定三场 `9031383523`、`9031384340`、`9031371970` 的原始回放，哈希依据 `docs/acceptance/7.41f-2026-10-06.json`。
旧比赛回放可能已不可下载；找不到时如实列出缺失及来源，不用新比赛冒充固定样本。

核验记录至少包括：比赛、补丁、slot、游戏时间、解析 tick/source_ref、导出值、客户端值、证据相对路径和哈希、结果及原因。
每场覆盖开局、中段、后段以及实际存在的暂停、购买、可见→消失、死亡→复活等边界；没有发生的事件记未覆盖。
按两个方向检查：导出事件是否真实存在；从游戏画面选择的事件是否被导出。分别保留错误与漏检分母。

基础六域用于未来旧 X 的准入。新增可见性、库存槽位、hp/mana 单位、死亡复活另存上下文核验报告，仍不授予 observer 训练资格。
尤其核查早期 `max_mana` 约 51.375 的原值，不猜倍率；不要以购买代替持有、库存代替立即可用。
无法操作游戏客户端时，可先完成解析与待核验时间点清单，再请用户只提供缺少的截图/录像。

原始 demo、工作区和大量截图放本地 data/ 或外部存储，不提交仓库。B 的代码提交限定为必要的独立核验辅助脚本及脱敏报告；若发现解析 bug，记录复现与建议，单独提交，不直接改 A 的门禁。
B 最终交付：环境/提交 SHA、执行命令及退出结果、逐场核验表与证据清单、仍 held 的原因、可独立复验的下一步。不存在证据时不生成 passed 记录，不开始训练。
