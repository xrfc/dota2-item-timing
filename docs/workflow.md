# 从 Demo 到报告：运行与核验流程

更新：2026-09-28；适用于当前 v0.2.0。下面命令在仓库根目录、Windows PowerShell 中运行。
`data-validate`、自动恢复、参考组和模型仍在 [TODO](roadmap.md) 中，没有相应可运行命令。
macOS/Linux 的环境建立方式见 [README](../README.md)。

## 1. 建立环境并验证示例

新环境运行一次；已有 `.venv` 时跳过创建，只按需安装依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,replay]"
.\.venv\Scripts\dota-items.exe report examples/match.synthetic.json --player-slot 0 --output reports/demo
Start-Process reports/demo/report.html
```

产物：`reports/demo/report.html` 与 `analysis.json`。页面应标记为合成数据，
示例候选装备的首次记录为 07:00、18:20、23:10。这只验收报告链路，不验收 Demo 解析。

## 2. 导入一场自己的比赛

保留下载的原始文件，先选一场完整 Demo，确认文件扩展名与实际来源。替换下面的示例路径。
压缩包支持 `.dem.bz2`、`.dem.zst`、`.dem.zip`；ZIP 中必须恰好有一个 `.dem`。
当前先串行使用一个导入进程，并避免将同一 Demo 的不同封装重复导入。

```powershell
$demoPath = 'C:\path\to\your-match.dem.bz2'
$importOutput = & .\.venv\Scripts\dota-items.exe ingest-demo $demoPath --data-dir data
if ($LASTEXITCODE -ne 0) { throw '导入失败，请查看上方错误。' }
$importResult = $importOutput | ConvertFrom-Json
$matchPath = $importResult.normalized_json
.\.venv\Scripts\dota-items.exe data-status --data-dir data
```

`status=imported` 表示本次写入，`cached` 表示命中当前缓存规则。
首次导入的结果还有玩家数、事件数、issues 和 manifest 路径；cached 结果字段较少。
不能把缓存命中或 issues 为空理解成文件完整性与游戏语义已验证。

解压只是把压缩包还原为 Demo；Gem 随后解析 Demo 才得到 JSON。两步不是同一个操作。
一场大型比赛解析可能需要数分钟，完整 JSON 也可能很大。

## 3. 找到玩家，生成并检查报告

先列出槽位与英雄，再选择自己。不要把数组第几项直接当成 player_slot。
如需确认英雄名称，应使用与比赛版本匹配的资料或直接对照游戏内比赛阵容。

```powershell
$match = Get-Content -LiteralPath $matchPath -Raw -Encoding utf8 | ConvertFrom-Json
$match.players | Select-Object player_slot, hero_id
$playerSlot = 0  # 示例值；按上一条输出和实际阵容修改
.\.venv\Scripts\dota-items.exe report $matchPath --player-slot $playerSlot --config configs/analysis.json --output reports/my-match
if ($LASTEXITCODE -ne 0) { throw '报告生成失败，请查看上方错误。' }
Start-Process reports/my-match/report.html
```

`configs/analysis.json` 目前只读取 `candidate_items`；先改为希望观察的物品 key。
此文件不支持英雄、角色或版本过滤，添加这些键不会自动建立参考组。
输出目录重复使用会覆盖旧报告，要保留多个报告请更换 `--output`。

检查比赛 ID、玩家槽位、时长、赛前负数、重复购买、质量提示、来源与候选装备。
Gem 的 patch 当前为未知；无记录不能直接解释为未购买；“首次记录”也不是送达时刻。
单场缺少预期玩家或事件时先调查，不靠手工补几个数让报告看起来完整。

可先人工比对当前 raw 文件哈希；这不是完整的引用校验器：

```powershell
$matchFolder = Split-Path -Parent $matchPath
$manifestPath = Join-Path $matchFolder 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$rawPath = Join-Path $matchFolder 'raw-gem.json'
$actualRawHash = (Get-FileHash -LiteralPath $rawPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualRawHash -ne $manifest.raw_json_sha256) { throw 'raw JSON 与 manifest 不一致。' }
```

通过只说明 raw 与 manifest 相符；还需要验证每条引用，以及 normalized 是否确实由该 raw 产生。
自动验证和异常状态正在 D01/D03 中规划。

## 4. 批处理、重跑与故障排查

单场核验通过后可小规模批处理，先处理自己的 3～5 场。
目录默认不递归，需扫描子目录时加 `--recursive`。建议输入目录与项目 data 目录分开。

```powershell
New-Item -ItemType Directory -Force -Path reports | Out-Null
.\.venv\Scripts\dota-items.exe ingest-demo 'C:\path\to\replays' --data-dir data 1> reports/import-results.jsonl 2> reports/import-errors.log
$batchExitCode = $LASTEXITCODE
$batchExitCode
```

stdout 每个成功/缓存结果一行 JSON；stderr 同时有解析进度和错误 JSON，因此错误文件不是纯 JSONL。
退出码 0 表示批次无捕获到的文件失败，1 表示至少一场失败；成功文件仍已导入。
`data-status` 当前只显示数量，不检查文件 hash、引用、语义或数据库与文件的一致性。

| 情况 | 当前处理方式 |
|---|---|
| Gem 未安装 | 在当前虚拟环境安装 `.[replay]`，确认调用的是 `.venv` 中的程序 |
| 文件头错误 / ZIP 内多个 Demo | 检查输入格式；多场比赛应放在目录中分别导入 |
| 缺有效 match_id / 英雄 / 回放损坏 | 保留失败日志，尝试完整原件；不要加入参考组 |
| 输出有 unknown / missing / invalid / 丢弃提示 | 回到原始 JSON 与游戏回放核验，记录处置结果 |
| 修改解析代码后仍然 cached | 当前缓存不按代码/解析器版本失效；用独立数据目录检查新结果 |
| 需要重解析 | 先备份原始 Demo 和 data；`--force` 会替换当前源文件对应的 JSON 与索引，不保留历史运行 |
| 强制重跑中断 / data 搬迁后路径失效 | 当前无自动恢复/重建命令；保留原目录和日志，优先从原件导入新的数据根目录后核对 |

比较新解析规则时，可使用 `--data-dir data/reparse-check`，让旧结果保留在原来的索引中；
不要把两个目录的记录拼起来当成更多比赛。完整的版本缓存、提交恢复和搬迁支持见 D02～D06。

OpenDota 是另一条可选入口：`fetch <match_id>` 缓存原始响应，再 `report data/raw/<match_id>.json`。
其实际命令见 README。它不下载 Demo、不自动申请解析，也不进入当前 Demo 索引。

## 5. 可复制的人工核验记录

把本节复制为本地 `data/validation/批次名称.md` 并填写；这些信息**不会被当前程序自动读取**。
仅当决定公开且完成脱敏后，再把概括性结论放入文档，不提交个人原始数据。

### 范围与环境

| 字段 | 填写值 |
|---|---|
| 标注批次 / 标注日期 / 复核人 | 待填写 |
| 英雄 / 位置 / 位置确认依据 | 待填写 |
| 补丁 / 模式 / 各自来源 | 待填写；未知或冲突必须明示 |
| 比赛日期及来源 | 待填写；后续时间划分需要 |
| 目标装备 key（3～5 件） | 待填写 |
| match_id + player_slot 清单 | 待填写；3～5 场只是起点 |
| 代码提交 / Python / Gem / 适配器与 schema 版本 | 待填写 |
| 源文件 / 解包 Demo / raw JSON hash | 从 manifest 摘录，并注明哪些已重新核验 |
| 游戏内时钟到游戏秒数的换算 | 待填写；保留赛前负数与暂停场景 |
| 核验对象和时间窗口 | 全场目标装备，或预先固定的连续窗口；不能只挑容易匹配的事件 |
| 匹配规则与时间容差 | 查看结果前确定；按回放可观察精度制定并注明理由 |
| 尚未覆盖的边界场景 | 赛前、重复、配方、自动合成、暂停、送达等逐项标记 |

### 双向标注步骤

1. 先从游戏回放独立标注所选范围的所有目标事件，保存游戏时钟、事件类型和本地截图/笔记位置。
   无法看清或无法区分购买/合成的事件标为无法判定。
2. 再与解析日志做一对一匹配。重复购买分别编号，一条输出不能匹配两条人工记录。
3. 从解析日志另外抽查 10～20 条作为初步正确性检查；含可见边界场景。
4. 只比较同一事件语义的时间；不能把送达比购买晚的差值当成解析误差。
5. 对漏检、额外记录和偏移回溯 raw JSON，区分上游缺失、适配过滤、时钟换算和人工标注问题。

| match_id / slot | 物品与重复序号 | 人工事件类型 | 游戏时钟 / 秒数 | 解析秒数 | raw 引用 / 画面证据 | 差值（解析−人工） | 匹配/漏检/额外/无法判断 | 原因与处置 |
|---|---|---|---|---|---|---|---|---|
| 待填写 | 待填写 | purchase / assembly / delivery 等 | 待填写 | 待填写或缺失 | 待填写 | 待填写或不适用 | 待填写 | 修复 / 排除 / 保留未知 |

### 批次结论

- 人工可判定目标事件数、匹配数、漏检数；解析记录数、可判定额外记录数、无法判断数。
- 在预先定义且语义一致的范围内计算漏检比例；分母为人工独立标注的可判定目标事件。
  无法判断数单列；额外记录需复核后才能认定误检。
- 对已匹配且语义相同的事件报告绝对时间误差中位数和最大值，并记录有方向的系统偏移。
- 按装备、场景、数据源列出问题；说明哪几场/哪种装备可继续分析，以及被排除的原因。
- 决定：继续参考组 / 修复后重验 / 缩小装备范围 / 仅保留日志浏览。

小样本用于发现问题，不作为总体准确率证明。未解决的系统性偏移、目标装备定义歧义应阻止相关分析。

## 6. 每次开发的完成流程

从 roadmap 选一个任务 → 明确输入输出与失败情形 → 加相关正反例 → 实现 → 验收 → 更新文档与 TODO → 小提交。
先实现 D01，后续遵循任务依赖；已有测试替身不代替真实回放语义核验。

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\pytest.exe -q
```

数据结构变化附迁移/兼容说明，解析规则变化重验固定的已核对样本；
发布比较或模型结果时保存数据清单、排除原因、配置及环境快照。
先完成一个英雄的可靠比较报告，再决定是否投入案例检索和预测。
