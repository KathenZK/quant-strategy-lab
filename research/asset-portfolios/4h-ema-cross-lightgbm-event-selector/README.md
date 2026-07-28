# Binance-4H-EMA-Cross-LightGBM-Event-Selector

- 完整家族名：`Binance-4H-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-4H-EMAX-LGBM`
- 市场：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`4h`
- 机制：已闭合 `4h` K 线上 `EMA21/EMA96` 交叉产生方向事件（金叉只做多、死叉只做空），固定 ATR bracket + 96 根超时出场；周期梯度扫描（15m → 1h → 4h）的第三个点。
- 防串线：是 [`BIN-15M-EMAX-LGBM`](../15m-ema-cross-lightgbm-event-selector/README.md)（archived）与 [`BIN-1H-EMAX-LGBM`](../1h-ema-cross-lightgbm-event-selector/README.md)（explore）同机制在 `4h` 周期的独立诊断线，互不继承证据。
- 数据口径：全市场 `4h` K 线由已审计的 `1h` Vision 归档确定性重采样得到（UTC 4h 边界 OHLCV 聚合），衍生口径记录于基线报告；`2026-01`–`2026-06` 对本机制家族为污染 holdout。

## 当前状态

- 状态：`archived / not promoted / not live-ready`
- 尚未注册版本；本 README 兼任临时主账。原料真实（P1 空头净 +0.25 ATR）但两种可执行形态均未过预注册门槛：裸信号组合回撤超红线（P2）、LightGBM 打分层机制判据未过（V2）。周期梯度终点 1d 组合级 kill gate 亦未过后，机制家族四周期整体关账（见 [1d P2 诊断](../1d-ema-cross-lightgbm-event-selector/diagnostics/bin-1d-emax-lgbm-p2-portfolio-control-a-2026-07-27.md)第 4 节）；重启条件见 V2 诊断第 5 节。

## 入口

- 决策日志：[decision-log.md](decision-log.md)
- P1 基线诊断：[bin-4h-emax-lgbm-p1-baseline-2026-07-24.md](diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md)
- P2 组合级诊断（对照组 A）：[bin-4h-emax-lgbm-p2-portfolio-control-a-2026-07-24.md](diagnostics/bin-4h-emax-lgbm-p2-portfolio-control-a-2026-07-24.md)
- V2 打分层诊断：[bin-4h-emax-lgbm-v2-scoring-2026-07-24.md](diagnostics/bin-4h-emax-lgbm-v2-scoring-2026-07-24.md)
- 契约：[组合级](specs/bin-4h-emax-portfolio-contract-2026-07-24.md)、[V2 打分层](specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
