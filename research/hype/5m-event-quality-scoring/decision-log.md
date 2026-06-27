# HYPE-5M-Event-Quality-Scoring Decision Log

## 2026-06-27 - Create independent event-quality scoring line

Status: `active diagnostic`

Decision:

- Create `HYPE-5M-Event-Quality-Scoring` as a new family instead of placing the
  work under `HYPE-5M-Micro-Scalp` or `HYPE-5M-Pullback-Trail`.
- Treat indicator rules as candidate event sources, not as final strategies.
- Start with an interpretable walk-forward ranking model before adding heavier
  machine learning dependencies.

Reasoning:

- Existing `1m` EMA-crossover diagnostics show that adding exits or transferred
  strength filters does not rescue raw cross-chasing.
- Existing `5m` fixed-rule scalp research found paper-audit candidates only
  after relaxing frequency, so the next useful question is whether event quality
  can be selected rather than whether one more static rule can be found.

Required V0 standards:

- Validate data continuity, closed-bar status, OHLC legality, and raw vs
  normalized alignment before reporting performance.
- Use closed-bar signals and next-open entries only.
- Use a purge window between training labels and test months.
- Preserve JSON/CSV artifacts and a Markdown diagnostic under this family.

## 2026-06-27 - Generic V0 no-go; seeded V0 paper-audit candidate

Status: `paper-audit candidate`

Evidence:

- Generic V0 report:
  `diagnostics/hype-5m-event-quality-v0-2026-06-27.md`
- Seeded V0 report:
  `diagnostics/hype-5m-seeded-event-quality-v0-2026-06-27.md`

Decision:

- Do not promote the generic multi-source event pool. It produced `252,277`
  candidate events but `0` paper-gate passes; the best ranked row was still
  negative OOS.
- Preserve `seeded_source_mean_q80` as a paper-audit candidate only.

Seeded V0 headline:

- Seed selection used `HYPE-5M-Micro-Scalp` relaxed-rounds configs but filtered
  seeds only by `train_2025_05_30_to_2026_03_01` metrics.
- OOS window starts at `2026-03-01 00:00:00+00:00`.
- Best row `seeded_source_mean_q80`: `184` OOS trades, `1.57` trades/day,
  `28.89%` 1x return, `1.222` PF, `15.47 bps` average trade, `-15.38%`
  max drawdown, and `27.18%` recent-30d return.

Boundary:

- This is not live-ready. The config universe was inherited from prior
  `HYPE-5M-Micro-Scalp` research, so the next step must be an anti-leakage
  seed-generation audit plus cost stress and paper-runner reconciliation.

## 2026-06-27 - Seeded V0 score/quantile ablation

Status: `paper-audit candidate unchanged`

Evidence:

- Ablation report:
  `diagnostics/hype-5m-seeded-event-quality-v0-ablation-2026-06-27.md`
- Full-year segment diagnostic:
  `diagnostics/hype-5m-seeded-event-quality-v0-q80-full-year-segments-2026-06-27.md`

Decision:

- Do not replace `current_70_20_10__q80` with the highest full-year return row.
- Keep `current_70_20_10__q80` as the balanced paper-audit row for follow-up
  audit, while treating high-return `q50/q60` rows as unstable diagnostics.

Findings:

- `current_70_20_10__q80`: `633` fixed-seed full-year replay trades,
  `61.81%` return, `1.128` PF, `9.30 bps` average trade, `-26.94%` max drawdown,
  `13.63%` recent-3m return, and `6/13` negative active months.
- `cfg_only__q60`: highest full-year return at `179.93%`, with `1.206` PF and
  `14.32 bps` average trade, but recent-3m return was `-6.39%` and max drawdown
  reached `-30.50%`, so it failed the stability gate.
- The ablation suggests much of the full-year edge comes from `cfg_name`
  historical means; `style` and `side` are secondary. This increases the need
  for anti-leakage seed-generation audit before any live or paper-live promotion.

Boundary:

- The ablation is a fixed seed-universe retrospective diagnostic, not strict
  anti-leakage OOS before `2026-03-01`. The seeds were still selected using
  `train_2025_05_30_to_2026_03_01` metrics.

