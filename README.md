# DOTA2 出装与装备时机分析

一个从自己的比赛出发的学习项目：重建装备购买日志，逐步加入同类对局比较和相似案例检索。

**当前 v0.1 可运行：**离线 JSON → 装备事件 → 候选装备首次记录 → HTML/JSON 报告；支持 OpenDota 比赛抓取与原始缓存。

**尚未实现：**参考组、角色/版本过滤、经济条件比较、相似案例与机器学习。不要把当前报告理解成出装推荐。

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

配置在 `configs/analysis.json`，`candidate_items` 使用上游物品 key。当前只指定关注装备，英雄、角色和版本限制留给后续参考组模块。

## 时间语义

- 时间以比赛开始后的秒数表示，允许赛前负数。
- 所有事件的 `event_kind` 为 `purchase_record`，不推断当前库存。
- 首次记录不等于合成完成、信使送达、可用或首次使用。
- 日志缺失、空日志、某装备无记录分别处理；都不能直接证明“没有购买”。
- 保留重复购买和未知物品 key；不从最终六格装备倒推获取时间。
- 每个事件保存原始 JSON 字段位置，每份报告保存源数据 SHA-256。

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

1. 选定一个英雄、位置、补丁版本和 3～5 件装备。
2. 获取自己的 3～5 场比赛，人工核验 10～20 次装备事件。
3. 建立参考组，展示记录比例、时间分布、有效比赛数与缺失率。
4. 在固定历史时刻检索相似案例，禁止使用未来字段。
5. 数据可靠后，比较规则与机器学习基线。

完整设计见 [工程设计](docs/engineering-design-v0.1.md)，实施事项见 [开发计划](docs/roadmap.md)。

## 数据来源

- [OpenDota API](https://docs.opendota.com/)
- [OpenDota 购买日志处理](https://github.com/odota/core/blob/master/svc/util/compute.ts)
- [OpenDota 数据类型](https://github.com/odota/core/blob/master/global.d.ts)
- [装备/英雄静态资料](https://github.com/odota/dotaconstants)

本项目是独立学习项目，与 Valve 或 OpenDota 没有隶属关系。代码采用 MIT 许可；第三方数据、游戏资源和依赖遵循其各自许可与使用条款。
