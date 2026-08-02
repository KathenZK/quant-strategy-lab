# Binance-4H-EMA-Cross-LightGBM-Event-Selector

- 完整家族名：`Binance-4H-EMA-Cross-LightGBM-Event-Selector`
- 别名：`BIN-4H-EMAX-LGBM`
- 市场：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`4h`
- 机制：已闭合 `4h` K 线上 `EMA21/EMA96` 交叉产生方向事件（金叉只做多、死叉只做空），固定 ATR bracket + 96 根超时出场；周期梯度扫描（15m → 1h → 4h）的第三个点。
- 防串线：是 [`BIN-15M-EMAX-LGBM`](../15m-ema-cross-lightgbm-event-selector/README.md)（archived）与 [`BIN-1H-EMAX-LGBM`](../1h-ema-cross-lightgbm-event-selector/README.md)（explore）同机制在 `4h` 周期的独立诊断线，互不继承证据。
- 数据口径：全市场 `4h` K 线由已审计的 `1h` Vision 归档确定性重采样得到（UTC 4h 边界 OHLCV 聚合），衍生口径记录于基线报告；`2026-01`–`2026-06` 对本机制家族为污染 holdout。

## 当前状态

- 状态：`explore / not promoted / not live-ready`（2026-07-30 基于 local+trend 新证据从 `archived` 重开）
- 尚未注册版本；本 README 兼任临时主账。局部+趋势精简选择器事件级越过成本墙（Gate B 过，2026-07-29）后正式立项 V3 组合级回测：回撤压回 −19.4%（G1 过）且打分层增值成立（G4 过），但盈利 83% 集中 2022 熊市、四年仅两年为正（G2 未过），**V3 不登记**。死因与重启条件见 [V3 组合级判决](diagnostics/bin-4h-emax-v3-portfolio-2026-07-30.md)。

## 入口

- 决策日志：[decision-log.md](decision-log.md)
- V3 组合级判决（最新）：[bin-4h-emax-v3-portfolio-2026-07-30.md](diagnostics/bin-4h-emax-v3-portfolio-2026-07-30.md)；契约：[V3 立项](specs/bin-4h-emax-v3-lean-selector-portfolio-contract-2026-07-30.md)
- local+trend 选择器移植诊断：[bin-4h-emax-local-trend-selector-2026-07-29.md](diagnostics/bin-4h-emax-local-trend-selector-2026-07-29.md)
- P1 基线诊断：[bin-4h-emax-lgbm-p1-baseline-2026-07-24.md](diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md)
- P2 组合级诊断（对照组 A）：[bin-4h-emax-lgbm-p2-portfolio-control-a-2026-07-24.md](diagnostics/bin-4h-emax-lgbm-p2-portfolio-control-a-2026-07-24.md)
- V2 打分层诊断：[bin-4h-emax-lgbm-v2-scoring-2026-07-24.md](diagnostics/bin-4h-emax-lgbm-v2-scoring-2026-07-24.md)
- 早期契约：[组合级](specs/bin-4h-emax-portfolio-contract-2026-07-24.md)、[V2 打分层](specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md)、[local+trend 移植](specs/bin-4h-emax-local-trend-selector-contract-2026-07-29.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
