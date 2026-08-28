# Binance-1D-MA7-Regime-Continuation

- Alias：`BIN-1D-MA7-RC`
- Market / timeframe：Binance USD-M perpetual，UTC `1d`
- 机制：对称 MA7 close cross 仅作事件 trigger；P0/P1 检验 `Slope + ER20 + RV20 percentile`，P2 改用突破前 ATR 收缩/扩张路径，P3 用固定规则、资产中性 breadth、逻辑回归和小型 LightGBM 做锁定确认。
- 边界：全历史动态归档合约池；P3 不使用 symbol、资产类别或 BTC 状态作为特征，固定 next-open、10/20 session hold 与成本；没有 funding，仍非可交易策略。
- 当前状态：P3 `NO-GO`；`explore / diagnostic-only / not promoted / not live-ready`

入口：

- [Core ledger](binance-1d-ma7-rc-core-ledger.md)
- [P0 frozen contract](specs/binance-1d-ma7-regime-continuation-p0-contract-2026-08-24.md)
- [P0 results](diagnostics/binance-1d-ma7-regime-continuation-p0-results-2026-08-24.md)
- [P1 readable states and frequency](diagnostics/binance-1d-ma7-regime-continuation-p1-readable-states-frequency-2026-08-24.md)
- [P2 ATR-path frozen contract](specs/binance-1d-ma7-regime-continuation-p2-atr-path-contract-2026-08-25.md)
- [P2 ATR-path results](diagnostics/binance-1d-ma7-regime-continuation-p2-atr-path-2026-08-25.md)
- [P3 fixed-rule + small-ML contract](specs/binance-1d-ma7-regime-continuation-p3-confirmatory-fixed-ml-contract-2026-08-25.md)
- [P3 confirmatory results](diagnostics/binance-1d-ma7-regime-continuation-p3-confirmatory-2026-08-25.md)
- [Historical P1 short-first candidate](specs/binance-1d-ma7-regime-continuation-short-first-account-candidate-2026-08-24.md)
- [Decision log](decision-log.md)
- [Artifacts index](artifacts/README.md)
