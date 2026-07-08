# HYPE-15M-Multi-Indicator-Intraday

- Full family name：`HYPE-15M-Multi-Indicator-Intraday`（历史别名：`HYPE-15M-MII`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `15m`
- 机制：多指标日内广搜（RSI/MACD/EMA/ADX/ATR/Donchian/Bollinger/成交量/结构），强制可执行时序：闭合 K 信号、下一根 open 入场、显式成本、单仓不重叠、stop-first 同 K 冲突处理。
- 当前状态：`HYPE-15M-MII-V1.4` 已登记为 `V1.3 + min_rvol96=0.85` 的进取观察版本，但尚未实现为 runner dry-run；当前 quant-runner 模拟盘仍是 `HYPE-15M-MII-V1.3`（V1.2 的固定 `2.5x` sizing 版），runner 观察报告见 `runner-tracking/`。

## 边界

- 不是 `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout` 或 `HYPE-Candle-Count-Reversal` 的版本。

## 入口

- 主账（V1/V1base/V1.1/V1.2/V1.3/V1.4 版本表与证据索引）：`hype-15m-mii-core-ledger.md`
- 决策记录（全部日期批次结论）：`decision-log.md`
- V1 冻结基线规格：`specs/hype-15m-mii-v1-baseline-spec.md`
- V1 实盘可行性审计（not-promoted）：`live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md`
- V1.3 runner 交接规格：`live-specs/hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md`
- V1.4 参数规格（非 runner dry-run）：`live-specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md`
- V1.3/V1.4 近期诊断（信号干旱 / ATR 口径 / min_atr 网格 / recent trade frequency / RVOL 阈值对比 / V1.4 TP-SL 与亏损环境过滤）：`notes/` 下 `hype-15m-mii-v1-3-*.md` 与 `hype-15m-mii-v1-4-*.md` 系列

研究脚本在 `scripts/`，被报告引用的 JSON/CSV/HTML 在 `artifacts/`。逐批结论以主账和 decision-log 为准，不在本 README 复述。
