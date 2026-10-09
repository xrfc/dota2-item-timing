# 来源、快照与内容范围

资料采集：2026-10-10（Asia/Shanghai；逐文件 UTC 观察时间见 source-manifest.json）。

## Valve 官方

- 列表：`https://www.dota2.com/datafeed/herolist?language=english` 和 `language=schinese`。
- 详情：`https://www.dota2.com/datafeed/herodata?language=<language>&hero_id=<id>`。
- 127 位英雄，中英文各一份详情；原始响应字节保存在 `sources/`，SHA-256 保存在 [来源清单](source-manifest.json)。
- 来源是官网当前返回值，不是游戏客户端全量实现。接口没有明确 patch 字段；未知枚举、占位参数与语言差异不自动解释。
- 技能文本等第三方内容属于其原权利人。仓库代码许可证不将这些文本重新授权为 MIT；用于训练、公开分发或其他产品时应分别确认适用条款。本次仅记录出处与候选状态，不宣称获得训练许可。

## OpenDota

- 项目：[odota/dotaconstants](https://github.com/odota/dotaconstants)。
- 固定数据：[build/heroes.json](https://github.com/odota/dotaconstants/blob/bf193a550f778dec35debf4d71d05a86bebcc418/build/heroes.json)。
- 用于核对英雄 ID／内部名和读取已发布的宽泛角色标签，不能替代当前官方技能说明，也不能把角色标签解释成比分、实际分路或克制结论。
- 复用时遵循该项目及底层内容各自适用的条款，不将社区来源等同于 Valve 的版本认证。

## 项目派生内容

- 原始响应保持不变；派生说明仅做去除 HTML、字段组织和证据引用。
- 自动关键词匹配全部标为待核验，不进入冷启动候选答案。
- 15 项逐条来源核对属于当前快照的解释示例，仍非全英雄机制验收或最佳出装监督。
- 冷启动导出是来源提取任务，输入与输出共享官方事实，并非独立事实记忆／推理题，不用这种任务的分数宣称模型掌握了 Dota。
