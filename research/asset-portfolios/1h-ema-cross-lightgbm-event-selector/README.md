# Binance-1H-EMA-Cross-LightGBM-Event-Selector

- 完整家族名：`Binance-1H-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-1H-EMAX-LGBM`
- 市场：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`1h`
- 机制：已闭合 `1h` K 线上 `EMA21/EMA96` 交叉产生方向事件（金叉只做多、死叉只做空），固定 ATR bracket + 96 根超时出场；若基线存活，后续沿用 15m 家族的 LightGBM 事件质量选择器设计。
- 防串线：是 [`BIN-15M-EMAX-LGBM`](../15m-ema-cross-lightgbm-event-selector/README.md)（已归档，HARD-GATE-FAILED）机制在 `1h` 周期的独立新研究线，不继承其证据；不是 [`BIN-1H-CSLGBM`](../1h-cross-sectional-lightgbm-selector/README.md) 的版本增量（事件驱动 + bracket 出场，非定时调仓）。
- 立项动机：名义成本固定（约 0.28% 来回）而 `1h` ATR 约为 `15m` 的两倍，成本折 ATR 单位约减半；15m 家族毛期望随价格尺度放大有微弱上升趋势。
- 数据边界警示：`2026-01`–`2026-06` 已被 15m EMAX 与 CSLGBM 揭示，对本机制家族视为污染 holdout；本线如推进到模型阶段，干净 OOS 只能取前瞻窗口（`2026-07` 之后）。

## 当前状态

- 状态：`archived`
- 尚未注册版本；本 README 兼任临时主账。周期梯度终点 1d 组合级 kill gate 未过后，EMA 交叉机制家族四周期整体关账（见 [1d P2 诊断](../1d-ema-cross-lightgbm-event-selector/diagnostics/bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md)第 4 节）；本线基线结论（成本减半、空头残差存在但逼空月脆弱）保留为档案证据。

## 入口

- 决策日志：[decision-log.md](decision-log.md)
- P1 基线诊断：[bin-1h-emax-lgbm-p1-baseline-2026-07-24.md](diagnostics/bin-1h-emax-lgbm-p1-baseline-2026-07-24.md)
- 2026H1 复用窗口审计（非干净 OOS）：[bin-1h-emax-lgbm-2026h1-reused-audit-2026-07-24.md](diagnostics/bin-1h-emax-lgbm-2026h1-reused-audit-2026-07-24.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
