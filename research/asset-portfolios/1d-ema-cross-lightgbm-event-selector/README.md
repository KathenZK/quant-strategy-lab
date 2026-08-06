# Binance-1D-EMA-Cross-LightGBM-Event-Selector

- 完整家族名：`Binance-1D-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-1D-EMAX-LGBM`
- 市场：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`1d`
- 机制：已闭合 `1d` K 线上 `EMA21/EMA96` 交叉产生方向事件（金叉只做多、死叉只做空），固定 ATR bracket + 96 根（96 天）超时出场；周期梯度扫描（15m → 1h → 4h → 1d）的第四个点。
- 防串线：与 [`BIN-15M-EMAX-LGBM`](../15m-ema-cross-lightgbm-event-selector/README.md)（archived）、[`BIN-1H-EMAX-LGBM`](../1h-ema-cross-lightgbm-event-selector/README.md)、[`BIN-4H-EMAX-LGBM`](../4h-ema-cross-lightgbm-event-selector/README.md) 同机制不同周期，互不继承证据；不是 [`Binance-1D-Turtle-Breakout`](../1d-turtle-breakout/README.md)（Donchian 突破，非 EMA 交叉）的增量。
- 数据口径：全市场 `1d` K 线由已审计 `1h` Vision 归档确定性重采样（UTC 日边界 OHLCV 聚合），衍生口径记录于基线报告；`2026-01`–`2026-06` 对本机制家族为污染 holdout。

## 当前状态

- 状态：`archived`（P2 组合级 kill gate 未过）
- 尚未注册版本；身份与终局裁决见 [binance-1d-emax-lgbm-core-ledger.md](binance-1d-emax-lgbm-core-ledger.md)。事件级空头优势真实（净 +0.733 ATR、逐年全正）但集中在成簇崩盘波，预注册资金框架下容量逆向选择使其不可收割（2022 利润占比 383%）。1d 为周期梯度最后候选，EMA 交叉机制家族四周期关账；重启条件见 P2 诊断第 4 节。

## 入口

- 主账：[binance-1d-emax-lgbm-core-ledger.md](binance-1d-emax-lgbm-core-ledger.md)
- 决策日志：[decision-log.md](decision-log.md)
- P1 基线诊断：[bin-1d-emax-lgbm-p1-baseline-2026-07-24.md](diagnostics/bin-1d-emax-lgbm-p1-baseline-2026-07-24.md)
- P2 组合级诊断（kill-gate 判定）：[bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md](diagnostics/bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md)
- 契约：[组合级](specs/bin-1d-emax-portfolio-contract-2026-07-27.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
