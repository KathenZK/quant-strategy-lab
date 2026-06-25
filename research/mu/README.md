# MU-HYPE-XFER MU Transfer Research

Family id: `MU-HYPE-XFER`

This direction transfers HYPE trend kernels, especially HYPE V35/V6 style long-only trend behavior, to MUUSDT / Binance TRADIFI perpetual data.

Main ledger:

- `mu-hype-xfer-session-aware-ledger.md`
- `legacy-canvas/`: migrated historical Canvas reports for MU transfer diagnostics and validations.

This is a core research direction, separate from HYPE-only strategy families.

Implementation note: MU scripts use `scripts/mu_hype_xfer_kernel.py` as a frozen local snapshot of the transferred HYPE EMA kernel. Do not import live HYPE family research scripts directly into MU research.
