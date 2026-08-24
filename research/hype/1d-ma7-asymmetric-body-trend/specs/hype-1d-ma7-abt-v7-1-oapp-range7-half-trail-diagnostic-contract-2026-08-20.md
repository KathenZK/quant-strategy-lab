# HYPE-1D-MA7-ABT-V7.1 OAPP 七日振幅半距市价保护诊断合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / not promoted / not live-ready`。本合同响应用户提出的“多头 OAPP 改成：持仓最高价跌掉过去已收盘 7 天最高价减最低价的一半就市价平”。不修改 V7.1，也不授权 runner 变更。

## 1. 唯一解释与候选

本轮只替换 long OAPP，不改 native MA7 迟滞、`1.5ATR` 日线 trailing、空头 RSI、cooldown、成本、funding 或 PEHC 规格本身。

唯一新增候选 `R7H`（range-7 half trail）：

1. 关闭 long OAPP 的 `0.5ATR` 激活、`10%` 峰值回吐、2 日确认和次日 open 成交。
2. 持仓最高价 = 入场后已完成小时的最高价；同一根 `1h` 内不假设先创新高再打回吐，只用上一小时及更早的最高价生成止损。
3. 已收盘 7 日振幅 = 当前未完成 UTC 日之前连续 7 根已闭合日 K 的 `max(high)-min(low)`。不足 7 根则本小时不启用 R7H。
4. 触发：`1h` 开盘或最低价触及 `holding_high - 0.5 * range7`。跳空按当时 open 参考价成交，盘中触及按止损价成交，并计不利滑点与手续费。
5. R7H 只把多头打成 flat，不走 `protective_stop` 的 MA-only forced short。若 R7H 与 `1.5ATR` trailing 同一小时都可触发，取更紧（更高）的止损；并列时保留原 `protective_stop`。
6. R7H 视为 OAPP 的利润保护替代，因此允许启动 PEHC shadow；shadow 仍按 `PEHC_294` 的下一 UTC open 复核，不在触发小时内补扫剩余小时。
7. native MA7 或原 `1.5ATR` protective/trailing 若更早触发，仍按 V7.1 原优先级与 forced-short 合同退出。

## 2. 控制与审计

- 控制：exact `HYPE-1D-MA7-ABT-V7.1`。
- 已知对照：关闭 long OAPP；不重新搜索参数。
- Canonical 窗必须复现控制 `+711.04% / -18.40% / 20笔`。
- 扩展窗必须复现 `2026-08-09 55.113` 开多与控制的 `2026-08-16 56.894` OAPP 平仓。
- 对 R7H 报告 canonical、扩展窗、8bps、额外 1 日 lag、funding-off、近期切片、R7H/OAPP/PEHC 次数和改变的 long episode。
- 单独报告 8 月事件反事实是否被 R7H 市价打出、或仍 terminal-censored。

## 3. 判定

- 若 R7H 与 OAPP off 路径等价，应明确写“本样本中等价于关闭 OAPP”，不得包装成独立改进。
- 若 canonical 收益下降、MDD 超过 20%，或 PEHC 贡献明显消失且没有收益/回撤双优，不建议替换 V7.1。
- 8 月事件已揭示，只能验证规则行为，不能作为晋升证据。
- 本轮只能给出 `KEEP V7.1`、`SHADOW R7H` 或 `NO-GO R7H`；不得登记 V7.2。
