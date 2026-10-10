# 知识维护、路径映射与证据恢复

**当前范围**：按[7.41f 主线](development-mainline.md)维护全部新结论；已有未标版本来源保持原字节/原状态，不重标成已认证7.41f。命石残留不进入推荐。开发文档职责见[全量盘点](documentation-inventory.md)。

2026-10-10 用户要求：本轮所有持久化资料和路径记录纳入 `xrfc/dota2-timing`，后续开发持续同步维护仓库。仓库是可发布成果的规范位置；临时输出与外部大文件另行保存。这是后续工作的维护约定，不代表已创建后台定时任务。

## 路径迁移清单

以下旧路径相对于原 OpenClaw workspace；规范路径相对于仓库根目录。旧工作稿保留，不删除；后续修改以仓库为准。

| 原位置 | 仓库规范位置 | 内容与边界 |
|---|---|---|
| `study/dota2-hero-capabilities/` | [knowledge/hero-capabilities/](../knowledge/hero-capabilities/README.md) | 官网快照、全英雄档案、评估脚本、来源及测试 |
| `study/dota2-event-trace-9031371970/` | [learning/exercises/event-lineage/9031371970/](../learning/exercises/event-lineage/9031371970/README.md) | 购买事件追踪、讲义及原始核对结果 |
| `artifacts/dota2-timing-evidence/7.41f-2026-10-06/` 中的清单与收据 | [knowledge/evidence/7.41f-2026-10-06/](../knowledge/evidence/7.41f-2026-10-06/README.md) | 来源／哈希／历史核验元数据，不含归档本体 |
| 原始 ZIP 与 `.dem.bz2` | 外部证据目录，以 `--evidence-root` 传入 | 大文件不进 Git；恢复后按收据验证 |
| 本次新增冷启动候选 | [knowledge/hero-capabilities/cold-start/](../knowledge/hero-capabilities/cold-start/manifest.json) | 可复现、冻结的公开事实提取候选，未准入 |
| 新追踪运行结果 | `learning/output/event-lineage/9031371970/trace-result.json` | 默认忽略；不覆盖已提交的历史结果 |

这次维护时，仓库本地检出位于 `/home/node/.openclaw/workspace/tmp/dota2-timing-audit-20261009`；外部证据位于 `/home/node/.openclaw/workspace/artifacts/dota2-timing-evidence/7.41f-2026-10-06`。这两项是历史环境记录，不是运行程序的硬编码依赖。克隆到其他位置时使用相对仓库路径和显式参数。

## 外部证据如何恢复

[download-manifest.json](../knowledge/evidence/7.41f-2026-10-06/download-manifest.json)保存四份制品的原仓库、artifact ID、文件名、大小、SHA-256 和 GitHub 元数据。Actions 制品可能过期；清单不能保证服务仍有文件。原归档已在上述外部目录留存，但不是异机备份。

恢复步骤：

1. 从现有保存副本恢复四份原始 ZIP，或在制品仍有效时按清单从原 GitHub artifact 下载。不要从候选数据重建并冒充原始证据。
2. 比对 ZIP 文件的大小与 SHA-256，并检查 ZIP CRC。
3. 从回放／工作区原归档恢复 `replays/` 到外部证据目录；复制元数据收据到同目录。原 ZIP 保持不变。
4. 按 [verification-receipt.json](../knowledge/evidence/7.41f-2026-10-06/verification-receipt.json)检查回放压缩文件和 raw Gem SHA-256。
5. 安装项目 replay/data 依赖，用本课脚本对已保存的解析证据重现事件链：

```bash
.venv/bin/python learning/exercises/event-lineage/9031371970/trace_event.py \
  --evidence-root /path/to/dota2-timing-evidence/7.41f-2026-10-06
```

Windows 使用 `.venv/Scripts/python.exe`。该脚本不重解析二进制；结果默认进入忽略的 `learning/output/`。历史单事件结果 18 项核对通过，不能代替游戏画面核验。

## 后续维护约定

- 每轮任务同时更新实现、来源／路径、状态、变更记录及相关测试，不只把成果留在聊天或临时目录。
- 官网资料是有日期、哈希和语言标记的冻结快照。内容变化必须记录新快照与差异；不得静默修改来源后沿用旧哈希和核验结论。
- 原始 JSON 与固定候选 JSONL 通过 `.gitattributes` 禁用换行转换，候选导出固定 UTF-8/LF，并检查实际文件字节哈希，避免平台搬迁改变冻结内容。
- 每项解释区分官方事实、检索线索、来源核对、共同认可的机制、决策监督；未知不写成不存在。
- 不以资料覆盖、候选条数或 CI 通过宣称全英雄理解、训练准入或模型效果。
- 不删除来源分支或旧证据；需要改变状态时保留历史日期和依据。
- 通过开发分支与 PR 发布，检查精确提交上的 CI；按授权合入 main 后同步本地。大型回放、个人资料、环境、密钥、模型产物继续不进 Git。

维护全链条的检查入口：`python scripts/check.py`。知识模块边界测试已纳入 learning scope，因此 Linux 和 Windows CI 都会执行，不需要额外采集或大模型 API。
