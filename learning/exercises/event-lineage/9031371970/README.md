# 第一课：追踪灰烬之灵的一次魔瓶购买

日期：2026-10-10。代码基线：`d0be28252e16d67b2ba7e18252825b5a02ea955f`。

## 本次结论与边界

比赛 `9031371970`，玩家槽位 `0`，英雄 `106 / npc_dota_hero_ember_spirit`。
保存的 Gem 数据记录：游戏时间 **122 秒（02:02）**、tick **9196**，有一条 `item_bottle` 的 `PURCHASE` 事件。

18/18 项程序核对通过，包括原始压缩回放与 Gem JSON 哈希、比赛和玩家身份、事件 tick/时间、当前转换与清洗代码重现、样本重现，以及保存的整场数据身份校验。

本次从保存的 Gem JSON 重做转换、清洗与选定玩家的样本生成，**不是重新解析 `.dem` 二进制**。历史机械审计为 passed，不代表人工游戏语义核验通过。未打开游戏客户端，未确认到货时刻、背包位置或购买合理性；训练准入仍为 held。

## 1. 来源：不要从一张无来源表格开始

- 回放：外部证据目录内的 `replays/9031371970.dem.bz2`（仓库不含二进制回放；见[路径与恢复](../../../../docs/knowledge-maintenance.md)）。
- 原始 Gem JSON：原始回放与工作区 ZIP 内的 `workspaces/9031371970/cache/matches/476dfa6a7b7328121c17103ab6fd2ea0ea72424162742d1608eeb16bb4296ede/raw-gem.json`。
- 最终清洗与样本：最终审计 ZIP 内的 `exports/9031371970/`。
- 完整哈希、归档成员路径和核对结果见 [trace-result.json](trace-result.json)。

哈希是内容指纹：本次重算值与先前留存值一致。它证明文件内容一致，不证明解析器对游戏的理解必然正确，也不是本次重新证明从二进制到 JSON 的转换。

## 2. 原始记录：先回答谁、什么、何时

原始 JSON 路径为 `players[0].purchase_log[6]`，数组从 0 开始，即第一名玩家的第七条购买记录：

```json
{
  "tick": 9196,
  "log_type": "PURCHASE",
  "target_name": "npc_dota_hero_ember_spirit",
  "value_name": "item_bottle",
  "timestamp_s": 345.933349609375,
  "game_time_s": 122,
  "source": "s2_direct"
}
```

这是原始事件的关键字段摘录，不是完整事件。这里的“原始”是解析器导出层，并非 `.dem` 的原始字节。

身份同时核对了原始 `player_id=0`、清洗后 `player_slot=0`、两边 `hero_id=106`，以及事件目标英雄名。数组位置本身不是足够的身份证明。

## 3. 时间：为什么 345.93 秒不是游戏内 05:45？

`timestamp_s` 是事件的引擎时间，`game_time_s` 是映射后的游戏时间。tick 是回放时间步编号，也不是视频帧号。

此场保存的时钟参数：

- `game_start_tick=5540`
- `game_start_time_s=224.06668090820312`
- `net_tick_offset=1183`
- `pauses=[]`

实际调用 Gem 的 `game_seconds_at(9196)` 得到 122。当前 Gem 在具有引擎时间锚点时，按如下方法计算整秒：

```text
round_half_up((tick + net_tick_offset - paused_ticks) / 30)
  - round_half_up(game_start_time_s)
= round_half_up((9196 + 1183) / 30) - round_half_up(224.0666809)
= 346 - 224
= 122
```

不要自行用 `tick / 30`，也不要简单减完再截断。本例没有记录暂停；其他比赛还必须处理暂停。这里验证的是解析数据与映射算法的一致性，画面时间仍待独立核验。

## 4. 统一格式与清洗：变简洁，但不能丢证据

项目真实适配器 `canonicalize_match` 产出：

```json
{
  "time": 122,
  "key": "bottle",
  "source_tick": 9196,
  "source_ref": "players[0].purchase_log[6]"
}
```

