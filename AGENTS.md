# Repository Rules For AI Agents

This repository is a data-first research archive, not a general strategy platform.

Before reading any HYPE strategy material, open:

1. `docs/research/STRATEGY_INDEX.md`
2. `docs/research/hype/AI_CONTEXT.md`
3. The relevant family `README.md`

Do not infer strategy identity from a bare version number such as `V13`, `V21`, `V35`, or `V36`.
HYPE version numbers are only meaningful inside a strategy family.

Canonical family ids:

- `HYPE-CC`: HYPE candle-count reversal family.
- `HYPE-EMA-X`: HYPE EMA golden/death cross family, including V14-era research.
- `HYPE-EMA-TB`: HYPE EMA trend breakout family.
- `MU-HYPE-XFER`: MU transfer research based on HYPE trend kernels.

Active code policy:

- Active package code is limited to data ingestion, data normalization, data quality checks, feature construction, and narrow research dataset exporters.
- Archived strategy, workflow, dashboard, journal, and backtest platform code lives under `archive/code/platform/`.
- Historical one-off research scripts live under `archive/scripts/research/`.
- Do not treat archived code as the current source of truth unless the user explicitly asks to inspect history.

Live-executable research policy:

- This repository studies strategies that can be traded online with real orders, not beautiful backtest illusions.
- Do not promote any strategy to live, paper-live, dry-run, handoff, or candidate status until its order timing and execution assumptions are audited.
- Treat impossible fills, crossed stops filled at stale stop prices, lookahead stop updates, unavailable intrabar decisions, and unfillable order assumptions as hard failures.
- If a strategy uses `min_hold_bars`, delayed exits, trailing stops, protection stops, or lockout periods, audit the protected interval and unlock behavior before discussing performance.
- A promotion write-up must cover fees, slippage, stop placement validity, stop-market behavior, sizing, emergency stop or kill switch, restart recovery, missing data behavior, and whether a live runner can reproduce the state machine.
- Negative live-feasibility findings must be written into `docs/research/` immediately and should downgrade the candidate instead of being hidden behind more parameter search.
- This rule exists because this repository has repeatedly made the same mistake, including earlier trend-strategy research and the HYPE-5M-PBTR V2.1A/V3.3/V4 lockout-stop audits. Live feasibility comes before performance storytelling.

When creating new research:

- Prefer a document-first workflow.
- Use generated one-off scripts for exploration.
- Preserve final results in the relevant family docs as repository-tracked Markdown files.
- Write new research reports in Chinese by default unless the user explicitly requests another language.
- Do not create research reports, ledgers, or durable analysis in Cursor Canvas files or any project-private Cursor directory.
- Use Canvas only for transient visualization when explicitly requested; if a Canvas is used, mirror the durable conclusion into the appropriate `docs/research/` Markdown file before treating the work as complete.
- Treat `legacy-canvas/` directories as frozen historical evidence from migrated Canvas files. Do not create new strategy research there; promote reviewed findings into family ledgers, `canonical-specs/`, `diagnostics/`, or `decision-log.md` instead.
- Only promote code back into `src/strategy_lab/` if it is reusable data infrastructure or a narrow dataset exporter.
