# HYPE-5M-Micro-Scalp

Family id: `HYPE-5M-Micro-Scalp`

Historical alias: `HYPE-5M-MS`

This family covers Binance HYPEUSDT perpetual `5m` micro-scalp research. The target shape is high-frequency, high-win-rate, small-per-trade edge with live-executable fixed bracket exits.

It is independent from:

- `HYPE-5M-Pullback-Trail`: pullback/resume entries with ATR trailing-stop exits.
- `HYPE-1M-EMA-Crossover`: Binance HYPEUSDT `1m` EMA crossover research.
- `HYPE-15M-Multi-Indicator-Intraday`: Binance HYPEUSDT `15m` broad indicator search.
- `HYPE-EMA-Crossover` and `HYPE-EMA-Trend-Breakout`: legacy `15m` EMA families.

## Current Scope

- Data: Binance HYPEUSDT perpetual `5m` normalized OHLCV under the repository data lake.
- Execution model: closed-bar signal, next-bar open entry, immediate fixed TP/SL bracket, conservative stop-first ordering when one candle can hit both target and stop.
- Cost model: observed Binance live cost from `HYPE-5M-Pullback-Trail` audits, recorded explicitly in each search report.
- Original frequency goal: roughly `3-5` completed trades per day.
- Current relaxed-search boundary: profitable candidates appeared only after relaxing frequency down to roughly `0.3-0.5` trades/day. This family has paper-audit candidates, but no live-ready strategy yet.

## Canonical Entrypoints

- `decision-log.md`: family decision history.
- `diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`: first executable broad search report.
- `diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`: round-by-round relaxed-constraint search.
- `diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`: parameter-neighborhood robustness check for the relaxed candidates.
- `canonical-specs/hype-5m-micro-scalp-v1-baseline-spec.md`: `HYPE-5M-Micro-Scalp-V1` baseline spec and parameter explanation.
- `ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`: V1 one-at-a-time full parameter ablation.
- `research-notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md`: V1 effective-parameter simplification and combo search.
- `research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md`: local robustness sweep for the simplified combo leads.
- `canonical-specs/hype-5m-micro-scalp-v1-1-baseline-spec.md`: `HYPE-5M-Micro-Scalp-V1.1` baseline spec.
- `ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md`: V1.1 full parameter ablation and dormant-field identification.
- `research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`: V1.1 effective-parameter micro-tuning.
- `canonical-specs/hype-5m-micro-scalp-v1-2-baseline-spec.md`：`HYPE-5M-Micro-Scalp-V1.2` 正式基线规格；源观察行为 `V1.1_tune_grid_004895`。
- `research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md`：V1.2 登记，以及 V1.1/V1.2 在 fee `0.001`/fill、slippage `4 bps`/fill、`1x/2x/3x` 下的统一成本复测。
- `canonical-specs/hype-5m-micro-scalp-v1-3-baseline-spec.md`：`HYPE-5M-Micro-Scalp-V1.3` 精简基线；剔除 V1.2 dormant 与等效关闭字段，仅保留 `18` 个有效参数。
- `ablations/hype-5m-micro-scalp-v1-3-full-parameter-ablation-2026-07-01.md`：V1.3 有效字段 one-at-a-time 全参数消融。
- `research-notes/hype-5m-micro-scalp-v1-3-baseline-backtest-2026-07-01.md`：V1.3 基线回测及与 V1.2 逐笔等价验证。

## Current Finding

The first 2026-06-26 strict search found many high-win and frequency-matched rows, but none with positive expectancy under the executable order model and observed Binance cost model. The best `3-5` trades/day row annualized only `0.23x`, and `0` configs passed the hard or audit gate.

The follow-up relaxed search changed one constraint at a time:

- `R1_relax_frequency`: frequency relaxed from `3-5/day` to `0.10-1.00/day`, leaving `32` round-gate candidates.
- `R2_relax_winrate_payoff`: win-rate requirement relaxed to `45%+` while requiring stronger PF/payoff, leaving `20` round-gate candidates.
- `R3_live_candidate_gate`: high-win micro-profit framing removed, keeping only executable positive profitability and split robustness, leaving `36` round-gate candidates.

The subsequent robustness sweep tested `749` local neighborhood configs around the better sample-size candidates. `407` passed the robust gate and `396` also passed the monthly gate. The current best balanced paper-audit candidate is:

