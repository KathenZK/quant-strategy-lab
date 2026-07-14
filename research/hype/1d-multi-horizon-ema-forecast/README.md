# HYPE-1D-Multi-Horizon-EMA-Forecast

- Alias：`HYPE-1D-MHEF`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`
- 机制：EMA `8/32`、`16/64`、`32/128`、`64/256` 形成经典 EWMAC forecast，按 `0.2/0.3/0.3/0.2` 融合并映射为最大 `1x` 连续仓位。
- 当前状态：`explore / not promoted / not live-ready`

## 边界

本家族是独立日线研究，不是 `HYPE-15M-MHEF` 或 `HYPE-1H-MHEF` 的版本。因 HYPE 历史不足以运行 intraday 家族的滚动 forecast 校准，日线使用固定 EWMAC scalar，结果不可与前两者作同口径参数优劣比较。

## 入口

- 主账：[hype-1d-mhef-core-ledger.md](hype-1d-mhef-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 基线回测：[hype-1d-mhef-classic-ewmac-backtest-2026-07-14.md](notes/hype-1d-mhef-classic-ewmac-backtest-2026-07-14.md)
- 脚本：[scripts/README.md](scripts/README.md)
- 产物：[artifacts/README.md](artifacts/README.md)
