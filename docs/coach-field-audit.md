# 教练任务字段核查：视野、装备、技能与战斗

核查日期：2026-10-06。项目运行代码基线 `dc9113013ae061e6898a2e1b3ea1bc0d4f80245a`，适配器 `gem-adapter/2.2`，特征 `coach-features/1`。核对 Gem **0.10.0** 的固定源码提交 [`69234e61`](https://github.com/whanyu1212/gem-dota/tree/69234e61fb4752063e5b3a536403a22c34e068b8)。

## 结论与证据范围

当前正式特征只包含所选玩家自己的位置、五个经济字段和近期购买计数。Gem 的默认解析输出还定义了阵营可见性、守卫、技能/物品使用、伤害和死亡等字段；项目保存完整 Gem JSON，但没有将这些字段接入规范化、质量审核和特征层。血量、魔法、存活状态和逐时刻库存是另一类缺口：Gem 内部采样已有，默认 `ParsedMatch` JSON 没有保留完整时序。

本次检查包括：

- 项目适配器、清洗、特征、配置源码。
- [已完成验收的 8 场](real-data-acceptance.md) `cleaned.json`，以及各场 `features.jsonl` / `labels.jsonl` 的首行结构；8 场均为 10 玩家，结构与代码输出一致。
- Gem 固定版本的模型、默认 parse 接线、序列化、玩家/视野/守卫/信使提取器、战斗事件及组装源码。

**本次没有重新解析 demo，也没有对这 8 场的新增 raw 字段逐场计数或游戏画面核验。** “默认 raw 有字段”表示源码定义并接入默认序列化，不表示本批每场该字段非空、完整或语义已经验收。新字段进入训练前仍需恢复原始回放工作区并完成该项验证。此前的 3 场机械准入也不覆盖这些新通道。

以下分四级：A＝当前规范化/特征已使用；B＝Gem 默认 raw 有对应字段，项目未接入；C＝Gem 内部提取器有，但默认 raw 缺完整时序；D＝当前受核查的输出没有，需要新增采集、派生或外部规则。B/C 不等于训练就绪。

## 当前实际输出：A

| 通道 | 已有字段 | 范围和限制 |
|---|---|---|
| 身份 | `match_id`、`duration`、`game_mode`；`player_slot`、`hero_id`，个别别名修复有 `hero_identity` | 规范化 `patch` 为 null，小版本证据在独立清单中 |
| 购买 | `purchase_log[].time/key/source_tick/source_ref` | 排除配方和组合眼投影；不等于持有、可用或被对方观察到 |
| 位置 | `position_log[].time/x/y/source_tick/source_ref` | 保留双方各自位置；没有从某一观察阵营过滤敌方位置 |
| 经济 | `economy_log[].time/gold/net_worth/last_hits/denies/xp_progress/source_tick/source_refs` | XP 含义仍待核验；不能把敌方完整经济当作己方当时已知信息 |
| 特征 | `hero_id`、`time_seconds`、`x/y`、五个经济字段、`position_age/economy_age`、`recent_purchase_count`、`recent_<item>_count`、缺失标记 | 按当前玩家构建，没有敌我交互、视野、库存、技能、战斗特征 |
| 标签 | `item_action/item_mask/item_reason`、`route_dx/route_dy/route_mask/route_reason` | 下一次观察购买和未来终点位移；没有反制正确性、gank 或注意力标签 |

默认决策步长为 30 秒，历史窗口 120 秒、未来窗口 60 秒，状态允许最大 30 秒陈旧。这些是现有购买/位移任务的配置，不能未经核验直接当成秒级 gank 预警标准。`position_age` 是位置采样年龄，不是“敌方消失多久”。

实现：[规范化](../src/dota_items/sources/gem_replay.py)、[位置经济导出](../src/dota_items/sources/gem_observations.py)、[特征](../src/dota_items/data/features.py)、[配置](../src/dota_items/data/contracts.py)。

## 视野

| 级别 | Gem 字段/结构 | 能提供什么 | 缺口/注意事项 |
|---|---|---|---|
| B | `hero_visibility_events[]`：`tick/player_id/hero_name/entity_index/entity_serial/radiant_state/dire_state` | 英雄对天辉/夜魇的可见性变化；状态为 `visible/hidden/unknown` | 未导出游戏秒或接入玩家视角；unknown 不能当 hidden；不是玩家实际看了小地图 |
| B | `entity_visibility_events[]`：上述实体身份、`class_name/npc_name/team/active` 和双方状态 | 网络 NPC 的包边界可见性与生命周期 | 不等于任意地图点的完整战争迷雾；必须处理实体编号复用 |
| B | `wards[]`、玩家 `obs_log/sen_log`：`tick/player_id/placer/ward_type/team/x/y/expires_tick/killed_tick/killer` | 守卫放置、位置、消失/被击杀证据 | 敌方真实眼位不能直接给己方模型；生命周期判定含上游规则，需跨补丁核验 |
| B | `smoke_events[]`、`participants` | 开雾者/队伍、参与者、施加/移除 tick、部分位置和游戏时间 | 回放事后信息不一定在当时可见；不能直接作为敌方已开雾的输入 |
| B | `vision_modifiers[]`、`vision_modifier_pairing_issues[]` | 显形/反隐相关 modifier、对象、来源阵营、生命周期和证据缺口 | 不等于全地图可见性；需保留配对/结束时间的不确定性 |
| B | `combat_log[].visible_radiant/visible_dire` | 单条战斗事件的阵营可见标记，可为 null | 事件可见性不等同于英雄持续可见或库存可查看 |
| D | 最后可见时间/位置、消失持续时间、未知区间 | 可从可见性事件和合规位置观测派生 | 当前没有；不得在敌方隐藏期间更新“最后已知位置” |
| D | 完整地图雾区、地形/树木遮挡、玩家注意力 | 当前没有经过验证的对应通道 | Gem 几何视野估计不含完整遮挡；demo 数据不能直接证明玩家眼睛看了哪里 |

优先复用 Gem 的阵营可见性证据，而不是另造“以英雄/眼位为圆心画圆”的真实视野判定。上游 `assess_point_vision` 明确是有限几何模型，且位置可选最近邻而非只取过去；不能原样用于严格截止时刻的训练输入。

源码：[视野结构](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/results/models.py#L34)、[提取器](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/extractors/visibility.py)、[视野分析边界](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/analysis/vision.py#L324)。

## 装备

| 级别 | 字段/结构 | 能提供什么 | 缺口/注意事项 |
|---|---|---|---|
| A | `purchase_log` | 有时间与来源的购买投影 | 不能据此完整重建库存；原始事件的可见性未带入规范化购买行 |
| B | `players[].final_items` | 结束时按槽位保存的物品 | 是最终状态，不能回填到早期时间；不能用作早期特征 |
| B | `combat_log` 中 `ITEM` 事件；`players[].item_uses` | 有时间的物品使用事件；全场使用次数汇总 | 全场次数不是当前次数；事件不提供持续的冷却/充能状态 |
| B | `neutral_item_finds[]` | `tick/player_id/item_ability_id/item_key/item_tier`、增强物品相关字段 | 获得事件不等于全程携带或已对敌方暴露 |
| B | `courier_snapshots[]` | `tick/team/state/flying/x/y` | 此结构没有信使唯一身份、所属玩家和货物；无法据此确认哪件装备送达了谁 |
| C | `PlayerExtractor.snapshots[].items` | 带 tick 的物品槽位名称；上游扫描主装备/背包/储藏处槽位 | 默认组装只保留 `final_items`，逐时刻库存没有随默认 raw 导出；槽位规则需按补丁核验 |
| D | 物品实例 ID、充能、冷却、禁用、背包切换冷却、精确交付 | 当前受核查的输出没有完整字段 | 需要扩展实体采样；不能简单由购买或使用事件推断完整状态 |
| D | 敌方最后已知库存、首次被发现时间、信息年龄 | 当前没有 | 需逐时刻库存、观察权限与保守派生规则，英雄可见不自动证明所有槽位/状态都可查看 |
| D | 威胁类型、反制关系、推荐动作/正确性标签 | 当前没有任务契约 | 机制可复用版本化目录，情境和标签需另建；不能把对方的购买意图当作已知事实 |

Gem 内部逐时刻库存已提供基础，优先扩展其输出或复用其提取器，不重写回放协议。现存默认 raw 缺少这段完整时序，不能仅重跑清洗补回来，需要原 demo 重解析并保存新证据。

源码：[内部采样](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/extractors/players.py#L727)、[最终库存组装](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/results/assembly.py#L810)、[信使结构](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/extractors/courier.py)。

## 技能与英雄状态

| 级别 | 字段/结构 | 能提供什么 | 缺口/注意事项 |
|---|---|---|---|
| B | `combat_log` 中 `ABILITY`，`MODIFIER_ADD/REMOVE` | 使用者、目标、技能名、事件 tick/游戏时间、部分技能等级/效果时长 | 可空字段需保留缺失；效果结束/驱散证据可能不完整 |
| B | `players[]._ability_snapshots` | `(tick, {ability_name: level})` 列表，默认序列化会保留 | 私有字段，需要封装和版本测试；源码采样来自 dense snapshots，部分注释却称分钟采样，不能只信注释 |
| B | `ability_upgrades_arr/ability_uses/ability_targets` | 加点顺序、全场施法次数和目标汇总 | 汇总无完整时间上下文，不可直接用于早期决策 |
| B | `players[].level/life_state_dead` | 末次等级、累计死亡秒数 | 不是逐时刻等级和 alive/dead 状态 |
| C | `PlayerStateSnapshot.level/hp/max_hp/mana/max_mana/life_state` | 内部带 tick 的英雄状态 | 默认 `ParsedPlayer` 没有保留完整对应时序；需扩展输出并重解析 |
| D | 技能剩余冷却、充能、施法/引导状态、耗蓝、可施放条件、状态抗性等 | 当前受核查的输出没有完整时序 | 技能等级和施法事件不能替代可用性；需处理刷新、减冷却和禁用等机制 |

内部采样部分读取失败会用 `or 0` 回退。扩展时要保存可用性标记，不能把缺失 hp/mana 当成真实零值。敌方技能冷却即使可以从回放读到，也仍须区分事后真实状态与己方可推断状态。

源码：[状态结构和读取](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/extractors/_snapshots.py#L327)、[技能快照组装](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/results/assembly.py#L1210)。

## 战斗与目标事件

| 级别 | 字段/结构 | 能提供什么 | 缺口/注意事项 |
|---|---|---|---|
| B | `combat_log[]` 的 `DAMAGE/HEAL/DEATH/ABILITY/ITEM/MODIFIER_ADD/MODIFIER_REMOVE/BUYBACK` 等 | 有序事件，详见下方字段 | 未接入项目的规范化、证据校验、缺失处理与特征层 |
| B | `players[].kills_log/buyback_log/buybacks` | 击杀/买活事件及部分派生信息 | 需要处理分身、召唤物、复活，不等于任意时刻存活状态 |
| B | `damage* / healing / kills / deaths / assists / stuns_dealt` 等 | 全场统计；另有部分 `*_t_min` 分钟累计曲线 | 赛后总量不能直接用作过去时刻特征；累计曲线仍需时钟和覆盖校验 |
| B | `teamfights/opendota_teamfights` | 派生战斗窗口、击杀、伤害、参战者等 | 依赖死亡分组和规则，不等于完整交战或 gank 标签；可能漏掉无死亡的突袭 |
| B | `towers/barracks/roshans/aegis_events/tormentors/courier_deaths/objectives` | 建筑与地图目标事件 | 可用于构建目标时间线；敌我可观察性需要单独处理 |
| D | gank 开始/到达/结束、主动接战还是被突袭、避险动作、提醒价值 | 当前没有任务标签 | 需制定操作定义、人工核验正负例；“未来没死亡”不等于没遭遇 gank |

`combat_log` 具体字段包括 `tick/log_type/game_time_s/timestamp_s`、`attacker_name/damage_source_name/target_name/inflictor_name/value/value_name`、`damage_type/stun_duration/ability_level`、`location_x/location_y`、阵营、英雄/幻象标志及其 presence 标志、`will_reincarnate`、`visible_radiant/visible_dire`、modifier 时长/驱散信息和 `source`。位置和可见性等字段可缺失，不能凭结构存在就认定齐全。召唤物伤害归属应检查 `damage_source_name`，死亡统计应处理 `will_reincarnate`。

源码：[战斗事件](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/combat/log.py#L157)、[战斗窗口](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/extractors/teamfights.py)、[默认解析接线](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/api.py#L235)、[默认序列化](https://github.com/whanyu1212/gem-dota/blob/69234e61fb4752063e5b3a536403a22c34e068b8/src/gem/results/serialization.py#L74)。

## 补齐顺序与验收条件

1. **先核验并接入 B 类视野与战斗事件。** 从已保存 raw 做逐场字段非空/缺失率和事件样例检查，保留原 tick、暂停感知时间、原始引用和未知状态。接口存在不自动获得训练资格。
2. **建立观察阵营数据层。** 生成最后可见位置/时间和消失时长；隐藏期间不更新敌方已知状态；unknown 与 hidden 分开；事件和特征都遵守截止时间。新增“改变隐藏敌人的真实位置，不改变己方可观察特征”的防泄漏测试。
3. **复用 Gem 采样扩展 C 类输出。** 保存带来源和缺失标记的库存、血魔、等级、存活状态，版本化后重解析固定 demo。核验购买、背包/储藏处、死亡/复活等边界。
4. **再补 D 类装备/技能可用性。** 先确定最小英雄和装备范围，核验冷却、充能、交付与可观察权限；数据尚不可得时显式输出未知。
5. **最后定义任务标签。** gank 标签与提醒策略分开；敌方威胁和推荐反制分开；赛后标签与当时输入分开。只有相关通道完成真实验收后，才接入统一数据集准入。

本轮交付的是字段核查及接入缺口，未改变现有数据 Schema、解析器或训练能力，也不将现有 8 场升级为新任务的已验收训练集。
