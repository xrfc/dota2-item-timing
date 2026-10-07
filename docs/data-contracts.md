# 数据与模型接口契约

> v0.4 数据准备更新：`prepare` 已实现单文件清洗/特征/标签；`build-samples` 输出固定 split 的训练数组和 train-only 预处理。输入、错误策略、任务 mask 和操作示例以[数据管线](data-pipeline.md)为准。实际模型与真实字段验收仍待完成。

基线：**0.4.0 / 2026-10-05**。本文件描述已实现格式。派生样本和任务资格见[数据管线](data-pipeline.md)；完整来源修订和真实语义资格仍待补足。

## 1. 版本与校验来源

| 对象 | 当前版本 | 校验位置 |
|---|---|---|
| Gem 规范导出 | gem-adapter/3.0 | Gem 适配器与比赛校验器；兼容读取 2.0–2.2 |
| 导入缓存清单 | demo-import/1.0 | 旧导入流程 |
| 工作区配置 | coach-workspace/1 | WorkspaceConfig；导出 workspace.schema.json |
| catalog | coach-catalog/1 | Workspace 程序检查 |
| 标签 | 无独立版本字段 | Labels；导出 labels.schema.json |
| 数据集 | coach-dataset/1 | 清单身份和文件指纹校验 |
| 数据集观测契约名称 | coach-match/1 | 清单中的 observation_schema；没有完整 Pydantic 模型或导出 Schema |
| 数据准备配置 | coach-preparation-config/1 | 严格 PreparationConfig；导出 preparation.schema.json |
| 单文件准备 | coach-preparation/3 | 清单身份、文件哈希；仍可检查历史 /1、/2 |
| 规范化上下文 | coach-context/1 | 七类通道，payload/引用/时钟校验，缺失为 null |
| 玩家视角表 | coach-observer/1 | observer JSONL 与 observe 查询；新通道语义待验收，不改原 X |
| 特征 | coach-features/1 | data/features.py 白名单与时间规则 |
| 样本数据集 | coach-samples/1 | 来源、split、配置、环境、源码与产物哈希 |
| 预处理 | coach-preprocessor/1 | JSON 参数、固定列序、train-only 拟合 |
| 训练状态 | coach-run/1 | jobs 程序管理 |
| 模型描述 | coach-model/1 | ModelOutput；导出 model.schema.json |
| 登记模型 | coach-registry/1 | 清单身份、模型描述和文件指纹校验 |
| 预测 | coach-predictions/1 | Predictions + 复盘语义校验；导出 predictions.schema.json |
| 复盘状态 | coach-review/1 | reviews 程序管理 |
| 旧购买时间线/分析结果 | 0.1 | domain.py 中的事实模型 |

`init` 导出的 5 个 Schema 位于工作区 `contracts/`。Pydantic 契约拒绝额外字段及非有限浮点数，但并非所有字段都启用严格类型模式，部分输入可被转换。其余 JSON 对象不应假定拥有同样的完整 Schema 校验。

所有受控 JSON 使用 UTF-8；指纹序列化采用排序键、2 空格缩进和末尾换行。文件哈希为文件字节 SHA-256；身份哈希为上述 JSON 序列化的 SHA-256，ID 截取前 24 个十六进制字符。

## 2. 比赛、玩家和观测

比赛导入至少需要正整数 `match_id`、有效 `duration` 和非空 `players`。比赛 ID 在 JSON 中是数值，不是字符串；catalog 用其字符串形式作为对象键。玩家槽位必须唯一且属于天辉 0–4 或夜魇 128–132。槽位不等于 `players` 数组下标。

用于理解格式的最小合成样本：

```json
{
  "_fixture": "Synthetic documentation example; not expert play",
  "schema_version": "gem-adapter/2.2",
  "match_id": 1000000200,
  "duration": 300,
  "players": [{
    "player_slot": 0,
    "hero_id": 44,
    "purchase_log": [{"time": 180, "key": "boots"}],
    "position_log": [{"time": 180, "x": -3200, "y": -4100}],
    "economy_log": [{
      "time": 180,
      "gold": 700,
      "net_worth": 1200,
      "last_hits": 12,
      "denies": 1,
      "xp_progress": null
    }]
  }]
}
```

该样本没有独立 raw 证据；校验只能证明自身结构一致。Gem 导入另有 `raw.json`，规范 JSON 通过 `evidence_source` 和 `evidence_sha256` 引用它。

