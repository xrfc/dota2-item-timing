# 数据、任务与接口契约

设计日期：2026-09-29。**本文全部是目标契约草案，不是当前可用 schema 或 API。**
现有 JSON/SQLite 结构见 [工程设计第 3 节](engineering-design.md#3-当前数据契约)。
实施 D01～D05 时只落地所需部分；数据集、快照和实验结构在对应阶段再创建。

## 1. 身份与版本必须分开

| 概念 | 身份/唯一性 | 规则 |
|---|---|---|
| 来源记录 source | 独立 source_id，引用输入 artifact | 同文件从两个路径取得可有两个来源记录，但不扩大逻辑样本 |
| 字节产物 artifact | SHA-256 原始字节；附大小与类型 | 压缩包、解包 Demo、raw JSON、标准结果分别计算，不混称一个 hash |
| 比赛 match | `match_id` | 正式有效 ID 才建立比赛；未知 ID 的输入可隔离保留，不伪造正式比赛 ID |
| 回放修订 replay_revision | 解包 Demo hash | 同比赛多个内容修订保留独立；不能只按 match_id 覆盖 |
| 解析推导 parse_key | Demo hash + 解析器身份/版本 + 解析配置 + 环境快照标识 | 相同内容和同规则可复用成功产物；压缩格式不影响该键 |
| 标准化推导 fact_key | raw hash + adapter/rule/schema 版本 + 标准化配置 + 相关静态资料 hash | 改标准化规则可复用 raw，无需重新解析 Demo |
| 执行尝试 attempt_id | 每次执行唯一 ID | 重试和强制重跑是新尝试；不覆盖失败/旧成功记录 |
| 事实集 fact_set_id | 已提交标准化产物的 ID | 指向一套自洽玩家/事件及质量；不得拼接不同运行的半套数据 |
| 数据集 dataset_id | 冻结清单的内容 hash | 成员、选择规则、元数据或版本改变即产生新数据集 |
| 分析/实验 analysis_id | 唯一运行 ID，附输入/配置/代码指纹 | 同数据可有多个分析；运行身份不等同数据身份 |

推导键使用明确字段与版本的规范化 JSON 编码再计算 hash，不能拼接无分隔字符串。
规范化规则需固定键顺序、UTF-8、有限数字与默认值，并保存实际配置快照；排除执行时间和本地绝对路径。
代码版本记录提交及未提交改动的内容指纹；正式可复现实验要求干净提交。
同键多次运行如语义输出不同，保留两次 attempt，标记非确定性调查，不默默选最新。

目标公共 JSON 契约中的 match_id 采用十进制字符串，避免未来 JS 客户端对大整数的歧义；
这是对当前整数契约的显式版本变更，不允许直接修改旧 `gem-adapter/1.0` 文件。
slot 仍用整数；所有 ID 均为身份而非统计数值。

## 2. 最小实体与关系

| 实体 | 必需信息 | 关系和约束 |
|---|---|---|
| artifacts | hash、字节数、media_type、相对路径、创建阶段 | 可被多个运行引用；路径必须在 data 根目录内 |
| sources | 来源类型、原文件名/脱敏来源、input hash、获取时间、可选 Demo hash | 不把认证参数写入 URL；原件不在本地时标记 external/missing |
| matches / revisions | match_id、revision hash、关联 source | 同 ID 多修订可共存；质量择优需要记录规则 |
| attempts | attempt_id、stage、推导键、输入/输出 artifacts、状态、时间、版本、错误 | 成功不可重写为新结果；取消/重试单独保留 |
| fact_sets | fact_set_id、match_id、revision/source、schema、规则、质量引用 | 完整记录所属产物；一次提交后不可就地编辑 |
| players / events | fact_set_id + slot；event_id、事件字段、证据 | 外键关联事实集，不能仅用 match_id 跨运行连接 |
| metadata_assertions | 对象、字段、值、状态、依据、作者/规则、版本、有效时间 | 用于 patch、角色等；冲突与选择决定可追溯 |
| dataset_manifests | 范围、选中事实集/玩家、排除清单、元数据快照、版本 | 同一比赛只能选择一个事实集；同一 match_id + slot 不重复 |
| analysis_runs | dataset/input ID、config hash、代码/环境、结果 artifacts | 报告页展示版本和质量范围；缺依赖时不可声称完整复现 |

这是逻辑模型，M1 不需要一次建齐所有表。SQLite 是可查询目录；JSON 产物保留不可变证据与清单。
定义哪个字段以哪个产物为准，避免 SQLite 与 JSON 成为两个可独立手改的事实源。

## 3. 事件、未知值与证据

### 3.1 有效购买事件

| 字段 | 目标类型/含义 | 必须满足 |
|---|---|---|
| event_id | fact_set 内稳定标识 | 包含源事件身份；重复购买不能仅按 item_key/time 去重 |
| match_id、player_slot | 比赛与玩家身份 | 对应当前事实集中的有效玩家 |
| event_kind | 首先仅 purchase_record | 新类型需要独立规则、核验与 schema 版本 |
| item_key、source_item_key | 统一 key 和上游原 key | 保留未知但合法非空 key；无法识别的原始值进入质量明细 |
| game_time_seconds | 有限数值，支持赛前负数 | 有明确时钟基准，不能用墙上时间、tick 或最终比赛长度代填 |
| source_tick | 可空整数 | 不用固定 tickrate 假装可转成游戏秒数 |
| time_basis | source_game_clock / derived_clock | 衍生时间保存转换规则和所依赖时钟证据 |
| provenance | artifact hash、引用类型、字段路径、规则版本 | 定位的是实际核验的证据产物 |

时间未知的原始观察仍保存在 raw 与 rejected/unknown 明细中，不作为有时间的有效事件。
之后若需要分析无时间事件，建立单独 observation 契约，不放宽已有有效时间线的意义。
过滤配方是业务规则，记录原因和计数；它不能意味着原始记录被删除。

目标证据引用使用 JSON Pointer，例如 `/players/0/purchase_log/3`，并与 artifact hash 绑定；
旧 `players[0].purchase_log[3]` 格式由兼容读入层处理。引用转义遵循
[RFC 6901](https://www.rfc-editor.org/rfc/rfc6901)，不能把字段路径当成可执行表达式。
时间来自游戏时钟换算时，可有多条证据引用；校验器既检查源事件，也检查转换依赖与规则。

### 3.2 元数据与未知状态

任何会用于筛选的字段至少保存 `value`、`status=known/unknown/conflict`、`source_ref`、
`method=observed/manual/inferred` 与规则版本。推断置信度可选，未校准时不造一个小数来表示“可靠”。

- patch 使用带命名空间的标识并保留原始 provider ID、可得 build、映射快照。只有验证过的映射才参与同补丁筛选。
- 角色使用明确的 pos1～pos5 或 unknown，并记录是人工确认还是推断；lane 信息单独存。
- 比赛开始日期保留 UTC 和来源；未知日期不能用导入日期替代进入时间测试集。
- 英雄/变体、物品价格和合成树绑定静态资料版本；静态资料包本身是带 hash 的 artifact。
- 人工更正追加 assertion 和选择决定，不改 raw；旧数据集仍引用旧的元数据快照。
- missing、invalid、empty、zero、not_observed 分开；null 只表示其字段契约约定的未知，不能一律填 0。

## 4. 质量与提交是两个维度

任务执行成功不保证数据适合统计。采用两个独立状态：

- **执行状态**：queued → running → validating → committed；终止分支为 failed / cancelled。
- **使用资格**：unassessed / qualified / quarantined / rejected，并附 quality_policy_version 与适用分析范围。

qualified 表示通过某个范围的门槛，不是整个回放绝对正确。局部语义不明可保存为 committed + quarantined
供排错和浏览；数据集只接收通过其门槛的事实集。研究使用资格不能由“退出码为 0”自动推导。

质量报告至少包含：结构、解析完成、证据一致性、时间可靠性、元数据覆盖、目标事件覆盖；
每项有 pass/fail/unknown、检查版本、证据和原因码。
源事件数应等于保留数 + 预期过滤数 + 异常丢弃数 + 暂不可判定数；分类互斥并在指定输入层统计。
不要把玩家级汇总与全场事件数混合相减。

## 5. 幂等、失败与恢复协议

1. 注册 attempt 与输入身份，取得写入权；解析子进程不直接修改主目录数据库。
2. 写独立 staging 目录，关闭文件后计算实际字节 hash，验证 JSON、证据、数量和质量。
3. 在同一文件系统内发布到新的不可变运行目录，保留完整 manifest；不覆盖旧运行目录。
4. 用短 SQLite 事务登记 artifacts、fact_set、质量与 committed 状态，按显式规则更新默认选择。
5. 读端只认目录中 committed 的完整结果；是否进研究集再看使用资格。

| 故障位置 | 应看到什么 | 恢复动作 |
|---|---|---|
| 解析/写 staging 中断 | 旧结果仍可读，新 attempt 未提交 | 标失败或取消；重新运行，不复用未知完整度的临时文件 |
| 发布文件后、DB 提交前 | 孤立不可变输出，不被正常查询选中 | 核验 manifest 后显式恢复登记，或列入可清理清单 |
| DB 事务失败 | 无半套新索引，旧选择不变 | 保留失败记录，检查磁盘/锁，有限重试 |
| 已提交文件后来缺失/改动 | 完整性检查失败，不再作为健康缓存 | 标记 damaged，受影响分析显示不可复现；从备份恢复或创建新运行 |
| 同键并发/重复任务 | 最多一个结果被设为有效选择 | 本地写锁与唯一约束；其他 attempt 复用已验证结果或重试 |

`damaged` 是产物健康状态，不把历史 committed 改写成“从未提交”；恢复操作留审计记录。
先保证进程异常的可恢复性；断电耐久性取决于文件同步、数据库设置和存储介质，未测试前不声称覆盖。
超时、资源限额和取消归入明确原因；失败重试不无限循环，也不在 schema/输入错误上反复重试。

## 6. 应用接口草案

以下名称表达未来用例，不是已实现 CLI 命令或 Python API；具体签名在各任务实施时冻结。

| 用例 | 输入 | 输出 | 关键约束 |
|---|---|---|---|
| ImportReplay | 本地路径、数据根、解析配置、重用策略 | task/attempt ID、阶段状态、fact_set ID、质量 | 缓存命中先校验；支持取消；不直接生成比较结论 |
| ValidateArtifacts | artifact/run/fact_set 选择、检查策略 | 结构化验证报告与健康状态 | 只验证不修补；修复是另一个显式操作 |
| RecoverCatalog | 待恢复目录、预览/执行选项 | 差异清单、恢复记录 | 默认预览，不自动信任孤立文件 |
| BuildDataset | 范围、元数据与事实集版本、质量策略 | 冻结清单、纳入/排除原因、计数 | 同场选择唯一事实集，来源冲突明确处置 |
| AnalyzeMatch | fact_set + slot、candidate config、可选 dataset | 结构化事实/比较结果、证据、局限 | 无参考集时降级为事实；不临时改范围凑样本 |
| BuildSnapshots / RetrieveCases | dataset、cutoff、特征与视角版本 | 快照或案例及距离解释 | 严格截止、排除自身、来源可追溯 |
| RunExperiment | 数据/划分清单、任务、基线与参数 | 指标、模型/预测、误差和环境清单 | 测试隔离；实验不改数据集 |

错误对象统一包含 code、stage、retryable、safe_message、attempt_id、局部 evidence ID；
预期原因至少区分 INPUT_INVALID、PARSER_UNSUPPORTED、PARSE_INCOMPLETE、RESOURCE_LIMIT、
EVIDENCE_MISMATCH、SCHEMA_UNSUPPORTED、CATALOG_CONFLICT、IO_FAILURE。
业务空结果属于有解释的结果状态，不一律算程序异常。日志不含认证串或完整聊天内容。

现有 CLI 的 JSON 行字段保留到迁移期；新增协议带版本，不能突然改变 stdout 的含义。
进度走 stderr，机器结果走 stdout。未来 HTTP API 使用任务 ID 查询状态，不直接返回服务器文件路径。

## 7. 数据集、快照与分析结果

数据集清单包含：schema、成员及所有相关 artifact hash、范围与排除规则、质量策略、元数据/静态快照、
创建代码版本、创建时间、每项排除原因与各层计数。创建时间不参与成员内容身份的定义，另存运行元数据。
manifest 的 hash 由无自引用的规范化内容计算；不要把 dataset_id 自身放进待 hash 的内容。

未来快照最少包含 match/slot/fact_set、cutoff_game_seconds、feature_schema、perspective、
各特征值/缺失状态、source_time 与 available_at_game_seconds。整局统计的可用时间不得伪装为 0。
取样点按“最后一个不晚于 cutoff 的已知观察”读取；不跨缺失区间或暂停盲目插值。
标签窗口、观察终止原因和已购目标状态与特征分列，防止标签被当成输入。

分析结果包含 input/dataset/config/代码/规则版本、任务、过滤计数、统计分母、结果值、证据列表、局限。
每个结果值应能定位到对应数据集与计算定义；UI 不重新计算另一个版本的指标。
涉及预测时增加 split ID、特征与标签版本、随机种子、基线结果和适用范围。

## 8. schema 演进与旧库迁移

领域 schema、数据库 migration、解析器、适配器、静态资料、质量策略和报告版本分别管理。
契约重大版本变化包括：字段改义、单位变化、事件类型含义变化或删除字段；兼容读取范围必须显式声明。
当前 Pydantic 拒绝额外字段，所以即使“只加一个可选字段”也要升级读取器和兼容测试，不能假定旧程序自然兼容。

v0.2.0 → 新契约建议采用**并存迁移**：

1. 备份旧 JSON、数据库与原始 Demo；记录旧库版本，迁移前做预检和空间估算。
2. 建新目录/目录库，验证 legacy raw，计算迁移时实际 hash；不伪造历史上并未保存的 hash 或版本。
3. 有 Demo 原件时按解包内容建立修订；缺原件但有 raw 时标记 legacy provenance，不能声称重新验证了原 Demo。
4. 重新构建事实集与引用，记录旧 source hash → 新 source/revision/fact_set 的映射。
5. 对比比赛、玩家、事件数量、已核验候选时间与排除明细，抽查报告；失败时回到旧目录。
6. 显式切换默认数据根。旧结果保持可读；迁移完成不自动删除旧库。

标准化输出可以重算，原始证据、人工标注、数据集选择与实验清单不能假定能再下载得到。
依赖升级通过同样的固定样本差异报告，不原地改写被冻结的实验数据。

## 9. 保留、删除与备份

未来默认保留已引用证据及最新可用结果；临时 staging 和未引用失败产物可按期限列入清理预览。
清理先遍历 source → run → dataset → analysis 的引用关系；删除会影响复现时先列出受影响结果并显式确认。
已冻结不意味着永不能删除隐私数据：需要删除时撤销相关数据集资格并保留不含敏感内容的失效记录。

本地备份至少包括目录数据库的一致快照、被引用 artifacts、人工标注和冻结清单；
保留独立副本，并用一次恢复到新路径的校验演练证明可恢复。
启用 WAL 后不得在活跃写入时仅复制主 `.sqlite` 文件当作一致备份。
原件外置时记录位置与可用状态；移动 data 不改其内容 hash，路径依赖通过数据根解析。
