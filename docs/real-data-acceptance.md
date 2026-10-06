# 真实回放采集与准入

更新：2026-10-06。真实验收与离线 CI 分开运行，禁止把合成数据、HTTP 请求成功、解析成功或 Actions 绿色状态当作训练资格。

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

[审计实现](../src/dota_items/data/acceptance.py) 输出 `pipeline_status`、`hold_reasons`、逐玩家通道覆盖率、坐标范围、最长采样间隔、监督标签数量和未知/截尾原因。时间核验复用 Gem 的暂停感知时钟，不使用简单的 `tick / 30` 替代比赛时间。

坐标保留 Gem 的 Source 2 世界单位。上游通过 cell 与局部向量还原坐标，不能假定为地图像素、0–256 网格或 0–1 归一化值；实测最小/最大值仅是本批分布，不可直接升级为所有英雄/补丁的合法边界。见 [Gem 0.10 坐标实现](https://github.com/whanyu1212/gem-dota/blob/v0.10.0/src/gem/extractors/_snapshots.py)。

当前审计是独立验收入口，尚未接入 `build-dataset` / `build-samples` 的强制门禁。未审计数据仍可能被手动标注后纳入旧入口，调用者必须使用验收清单筛选；统一门禁属于 D05/C01 的剩余工作。

## 购买口径修正

真实比赛 `9031383523` 中，原清洗结果比 OpenDota 多 29 条 `ward_dispenser` 记录；这些是组合真假眼事件。清洗版本 `coach-preparation/2` 按 [OpenDota 购买投影规则](https://github.com/odota/core/blob/master/svc/util/compute.ts) 排除 `recipe_*` 和 `ward_dispenser`，在质量报告记为 `exclude`，不混入数据损坏的 `quarantine`。免费假眼 `ward_observer` 和真实重复购买继续保留。

原始输入与 Gem 证据不改写，历史 /1 产物也不覆盖；新清洗版本生成新的 preparation ID，历史快照应保留原语义。`no_purchase` 仅表示投影内没有购买记录，不代表没有买配方、没有花钱或没有其他动作。

已备份的真实回放可通过 `python scripts/audit_saved_replays.py --source data/acceptance --output data/regression` 重跑清洗与审计。该命令校验 demo 哈希并复用已有 Gem 原始导出，**不声称重新解析二进制**。[回归工作流](../.github/workflows/replay-regression.yml) 从固定采集任务恢复产物后执行同一入口，输出修正前后购买对照与状态冲突片段。

## 结果解释和保留

`report.json` 的 `downloaded` 只表示取得字节；`status=collected` 只表示达到下载数量。逐场 `prepared` 表示 prepare 完成；真正的机械校验结果看 `audit.pipeline_status`。没有 audit 或处于 `held` 时不得认定通过。预期的网络/数据问题记录为报告结果，程序错误仍使任务失败。

发现样本用于规则校准和后续回归，不作为最终模型测试集。重跑发现命令会得到新比赛，固定回归应保留已下载的 demo、SHA-256、元数据、精确依赖版本与源码提交。

Actions 产物有保留期限，不是永久对象存储。下载 artifact 后应保留到自己的数据目录并备份；回放 CDN 链接也可能过期。自动流程没有游戏客户端，尚未完成人工游戏画面对照、完整事件漏检率或正确决策判断。
