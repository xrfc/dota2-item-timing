# 真实回放采集与准入

更新：2026-10-06。真实验收与离线 CI 分开运行，禁止把合成数据、HTTP 请求成功、解析成功或 Actions 绿色状态当作训练资格。

## 本轮结果

**8 场真实 demo 已下载并解析；最终 3 场通过机械审计、5 场隔离。完整训练准入仍为 held。** 所有比赛均为 Ranked All Pick，按官方发布时间推定属于 7.41f；采集时的玩家资料中共 78 个 Immortal 段位、2 个 Divine V 段位。段位是查询时快照，不是精确 MMR 或永久身份。

| 比赛 | 时长 | 最终人数 | 隔离记录数 | 机械准入与原因 |
|---|---:|---:|---:|---|
| [9031370153](https://www.opendota.com/matches/9031370153) | 37:10 | 10 | 348 | held：暂停边界同秒状态冲突 |
| [9031384340](https://www.opendota.com/matches/9031384340) | 35:07 | 10 | 0 | passed |
| [9031383523](https://www.opendota.com/matches/9031383523) | 30:53 | 10 | 0 | passed；另有 OpenDota 事件对照 |
| [9031380277](https://www.opendota.com/matches/9031380277) | 21:47 | 10 | 294 | held：暂停边界同秒状态冲突 |
| [9031377294](https://www.opendota.com/matches/9031377294) | 31:46 | 10 | 0 | held：slot 4 的 leaver_status=1 |
| [9031375030](https://www.opendota.com/matches/9031375030) | 41:44 | 10 | 18 | held：结束秒的状态冲突 |
| [9031371970](https://www.opendota.com/matches/9031371970) | 38:59 | 10 | 0 | passed |
| [9031369678](https://www.opendota.com/matches/9031369678) | 26:41 | 10 | 0 | held：slot 2 的 leaver_status=1 |

`leaver_status=1` 只作为断线风险证据，不据此判断玩家挂机。暂停和结束边界的记录仍保留在原始证据里；没有通过“选一条看起来合理的记录”消除冲突。

- 压缩回放共 **326,573,660 字节**；初次 prepare 约 **35.9–67.8 秒/场**，这是本次 runner 上的观测，不是性能保证。
- 最终 80 名玩家身份与 API 一致、比赛时长差为 0；**319,659 条时间映射检查，0 条不一致**。这证明导出与 Gem 时钟一致，不是独立游戏画面的时钟验证。
- 全批 5,320 个窗口；通过组 **2,110 个窗口、1,006 个购买标签、2,050 个位移标签**。通过组的 30 秒决策网格上，位置与五个经济字段覆盖率均为 100%。
- 已验证通过组可以转换为 `float32` 数组，形状为 `710×38`、`620×38`、`780×38`；值有限、未知物品标签保留 -1/mask=false。只是数组接口冒烟，没有执行训练、正式角色数据集构建或模型评估。

逐场 SHA-256、原始来源、prepare ID、段位证据、统计与对照明细见 [固定清单 JSON](acceptance/7.41f-2026-10-06.json)；原始解析时的完整环境见 [依赖记录](acceptance/7.41f-2026-10-06.dependencies.txt)。

下载：[8 场 demo 与原始工作区](https://github.com/xrfc/dota2-item-timing/actions/runs/37393085454/artifacts/11382665563)（ZIP 约 460 MiB，**2026-10-13 00:25 UTC 到期**）；[最终审计和派生样本](https://github.com/xrfc/dota2-item-timing/actions/runs/37451030026/artifacts/11406303075)（约 8.5 MiB，2026-11-05 到期）。这两个包分别保留初次解析证据和修正后的派生结果，不可混用旧购买标签。

执行证据：[真实采集](https://github.com/xrfc/dota2-item-timing/actions/runs/37393085454)、[修正后的原始导出回归](https://github.com/xrfc/dota2-item-timing/actions/runs/37451030026)、[75 项工程测试与跨平台 CI](https://github.com/xrfc/dota2-item-timing/actions/runs/37451030005)。

## 复现入口

```bash
python scripts/bootstrap.py --replay --data --dev
.venv/bin/python scripts/accept_replays.py --config configs/acceptance/7.41f.json --output data/acceptance
```

Windows 将解释器换成 `.venv/Scripts/python.exe`。在仓库根目录运行，网络只用于官方补丁表、OpenDota 的只读查询和公开回放下载。使用已有 Gem 解析、prepare 清洗与特征管线，不重新实现 replay 协议。

已有报告的输出目录不能覆盖；再次运行请换 `--output`。添加 `--candidates 旧目录/report.json` 可重试同一批已下载比赛并保留原段位证据，仍会重新获取详情和回放；CDN 过期时需要使用自己备份的 demo。默认命令完成采集即返回 0，外部不可用会明确写成 `incomplete`；需要自动门禁时加 `--strict`，未达到目标管线通过数量就返回 1。

[独立 Actions 工作流](../.github/workflows/real-data-acceptance.yml) 在采集配置变更或手动触发时执行，普通代码提交不重复下载。运行前查看容量和时限配置；解析按场串行，单场子进程超时不会让其他候选永久等待。批次有下载预算和总时限，但尚无独立的解析内存配额。

`data/acceptance/` 为忽略的运行目录；原 demo、OpenDota 响应、官方版本表、prepare 产物、日志和报告不混入源码或学习资料。轻量的最终验收清单进入 `docs/acceptance/`，学习记录仍放在 `learning/`。

## 来源证据与筛选

| 条件 | 本轮规则 | 含义与限制 |
|---|---|---|
| 小版本 | 官方 patch 表中 7.41f 发布后至少 24 小时，比赛结束早于下一补丁或采集时刻 | `time_inferred`，不是从 demo build 直接证实；24 小时是保守的发布边界缓冲 |
| 主版本 | OpenDota 的 `patch=60` 不足以辨认 7.41f | 不依赖网站的全局“最新补丁”横幅判断历史比赛 |
| 高分证据 | `avg_rank_tier >= 75`，`num_rank_tier >= 8` | OpenDota 的最高平均段位档；至少 8 位有段位记录，不等于 10 人均为 Immortal，更不等于已知 MMR |
| 模式 | `game_mode=22`、`lobby_type=7` | 标准 Ranked All Pick；不混入 Turbo、自定义或活动模式 |
| 时长 | 900–5400 秒 | 当前校准队列的范围；范围外不代表非法比赛，应另建验收组 |
| 下载 | API 实际提供公开 `replay_url`，归属于允许的 Valve/国服回放域名 | 无 URL、过期、拒绝访问均保留失败原因，不猜 salt 或绕过访问权限 |
| 身份 | 列表与详情的 match_id、开始时间、时长一致 | 下载后还要核对 demo 身份，不能只信文件名 |

首次查询的 500 条最高段位记录均为 `75`。上游 `averageMedal` 将个人 Immortal 编码 `80` 转成 39 颗累计星，再转回 `75`；平均段位查询参数也封顶 75。因此 `avg_rank_tier >= 80` 会漏掉目标候选。

来源：[官方补丁表](https://www.dota2.com/datafeed/patchnoteslist?language=english)、[7.41f 公告](https://www.dota2.com/newsentry/677383425371407609?l=english)、[OpenDota 查询实现](https://github.com/odota/core/blob/master/svc/api/spec.ts)、[平均段位算法](https://github.com/odota/core/blob/master/svc/util/utility.ts)。这些来源的快照、采集时间或具体运行记录应与最终清单一起保存。

## 准入分层

1. **候选数据**：通过上述版本、段位、模式筛选，有来源记录；尚不能用于训练。
2. **管线审计通过**：真实解析、清洗、证据文件哈希校验成功；10 名玩家的槽位/英雄、比赛身份和时长与 API 对应；有比赛结束状态；观测 tick 转时间一致；没有未处理的清洗隔离或缺失通道。任何失败都进入 `held`，保留原因。
3. **任务数据准入**：还须检查每个玩家的实际覆盖率、标签数量及任务所需语义。原始购买事件只能作为“下一个观察到的购买”；没有连续事件覆盖证据时不能制造 `no_purchase`。位置终点位移只能作为行为模仿目标，不能当作真实路径或路线优劣标签。
4. **决策质量学习**：本轮不批准。职业/高分玩家做过某个行为，并不证明该决策正确；库存、视野、存活状态和队友上下文尚未纳入。

本批通过组的物品标签为 `other=982`、`power_treads=7`、`black_king_bar=17`、`desolator=0`、`no_purchase=0`。另外 907 个窗口覆盖未知、137 个同时购买、60 个右截尾，均不作负例。由此明确：**默认五分类任务暂不准入训练**，不能把缺少的类别当成负样本，也不能用重复采样补出不存在的类别。需要先缩小任务范围或补齐有独立比赛支持的类别；数量达到非零也不等于统计上足够。

一场独立解析对照中，净资产 310 个分钟点有 139 个不同（最大差 272），补刀 10 个不同（最大差 3），反补 1 个不同。这些差异尚未区分完采样时刻和导出误差，因此不设一个宽松容差把它们算成全部通过。

经验字段也存在文档与实测冲突：Gem 0.10 文档把 `xp_t` 描述为升级后重置的等级内进度，但本批 80 名玩家的 `xp_progress` 序列均未出现下降；例如 15 级英雄的末值为 13,407。其与 OpenDota XP 的 310 个分钟点有 296 个一致、14 个不同。当前保留原值和历史字段名，标记 **语义待核验**，不再宣称它是等级内经验；在完成游戏内核验前不得按该含义训练或解释。

[审计实现](../src/dota_items/data/acceptance.py) 输出 `pipeline_status`、`hold_reasons`、逐玩家通道覆盖率、坐标范围、最长采样间隔、监督标签数量和未知/截尾原因。时间核验复用 Gem 的暂停感知时钟，不使用简单的 `tick / 30` 替代比赛时间。

坐标保留 Gem 的 Source 2 世界单位。上游通过 cell 与局部向量还原坐标，不能假定为地图像素、0–256 网格或 0–1 归一化值；实测最小/最大值仅是本批分布，不可直接升级为所有英雄/补丁的合法边界。见 [Gem 0.10 坐标实现](https://github.com/whanyu1212/gem-dota/blob/v0.10.0/src/gem/extractors/_snapshots.py)。

当前审计是独立验收入口，尚未接入 `build-dataset` / `build-samples` 的强制门禁。未审计数据仍可能被手动标注后纳入旧入口，调用者必须使用验收清单筛选；统一门禁属于 D05/C01 的剩余工作。

## 购买口径修正

真实比赛 `9031383523` 中，原清洗结果比 OpenDota 多 29 条 `ward_dispenser` 记录；这些是组合真假眼事件。清洗版本 `coach-preparation/2` 按 [OpenDota 购买投影规则](https://github.com/odota/core/blob/master/svc/util/compute.ts) 排除 `recipe_*` 和 `ward_dispenser`，在质量报告记为 `exclude`，不混入数据损坏的 `quarantine`。免费假眼 `ward_observer` 和真实重复购买继续保留。

原始输入与 Gem 证据不改写，历史 /1 产物也不覆盖；新清洗版本生成新的 preparation ID，历史快照应保留原语义。`no_purchase` 仅表示投影内没有购买记录，不代表没有买配方、没有花钱或没有其他动作。

最终全批排除了 334 条组合眼事件。一场有独立 OpenDota 解析的比赛 `9031383523`，修正后的 346 条购买记录在物品、时间和重复次数上完全一致；其他 7 场缺少同等事件级对照，不能外推为事件完整率 100%。

另修复了 `queen_of_pain`、`anti_mage`、`vengeful_spirit` 别名导致 `hero_id=0` 而遗漏玩家的问题。适配器 2.2 复用 `gem.catalog.heroes` 解析，记录 `hero_identity` 的原名、规范名和 raw 引用；没有用 API 覆盖原始解析值或维护另一份英雄表。新结果全部为 10 玩家并与 API 身份一致，原始 Gem JSON 中的 0 值仍可查。

已备份的真实回放可通过 `python scripts/audit_saved_replays.py --source data/acceptance --output data/regression` 重跑清洗与审计。该命令校验 demo 哈希并复用已有 Gem 原始导出，**不声称重新解析二进制**。[回归工作流](../.github/workflows/replay-regression.yml) 从固定采集任务恢复产物后执行同一入口，输出修正前后购买对照与状态冲突片段。

## 结果解释和保留

`report.json` 的 `downloaded` 只表示取得字节；`status=collected` 只表示达到下载数量。逐场 `prepared` 表示 prepare 完成；真正的机械校验结果看 `audit.pipeline_status`。没有 audit 或处于 `held` 时不得认定通过。预期的网络/数据问题记录为报告结果，程序错误仍使任务失败。

发现样本用于规则校准和后续回归，不作为最终模型测试集。重跑发现命令会得到新比赛，固定回归应保留已下载的 demo、SHA-256、元数据、精确依赖版本与源码提交。

Actions 产物有保留期限，不是永久对象存储。下载 artifact 后应保留到自己的数据目录并备份；回放 CDN 链接也可能过期。自动流程没有游戏客户端，尚未完成人工游戏画面对照、完整事件漏检率或正确决策判断。
