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
- `HYPE-EMA-TB`: HYPE EMA trend breakout family.

Active code policy:

- Active package code is limited to data ingestion, data normalization, data quality checks, feature construction, and narrow research dataset exporters.
- Archived strategy, workflow, dashboard, journal, and backtest platform code lives under `archive/code/platform/`.
- Historical one-off research scripts live under `archive/scripts/research/`.
- Do not treat archived code as the current source of truth unless the user explicitly asks to inspect history.

When creating new research:

- Prefer a document-first workflow.
- Use generated one-off scripts for exploration.
- Preserve final results in the relevant family docs.
- Only promote code back into `src/strategy_lab/` if it is reusable data infrastructure or a narrow dataset exporter.
