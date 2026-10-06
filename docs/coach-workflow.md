# 教练工作流：训练前后基础设施（v0.3）

> v0.4 数据准备更新：`prepare` 已实现单文件清洗/特征/标签；`build-samples` 输出固定 split 的训练数组和 train-only 预处理。输入、错误策略、任务 mask 和操作示例以[数据管线](data-pipeline.md)为准。实际模型与真实字段验收仍待完成。

本阶段提供数据和程序执行管线。特征窗口、初始标签策略和预处理已实现；训练算法、网络结构和模型权重由下一阶段实现。
程序可在本地或云端的 Python 环境运行；当前通过文件夹接入回放，尚无网页上传服务。

核对日期：2026-10-02。实际完成度见[项目状态](project-status.md)，字段与限制见[数据契约](data-contracts.md)，技术取舍见[选型路线](long-term-roadmap.md)。

## 1. 安装与离线验证

Python 3.11+，在仓库根目录运行：

```bash
python scripts/bootstrap.py --replay --dev
python coach.py demo
python coach.py doctor
python coach.py status
```

安装脚本创建 `.venv`；`coach.py` 自动选择它。安装需要网络，安装后本地回放解析、
数据集和报告可以离线运行。无需 CUDA、PyTorch、API key 或语言模型服务。
只测试 JSON 管线可使用 `python scripts/bootstrap.py --dev`，以后再加 `--replay`。

`demo` 生成 6 场明确标注为 synthetic 的比赛，构建 4/1/1 的训练/验证/测试快照，
生成一份购买事实报告，并运行数据校验。它不会训练模型，也没有伪造的“模型准确率”。
同一工作区重复执行会复用比赛和数据集，生成新的报告。

安装后的等价命令为 `dota-coach`。可用全局选项选择工作区：

```bash
python coach.py --workspace /path/to/my-coach init
```

全局选项必须在子命令之前。也可设置 `DOTA_COACH_WORKSPACE`；默认是当前目录下的
`coach-workspace/`。项目不自动加载 `.env`。

## 2. 导入职业、高分与个人回放

```bash
python coach.py init
python coach.py ingest /path/to/replays
```

支持 `.dem`、`.dem.bz2`、`.dem.zst`、`.dem.zip` 和项目/OpenDota 形状的比赛 JSON。
目录默认递归扫描；使用 `--no-recursive` 只扫描当前目录。
把文件放入 `coach-workspace/inbox/reference/` 或 `inbox/personal/` 后，直接运行
`python coach.py ingest` 即可扫描整个 inbox。文件夹名称本身不会赋予职业或高分身份。

导入流程：

1. 本地 Gem 解析，保留原始 JSON；支持已有 `dota-items ingest-demo` 产物。
2. 校验比赛、玩家槽位、购买事件、时间序列、原始证据指纹和事件引用。
3. 在临时目录复制并再次验证，发布数据包后原子更新目录索引。
4. 按 `match_id` 去重。内容指纹相同返回 `cached`；同一比赛内容冲突则拒绝覆盖。
5. 每个输入的结果写入 `imports/import-*.json`，单场失败后继续处理其他文件，批次返回非零退出码。

`--force` 只重建中间解析缓存，不覆盖已冻结的数据包或数据集。
解析器升级产生不同的规范数据时，使用另一个工作区导入，避免混合解析版本。
内容寻址的数据包可以在发布后、索引提交前崩溃时由下次相同导入恢复。

旧 `dota-items` 的缓存仍采用源文件字节哈希，并可能对同一回放的不同压缩格式分别解析。
新工作区在解析后按比赛去重，保证这些格式不会重复进入数据集；尚未实现解析前的跨压缩格式缓存复用。
原 demo 不会自动复制进数据包；请自行保存原文件和来源。导入目录中不要混入 manifest/quality 等辅助 JSON，它们也会被尝试当作比赛。

导入成功不代表训练价值已核验。角色、补丁、职业身份或分数来源需要你记录：

```bash
python coach.py annotate 8822520406 --tier pro --patch 7.xx --role 1 --player-slots 0 --label-source "赛事名称/轮次/来源链接"
python coach.py annotate 1234567890 --tier personal --patch 7.xx --role 1 --player-slots 128 --label-source "我的回放"
```

