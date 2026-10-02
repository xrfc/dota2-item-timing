# DOTA2 AI 教练 · 回放与模型工作流

目标是从职业/高分 Demo 学习出装和地图决策，再复盘自己的比赛。
当前 v0.3 先实现**模型训练前后的基础设施**，深度学习模型与训练方法留到下一阶段。

```text
回放文件夹 → 解析与证据校验 → 人工标注来源/版本/位置 → 固定数据集
                                                        ↓
HTML 复盘 ← 预测接口与证据检查 ← 模型登记 ← 你的训练程序
```

**现在可以使用：**批量导入、购买/位置/经济时间序列、数据集版本与按比赛划分、
训练程序执行接口、实验配置和日志、模型产物登记、预测接口、HTML/JSON 复盘。
框架不依赖 PyTorch、GPU 或外部语言模型服务。

在仓库根目录执行（Python 3.11+，Windows/macOS/Linux）：

```bash
python scripts/bootstrap.py --replay --dev
python coach.py demo
python coach.py doctor
```

`coach.py` 自动使用项目的 `.venv`，不需要手动激活。`demo` 用 6 场合成数据验证导入、
数据集构建和报告；不会训练模型，也不表示教练效果。只跑 JSON 示例时可省略 `--replay`。

真实回放流程和模型接入见 **[教练工作流](docs/coach-workflow.md)**。
`python coach.py init` 会生成工作区、JSON Schema 和待实现的训练/推理适配器。
已有 `dota-items` 命令仍用于原有事实报告。

**当前工程可运行：**离线 JSON → 装备事件 → 候选装备首次记录 → HTML/JSON 报告；支持 OpenDota 比赛抓取与原始缓存。

**本地 replay 管道：**DOTA2 `.dem`（或 `.dem.bz2` / `.dem.zst` / `.dem.zip`）
→ Gem 原始 JSON → 项目标准 JSON → 现有报告，同时建立 SQLite 索引。解析完全离线。

**尚未实现：**模型训练算法、胜率/决策价值估计、参考组统计、相似案例、网页上传界面。
数据集已支持按人工标注的版本/位置和英雄筛选。当前事实报告不构成出装推荐。

## 文档导航与当前重点

2026-10-02 增加可执行工作流。新工作区与适配器契约以 [教练工作流](docs/coach-workflow.md)
为准；其他设计文档保留先前分析和后续研究计划。

| 文档 | 用途 |
|---|---|
| [教练工作流](docs/coach-workflow.md) | v0.3 命令、数据集、适配器契约、日志、失败恢复 |
| [工程设计](docs/engineering-design.md) | 全流程、当前数据契约、目标架构和研究边界 |
| [长期技术路线](docs/long-term-roadmap.md) | 模块边界、技术选择、扩展条件与架构决策 |
| [数据与接口契约](docs/data-contracts.md) | 身份、版本、质量、重跑、迁移与接口草案 |
| [验证与交付规范](docs/validation-and-delivery.md) | 测试分层、实验评估、复现、发布和维护 |
| [工程审查](docs/project-review.md) | 基于 v0.2.0 代码的不足、影响与改进依据 |
| [运行与核验流程](docs/workflow.md) | 从单场导入到报告、批处理、故障排查与人工标注模板 |
| [TODO 与阶段验收](docs/roadmap.md) | 有优先级、依赖和完成标准的任务清单 |

当前重点是收集并核验回放，让数据准备与未来模型执行可以重复运行。
新工作区在导入时验证证据，并按 match_id 去重；数据集和模型带文件指纹。
旧流程曾验证一场公开回放，新时序字段仍需真实回放核验，购买记录也不等于装备送达或可用。

## 快速开始

Python 3.11+。在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\dota-items.exe report examples/match.synthetic.json --player-slot 0 --output reports/demo
Start-Process reports/demo/report.html
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/dota-items report examples/match.synthetic.json --player-slot 0 --output reports/demo
```

示例数据完全为合成数据，不是实际比赛或当前版本出装建议。报告不依赖外部脚本/CDN，可以离线打开。

## 分析实际比赛

先缓存比赛，然后选择正确的 `player_slot`。玩家槽位来自比赛 JSON，不能用数组下标代替。

```powershell
.\.venv\Scripts\dota-items.exe fetch 你的比赛ID
.\.venv\Scripts\dota-items.exe report data/raw/你的比赛ID.json --player-slot 0 --output reports/my-match
```

`fetch --refresh` 可重新抓取。部分比赛没有解析购买日志，报告会显示缺失；当前程序不会自动提交解析任务。

可选 API key 通过环境变量 `OPENDOTA_API_KEY` 提供；不要写进命令参数、提交到 Git 或分享原始认证信息。`.env.example` 只是说明，本程序不会自动读取 `.env`。

## 导入已下载的 DOTA2 Demo

首次使用先安装 replay 可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,replay]"
.\.venv\Scripts\dota-items.exe ingest-demo "C:\path\to\match.dem.bz2" --data-dir data
.\.venv\Scripts\dota-items.exe data-status --data-dir data
```

`ingest-demo` 每成功导入一场，会输出包含 `normalized_json` 的 JSON 行。
把该路径传给已有的 `report` 命令：

