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
