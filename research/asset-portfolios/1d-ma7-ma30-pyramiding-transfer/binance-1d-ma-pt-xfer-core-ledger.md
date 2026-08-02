# Binance-1D-MA7-MA30-Pyramiding-Transfer Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-MA30-Pyramiding-Transfer`
- Alias：`BIN-1D-MA-PT-XFER`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`BTCUSDT` / `ETHUSDT` perpetual，UTC `1d`
- Mechanism summary：固定迁移 HYPE MA7/MA30 双向 reclaim、盈利后从 `0.5x` 重置到 `3x`、ATR stop/trailing/profit-lock。
- Boundary / collision warnings：仅做跨资产 transfer；不是 `BTC-1H-AR`、`ETH-1H-AR` 或任一多资产组合的版本。

## Current State

- Current version(s)：无；当前为未编号直迁 observation。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live status：无。
- Live-readiness blockers：共同 `425` 日窗口中 BTC/ETH 均为净亏损，年化因子分别 `0.7353x`、`0.8135x`，MDD 分别 `-63.88%`、`-62.25%`；两年扩展窗口也未通过 `>20x / <=20% MDD`，且有效开盘杠杆均曾超过 `3x`。
- Next decision gate：本次直迁已判失败；若继续研究，必须建立 BTC/ETH 各自独立的日线家族并在搜索前锁定目标资产验证边界，不得把后续调参包装为本次 direct-transfer 成功。

## Version Rules

- 本次原参数复现属于 observation，不登记版本。
- 若未来为 BTC 或 ETH 单独调参，应进入相应资产下的新 `1d` 家族，不能沿用本 transfer 身份。
- 只有用户明确要求登记时才创建本家族版本；登记不表示 promotion。

## Version Table

当前无 registered version。

## Shared Assumptions

- Data：Binance USD-M `1h` 已收盘 K 聚合完整 UTC 日 K；实际 funding。
- Cost：手续费 `0.001/fill`，基础不利滑点 `4 bps/fill`；另审计 `8 bps/fill`。
- Execution timing：日 K 收盘计算，下一 UTC 日 open 执行；另审计 `K+2`。
- Position sizing：来源配置初始 `0.5x`，盈利条件满足后重置目标 `3x`；成交之间数量固定。

## Evidence Map

- Specs：[冻结迁移契约](specs/binance-1d-ma7-ma30-pyramiding-transfer-contract-2026-07-30.md)
- Diagnostics：[BTC/ETH 直迁报告](diagnostics/binance-1d-ma7-ma30-pyramiding-transfer-2026-07-30.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