```powershell
.\.venv\Scripts\dota-items.exe report "data\matches\<输出中的source_sha256>\normalized.json" --player-slot 0 --output reports/my-match
```

也可以传入存放回放的目录；默认只扫描该目录，添加 `--recursive` 扫描子目录。
相同输入内容再次导入会跳过解析，`--force` 可重新解析。批量导入时一场失败不会阻止
其他比赛，但命令会返回非零退出码。Gem 对大型比赛的离线解析可能需要数分钟。

当前去重依据是输入文件字节，同一 Demo 的不同压缩格式仍会产生多条导入记录。
`data-status` 的 `matches` 是导入记录数；缓存尚未验证输出内容和解析规则版本。
`--force` 会替换旧产物，文件与数据库尚无统一恢复协议；重跑前保留原件和数据备份。
具体限制与改进任务见 [工程审查](docs/project-review.md)。

文件位于 `data/matches/<源文件 SHA-256>/`：

| 文件 | 含义 |
|---|---|
| `raw-gem.json` | Gem 的完整、未简化解析结果 |
| `normalized.json` | 可直接供本项目 `report` 使用的玩家与购买事件 |
| `manifest.json` | 原文件和解包后回放哈希、解析器版本、数据质量提示 |
| `data/index.sqlite` | 比赛、玩家、购买事件的本地索引 |

原始 JSON 可能包含玩家昵称、Steam ID、聊天等内容，因此整个 `data/` 默认不提交 Git。
项目不会把 `.dem` 复制进仓库，也不会自动把真实比赛上传到 OpenDota。

Gem 使用 0–9 的玩家编号，本项目标准 JSON 转为 OpenDota 风格槽位：天辉 0–4、
夜魇 128–132。`purchase_log` 中无法确定时间的事件会跳过并在报告中提示；装备 key
去掉 `item_` 前缀。比赛版本目前保持未知值，不从当前静态资料反推历史版本。

管道已用一场公开的完整比赛（ID `8822520406`）做端到端测试：10 名玩家、362 条购买事件，
事件都能追溯到原始 Gem JSON。自动化测试使用合成数据验证边界情况。
**购买时间的游戏语义仍需人工核验**：先核对 10–20 条购买记录，再从回放独立标注目标装备，
反向检查漏检。记录模板与判定方法见 [运行与核验流程](docs/workflow.md)。

配置在 `configs/analysis.json`，`candidate_items` 使用上游物品 key。当前只指定关注装备，英雄、角色和版本限制留给后续参考组模块。

## 时间语义

- 时间以比赛开始后的秒数表示，允许赛前负数。
- 所有事件的 `event_kind` 为 `purchase_record`，不推断当前库存。
- 首次记录不等于合成完成、信使送达、可用或首次使用。
- 日志缺失、空日志、某装备无记录分别处理；都不能直接证明“没有购买”。
- 保留重复购买和未知物品 key；不从最终六格装备倒推获取时间。
- 每个事件保存原始 JSON 字段位置，每份报告保存来源指纹；Gem 报告当前使用声明的原始 JSON
  SHA-256，尚未自动重新核验对应证据文件。

实际比赛字段语义需要人工对照回放。当前测试验证代码与合成样本，不证明实际比赛解析准确。

## 项目结构

```text
src/dota_items/
  sources/       数据源、缓存、有限重试
  domain.py      类型、单位、证据
  normalize.py   上游字段映射与质量检查
  analysis.py    首次记录分析
  report.py      自包含 HTML
  cli.py         命令入口
configs/         关注装备
examples/        可公开的合成输入
tests/           语义边界、抓取与端到端检查
docs/            工程设计与后续计划
```

实际数据和生成报告分别在 `data/`、`reports/`，默认不提交。测试样本仅使用合成数据，不包含账号信息。

## 开发检查

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\pytest.exe -q
```

GitHub Actions 位于 `.github/workflows/ci.yml`，在 Python 3.11 / 3.12 上运行检查、测试与示例报告。
版本号在 `pyproject.toml` 和 `src/dota_items/__init__.py`。

## 下一步

1. 完成 D01：验证 raw 文件、证据引用和测试 fixture；再处理去重、缓存和重跑一致性。
2. 选定一个英雄、位置、补丁、模式和 3～5 件装备，核验自己的 3～5 场比赛。
3. 建立去重且来源明确的参考组，展示时间分布、分母、观察窗口与缺失率。
4. 首个比较报告通过验收后，按兴趣加入历史案例检索和行为预测实验。

完整设计见 [工程设计](docs/engineering-design.md)，实施事项见 [TODO 与阶段验收](docs/roadmap.md)。

## 数据来源

- [Gem 本地回放解析器](https://github.com/whanyu1212/gem-dota)
- [OpenDota API](https://docs.opendota.com/)
- [OpenDota 购买日志处理](https://github.com/odota/core/blob/master/svc/util/compute.ts)
- [OpenDota 数据类型](https://github.com/odota/core/blob/master/global.d.ts)
- [装备/英雄静态资料](https://github.com/odota/dotaconstants)

本项目是独立学习项目，与 Valve 或 OpenDota 没有隶属关系。代码采用 MIT 许可；第三方数据、游戏资源和依赖遵循其各自许可与使用条款。
