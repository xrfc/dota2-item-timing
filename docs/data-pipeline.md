# Demo 到训练样本的数据管线

更新：**2026-10-09 / main 725f35c / 0.4**，清洗版本 `coach-preparation/3`。新增 context 与 observer JSONL，使用方法和边界见[上下文接入](observer-context.md)；原 X 数组保持原定义。本页描述已实现的数据准备；[8 场真实验收](real-data-acceptance.md)已完成机械检查，游戏语义仍有未解决项。入口是本地文件/目录，网页上传尚未实现。

## 最短使用路径

```bash
python scripts/bootstrap.py --replay --data --dev
python coach.py --workspace coach-workspace/real prepare /path/to/match.dem
```

`prepare` 自动初始化工作区，调用 Gem、清洗数据、生成特征/标签、导入比赛，并返回 `preparation_id`、`match_id`、产物路径和可监督样本数。也接受目录，逐文件处理；单文件失败不会中止其他输入，批次有失败时退出码为 1。默认目录是工作区 `inbox/`。支持 `.dem`、`.dem.bz2`、`.dem.zst`、`.dem.zip` 和规范 JSON；ZIP 必须恰好包含一个 demo。

一个 demo 不需要先拥有三场数据，也不需要 GPU、模型或专家标注就能提取样本。但它不会自动成为职业训练参考；个人比赛、未知来源与合成数据不能冒充专家数据。

准备足够的参考比赛后，分别标注来源，再固定划分和生成训练数组：

```bash
python coach.py --workspace coach-workspace/real annotate MATCH_ID --tier high_mmr --patch PATCH --role 1 --player-slots 0 --label-source "可核实的来源说明"
python coach.py --workspace coach-workspace/real build-dataset --patch PATCH --role 1 --require-spatial
python coach.py --workspace coach-workspace/real build-samples OBSERVATION_DATASET_ID
python coach.py --workspace coach-workspace/real doctor
```

将大写占位符换成真实值；重复 annotate 标注所选参考玩家。`build-dataset` 返回观察数据集 ID，`build-samples` 返回新的样本数据集 ID，后者可传给现有 `train` 命令。至少三场独立比赛才能使 train/validation/test 非空；这不是模型训练所需数据量的承诺。

不依赖真实回放的完整演练：

```bash
python scripts/bootstrap.py --data --dev
python coach.py --workspace coach-workspace/practice demo
python coach.py --workspace coach-workspace/practice prepare coach-workspace/practice/inbox/synthetic
python coach.py --workspace coach-workspace/practice build-samples OBSERVATION_DATASET_ID
```

上述 ID 从 demo 输出 `dataset.dataset_id` 取得。所有示例都带 synthetic 标识，仅用于验证管线。

## 输入与配置契约

Gem 协议解析仍由 `gem-dota` 完成。JSON 输入必须是本项目的规范比赛格式或兼容的 OpenDota 形状，不能直接把 Gem 原始导出交给 prepare。支持无 `schema_version` 的历史输入，以及 `gem-adapter/2.0`、`gem-adapter/2.1`、`gem-adapter/2.2`、`gem-adapter/3.0`；未知版本拒绝。最小可检查示例：

```json
{
  "match_id": 123456,
  "duration": 120,
  "players": [{
    "player_slot": 0,
    "hero_id": 44,
    "purchase_log": [{"time": 60, "key": "boots"}],
    "position_log": [{"time": 0, "x": -5000, "y": -4000}],
    "economy_log": [{"time": 0, "gold": 500, "net_worth": 600}]
  }]
}
```

这只是格式示例，不表示真实比赛。ID/时长/英雄必须是整数，拒绝 bool 伪装的数字；玩家槽位是 0–4 或 128–132，不能重复，最多十人。时长为非负游戏秒；位置/经济时间必须在 `[0,duration]` 内。赛前购买允许到 -3600 秒；物品为无 `item_` 前缀的小写 canonical key。额外比赛元数据不会自动进入模型特征。

