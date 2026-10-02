# 开发与贡献

当前重点是可靠、便于执行的训练前后基础设施。实际模型属于下一阶段；不要用生成随机权重或固定分数的演示代替可验证的模型能力。

## 环境与检查

Python 3.11+。在仓库根目录执行：

```bash
python scripts/bootstrap.py --replay --dev
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q
python coach.py --workspace coach-workspace/dev-check demo
python coach.py --workspace coach-workspace/dev-check doctor
```

Windows 将 `.venv/bin/python` 替换为 `.venv/Scripts/python.exe`。只开发 JSON 工作流可不安装 `--replay`；真实回放解析需要它。测试和 demo 不要求 CUDA、PyTorch 或 API key。

CI 在 Ubuntu Python 3.11/3.12 执行完整检查；Windows Python 3.12 执行工作流测试与 demo，见[配置](.github/workflows/ci.yml)。具体测试边界见[验证与交付](docs/validation-and-delivery.md)。

## 代码边界

- `sources/` 负责外部读取、Gem 解析和观测导出。
- `normalize.py / domain.py / analysis.py / report.py` 保留购买事实管线。
- `workflow/` 负责工作区、质量校验、快照、任务协议和模型报告。
- 训练算法通过适配器接入，不把 PyTorch 作为基础 CLI 的强制依赖。

新增或修改接口时同时更新[数据契约](docs/data-contracts.md)、适配器模板及有意义的边界测试。更改缓存/快照含义时明确版本兼容策略；禁止原地修改已冻结的数据来让旧哈希继续通过。

## 数据与验证

使用明确标注的 synthetic fixture 编写可公开的自动化测试。真实回放、玩家数据、大型模型权重、工作区和密钥不应进入提交；默认忽略规则只覆盖项目约定路径，使用自定义目录时自行检查 `git status`。

真实数据核验需要保存来源、补丁、解析环境和人工对照记录；可不公开回放本体。模型效果必须在独立比赛上验证，不能把桩程序接口测试或同局样本当成泛化结果。

## 提交要求

说明触发问题、最终行为、验证结果和剩余限制。文档变更应核对命令、路径和相对链接；无需为纯文字改动增加镜像实现的测试。

检查完成后提交到开发分支，PR 描述围绕最终变更。同步更新[完成度](docs/project-status.md)、[任务清单](docs/roadmap.md)和[变更记录](CHANGELOG.md)，不要仅把规划写成完成。现有代码与文档有差异时，以代码核验结果修正文档并记录尚未满足的验收条件。