| 通道/字段 | 当前语义 |
|---|---|
| purchase_log.time / key | 游戏秒数、装备键；保留赛前负时间和重复购买 |
| purchase_log.source_tick / source_ref | Gem 原始 tick 和购买事件引用；普通 JSON 可无 |
| position_log.time / x / y | 自身世界坐标及游戏时间；不代表可达区域或路线动作 |
| position_log.source_tick / source_ref | tick 及 raw 中的三元组引用 |
| economy_log.time / source_tick | 此经济采样的时间与 tick |
| gold / net_worth | 未花费金钱 / 净资产；不是同一个量 |
| last_hits / denies | 原始补刀 / 反补采样 |
| xp_progress | 历史字段名，保存 Gem xp_t 原值；等级内进度的上游说明与真实样本冲突，语义待核验 |
| economy_log.source_refs | 每个非空经济字段到 raw 数值的引用 |

Gem 用暂停感知的 `game_clock.game_seconds_at(tick)` 转换时间，位置/经济只导出 `0 <= time <= duration` 的有效采样。无时钟时这些通道为空；缺失或非法经济值为 null，不补零、不插值。位置和经济分别排序，没有统一重采样时间轴。

购买缺失、空数组、非法记录含义不同：缺失可导入但有警告；空数组记为 present 并有空日志提示；非法购买会被新工作区拒绝。因而 present 不保证真的发生过购买，也不保证日志完整。

自定义 JSON 的位置/经济校验目前以 -1 作为时间排序初值，可能接受 [-1, 0) 的记录；这是待收紧的验证边界。新生成的数据应遵循非负观测时间。校验器不会重建 raw 的 game_clock 逐项验证导出的秒数，不能仅凭数值引用通过宣称时间语义已完全核验。

## 3. 证据引用

当前引用是受限路径语法，如 `players[0].purchase_log[2]` 或 `players[0].gold_t[3]`；**不是 JSON Pointer**，没有 eval。

外部 raw 模式会核对证据哈希及 match_id：

- 购买：核对装备、原始时间（存在时）和 tick。
- 位置：核对 raw 三元组 `[tick, x, y]`。
- 经济：核对非空字段对应的原始数值。

导入发布后 `evidence_source` 改为数据包内 `raw.json`。没有外部证据时，购买引用默认指向输入自身；这不提供独立解析证明。

预测解释的 `evidence_refs` 使用另一层引用：指向 **normalized.json** 中所选玩家的一整条 purchase_log / position_log / economy_log 记录，不能指向整局汇总或单一字段，且记录时间不得晚于决策时间。原始证据引用和预测解释引用不要混用。

## 4. 质量、标签和 catalog

`quality.json` 包含 `match_id`、`synthetic`、`warnings`、`channels`。每个槽位的 channels 包含：

- `purchases`：购买日志状态。
- `positions`：位置记录数。
- `economy`：至少一个经济字段有值的记录数。

这些数字不是覆盖率。尚无统一 `qualified/quarantined` 状态、完整解析证明、逐原因丢弃计数或死亡期间有效性判断。

标签：

```json
{
  "tier": "pro",
  "patch": "7.xx",
  "role": 1,
  "player_slots": [0],
  "label_source": "填写实际赛事或分数证据"
}
```

patch 是人工填写并精确比较的非空字符串，示例 `7.xx` 必须替换。tier 可为 pro/high_mmr/personal/unknown/synthetic；role 为 1–5，槽位列表非空且不重复、必须存在。每场只有一组标签；重复 annotate 覆盖当前组。工作区依据 `_fixture` 标记区分合成样本并限制重标，不能把它当成数据真伪鉴定机制。

catalog 顶层为 `schema_version` 与 `matches`。每条比赛记录包含 match_id、bundle_id、相对 path、files、demo_sha256（可空）、labels（初始为空）、synthetic、imported_at、channels、warnings。bundle_id 由数据包文件指纹映射生成。当前标签和 catalog 本身不属于只读证据；固定数据集会复制当时标签。

## 5. 工作区和数据集

默认配置：

```json
{
  "schema_version": "coach-workspace/1",
  "seed": 42,
  "validation_fraction": 0.15,
  "test_fraction": 0.15,
  "candidate_items": ["power_treads", "desolator", "black_king_bar"]
}
```

两个留出比例均在 (0, 1)，和必须小于 1；候选装备列表非空。candidate_items 目前用于事实报告，仍会进入数据集身份，因此改它也会改变新数据集 ID。

manifest 包含 schema_version、observation_schema、config、filters、matches、files、limitations、dataset_id、created_at。filters 包含 patch、role、hero_id、require_spatial、synthetic_only。

每条 matches / split JSONL 记录包含 match_id、bundle_id、player_slots、labels、channels、split、path。path 相对于快照目录；完整数据包位于 `matches/<match-id>/`。JSONL 每行一场比赛。

