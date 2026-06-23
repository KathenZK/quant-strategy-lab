# Research Archive

The research layer is the main knowledge surface of this repository.

Use these entrypoints:

- `STRATEGY_INDEX.md`: global strategy-family map and naming rules.
- `hype/AI_CONTEXT.md`: HYPE-specific reading rules.
- `hype/families/`: strategy-family archives.
- `hype/transfer/`: legacy cross-asset transfer checks derived from HYPE kernels; currently retained for review, not a HYPE strategy family.
- `mu/README.md`: MU transfer research entrypoint.

Historical strategy research that is no longer an active research entrypoint lives under `../../archive/research/`.

The repository no longer treats package strategy code as the primary research interface. New experiments can use one-off scripts, but conclusions should be written back into the relevant family documents.

## Report Storage Policy

Research reports, strategy ledgers, experiment conclusions, and durable decision records must live in this repository as Markdown under `docs/research/`.

Generated research reports should be written in Chinese by default unless the user explicitly asks for another language.

Cursor Canvas files and other Cursor-private project directories are not canonical storage. They may be used only as temporary visualization surfaces when explicitly requested. Any durable finding produced through a Canvas must be mirrored back into the relevant Markdown document before the research is considered complete.