`7.xx` 和比赛 ID 是命令占位示例，请替换为真实值。角色为 1–5 号位；玩家槽位使用
天辉 0–4、夜魇 128–132，不是数组下标。一次标注的角色适用于所选的全部玩家；应只选择
确实担任该角色的玩家。当前每场比赛保存一组参考玩家标注，不自动推断角色或 MMR。
重复 annotate 会覆盖当前标签，没有标签历史；已冻结数据集中的标签不受影响。
`tier` 为 `pro` / `high_mmr` / `personal` / `unknown` / `synthetic`。
合成样本不能重新标成真实比赛。

## 3. 固定数据集

```bash
python coach.py build-dataset --patch 7.xx --role 1 --hero-id 44 --require-spatial
```

默认只纳入已标注的 `pro` 和 `high_mmr` 比赛，排除个人回放、未标注记录和合成数据。
`--hero-id` 可省略，`--require-spatial` 要求玩家具有位置和至少有一个可用数值的经济采样。
该开关只检查非空，不检查时间覆盖率、完整解析或采样对齐；购买日志 present 也可能是空数组。
只做出装实验时可省略它。合成测试使用 `--synthetic-only`，该开关会仅选择 synthetic，
不会将合成和真实样本混合。

至少需要 3 场不同比赛才能生成非空的训练、验证和测试集。这只是基础设施的最低条件，
不表示 3 场足够训练模型。划分以比赛为单位，同场所有玩家均进入同一个 split。
按照固定 seed 和比赛 ID 的哈希排序划分，比例在 `workspace.json` 中配置。
相同输入、标注、配置会得到同一个数据集 ID；新增比赛可能改变新版本的划分，比较实验时应固定同一 ID。

```text
datasets/<dataset-id>/
  manifest.json           # 配置、筛选条件、来源标注、划分、每个文件的 SHA-256
  train.jsonl             # 每行对应一场比赛，包含所选玩家槽位和相对路径
  validation.jsonl
  test.jsonl
  matches/<match-id>/
    normalized.json
    raw.json              # 输入有独立原始证据时保留
    quality.json
```

数据集复制数据包，不依赖后续目录索引或标注变化。启动训练前后都会校验它的文件指纹。
数据集路径可随整个工作区搬迁，不依赖原 `.dem` 路径或旧 SQLite 中的绝对路径。
保存完整 raw 会占用磁盘，暂未使用硬链接、对象存储或自动清理。
`excluded` 筛选原因同时写入 manifest 和命令结果。
快照目前没有完整携带原 demo、解析 manifest、Git 版本和依赖锁，哈希只能保证已登记内容可校验，不能单独保证实验完整复现。

### 数据契约 `coach-match/1`

`coach-match/1` 是数据集声明的观测契约名称，目前没有完整的 Pydantic Match 类或独立 Schema。
比赛必须包含 `match_id`、`duration`、`players`；玩家需要有效 `player_slot`、`hero_id`。
`purchase_log` 缺失会记录警告并阻止该玩家成为训练参考；位置/经济通道可缺失。
Gem 的导出版本为 `gem-adapter/2.2`。

| 通道 | 字段 | 语义 |
|---|---|---|
| purchase_log | time, key, source_tick, source_ref | 购买日志事件，可能有赛前负时间 |
| position_log | time, x, y, source_tick, source_ref | 玩家自己的世界坐标；不划分地图语义区域 |
| economy_log | time, gold, net_worth, last_hits, denies, xp_progress | 自身经济；缺失值为 null |
| economy_log.source_refs | 字段名 → raw JSON 路径 | 对应原始数值的证据 |

`time` 为游戏秒数。Gem tick 经暂停感知的 `game_clock` 转换，不直接除以 30。
没有可用时钟或有效坐标的采样不导出。`gold` 是未花费金钱；`xp_progress` 是保留 Gem
`xp_t` 原值的历史字段名，其等级内/累计语义存在文档与实测冲突，核验前不作该含义的训练解释。
位置和经济各保留自己的时间轴，不在此层插值或未来填充。
购买记录不代表完成合成、库存或装备送达；当前没有库存可用性、存活状态、敌方可见性契约。

观察数据集保留整场数据和其他玩家；`build-samples` 遵守 `player_slots`，生成白名单历史特征、未来标签及仅用 train 拟合的预处理。下一阶段训练器优先读取 `coach-samples/1` 的数组并使用任务 mask，详细格式见[数据管线](data-pipeline.md)。
验证集用于调参，测试集只作最后评估；框架不能阻止任意用户模型自行读取额外未来数据。

## 4. 下一阶段接入自己的训练程序

