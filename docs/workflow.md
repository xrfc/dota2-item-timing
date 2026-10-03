# 日常操作、迁移与恢复

基线：v0.3。首次使用及模型接入命令见[教练工作流](coach-workflow.md)；本文件维护日常操作、旧入口衔接与真实回放核验。

按学习计划开发清洗、对齐、样本和预处理功能时，使用[开发流程](development-workflow.md)与 [L01–L12 任务清单](roadmap.md)。下述日常操作是已有命令；学习任务中的新接口仍待实现。完整来源、质量和样本记录可复制[数据审计模板](templates/data-audit.md)。

## 1. 建议的本地使用方式

把合成演练和真实数据放在不同工作区，便于核对状态：

```bash
python scripts/bootstrap.py --replay --dev
python coach.py --workspace coach-workspace/demo demo
python coach.py --workspace coach-workspace/real init
python coach.py --workspace coach-workspace/real ingest /path/to/replays
python coach.py --workspace coach-workspace/real status
python coach.py --workspace coach-workspace/real doctor
```

安装后除 OpenDota fetch 外，已有回放/JSON 的操作可离线进行。目录导入默认递归；输入目录只放回放和比赛 JSON，不要把包含 manifest、quality 等辅助 JSON 的整个数据目录当作比赛输入。

建议每次批量导入后查看：

1. `imports/import-*.json`：逐文件 imported/cached/failed 和 error。
2. `catalog.json`：逻辑比赛、当前标签、警告和数据包路径。
3. `replays/<match-id>-<bundle-id>/quality.json`：通道是否存在，有哪些基础警告。
4. `doctor`：比赛包和数据集指纹是否仍有效。

文件夹 reference/personal 只是组织方式，不自动赋予 tier、role 或 patch。按实际来源标注后才构建参考数据集。命令占位示例：

```bash
python coach.py --workspace coach-workspace/real annotate 8822520406 --tier pro --patch 7.xx --role 1 --player-slots 0 --label-source "实际赛事/轮次/来源链接"
python coach.py --workspace coach-workspace/real build-dataset --patch 7.xx --role 1 --hero-id 44 --require-spatial
```

替换比赛 ID、补丁、槽位和来源；构建至少需要 3 场符合条件的不同比赛。输出中的 excluded 尚未自动存入快照，如需保留可把本次 stdout 重定向到工作区文件：

```bash
python coach.py --workspace coach-workspace/real build-dataset --patch 7.xx --role 1 --hero-id 44 --require-spatial > coach-workspace/real/dataset-selection.json
```

仅在命令成功退出时将此文件作为筛选结果，失败信息在 stderr。每次构建需长期保留时使用不同文件名，避免覆盖之前的结果。

## 2. 旧 dota-items 入口

安装包后可以继续使用原命令；未激活 venv 时使用下面的模块形式。Windows 将 `.venv/bin/python` 替换为 `.venv/Scripts/python.exe`。

```bash
.venv/bin/python -m dota_items.cli report examples/match.synthetic.json --player-slot 0 --output reports/smoke
.venv/bin/python -m dota_items.cli ingest-demo /path/to/replays --recursive --data-dir data
.venv/bin/python -m dota_items.cli data-status --data-dir data
```

| 命令 | 行为与边界 |
|---|---|
| fetch MATCH_ID | 缓存 OpenDota 比赛 JSON；默认 data/raw；--refresh 重新获取 |
| ingest-demo INPUT | 解析回放并写 raw-gem.json、normalized.json、manifest.json、index.sqlite；目录默认不递归 |
| data-status | matches 是输入哈希索引的行数，可能大于独立比赛数；另有 distinct match_ids |
| report INPUT --player-slot SLOT | 输出 analysis.json/report.html；默认配置 configs/analysis.json、输出 reports/latest |

旧导入成功结果为 stdout JSONL；进度和错误在 stderr，批次有失败则退出 1。它不创建新工作区、不标注、不固定数据集。report 的声明哈希没有新导入同等的外部证据校验。

需要 OpenDota 网络数据时：

```bash
.venv/bin/python -m dota_items.cli fetch 8822520406
python coach.py --workspace coach-workspace/real ingest data/raw/8822520406.json
```

API 可因回放状态或服务限制缺字段；成功 fetch 不保证具备训练所需通道。可通过环境变量传入 OPENDOTA_API_KEY，项目不自动加载 .env。当前不自动请求远端解析、不自动下载 demo。缓存命中主要依赖文件存在，不能视作内容重新验证。

## 3. 从旧缓存迁移

采用新旧并存方式：

1. 停止正在写旧 data 和新工作区的任务，备份旧目录、原 demo 与来源记录。
2. 初始化新工作区。
3. 对选定比赛显式导入旧的 normalized.json，并保留它引用的 raw-gem.json 在原相对位置。
4. 核对导入、doctor、购买事实与人工记录，重新填写来源标签。
5. 固定新数据集，再比较逻辑比赛数和通道情况；保留旧目录用于追查。

占位路径示例：

```bash
python coach.py --workspace coach-workspace/migrated init
python coach.py --workspace coach-workspace/migrated ingest data/matches/SOURCE_HASH/normalized.json
python coach.py --workspace coach-workspace/migrated doctor
```