## 2026-06-27 - Create core ledger and Seeded V0.1 style-prune

Status: `paper-audit candidate refined`

Evidence:

- Core ledger:
  `hype-5m-event-quality-scoring-core-ledger.md`
- Style-prune report:
  `diagnostics/hype-5m-seeded-event-quality-v01-style-prune-2026-06-27.md`

Decision:

- Treat `HYPE-5M-Event-Quality-Scoring-Seeded-V0` / `current_70_20_10__q80`
  as the Base version.
- Promote `no_wick_no_breakout__q80` to the current refined diagnostic
  candidate for follow-up paper audit.
- Keep `bb_vwap_only__q85` as a lower-drawdown simplified alternative.
- Do not continue treating `wick_reject` and `micro_breakout` as required
  baseline event sources; they should remain removed unless a later focused
  audit proves a constrained version is useful.

Findings:

- Base `base_all__q80`: `633` trades, `61.81%` full-year return, `1.128` PF,
  `9.30 bps` average trade, `-26.94%` max drawdown, and `6/13` negative months.
- Refined `no_wick_no_breakout__q80`: `545` trades, `238.78%` full-year return,
  `1.383` PF, `24.05 bps` average trade, `-16.75%` max drawdown, `25.33%`
  recent-3m return, and `2/13` negative months.
- Lower-drawdown `bb_vwap_only__q85`: `347` trades, `194.31%` full-year return,
  `1.489` PF, `33.06 bps` average trade, `-10.79%` max drawdown, `34.77%`
  recent-3m return, and `1/13` negative months.

Boundary:

- These results are still fixed seed-universe diagnostics, not strict
  anti-leakage OOS before `2026-03-01`. Next steps must be seed audit, cost
  stress, drawdown-control ablation, and paper-runner reconciliation.

## 2026-06-27 - Seeded V0.1 full parameter ablation

Status: `paper-audit candidate refined`

Evidence:

- Full parameter ablation:
  `diagnostics/hype-5m-seeded-event-quality-v01-full-ablation-2026-06-27.md`

Decision:

- Confirm that `no_wick_no_breakout` remains the best event-source set under
  the wider parameter search.
- Preserve `no_wick_no_breakout__current_70_20_10__q80` as the Base-score
  V0.1 control.
- Promote `no_wick_no_breakout__cfg_side_88_12__q80` as the current V0.1
  full-ablation lead for follow-up audit.
- Do not treat `style_only` or `side_only` as viable simplified models; both
  failed the stricter stability gate.

Findings:

- Full grid: `6` style sets × `7` score variants × `7` quantile thresholds.
- Lead row `no_wick_no_breakout__cfg_side_88_12__q80`: `549` trades,
  `287.61%` full-year return, `1.425` PF, `26.33 bps` average trade,
  `-16.30%` max drawdown, `24.59%` recent-3m return, and `1/13` negative months.
- Base-score control `no_wick_no_breakout__current_70_20_10__q80`: `545`
  trades, `238.78%` return, `1.383` PF, `24.05 bps` average trade,
  `-16.75%` max drawdown, `25.33%` recent-3m return, and `2/13` negative months.
- Low-drawdown alternative `bb_vwap_only__current_70_20_10__q85`: `347`
  trades, `194.31%` return, `1.489` PF, `33.06 bps` average trade,
  `-10.79%` max drawdown, and `34.77%` recent-3m return.
- The best score variants are `cfg_side_88_12` and `cfg_only`; removing
  `style_mean` after style pruning improves results. This supports the view that
  the strategy is still driven by historical config quality ranking, with side
  as a small auxiliary term.

Boundary:

- This is still a fixed seed-universe diagnostic, not strict anti-leakage OOS
  before `2026-03-01`. It must not be promoted before seed audit, cost stress,
  drawdown-control ablation, and paper-runner reconciliation.

## 2026-06-27 - Register Seeded V1 and block live promotion

Status: `research lead / paper-audit lead only`

Evidence:

- Live feasibility audit:
  `diagnostics/hype-5m-seeded-v1-live-feasibility-2026-06-27.md`

Decision:

- Register `no_wick_no_breakout__cfg_side_88_12__q80` as
  `HYPE-5M-Event-Quality-Scoring-Seeded-V1`.
