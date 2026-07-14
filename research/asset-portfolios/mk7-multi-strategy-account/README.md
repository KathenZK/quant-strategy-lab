# Binance-MK7-Multi-Strategy-Account

- Full family name：`Binance-MK7-Multi-Strategy-Account`
- External alias：`mk7`
- Market：Binance USD-M Futures perpetual
- Symbols：`TRXUSDT / SOLUSDT / HYPEUSDT / ETHUSDT / BTCUSDT / BNBUSDT`
- Timeframes：`1m / 5m / 15m / 30m / 1h / 6h / 12h`
- Status：`explore / not promoted / not live-ready`

## 家族边界

本研究线用于审计外部 `mk7` 冻结规格：六币 `1h` adaptive-regime 腿、HYPE K2FQ、HYPE MII 与双槽共享账户。它不是 [`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`](../1h-adaptive-regime-multi-asset-ensemble/README.md) 的新版本，也不改变任何成分家族的版本身份。

当前只把 `mk7-v8` 作为外部规格观察对象；尚未在本仓库登记为正式版本。全窗 LSR 已补齐，独立回测接近但未逐笔对齐；回测终点后 10.875 天 forward 基本持平且仅4笔。

## 入口

- [主账](mk7-multi-strategy-account-core-ledger.md)
- [决策记录](decision-log.md)
- [独立回测笔记 2026-07-13](notes/mk7-v8-backtest-2026-07-13.md)
- [回测窗口后 forward 审计](notes/mk7-v8-post-window-forward-audit-2026-07-13.md)
- [`mk7-v8` 复现阻塞诊断](diagnostics/mk7-v8-reproduction-blocker-2026-07-12.md)
- [回测脚本](scripts/research_mk7_v8_backtest.py)
