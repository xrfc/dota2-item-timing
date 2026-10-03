# DOTA2 AI 教练基础设施

从职业或高分回放中准备训练数据，用自己的深度学习模型复盘出装与路线决策。当前版本 **0.3.0** 完成了训练前后的本地工作流；实际网络、特征窗口、训练算法和效果评估将在下一阶段实现。

## 当前能做什么

- 批量导入 `.dem`、压缩回放或比赛 JSON，记录购买、位置和自身经济时序。
- 校验证据、按比赛去重、人工标注参考选手，固定按比赛划分的数据集。
- 调用你实现的训练/推理程序，保存配置、日志、状态和模型产物。
- 在没有模型时生成购买事实报告；接入模型后展示候选出装/路线及引用的观测记录。
- 用合成样本离线验证基础设施。Linux Python 3.11/3.12 和 Windows Python 3.12 已通过 CI。

当前没有网页上传、自动获取职业回放、可用模型权重或“决策正确率”。新增位置/经济字段仍需真实回放对照验证。完整边界见[完成度与验证证据](docs/project-status.md)。

## 快速开始

需要 Python 3.11+。在仓库根目录运行，Windows 也可使用这些命令：

```bash
python scripts/bootstrap.py --dev
python coach.py demo
python coach.py doctor
python coach.py status
```

安装需要网络；以上 demo 在安装后可以离线执行。它生成 6 场带 synthetic 标识的比赛、4/1/1 划分的数据集和购买事实 HTML，不执行模型训练。输出 JSON 中的 `report` 是报告路径。

解析真实回放时安装可选依赖：

```bash
python scripts/bootstrap.py --replay --dev
python coach.py --workspace coach-workspace/real init
python coach.py --workspace coach-workspace/real ingest /path/to/replays
```

将 `/path/to/replays` 换成自己的目录。然后标注补丁、角色、参考玩家与职业/高分来源，再构建数据集。完整操作见[教练工作流](docs/coach-workflow.md)。

`coach.py` 自动使用项目的 `.venv`；安装后的等价入口为 `dota-coach`。工作区默认是当前目录的 `coach-workspace/`，也可通过 `DOTA_COACH_WORKSPACE` 设置。项目不自动读取 `.env`。

## 技术选型

| 选择 | 当前用途与理由 | 主要代价 |
|---|---|---|
| Python 3.11+ | 数据处理、CLI 和未来 PyTorch 模型共用语言 | 大文件处理和并行解析需要额外设计 |
| Gem（可选） | 复用 Dota 2 回放解析能力，项目负责语义适配 | 依赖解析器及游戏版本，需要真实样本核验 |
| Pydantic 2 | 配置、模型产物、预测接口校验并导出 Schema | 格式通过不代表游戏语义或模型结论正确 |
| JSON/JSONL + SHA-256 | 可检查、可搬迁的数据包和固定快照 | 全量读取与复制占内存、磁盘；无签名或物理只读保证 |
| SQLite | 旧回放解析缓存的索引 | 尚未统一成新工作区的任务/元数据数据库 |
| Python 子进程 + 静态 HTML | 模型框架独立、日志可追踪，结果可离线查看 | 依赖仍共用环境，没有队列、GPU 调度和完整进程树管理 |

取舍、替代方案及升级条件见[技术选型与优化路线](docs/long-term-roadmap.md)。当前无需 PyTorch、CUDA、外部语言模型 API 或常驻服务器。

## 数据流

```text
回放 / 比赛 JSON
  → Gem 解析与证据校验
  → 工作区数据包 + 人工标签
  → 按比赛划分的固定数据集
  → 自定义训练器（待实现）→ 运行记录 → 模型登记
  → 自定义预测器（待实现）→ 事实 + 候选决策报告
```

数据集保留整场数据，还没有生成决策窗口。训练器需要自行按截止时间取历史，分离未来标签，并仅用训练集拟合预处理。报告中的时间引用检查无法替代模型内部的数据泄漏审计。

## 文档与开发

- [文档索引](docs/README.md)：各文档职责与建议阅读顺序。
- [项目完成度](docs/project-status.md)：已实现、已验证、待补足。
- [架构](docs/engineering-design.md)与[数据契约](docs/data-contracts.md)：代码边界和真实接口。
- [日常操作与恢复](docs/workflow.md)、[验证与交付](docs/validation-and-delivery.md)。
- [任务清单](docs/roadmap.md)、[风险复核](docs/project-review.md)。
- [学习驱动的开发流程](docs/development-workflow.md)：先完成 L01–L12 数据准备任务，配套任务记录、数据审计和防泄漏验收。
- [贡献指南](CONTRIBUTING.md)、[变更记录](CHANGELOG.md)。

旧入口 `dota-items fetch / ingest-demo / data-status / report` 保留，可继续生成购买事实报告；它的缓存和校验边界见[操作指南](docs/workflow.md)。新工作区的去重、快照和证据校验不能反推成旧入口也具有同等保障。

开发检查：

```bash
python scripts/bootstrap.py --dev --replay
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q
```

Windows 将 `.venv/bin/python` 换为 `.venv/Scripts/python.exe`。测试中的模型程序是接口桩，不能作为训练效果证据。许可证：[MIT](LICENSE)。