- `R1_relax_frequency_R01242__tp_sl_0011`: `vwap_revert`, both sides, `188` trades, `0.48` trades/day, annualized `1.32x`, win rate `85.11%`, PF `1.468`, average trade `16.67 bps`, maxDD `-8.16%`, VAL PF `5.445`, FWD PF `3.550`, recent 30d return `10.46%`, `3/14` negative months.

This candidate is now recorded as `HYPE-5M-Micro-Scalp-V1` baseline. The 2026-06-29 full parameter ablation tested `103` configs (`1` baseline + `102` one-at-a-time variants): V1 is most dependent on keeping `entry_style=vwap_revert`, `require_trend=true`, `ema_slow=96`, and `vwap_dev_bps=75`; TP/SL, hold/cooldown, ATR bounds, and distance filters have wider viable neighborhoods.

The 2026-06-30 simplified combo search fixed the dormant fields that do not participate in `vwap_revert` and searched only the effective fields. On the refreshed data through `2026-06-30 06:15:00+00:00`, V1 reproduced as `189` trades, `0.48` trades/day, annualized `1.34x`, win `85.71%`, PF `1.490`, maxDD `-8.16%`. The simplified combo sweep evaluated `49016` configs and found `633` strict-improve rows. A follow-up local robustness sweep evaluated `13389` neighbors around five leads. The preferred observation `V1S_rand_016782__N00596` is now recorded as `HYPE-5M-Micro-Scalp-V1.1`: `182` trades, `0.46` trades/day, annualized `2.13x`, win `87.91%`, PF `2.660`, average trade `45.88 bps`, maxDD `-8.06%`, VAL PF `2.441`, FWD PF `5.739`, recent30 `11.86%`, and `2` negative months.

The V1.1 full parameter ablation tested `103` configs and confirmed the remaining dormant groups under `vwap_revert`: `bb_z`, `breakout_bps`, `min_dir_roc_bps`, `max_counter_roc_bps`, `pullback_bps`, `rsi_high`, `rsi_low`, `donchian`, `rsi_window`, and `wick_atr`. The follow-up V1.1 micro-tune evaluated `44001` configs and found `2` strict-improve rows. The preferred observation `V1.1_tune_grid_004895` was formally recorded as `HYPE-5M-Micro-Scalp-V1.2` on 2026-07-01; this is a version identity change, not a live-ready promotion.

2026-07-01 指定成本复测将前序观测成本替换为 fee `0.001`/fill 与双边各 `4 bps` 不利滑点。V1.1 在 `1x/2x/3x` 下年化 `1.56x/2.38x/3.55x`，maxDD `-9.84%/-19.12%/-27.82%`；V1.2 年化 `1.76x/2.98x/4.89x`，maxDD `-9.96%/-19.90%/-29.67%`。V1.2 收益更高，但在该成本模型下回撤略深；canonical 默认敞口为 `1x`，`2x/3x` 只作压力测试。

2026-07-01 V1.3 自 V1.2 剔除 `12` 个不生效字段（`10` 个 dormant + `min_adx` + `max_atr_pct_bps`），schema 只保留 `18` 个有效参数。在 fee `0.001`/fill、slippage `4 bps`/fill 下，V1.3 与 V1.2 逐笔路径完全等价：`180` 笔、`0.45` 笔/天、年化 `1.76x`、PF `1.934`、maxDD `-9.96%`。V1.3 全参数消融 `60` 组（`1` baseline + `59` variants），显示 `tp_bps`、`close_pos`、`require_body_dir` 附近仍有更高收益邻域，但 FWD 样本仍薄，不构成 live-ready 证明。

当前 V1、V1.1、V1.2 均只属于 paper-audit observation。任何 live、paper-live、handoff 或真实资金部署前，仍需完成逐笔路径、订单维护、重启状态和 paper/live-dry-run reconciliation。

## Directory Rules

- `scripts/`: one-off reproducible search and audit scripts for this family.
- `artifacts/`: retained JSON/CSV evidence cited by Markdown reports.
- `diagnostics/`: search reports, live-feasibility audits, and no-go records.
- `research-notes/`: exploratory notes that are not candidate specs.
- `live-specs/`: only use after a candidate has paper-audit evidence.

Do not cite a bare version number for this family. Use names such as `HYPE-5M-Micro-Scalp-search-2026-06-26` or a later explicit candidate id.
