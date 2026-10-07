# 视野、战斗与英雄状态接入

更新：2026-10-07。已接入可追溯通道和按观察阵营生成的上下文。实际教练模型、gank/反制标签、冷却/充能与字段的游戏画面语义验收尚未实现。

## 使用入口

```bash
python scripts/bootstrap.py --replay --data --dev
python coach.py --workspace coach-workspace/context-v3 prepare /path/to/match.dem.bz2
python coach.py --workspace coach-workspace/context-v3 observe PREPARATION_ID --player-slot 0 --time 600
```

替换 prepare 返回的 ID；slot 为天辉 0–4 或夜魇 128–132，time 为比赛秒。observe 校验产物哈希后读取清洗数据，拒绝不存在的玩家、越界时间和没有 context 的历史产物。输出是观测证据，不是模型建议。

使用独立工作区保存新解析版本；同一工作区同场不同内容仍拒绝覆盖。旧 preparation /1、/2 可继续读取，旧规范化 JSON 仍可准备，但没有捕获的字段不能凭空补齐。

## 三层数据

| 层次 | 文件/版本 | 内容与边界 |
|---|---|---|
| 原始证据 | `raw-gem.json` 或包内 `raw.json` | Gem 默认结果追加 `coach_state_snapshots` 与 `coach_capture_version`；含隐藏敌方状态和事后信息 |
| 规范化上下文 | `cleaned.json.context`，`coach-context/1` | 7 类通道，保留原 payload、tick、时间和来源；不能整包当实时特征 |
| 玩家视角 | `observer.jsonl`，`coach-observer/1` | 自己的状态、敌方可见性与最后已知位置、明确对己方可见的近期战斗；标记 `semantic_review_required` |

prepare 生成 `observer.jsonl`。build-samples 生成 `train.observer.jsonl`、`validation.observer.jsonl`、`test.observer.jsonl`，按所选玩家和比赛划分，以相同 `sample_id` 对齐原有特征。旧输入没有 context 时 observer 表为空，不能据此断言没有敌人或事件。

**原有 `coach-features/1`、NPZ 的 X 以及购买/位移标签保持原定义。** 新上下文是独立的嵌套 JSONL，尚未编码成新模型张量。训练器需显式选择契约，不能直接拼入 raw、全场统计或未来标签。

## 已接入通道

每行统一为 `time/source_tick/source_ref/payload`。payload 保留原始记录；source_ref 指向 raw 中的相同行。缺少通道为 null，有通道但无记录为 []。available 只表示通道可用，不宣称事件完整率。

| `context.channels` 键 | 保存内容 | observer 当前使用 |
|---|---|---|
| `hero_visibility_events` | 玩家/实体身份，双方 visible/hidden/unknown | 敌方可见性、最后可见位置、消失时间 |
| `entity_visibility_events` | NPC 可见性、身份、生命周期 | 留作证据 |
| `combat_log` | DAMAGE、HEAL、DEATH、ABILITY、ITEM、MODIFIER_ADD/REMOVE、BUYBACK | 仅己方可见标记明确为 true 的部分 |
| `wards` | 守卫位置、放置和生命周期 | 全知证据，不直接输出敌方眼位 |
| `smoke_events` | 开雾、成员、生命周期 | 全知证据，不假设己方知道敌方开雾 |
| `vision_modifiers` | 显形/反隐效果、配对与结束证据 | 不冒充完整地图视野 |
| `coach_state_snapshots` | 血魔、等级、存活、技能等级和库存时序 | 只向 observer 输出自己的状态 |

位置复用已有 `position_log`。视野保留最多提前 3600 秒的赛前转换，避免丢掉开局状态；其余新增通道限定比赛开始至结束。时间统一通过 Gem 暂停感知时钟计算，排除数保存在 `context.excluded`。

## 状态采集与版本

默认 Gem JSON 没有完整库存/血魔/存活时序。新增采集复用 `PlayerExtractor`、其他默认提取器及组装器，保留 dense snapshots；没有重新实现回放协议或使用全局 monkey patch。

- 保存 `hp/max_hp/mana/max_mana/level/life_state`、`ability_levels`、`items`、实体身份、player_id 与 tick。
- `items` 是槽位数字到原始物品名的映射，范围为 Gem 扫描的 0–16；不新增信使货物、物品实例生命周期或“立即可用”推断。
- 保存 `inventory_handles/inventory_empty_handle/inventory_unknown_slots/inventory_complete`。空槽位常量复用 Gem 的 **0xFFFFFF**；缺 handle 或非空物品无法解析才标记未知，并校验标记与 handle 证据一致。
- 血魔和存活字段直接读取可空实体值，区分真实 0 与读取失败 null；无效等级为 null。空技能等级表不证明全部技能未学习。
- 复用约 30 tick 的采样间隔，不宣称每帧或精确交付时刻。槽位含义需按补丁核验，不直接继承上游历史注释。
- mana/max_mana 暂按解析原值保留：本批早期样本出现最大魔法约 51.375 等数值，游戏内单位/解码语义待核验。没有猜测倍率修正，不能据此宣称某技能可施放。

