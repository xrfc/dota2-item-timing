# DOTA2 AI 教练基础设施

从职业或高分回放中准备训练数据，用自己的深度学习模型复盘出装与路线决策。当前版本 **0.4.0** 已实现 demo 清洗、历史特征/未来标签、训练集预处理和模型执行接口；实际网络、训练算法和效果评估将在下一阶段实现。

## 当前能做什么

- 批量导入 `.dem`、压缩回放或比赛 JSON，记录购买、位置和自身经济时序。
- 一条 `prepare` 命令生成特征、标签、缺失掩码和清洗报告；`build-samples` 输出训练数组。
- 校验证据、按比赛去重、人工标注参考选手，固定按比赛划分的数据集。
- 调用你实现的训练/推理程序，保存配置、日志、状态和模型产物。
- 在没有模型时生成购买事实报告；接入模型后展示候选出装/路线及引用的观测记录。
- 用合成样本离线验证基础设施。Linux Python 3.11/3.12 和 Windows Python 3.12 已通过 CI。
- 独立采集指定补丁的公开高分候选回放，保存来源与逐场管线审计；[真实数据验收](docs/real-data-acceptance.md)说明准入边界和复现方法。

当前没有网页上传、自动获取职业回放、可用模型权重或“决策正确率”。已完成一批 7.41f 真实回放的采集与管线审计；坐标和经济字段的游戏语义核验仍未全部完成。完整边界见[完成度与验证证据](docs/project-status.md)。

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
python scripts/bootstrap.py --replay --data --dev
python coach.py --workspace coach-workspace/real init
python coach.py --workspace coach-workspace/real prepare /path/to/replays
```

将 `/path/to/replays` 换成自己的目录。然后标注补丁、角色、参考玩家与职业/高分来源，再构建数据集。完整操作见[数据管线](docs/data-pipeline.md)和[教练工作流](docs/coach-workflow.md)。

`coach.py` 自动使用项目的 `.venv`；安装后的等价入口为 `dota-coach`。工作区默认是当前目录的 `coach-workspace/`，也可通过 `DOTA_COACH_WORKSPACE` 设置。项目不自动读取 `.env`。

## 技术选型

| 选择 | 当前用途与理由 | 主要代价 |
|---|---|---|
| Python 3.11+ | 数据处理、CLI 和未来 PyTorch 模型共用语言 | 大文件处理和并行解析需要额外设计 |
| Gem（可选） | 复用 Dota 2 回放解析能力，项目负责语义适配 | 依赖解析器及游戏版本，需要真实样本核验 |
| pandas + scikit-learn（data 可选依赖） | 向后时间对齐、填补/标准化/类别编码 | 目前整 split 在内存处理，依赖真实语义验收 |
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
  → 清洗、历史特征与未来标签 → 仅 train 拟合预处理 → NumPy 数组
  → 自定义训练器（待实现）→ 运行记录 → 模型登记
  → 自定义预测器（待实现）→ 事实 + 候选决策报告
```

观察快照保留整场数据；`build-samples` 生成与其绑定的独立样本快照。训练时必须使用任务 mask 排除未知/截尾标签，推理复用保存的预处理参数。报告中的时间引用检查无法替代模型内部的数据泄漏审计。

## 文档与开发

- [文档索引](docs/README.md)：各文档职责与建议阅读顺序。
- [项目完成度](docs/project-status.md)：已实现、已验证、待补足。
- [架构](docs/engineering-design.md)与[数据契约](docs/data-contracts.md)：代码边界和真实接口。
- [日常操作与恢复](docs/workflow.md)、[验证与交付](docs/validation-and-delivery.md)。
- [任务清单](docs/roadmap.md)、[风险复核](docs/project-review.md)。
- [独立学习区](learning/README.md)：组件地图、技术选型、交互实验和 L01–L12 实践计划。运行 `python learning/build.py`，打开 `learning/output/index.html`。
- [贡献指南](CONTRIBUTING.md)、[变更记录](CHANGELOG.md)。

旧入口 `dota-items fetch / ingest-demo / data-status / report` 保留，可继续生成购买事实报告；它的缓存和校验边界见[操作指南](docs/workflow.md)。新工作区的去重、快照和证据校验不能反推成旧入口也具有同等保障。

开发检查：

```bash
python scripts/bootstrap.py --dev --replay --data
python scripts/check.py
```

检查入口自动使用项目 `.venv`，Linux、macOS 和 Windows 使用同一命令。安装 Node.js 22+ 可执行学习区的 JavaScript 检查。测试中的模型程序是接口桩，不能作为训练效果证据。许可证：[MIT](LICENSE)。