- 默认 tier 仅 pro/high_mmr；synthetic-only 模式仅 synthetic，禁止混合。
- 按 seed 与 match_id 哈希排序；validation/test 各取 `max(1, int(N * fraction))`，剩余为 train。无训练比赛时报错。
- 最少 3 场，6 场默认划分为 train 4 / validation 1 / test 1。
- require_spatial 仅要求位置数和可用经济行数都大于 0。
- ID 计算排除 dataset_id 和 created_at，包含其余清单内容及文件哈希。
- 筛选的 excluded 列表仅随命令结果返回，尚未保存到 manifest；需要留档时保存 stdout。
- 所选槽位是使用约定，快照没有物理剔除其他玩家或未来数据。

目前没有 features、labels、窗口长度、地图分区或动作词表的正式模型输入契约。

## 6. 训练器协议和模型描述

调用形式：

```text
<当前Python> <trainer.py> --dataset <快照绝对目录> --output <run/output绝对目录> --config <保存后的配置JSON>
```

配置必须是 JSON 对象，未提供时为 `{}`。工作目录为 trainer 所在目录，stdout/stderr 合并到 process.log；默认超时 86400 秒。程序成功退出且产物契约通过后 run 才变为 succeeded。

输出 `model.json`：

```json
{
  "schema_version": "coach-model/1",
  "framework": "pytorch",
  "feature_schema": "my-decision-features/1",
  "tasks": ["item", "route"],
  "artifacts": ["weights.pt", "preprocessor.json"],
  "metrics": {},
  "notes": "记录训练范围、实际评估和限制"
}
```

framework / feature_schema 非空；tasks 至少一个且只能 item/route。artifacts 非空且不重复，每项必须是 output 内非空普通文件，禁止目录穿越、符号链接和保留名称 model.json/registry.json。metrics 必填，可为空，值必须有限；框架不核验计算方式或性能门槛。

run_id 是 `run-` 加 16 位 UUID 十六进制片段。run.json 记录 dataset_id、状态、起止时间、配置、主脚本哈希、部分环境版本；成功时记录模型描述和文件指纹，失败时记录 error。状态为 running/succeeded/failed/interrupted，没有 queued/resuming；强杀可能残留 running。

register-model 只接受 succeeded run，复验数据集和输出。registry 包含 run_id、dataset_id、model、files、model_id、registered_at；ID 排除 model_id/registered_at，**包含 run_id**，所以不同训练运行即使权重相同也可得到不同模型 ID。

## 7. 预测器协议和复盘

```text
<当前Python> <predict.py> --model <登记目录> --match <normalized.json> --player-slot 128 --output <predictions.json>
```

预测器默认超时 3600 秒。模型目录包含 registry.json、model.json 和声明的产物。

```json
{
  "schema_version": "coach-predictions/1",
  "model_id": "填写本次登记的模型ID",
  "match_id": 1234567890,
  "player_slot": 128,
  "decisions": [{
    "time_seconds": 600,
    "task": "route",
    "observed_action": "由预测器描述的行动",
    "alternatives": [{"label": "候选地图区域", "score": 0.6}],
    "evidence_refs": ["players[5].position_log[30]"],
    "note": "填写当时上下文与局限"
  }],
  "limitations": []
}
```

这是格式示例，引用索引、比赛、模型和槽位必须与实际输入一致。score 示例没有模型依据。

限制：decisions 最多 10000；每个 decision 时间非负且不超过比赛时长；候选 1–10 个，label 最长 300 字符，score 在 [0,1]；证据 1–20 条；observed_action 可空、最长 300；note 最长 3000。候选分数不要求和为 1，也不代表校准后的胜率。

复盘还检查模型的 patch/role/英雄适用域、所选槽位、合成/真实一致、声明任务和时间引用。若比赛出现在关联数据集的任意 split，会添加“非独立泛化验证”的提示。observed_action 和 note 是模型输出文字，未逐项验证其事实含义。

review.json 包含 review_id、match_id、player_slot、model_id、bundle_id、mode、状态与时间；成功时有 report 路径。facts 模式也输出 facts.json/facts.html/report.html；模型模式另有 predictions.json 与执行日志。

## 8. 兼容和待设计接口

当前不会自动迁移 schema 或合并同比赛的多个解析修订。升级导致内容变化时，新建工作区重导入并保留旧数据集。旧缓存版本、绝对路径和 OpenDota 缓存策略见[操作指南](workflow.md)。

下一阶段应先定义独立来源身份、解析版本、质量资格及标注修订，再定义严格截止时间的训练窗口、动作/标签与评估输入。不要把这些规划字段写入现有 Pydantic 对象；extra=forbid 会拒绝未知字段。