- Do not mark V1 as live-ready, paper-live-ready, or dry-run handoff.
- Require seed-generation anti-leakage, paper-runner reconciliation,
  order-maintenance audit, cost/slippage stress, restart recovery, and kill
  switch definition before any live or paper-live promotion.

V1 headline:

- Score: `0.875 * cfg_mean + 0.125 * side_mean`.
- Event styles: keep `bb_revert`, `macd_flip`, `trend_rsi_snapback`,
  `vwap_revert`; remove `wick_reject` and `micro_breakout`.
- Fixed seed-universe full-year replay: `549` trades, `287.61%` return,
  `1.425` PF, `26.33 bps` average trade, `-16.30%` max drawdown.
- Recent 90d: `112` trades, `24.59%` return, `1.303` PF, `-16.30%` max DD.
- Recent 30d: `51` trades, `46.29%` return, `2.209` PF, `-5.24%` max DD.

Live-feasibility blockers:

- Fixed seed universe still comes from prior `HYPE-5M-Micro-Scalp` search;
  strict anti-leakage seed generation has not been demonstrated.
- Backtest entry is next-open plus observed slippage; live latency after candle
  close and real market-order fill need paper-runner reconciliation.
- Backtest assumes immediate TP/SL bracket after entry; live unprotected window
  between entry fill and bracket confirmation is not audited.
- Stop-market behavior is conservative in backtest, but real Binance trigger,
  slippage, reduce-only order handling, orphan-order cleanup, and restart
  recovery are not audited.
- Additional roundtrip cost stress: `10 bps` still leaves `124.08%` return and
  `1.247` PF, but `20 bps` drops to `29.47%` return / `1.090` PF and `30 bps`
  turns negative. Position-size slippage is not modeled.

Boundary:

- V1 is a strong research lead, not a tradable deployment spec.

## 2026-06-27 - Seeded V1 strict seed-generation audit failed

Status: `fixed-seed diagnostic / anti-leakage failed`

Evidence:

- Strict seed audit:
  `diagnostics/hype-5m-seeded-v1-strict-seed-audit-2026-06-27.md`
- Script:
  `scripts/research_hype_5m_seeded_v1_strict_seed_audit.py`

Decision:

- Downgrade `HYPE-5M-Event-Quality-Scoring-Seeded-V1` from paper-audit lead to
  fixed seed-universe diagnostic only.
- Do not proceed to paper-runner reconciliation, paper-live, dry-run handoff, or
  live deployment from V1.
- Treat the previous fixed seed-universe V1 result as likely containing material
  config-universe / seed-selection bias.

Strict audit method:

- Generate a fixed no-data config universe from the relaxed-rounds targeted
  random generator, but disable `seed_configs_from_previous()` and do not read
  any historical summary seed list.
- Use `2000` configs per relaxed round, `6000` total configs, restricted to the
  V1 allowed styles: `bb_revert`, `macd_flip`, `trend_rsi_snapback`,
  `vwap_revert`.
- For each test month, select up to `100` seed configs using only trades before
  that month minus a `12h` purge window.
- Then generate that month's events from the selected seeds and trade them with
  the V1 scorer `0.875 * cfg_mean + 0.125 * side_mean` at `q80`.
- OOS starts at `2025-08-01` because the data starts on `2025-05-30` and the
  audit reserves `60` days of minimum seed-selection history.

Findings:

- Strict audit result: `493` trades, `-61.16%` return, `0.843` PF,
  `-16.58 bps` average trade, and `-65.94%` max drawdown.
- Only `2025_08`, `2025_11`, and `2026_03` were positive; most months were
  negative, including `2026_01` at `-32.35%`.
- This contradicts fixed seed-universe V1, which had `549` trades, `287.61%`
  return, `1.425` PF, and `-16.30%` max drawdown.

Boundary:

- The strict audit uses a bounded `6000`-config universe, not the full original
  `21000` relaxed-round scale. Expanding the strict universe can be a follow-up,
  but the current evidence is already a promotion blocker.
- Any future continuation should be a new strict rolling-seed V2 search, not a
  parameter tweak on fixed-seed V1.
