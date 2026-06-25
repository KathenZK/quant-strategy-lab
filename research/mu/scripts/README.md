# MU-HYPE-XFER Research Scripts

This directory contains one-off reproduction, alignment, transfer, and report-generation scripts for `MU-HYPE-XFER`.

Rules:

- Keep scripts here when they only serve MU transfer research.
- Write durable Markdown conclusions back to `research/mu/`.
- Write retained JSON, CSV, and HTML outputs to `../artifacts/`.
- Promote code to `src/strategy_lab/` only if it becomes reusable data infrastructure or a narrow dataset exporter.
- `mu_hype_xfer_kernel.py` is a frozen local snapshot of the HYPE EMA transfer kernel used by MU scripts. Do not import evolving `research/hype/.../scripts/` modules directly from MU scripts.
