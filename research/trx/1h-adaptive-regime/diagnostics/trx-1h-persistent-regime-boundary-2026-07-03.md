# TRX-1H 持续 regime 机制上界审计 - 2026-07-03

## 结论

在故意偏乐观的持仓路径上仍没有冻结 finalist 同时通过 full 与最近三个月 locked OOS 的三项硬门槛；持续持仓机制不能补救首轮差距。

- causal states：`392`；generated variants：`12936`；eligible：`11308`。
- prefit pass：`0`；locked target pass：`0/300`。
- 最佳 prefit-selected：`bb_revert_state_96_e2_x0__long__x0.75`；prefit annual `1.032x`，DD `-17.65%`，win `69.12%`。
- locked OOS：annual `0.925x`，DD `-4.41%`，win `66.67%`，trades `9`。

## 覆盖

EMA/price-EMA/MACD/Donchian 持续趋势状态，以及 Bollinger/RSI/Stochastic/rolling-VWAP 持续均值回归状态；每种覆盖 both/long/short 与 `0.5x-10x` 杠杆。

## 审计边界

所有状态都只使用闭合 K，并从下一根 open 改变仓位；计入 `0.001` fee/fill、`4 bps` slippage/fill 和历史资金费。为构造对持续 regime 的有利上界，本审计只在交易端点计算回撤，不读取 intrabar adverse excursion，也不模拟保护 stop。因此它不能产生 candidate；若这种偏乐观边界仍不达标，就没有理由继续把该机制包装成可实盘策略。

## 产物

- `research/trx/1h-adaptive-regime/artifacts/trx_1h_persistent_regime_boundary_2026-07-03.json`
- `research/trx/1h-adaptive-regime/artifacts/trx_1h_persistent_regime_boundary_2026-07-03.csv`
