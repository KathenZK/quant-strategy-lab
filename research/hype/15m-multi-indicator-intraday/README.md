# HYPE-15M-Multi-Indicator-Intraday

- Full family name：`HYPE-15M-Multi-Indicator-Intraday`（历史别名：`HYPE-15M-MII`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `15m`
- 机制：多指标日内广搜（RSI/MACD/EMA/ADX/ATR/Donchian/Bollinger/成交量/结构），强制可执行时序：闭合 K 信号、下一根 open 入场、显式成本、单仓不重叠、stop-first 同 K 冲突处理。
- 当前状态：`HYPE-15M-MII-V1.4A`（`V1.4 + TP=1.4*ATR96 / SL=3.0*ATR96`）已替代 V1.3，当前 quant-runner `hype-mii-dry-run` 实例运行 V1.4A；状态为 `dry-run validation / not live-ready`。V1.3 已停止并标记 superseded，历史事件保留；runner 证据见 `runner-tracking/`。

## 边界

- 不是 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout` 或 `HYPE-Candle-Count-Reversal` 的版本。

## 入口

- 主账（V1/V1base/V1.1/V1.2/V1.3/V1.4 版本表与证据索引）：`hype-15m-mii-core-ledger.md`
- 决策记录（全部日期批次结论）：`decision-log.md`
- V1 冻结基线规格：[`specs/hype-15m-mii-v1-baseline-spec.md`](specs/hype-15m-mii-v1-baseline-spec.md)
- V1 实盘可行性审计（not-promoted）：[`diagnostics/hype-15m-mii-v1-live-feasibility-2026-06-29.md`](diagnostics/hype-15m-mii-v1-live-feasibility-2026-06-29.md)
- V1.2 完整复现规格：[`specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`](specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md)
- V1.3 runner 交接规格：[`live-specs/hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md`](live-specs/hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md)
- V1.4 参数规格（非 runner dry-run）：[`specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md`](specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md)
- V1.4A 参数规格（近期窗口 TP/SL 观察变体）：[`specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md`](specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md)
- V1.4 live validation spec（同事验证交接，非实盘批准）：[`live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md`](live-specs/hype-15m-mii-v1-4-live-validation-spec-not-live-ready-2026-07-09.md)
- V1.4A dry-run validation spec（小额 dry-run 交接，非实盘批准）：[`live-specs/hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md`](live-specs/hype-15m-mii-v1-4a-dry-run-validation-spec-not-live-ready-2026-07-10.md)
- V1.3/V1.4 近期诊断（信号干旱 / ATR 口径 / min_atr 网格 / recent trade frequency / RVOL 阈值对比 / V1.4 TP-SL、TP-SL 邻域、亏损环境过滤与动态止损）：`notes/` 下 `hype-15m-mii-v1-3-*.md` 与 `hype-15m-mii-v1-4-*.md` 系列

研究脚本在 `scripts/`，被报告引用的 JSON/CSV/HTML 在 `artifacts/`。逐批结论以主账和 decision-log 为准，不在本 README 复述。
