# HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble

Alias：`HYPE-15M-TB-MII-ENS`

Created：2026-07-07

## 边界

本目录研究 Binance HYPEUSDT 永续 `15m` 上把两个既有家族版本组合成一个新策略：

- 趋势腿：`HYPE-EMA-Trend-Breakout` 的 V35 或 V39（EMA96/384 趋势突破 + ADX/成交量/1h 确认，K+2 open 入场，5ATR 止盈 / 7ATR 硬止损 / ADX22 delayed3 / 384 根 timeout，ATR 动态仓位上限 3x；V39 = V35 + `long_vol_min 0.35` + `short_target_atr_pct 0.022` - 空头 1h EMA 确认）。
- 反转腿：`HYPE-15M-Multi-Indicator-Intraday` 的 V1.3 或 V1.4（RSI(7) 40/60 反转 + MACD 方向 + ATR96 0.75%-2.80%，K+1 open 入场，ATR96 bracket TP=1.25x / SL=5.0x / hold=24，固定 2.5x 暴露；V1.3 `RVOL96>=1.0`，V1.4 `RVOL96>=0.85`）。

本目录不修改两个母家族的版本定义；母版本口径以各自主账为准：

- [hype-ema-tb-core-ledger.md](../15m-ema-trend-breakout/hype-ema-tb-core-ledger.md)
- [hype-15m-mii-core-ledger.md](../15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md)

## 当前状态

- 当前状态：`V2 live validation spec draft / live-executable FAILED / NO-GO / not promoted / not dry-run / not live-ready`。
- 当前登记版本：`V2 = HYPE-EMA-TB-V39 + HYPE-15M-MII-V1.4`，单账户 `single_v39_priority_k1`（V39 优先 + V1.4 强平让位）。
- 首次组合回测（V35 + V1.3）见 [hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md](notes/hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md)。
- V39 + V1.3 组合回测（含门禁校验）见 [hype-15m-tb-mii-ensemble-v39-combination-backtest-2026-07-08.md](notes/hype-15m-tb-mii-ensemble-v39-combination-backtest-2026-07-08.md)。
- V39 + V1.4 组合回测（含门禁校验）见 [hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md](notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md)。
- V2 近一年周度开单审计见 [hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md](notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md)。
- V2 live validation spec（非实盘批准）见 [hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md](live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)。
- V2 live-executable 审计（失败）见 [hype-15m-tb-mii-ens-v2-live-executable-audit-2026-07-09.md](diagnostics/hype-15m-tb-mii-ens-v2-live-executable-audit-2026-07-09.md)。
- 家族主账：[hype-15m-tb-mii-ens-core-ledger.md](hype-15m-tb-mii-ens-core-ledger.md)。

## 阅读顺序

1. `../../README.md`
2. `../README.md`
3. 本文件
4. [hype-15m-tb-mii-ens-core-ledger.md](hype-15m-tb-mii-ens-core-ledger.md)
5. [decision-log.md](decision-log.md)
6. [notes/](notes/) 内具体报告
7. [live-specs/](live-specs/) 内 runner / dry-run / live validation 规格