SOURCE_HASH 替换为实际目录。不要递归导入整个 data：raw、manifest 也有 .json 后缀，会被尝试当作比赛。

旧导出的购买数据可能没有位置/经济通道。新工作区不会补出缺失字段；需要时用原 demo 在新工作区重新解析。解析器升级产生内容冲突时另建工作区，--force 只作用于中间缓存，不覆盖既有比赛包。当前没有自动旧新 ID 映射或多来源合并工具。

## 4. 备份与恢复

复制前停止写任务，备份整个工作区，尤其是 catalog、replays、datasets、adapters、runs、models、reviews 与配置。原始 demo 如果在工作区外，需要另行备份；解析中间 manifest 也应保留，因为冻结数据集尚未完整携带所有解析环境信息。

恢复建议：

1. 恢复到新目录，重建 Python 环境，不直接跨系统复制 venv。
2. 用全局 --workspace 指向新目录，执行 status 和 doctor。
3. 打开已有事实报告，并对一场已导入比赛重新生成报告，核对内容。
4. 接入模型后再核验登记产物及一次预测。doctor 本身不检查模型/运行/报告。
5. 保留旧路径的 invocation/report 元数据作为历史记录；搬迁后它们不会自动改写，实际文件可按新目录定位。

数据集和登记产物内部使用相对路径；旧 SQLite 缓存使用绝对路径，需要保留旧环境或从原 demo 重建。框架没有自动清理命令；删除数据包、数据集或模型前先确认引用关系并保留备份。

## 5. 故障处理

| 现象 | 定位和处理 |
|---|---|
| No module named gem | 用同一环境重新执行 bootstrap --replay；JSON 流程不依赖 Gem |
| 某场导入失败、后续仍在运行 | 批次按设计继续；结束后看 imports 结果，仅对失败输入排查重试 |
| Need at least 3 eligible distinct matches | 核对 tier、patch/role/hero、槽位、购买状态及空间通道；三个文件不一定是三场 |
| already exists with different content | 保留两个来源核对；新工作区导入不同解析版本，勿改旧快照哈希 |
| Missing or changed artifact / fingerprint mismatch | 保留损坏文件与日志；从备份或原数据重建，不能手改 manifest 掩盖变化 |
| .writer.lock 残留 | 确认该工作区所有写进程已退出，再移除锁并重试；活跃任务时不能删锁 |
| Trainer/Predictor not implemented | 当前模板刻意没有模型实现；先完成自己的适配器 |
| train/review failed | 看 run/review 状态、process.log、invocation.json；校验输出契约和依赖 |
| 强杀后仍是 running | 当前没有心跳与自动恢复；确认进程已结束，保留旧 run，重跑获得新 ID |
| 解析一直不返回 | Gem 解析暂无任务级超时；人工终止后确认进程状态，再检查缓存与原输入 |

训练器自行创建的子进程可能需要额外清理。通用自动续训尚未实现；检查点和恢复参数由训练器管理。Gem 缺失但 doctor 的 ok 为 true 是正常的 JSON 工作流状态，查看 replay_parser_installed 字段即可。

## 6. 可复制的人工核验记录

以下为待填写模板，不代表当前已有对应验收数据。先选 3–5 场发现问题，10–20 条事件可作初查；最终需要独立标注明确窗口中的全部目标事件以检查漏检。

### 样本与环境

| 字段 | 填写内容 |
|---|---|
| match_id / 原文件与解压 demo 哈希 | |
| 原始来源、访问依据、职业/高分证据 | |
| patch / game_mode / 英雄 / role / player_slot | |
| Gem 精确版本 / adapter 版本 / Git 提交 / Python | |
| 比赛时长、完整结束、暂停与恢复区间 | |
| 核验窗口、目标装备、位置/经济采样规则 | |
| 操作者、日期、回放时间码/记录位置 | |
| 未知、冲突和未覆盖情况 | |

### 购买双向对照

| 人工事件 ID | 游戏时间 | 装备 | 购买/合成/送达 | 导出 key/time/ref | 匹配/误检/漏检 | 差异说明 |
|---|---|---|---|---|---|---|
| 待填写 | | | | | | |

独立从回放标注目标事件，再与导出列表双向匹配。记录时间误差，分开报告误检和漏检；没有观察完整窗口时注明分母不完整。覆盖赛前、重复购买、配方、自动合成、退回/拆分、暂停和送达差异，未出现的边界列为未覆盖。

### 位置与经济对照

| 时间码 / tick | 通道 | 人工观察或原始值 | 导出值 | 单位/时间是否一致 | 缺失原因 |
|---|---|---|---|---|---|
| 待填写 | position / gold / net_worth / last_hits / denies / xp_progress | | | | |

在暂停前后、死亡/复活、等级提升和缺失片段附近核验。位置不能只看曲线平滑就判正确；坐标系、tick 转换和采样对齐都需确认。xp_progress 回落可能是升级后的等级内进度，不能当累计经验下降。

### 结论

记录独立比赛数、目标事件分母、误检/漏检、时间误差、通道覆盖、系统性问题、纳入/排除决定与原因。若无法确认语义，应缩小字段或任务范围，再固定数据集。验收规则见[验证与交付](validation-and-delivery.md)。
