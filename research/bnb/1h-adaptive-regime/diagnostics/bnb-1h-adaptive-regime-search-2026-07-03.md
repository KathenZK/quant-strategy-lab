# BNB-1H-Adaptive-Regime 广泛搜索 - 2026-07-03

## 结论

预先冻结的唯一 primary 未能同时通过全样本与最近三个月 locked OOS 硬门槛，当前为 `NO-GO / not promoted / not live-ready`。

- primary：`ENS__BNB_1H_AR_N1262968__BNB_1H_AR_N1404587`；kind/styles：`ensemble` / `bb_break+stoch_reversal`。
- full：annual `4.20x`，return `1375.33%`，DD `-31.90%`，win `73.53%`，trades `136`，PF `3.160`。
- locked OOS：annual `0.28x`，return `-27.10%`，DD `-31.90%`，win `42.86%`，trades `14`，PF `0.476`。
- hard gate：`False`。

## 数据与防泄漏

- Binance USD-M Futures `BNBUSDT` perpetual `1h`：`17520` 根闭合 K；UTC `2024-07-03T06:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`。
- missing=`0`，duplicate=`0`，funding rows=`2190`。
- train：`2024-08-17T06:00:00+00:00` 至 `2025-10-07T01:00:00+00:00`；validation 至 `2026-04-03T06:00:00+00:00`。
- locked OOS：`2026-04-03T06:00:00+00:00` 至 `2026-07-03T06:00:00+00:00`。搜索阶段的 feature frame 不含任何 OOS K；primary JSON 落盘后才构建 OOS features。
- 只解锁一个预声明 primary；未根据 OOS 从多个候选中择优。

## 搜索覆盖

- curated_configs：`768`。
- random_configs：`1000000`。
- first_pass_evaluated：`417814`。
- first_pass_eligible：`109999`。
- first_pass_prefit_pass：`0`。
- neighbors_requested：`500000`。
- neighbors_evaluated：`391961`。
- neighbors_eligible：`226747`。
- neighbors_prefit_pass：`0`。
- retained_singles：`2000`。
- retained_ensembles：`200`。
- 指标/机制：EMA/MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d 闭合 regime、funding filter、fixed/risk sizing、fixed/trailing exit。

## 执行与成本

- 闭合 K 产生信号，下一根 open 市价入场；单仓、不加仓。
- 入场后立即具备 ATR stop/TP；同 K 双触发 stop-first；open 穿越 stop 按 open 成交。
- trailing 只在完整 K 结束后更新，新 stop 从下一根 K 生效。
- fee `0.1000%/fill`，slippage `0.0400%/fill`，另计真实 Binance funding。

## Promotion 边界

locked hard gate 未通过，禁止标记 candidate、paper-live、dry-run、handoff 或 live。

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_adaptive_regime_frozen_primary_2026-07-03.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_adaptive_regime_search_2026-07-03.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_adaptive_regime_prefit_2026-07-03.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_adaptive_regime_slices_2026-07-03.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_adaptive_regime_primary_trades_2026-07-03.csv`