- `item_bottle → bottle`：去除统一前缀。
- `game_time_s → time`：统一字段名；已有事件时间优先，没有时才回退到时钟映射。
- `source_ref`：回到原始 Gem JSON 的地址。

`clean_match` 检查时间、物品键等，保留该事件并补充 `input_ref`。`input_ref` 指向清洗输入，`source_ref` 指向原始 Gem；这条记录两者恰好相同，其他记录不能假定相同。

本次使用当前项目函数重算，结果与归档中的该清洗事件完全一致。没有改动原始证据。

## 5. 从事实到机器学习样本

追踪对应样本 `9031371970:0:120`：比赛、玩家槽位、观察截止时间。

```text
02:00，观察截止 T=120          02:02，购买魔瓶             03:00，预测窗口结束
       X：只能看这里及之前 ───────── y：观察 (120,180] ──────────┤
```

保存的 X 部分字段：`hero_id=106`、`time_seconds=120`、`last_hits=6`、`net_worth=966`、`recent_purchase_count=0`。这些是保存的观察值，不是已独立核验的游戏真值。

`recent_purchase_count=0` 表示配置的历史窗口 `(0,120]` 内没有已记录购买，不表示开局没买东西，更不表示背包为空。开局的负时间购买不在这个窗口。

保存的 y（购买标签部分）：

```json
{
  "item_action": "other",
  "item_mask": true,
  "item_reason": "next_observed_purchase"
}
```

为什么不是 bottle？当前候选类别是 `power_treads`、`desolator`、`black_king_bar`。魔瓶不在其中，所以映射成 other。other 不是没购买，也不等于“错误选择”。

`item_mask=true` 只表示按此样本规则该购买标签可用，不等于整场获准训练。

`trace.label_refs` 包含 `players[0].purchase_log[6]`，`trace.feature_refs` 不含这条购买。当前代码重新生成的 X、y、trace 与保存样本分别完全一致。

这就是防止未来信息泄漏：02:02 的购买可以成为 02:00 的答案，但不能提前放进 02:00 的输入。

该玩家没有完整购买覆盖声明（`purchase_coverage=null`），因此这里最多称为“下一次已观察到的购买”，不是独立证明期间没有漏掉其他购买。没有记录时也不能随意制造 `no_purchase` 标签。

## 6. 亲手复查

在仓库根目录执行（先安装 replay/data 依赖，并恢复外部证据）：

```bash
.venv/bin/python learning/exercises/event-lineage/9031371970/trace_event.py \
  --evidence-root /path/to/dota2-timing-evidence/7.41f-2026-10-06
```

[脚本](trace_event.py) 只读取原证据，使用当前项目函数重现，在临时目录做身份校验，然后默认写入忽略的 `learning/output/event-lineage/9031371970/trace-result.json`；本课提交的 `trace-result.json` 是原始历史核对结果，不自动覆盖；不会训练、改代码或改原始归档。

可对照的项目源码：

- `src/dota_items/sources/gem_replay.py`：统一格式与玩家槽位转换。
- `src/dota_items/data/cleaning.py`：清洗规则与输入引用。
- `src/dota_items/data/features.py`：历史窗口、未来窗口、标签及追踪表。
- `src/dota_items/workflow/validation.py`：来源和身份校验。

## 7. 你先回答的三个问题

1. 如果把 02:02 的“买了魔瓶”放进 02:00 的输入，会造成什么问题？
2. `other`、`no_purchase`、`coverage_unknown` 的区别是什么？
3. 这条记录为什么不能直接支持“02:02 买魔瓶是最佳决策”？

下一步人工核验定位：打开比赛 `9031371970`，选择灰烬之灵，观察约 01:55—02:10 的购买提示、金钱变化、储藏处与信使。购买和送达要分别记录；保存能支持判断的画面与游戏内时间。没有明确画面证据时保留“未确认”，不要填成通过。
