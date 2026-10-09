# 开发与贡献

当前重点是可靠、便于执行的训练前后基础设施。实际模型属于下一阶段；不要用生成随机权重或固定分数的演示代替可验证的模型能力。

学习计划、练习与个人记录统一放在 [learning/](learning/README.md)。工程贡献以本指南和工程 ToDo 为准。

## 环境与检查

Python 3.11+。在仓库根目录执行：

```bash
python scripts/bootstrap.py --replay --data --dev
python scripts/check.py
python coach.py --workspace coach-workspace/dev-check demo
python coach.py --workspace coach-workspace/dev-check doctor
```

检查入口自动选择 `.venv`，跨平台使用同一命令。可用 `--scope engineering` 或 `--scope learning` 选择检查范围；安装 Node.js 22+ 后执行 JavaScript 检查。只开发 JSON 工作流可不安装 `--replay`；真实回放解析需要它。测试和 demo 不要求 CUDA、PyTorch 或 API key。

CI 在 Ubuntu Python 3.11/3.12 执行完整检查；Windows Python 3.12 执行工作流测试、独立学习检查与 demo，见[配置](.github/workflows/ci.yml)。具体测试边界见[验证与交付](docs/validation-and-delivery.md)。

## 仓库结构与维护约定

```text
src/dota_items/       正式工程包、数据源适配与工作流
tests/              工程回归测试
scripts/            环境准备与统一检查入口
docs/               工程设计、契约、操作、验收与 ToDo
learning/           全部学习资料、可视化、实验、模板和学习测试
knowledge/          公开知识快照、来源记录、待核验解释与冷启动候选
configs/            工程配置示例
examples/           明确标注的公开合成输入
coach.py            自动使用 venv 的工程启动入口
```

新增文件按职责放入现有目录；不保留手工复制的模块、文档副本或空占位目录。正式包只从 `src/` 构建，工程测试放 `tests/`，学习生成器测试放 `learning/tests/`，知识模块的来源／解释／候选边界测试随模块维护并由统一 learning scope 执行。每份文档维护一项主职责，相同命令和验收状态通过链接引用；历史实现通过 Git 查看，不维护版本名副本。

`build/`、`dist/`、缓存和环境属于可再生输出；`coach-workspace/`、`data/`、`reports/` 是工程数据/产物，`learning/output/` 是学习产物，均不提交。清理时可删除已确认的构建和缓存；用户回放、工作区、模型和笔记需先备份，不当作缓存删除。不要创建另一个源码目录来保存生成产物。

## 代码边界

- `storage.py` 维护数据源与工作流共用的文件指纹和存储基础操作。
- `sources/` 负责外部读取、Gem 解析和观测导出。
- `normalize.py / domain.py / analysis.py / report.py` 保留购买事实管线。
- `workflow/` 负责工作区、质量校验、快照、任务协议和模型报告。
- 训练算法通过适配器接入，不把 PyTorch 作为基础 CLI 的强制依赖。

新增或修改接口时同时更新[数据契约](docs/data-contracts.md)、适配器模板及有意义的边界测试。更改缓存/快照含义时明确版本兼容策略；禁止原地修改已冻结的数据来让旧哈希继续通过。

## 数据与验证

使用明确标注的 synthetic fixture 编写可公开的自动化测试。真实回放、玩家数据、大型模型权重、工作区和密钥不应进入提交；默认忽略规则只覆盖项目约定路径，使用自定义目录时自行检查 `git status`。

真实数据核验需要保存来源、补丁、解析环境和人工对照记录；可不公开回放本体。模型效果必须在独立比赛上验证，不能把桩程序接口测试或同局样本当成泛化结果。

公开知识的冻结来源及明确未准入的可再生候选可放入 `knowledge/`，第三方内容保持来源及权利说明，不适用“所有生成输出都忽略”的规则；不将真实回放或完整玩家资料迁入其中。用户要求本轮及后续成果同步仓库，路径映射、证据边界和维护约定见[知识维护](docs/knowledge-maintenance.md)。

## 提交要求

说明触发问题、最终行为、验证结果和剩余限制。文档变更应核对命令、路径和相对链接；无需为纯文字改动增加镜像实现的测试。

检查完成后提交到开发分支，PR 描述围绕最终变更。同步更新[完成度](docs/project-status.md)、[任务清单](docs/roadmap.md)和[变更记录](CHANGELOG.md)，不要仅把规划写成完成。现有代码与文档有差异时，以代码核验结果修正文档并记录尚未满足的验收条件。