- 金钱：`gold`、`net_worth`；计数：`last_hits`、`denies`；历史字段名 `xp_progress` 直接保留 Gem `xp_t` 原值。上游的“等级内进度”文档与本批实测冲突，语义待核验，不能按字段名推断升级重置。
- `x/y` 使用解析器原始坐标。缺少地图和补丁的真实核验，不自动换算单位或映射到野区/线路。
- 缺少通道与空数组分别记录；缺失经济字段保持 null，负数、bool、NaN/Infinity 都不是有效经济值。
- 带 `evidence_source` 的 JSON 必须同时提供 `evidence_sha256`，引用同目录内的原始证据。幸存记录的值和引用会被核对；篡改哈希、路径越界或证据不一致会拒绝整份输入。
- JSON 限制 256 MiB；原生/解压 demo 上限 2 GiB。默认比赛时长上限 6 小时、每玩家每通道 50 万行、每场最多 10 万个样本。解析本身尚无独立内存/超时隔离。

初始化生成 `preparation.json` 和 `contracts/preparation.schema.json`。修改配置或用 `--config path.json` 指定：

| 字段 | 默认 | 语义 |
|---|---:|---|
| `step_seconds` | 30 | 从 0 秒开始生成决策时刻 |
| `history_seconds` | 120 | 最近购买记录窗口 `(t-history,t]` |
| `horizon_seconds` | 60 | 标签观察窗口 `(t,t+H]` |
| `max_observation_age_seconds` | 30 | 当前位置/经济向后匹配的最大年龄 |
| `route_tolerance_seconds` | 10 | 路线终点在 `t+H` 之前的最大年龄 |
| `invalid_policy` | quarantine | 局部坏记录隔离；reject 则整份输入失败 |
| `candidate_items` | power_treads/desolator/black_king_bar | 固定输出动作空间；其他物品归为 other |

配置严格校验未知字段和类型。阈值是工程默认值，需在真实回放上校准。修改配置、代码或环境会产生新的派生产物身份；原始比赛内容冲突仍遵循工作区的拒绝策略，解析器修订建议使用新工作区。

## 清洗与失败行为

| 情况 | 处理 |
|---|---|
| 无效身份、重复玩家、未知 schema、错误容器类型、超限 | 拒绝整份输入，写入批次错误 |
| 时间非法、位置非有限、坏购买行 | 隔离该行，记录原始 `source_ref` 和原因 |
| 经济字段非法 | 字段置 null，记录原因；不伪造为 0 |
| 观测乱序 | 稳定排序，记录排序动作 |
| 同时间戳相同位置/经济状态 | 保留一条，记录去重 |
| 同时间戳相互矛盾的状态 | 隔离该时刻全部冲突记录 |
| 相同时间/物品的购买 | 保留，可能确实重复购买 |
| recipe_*、ward_dispenser | 从学习购买投影中排除，记录 exclude；免费假眼仍保留 |
| 同时购买不同物品 | 无可靠先后关系，相关 item 标签 mask=false |
| 无历史、过旧观测 | 特征 null，附缺失标记；不向未来插值 |
| replay 末尾不足未来窗口 | 标签 right_censored，mask=false |

原始输入不修改。单文件产物保留原字节 `input.json`；有 Gem 证据时另存 `raw.json`；`cleaned.json` 为派生副本。`quality.json` 保留每通道输入/保留/无效行数、排序/去重/隔离明细、Gem 适配阶段警告和两类任务的监督样本数。字段隔离数不等于丢弃行数。若清洗副本用于导入，规范比赛还保存 `cleaning_audit`；后续样本质量文件保留这个来源审计。

`imports/prepare-*.json` 持续记录每个文件的成功/失败；失败文件仍留在原位置，不会被自动移动或删除。进程硬中断可能留下没有 `finished_at` 的批次，当前不会自动标记恢复成功。

## 特征与标签

`features.jsonl`、`labels.jsonl`、`trace.jsonl` 使用 `match_id:player_slot:cutoff` 形式的 `sample_id` 关联。它是元数据，不进入 X。跨配置样本要同时使用 manifest 的 preparation/dataset ID 才能唯一定位版本。

特征白名单包括：游戏秒、英雄类别、当前位置及年龄、自身经济各字段及年龄、历史窗口内总购买记录数和各候选物品的购买记录数；数值特征有显式缺失标记。当前不含背包/库存、信使、敌方视野、队友状态、死亡状态、比赛结果和赛后汇总。购买计数描述观察到的记录，不代表拥有该物品。

pandas `merge_asof(direction="backward", tolerance=...)` 只读取 `time<=cutoff` 的最新采样。字段缺失不会由未来补齐。比赛最终时长和未来覆盖信息只用于样本生成及标签资格，不进入 X。

