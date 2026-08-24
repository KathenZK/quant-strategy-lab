# BIN-1D-BE-CPEHC Decision Log

## 2026-08-13 — P0 家族与合同冻结

- COST修复2022后，剩余瓶颈是高盈利BTC long中的`-35.22%`回吐；CPPR减仓改善风险但破坏复利。
- 冻结early full exit `1ATR/20%/1d`，并在flat后只允许一次“close重破原favorable extreme”的同方向handoff。
- 只测试window `7/14/30d` × confirm `1/2d`；不搜buffer、ATR、fraction、重复handoff或杠杆。
- 因冻结日已到`2026-08-13`，新prospective锚点后移到`2026-08-14` closed / `2026-08-15` execution。