`init` 创建 `adapters/train.py` 和 `adapters/predict.py` 的参数模板，以及 `contracts/` 下的
JSON Schema。模板会明确退出并提示尚未实现，不会输出伪造权重。
再次 init 不覆盖你已经修改的适配器。

实现模型后执行以下命令，替换 DATASET_ID / RUN_ID 与脚本路径；`configs/my-training.json` 需先自行创建为 JSON 对象，不传 `--config` 时使用 `{}`：

```bash
python coach.py train DATASET_ID --config configs/my-training.json
python coach.py train DATASET_ID --trainer /path/to/my_trainer.py --timeout 86400
python coach.py register-model RUN_ID
```

训练器调用约定：

```text
<当前Python> train.py --dataset <快照绝对目录> --output <run/output目录> --config <配置JSON>
```

工作目录是训练器脚本所在目录，方便导入同目录模块；运行不经过 shell。
配置会复制保存到 run 中；每次运行生成独立 ID，记录 Python/相关包版本、适配器主文件副本和哈希、
调用参数、起止时间、状态及合并的 stdout/stderr。适配器依赖的其他代码和完整环境锁文件仍需自行版本管理。
模型依赖应安装到同一个 `.venv`，可使用 CPU 或本机 GPU，不由框架选择训练设备。

训练程序成功退出后必须写入 `output/model.json`，例如：

```json
{
  "schema_version": "coach-model/1",
  "framework": "pytorch",
  "feature_schema": "my-decision-features/1",
  "tasks": ["item", "route"],
  "artifacts": ["weights.pt", "preprocessor.json"],
  "metrics": {},
  "notes": "填写数据范围、模型局限和实际评估结果"
}
```

这是格式示例，不包含训练后的模型或效果。指标由你的训练/评估程序提供，必须是有限数值。
产物必须是 output 内的非空普通文件，禁止目录穿越和符号链接。
非零退出码、超时、缺少文件或契约错误都会将 run 标记为 failed 并保留日志。
仅 succeeded 的 run 可以登记模型；登记复制产物并以内容/来源生成模型 ID。
框架不会反序列化权重，也不自动发布模型服务。

## 5. 复盘自己的比赛

模型尚未实现时，先用事实报告确认输入：

```bash
python coach.py review 1234567890 --player-slot 128
```

模型实现、登记且个人比赛完成标注后：

```bash
python coach.py review 1234567890 --player-slot 128 --model MODEL_ID
python coach.py review 1234567890 --player-slot 128 --model MODEL_ID --predictor /path/to/predict.py
```

预测器调用约定：

```text
<当前Python> predict.py --model <登记目录> --match <normalized.json> --player-slot 128 --output <predictions.json>
```

模型目录包含 `registry.json`、`model.json` 和已登记的产物。
预测输出遵循 `contracts/predictions.schema.json`：

```json
{
  "schema_version": "coach-predictions/1",
  "model_id": "实际模型ID",
  "match_id": 1234567890,
  "player_slot": 128,
  "decisions": [{
    "time_seconds": 600,
    "task": "route",
    "observed_action": "由预测器描述的实际行动",
    "alternatives": [{"label": "候选地图区域", "score": 0.6}],
    "evidence_refs": ["players[5].position_log[30]"],
    "note": "说明上下文和局限，不将行为偏好直接称为决策正确率"
  }],
  "limitations": []
}
```

上面分数仅为格式示例。`players[5]` 是 JSON 数组索引，不等于玩家槽位，必须按实际输入定位。
引用需指向该玩家的一整条购买、位置或经济记录；该记录时间不得晚于决策时间。
报告检查模型/比赛/玩家身份、范围、任务和证据。个人回放的补丁、角色、英雄须匹配数据集范围；
合成模型不会用于真实回放。已出现在关联数据集任意 split 中的比赛会在报告里标注，避免当成独立泛化验证。
`observed_action` 和解释文字由预测器提供，框架不会逐项验证其中的事实断言；预测器也会收到整场输入，必须自行遵守特征截止时间。

HTML 不依赖 CDN，外部文本全部转义，同时输出事实报告和预测 JSON。
模型分数表示模型偏好，不自动解释成胜率或“正确/错误”；因果价值评估留给后续模型设计。

## 6. 工作区、排障与恢复