扩展使用 Gem 部分内部 API，因此固定 `gem-dota==0.10.0`，升级前必须跑真实回归。规范化为 `gem-adapter/3.0`，采集为 `gem-state-capture/2`，准备为 `coach-preparation/3`。缓存新增相关适配器源码指纹校验，并保留 raw 哈希校验；这不代表所有缓存迁移风险已解决。

## 观察阵营和缺失规则

1. 只用 `time < cutoff_seconds` 的完整时间桶。Gem 输出整秒，排除截止秒内事件避免后续 tick 混入；不是亚秒级实时系统。
2. 最后可见位置须在截止前、该位置 tick 对己方可见、实体身份仍对应。隐藏期间不更新；unknown 与 hidden 分开。
3. `hidden_since/hidden_for_seconds` 只在同一实体观察到 visible→hidden 后生成；初始隐藏、unknown→hidden 或实体复用时不猜起点。
4. 不输出敌方库存、血魔、技能等级、赛末装备或全场统计；也不将敌方购买当作己方已知装备。
5. 自身状态过旧为 stale，同游戏秒不同状态为 conflicting，缺失为 unavailable；此时 `self_state=null`，不补 0。默认 30 秒陈旧阈值仍需针对 gank 调整。
6. 战斗窗口统计所有明确对己方可见的事件，展示最多最近 50 条并标记 `events_truncated`；null 可见性不当作 true。这不是全部真实战斗计数。

网络可见性不证明玩家实际看了小地图。守卫/效果的未来结束时间、完整开雾成员等只留在证据层。

新通道校验结构、时间、身份、数值和来源。非法记录默认隔离整个通道，保留输入和原因，避免丢掉一次视野转换后继续误判可见；`invalid_policy=reject` 则拒绝。原始 payload 篡改或派生时间不一致会拒绝导入。

## 验证与复现

[回归测试](../tests/test_observer_context.py)覆盖隐藏/未来信息扰动、未知、截止秒、实体复用、状态冲突、非法转换、证据篡改、空槽位、赛前视野、划分和 CLI 边界。

```bash
python scripts/verify_context_replays.py --replays /path/to/replays --output data/context-check --match-ids 9031383523 9031384340 9031371970
```

该入口按[固定清单](acceptance/7.41f-2026-10-06.json)校验压缩文件 SHA-256，逐场重新解析二进制，每场上限 600 秒。只读本地 demo，不重新发现/下载比赛；已有报告拒绝覆盖。报告保存通道行数、缺失、库存完整性、来源/代码指纹、样本对齐及真实隐藏坐标扰动检查。新任务训练准入始终保持待审。

## 下一阶段

| 顺序 | 工作 | 验收标准 |
|---|---|---|
| 1 | 核验可见/消失、库存槽位、血魔单位、死亡/复活 | 独立游戏画面对照，记录错误/缺失分母；非空不等于正确 |
| 2 | 将通道版本、缺失门槛和语义状态接入统一准入 | held、未审计或不兼容数据不能进入对应任务快照 |
| 3 | 敌方已知装备与技能/装备可用性 | 核验观察权限；补冷却、充能、交付、禁用，不用购买代替持有 |
| 4 | gank 事件和反制任务标签 | 区分主动接战/被突袭、无死亡突袭和未知负例，人工复核 |
| 5 | 新模型输入编码和独立评估划分 | observer 张量 Schema、仅训练集拟合、固定比赛/时间留出，再训练 |

先完成小范围证据核验，再扩大英雄/补丁或模型复杂度。本轮让核验可执行，尚不能自动判断决策是否正确。

## 2026-10-07 实测结果

固定 3 场均重新解析 demo 二进制并完成 prepare、来源校验、样本 ID 对齐和真实隐藏坐标扰动检查。87 项工程测试、10 项学习 Python 测试及 6 项 JS 测试通过。

| 比赛 | observer 样本 | 状态快照 | 英雄视野变化 | 战斗事件 | 本次解析与审计秒数 |
|---|---:|---:|---:|---:|---:|
| 9031383523 | 620 | 18540 | 3037 | 42556 | 122.921 |
| 9031384340 | 710 | 21080 | 2869 | 57688 | 165.323 |
| 9031371970 | 780 | 23400 | 3566 | 96572 | 209.843 |

共 2110 条玩家视角样本、63020 条状态快照。此次状态字段均有值，所扫描槽位均已解析为物品或空槽位；这不证明其游戏语义/单位正确，也不覆盖未扫描的状态。三场清洗隔离均为 0；原购买/位移样本数与上一轮一致。

运行耗时仅为本次环境观测。逐场数据哈希、代码指纹、缺失统计和视野状态分布见[固定报告](acceptance/context-2026-10-07.json)。新任务训练准入仍为 held，未进行游戏客户端人工对照。
