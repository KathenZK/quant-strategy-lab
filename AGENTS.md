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

When creating new research:

- Prefer a document-first workflow.
- Use generated one-off scripts for exploration.
- Preserve final results in the relevant family docs as repository-tracked Markdown files.
- Write new research reports in Chinese by default unless the user explicitly requests another language.
- Do not create research reports, ledgers, or durable analysis in Cursor Canvas files or any project-private Cursor directory.
- Use Canvas only for transient visualization when explicitly requested; if a Canvas is used, mirror the durable conclusion into the appropriate `docs/research/` Markdown file before treating the work as complete.
- Only promote code back into `src/strategy_lab/` if it is reusable data infrastructure or a narrow dataset exporter.