两种初始监督任务：

1. **下一个观察到的购买记录**：未来窗口首个事件为候选物品、other；同刻不同物品则 unknown。窗口内没有记录时，只有明确 `purchase_coverage` 覆盖整个窗口才允许 no_purchase；否则 mask=false。正例的含义是“下一个被记录的购买”，日志漏检仍可能造成偏差。
2. **未来位置位移**：选择不晚于 `t+H` 且在容差内、严格晚于 t 的终点，减去当前可用位置得到 dx/dy。保留终点实际时间。没有有效起终点或窗口右截尾则 mask=false。这是运动监督，不是最优路线标签；复活、传送等行为尚未分类。

可选 `purchase_coverage` 是玩家级来源断言：

```json
{"start_seconds": 0.0, "end_seconds": 120.0, "source": "覆盖范围的核验依据"}
```

必须放在玩家对象内，结束不能超过 duration。它不是自动验证的事实，缺失时保持未知。因无效数据被隔离的购买行会撤销此覆盖断言；按已定义投影排除配方/组合眼不属于数据丢失。Gem 的结束 tick 本身不足以证明事件流完整，管线不会仅凭该 tick 自动声明连续覆盖。

`trace` 将历史引用与标签引用分开，并保留 cutoff、未来窗口终点、实际路线终点和覆盖断言。单文件引用相对于 `input.json`；固定样本数据集引用相对于源观察数据集对应的 normalized.json。Gem 的进一步原始证据引用保留在规范记录中。

## 固定样本与训练接口

`build-samples` 读取已经冻结的比赛划分，不重新随机划分窗口。每个 split 输出：

```text
train.features.jsonl / train.labels.jsonl / train.trace.jsonl
train.quality.json
train.npz
validation.* / test.*
preprocessor.json
manifest.json
```

manifest 记录源 dataset ID 和 manifest 哈希、split 的比赛/窗口/监督样本分母、配置、项目 Python 源码指纹、依赖版本和每个产物 SHA-256。`doctor` 检查 prepared 产物及两种数据集的身份和文件哈希。原始 demo 只记录身份，不会自动复制进每个样本快照；仍需自行备份原文件。

预处理复用 scikit-learn：固定零填补加缺失指示器；`StandardScaler` 仅在 train 拟合；英雄 `OneHotEncoder` 的类别仅来自 train，未知英雄编码全零。全缺失列保留，零方差由 StandardScaler 处理。数值超出 float32 可表达范围时失败，不发布无穷值数组。候选动作表来自明确配置，不扫描验证/测试数据推导。当前在内存处理整个 split，规模扩大后需评估 Parquet/分块拟合。

```python
import numpy as np
from pathlib import Path

folder = Path("coach-workspace/real/datasets/SAMPLE_DATASET_ID")
with np.load(folder / "train.npz", allow_pickle=False) as batch:
    item_mask = batch["item_mask"]
    X_item = batch["X"][item_mask]
    y_item = batch["item_target"][item_mask]
    route_mask = batch["route_mask"]
    X_route = batch["X"][route_mask]
    y_route = batch["route_target"][route_mask]
```

无效 item target 为 -1；无效路线以 `[0,0]` 占位，**必须用对应 mask 筛选或屏蔽损失**。禁止把占位值训练成真实负例。`preprocessor.json` 是 JSON 参数，不是可执行 pickle；推理复用 `data.preprocessing.transform_features`，并与对应 PreparationConfig/特征版本一起登记到模型 artifacts。

已有适配器模板不会被初始化命令覆盖。新模板包含数组读取示例；旧工作区参考本页修改自己的 train.py。实际训练算法、损失和模型效果评估仍由下一阶段实现。

## 验收边界

生产测试覆盖非法值/结构、排序冲突、缺失与过旧数据、截止边界、未知覆盖/截尾、未来扰动、train-only 预处理、未知英雄、保存加载一致性、幂等/篡改检测、批次失败隔离及训练接口数组读取。Gem 分支使用受控解析结果测试，不能代替真实 demo 回归。

下一步用 3–5 场真实回放核对暂停时钟、坐标、经济单位、购买漏检与路线缺口。完成语义验收后再决定哪些任务/范围可以纳入正式训练；不要用合成测试通过宣称职业动作正确性已被学会。