```text
coach-workspace/
  workspace.json           # seed、划分比例、事实报告关注装备
  catalog.json             # 比赛索引、标签、数据包指纹
  inbox/                   # 放入回放文件；模型不直接读这里
  cache/                   # 旧 Gem/SQLite 解析缓存，可从原回放重建
  replays/                 # 按内容发布的数据包
  datasets/                # 固定数据集
  adapters/                # 你后续实现的 train.py / predict.py
  contracts/               # 接口 JSON Schema
  imports/                 # 每次批量导入结果
  runs/<id>/               # run.json / config.json / invocation.json / process.log / output/
  models/<id>/             # 登记产物与来源
  reviews/<id>/            # 状态、日志、事实和预测报告
```

`status` 查看比赛/数据集/模型 ID、未标注比赛数量和运行/复盘状态，本身不做完整性扫描。
`doctor` 对回放包做文件与比赛校验、对数据集做身份与文件指纹校验，并报告是否安装 Gem。
它不检查模型、运行、报告、原 demo 或旧缓存，也不修复损坏；Gem 缺失本身不会令 JSON 工作流的 doctor.ok 变为 false。
Gem 缺失只阻止 `.dem` 解析，不阻止 JSON 数据、训练适配器或报告。
新工作区导入发布、标注和数据集构建使用一个写锁；Gem 中间缓存解析不受此锁保护。
训练和复盘各有独立输出目录。数据包/快照内部采用相对路径；历史 invocation.json 和 review.json 的命令、报告路径可能为绝对路径，搬迁后不会自动改写。

| 现象 | 处理 |
|---|---|
| Gem 缺失 | 运行 `python scripts/bootstrap.py --replay` |
| 没有足够的 eligible matches | 查看标注、patch/role/hero 筛选和时序通道，至少 3 场 |
| changed artifact / fingerprint mismatch | 保留损坏产物排查，从原始文件在新工作区重建，勿伪造哈希 |
| Trainer/Predictor not implemented | 属于下一阶段的接口模板，先完成自己的模型程序 |
| 模型任务 failed | 检查对应目录的 process.log、invocation.json、配置与输出契约 |
| 中断后显示 running | 进程被强制杀死可能来不及更新状态；确认进程结束后重跑，会生成新 ID |
| 残留 .writer.lock | 确认没有导入/构建进程运行，再删除该锁文件后重试 |

重跑训练不会覆盖先前 run；检查点恢复由训练器通过自己的 config 实现，当前无通用自动续训。
超时控制管理直接启动的适配器进程；若训练器自行创建分布式子进程，需要自行清理进程组。
本轮未引入后台队列、Web API、GPU 调度、自动下载职业回放或模型性能判定。

## 7. 命令与机器输出速查

全局 `--workspace` 必须放在子命令前；可运行 `python coach.py <命令> --help` 查看精确参数。

| 命令 | 输入/默认值 | 成功输出重点 |
|---|---|---|
| init | 工作区；重复运行保留现有配置和适配器，重新导出 Schema | workspace、status=ready |
| demo | 6 场内置合成比赛 | dataset、report、doctor |
| ingest [INPUT] | 默认 inbox；默认递归；--force 重建解析缓存 | batch_id、results、ok；逐文件日志在 imports |
| annotate MATCH_ID | --tier、--patch、--role、--player-slots、--label-source 必填 | match_id、labels |
| build-dataset | --patch、--role 必填；可选 --hero-id、--require-spatial、--synthetic-only | dataset_id、path、split_matches、excluded |
| train DATASET_ID | 默认 adapters/train.py；默认超时 86400 秒 | run_id、status、model、files |
| register-model RUN_ID | 仅 succeeded run | model_id、path、dataset_id |
| review MATCH_ID | --player-slot 必填；--model 可选，默认预测器 adapters/predict.py；超时 3600 秒 | review_id、mode、status、report |
| status | 已初始化工作区 | 比赛计数/ID、数据集、模型、runs、reviews |
| doctor | 已初始化工作区 | ok、validated_matches、errors、replay_parser_installed |

成功结果为 stdout 上的单个 JSON 对象（可多行，不是 JSONL），进度与错误在 stderr。
正常退出 0；处理错误、批次有失败或 doctor 检出错误时退出 1；参数用法错误通常为 2；用户中断为 130。
旧 `dota-items ingest-demo` 的 stdout JSONL 协议不同，见[操作指南](workflow.md)。

## 验证范围

自动化测试覆盖合成数据闭环、整场划分、去重、文件损坏、证据校验、搬迁工作区、
训练/推理进程接口、超时、失败记录、模型登记和未来证据拒绝。
测试中的训练和预测脚本只是接口桩，不训练深度学习模型。
Gem 的原始购买流程来自已有项目；新增位置/经济字段的真实 Demo 对照验证尚待完成。
