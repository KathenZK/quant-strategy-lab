# BIN-15M-AS6S V5 代码无效参数等价审计（2026-07-15）

本审计逐字段改成明显不同的值，并在 `4 bps/K+1`、`8 bps/K+1`、`4 bps/K+2` 三个场景比较完整交易路径哈希。

- 预期实例：`46`
- 已测试：`46`
- 精确等价：`46`
- 失败：`0`
- 结论：`PASS`
- 数据严格为 `ts < 2026-07-14T09:00Z`；未读取未来OOS，未修改V5。

只有三场景的信号时间、进出场、方向、成交价、strength原始分数、收益、MAE和退出原因全部一致，才判定可从clean接口移除。

结构化结果：[`binance_as6s_v5_inert_parameter_equivalence_2026-07-15.json`](../artifacts/binance_as6s_v5_inert_parameter_equivalence_2026-07-15.json)。
