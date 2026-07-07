# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble 首次组合回测 - 2026-07-07

## 结论

把六个 1h adaptive-regime 家族的最新登记版本按等权 `1/6` 组合成一个多资产组合后，全期（2024-08-17 至 2026-07-02 UTC）小时再平衡口径年化 `4.07x`、总收益 `+1284.22%`、最大回撤 `-4.43%`、逐笔胜率 `89.66%`（`522` 笔，PF `6.627`）。分散效果显著：单资产 sleeve 回撤均在 `-15.70%` 至 `-19.11%`，组合回撤压缩到 `-4.43%`；六个 sleeve 日收益相关性最高仅 `0.185`（HYPE-ETH），其余接近 `0`。

但这是 `first combination diagnostic / NO-GO / not promoted / not live-ready`：

- 六个成分策略全部是 diagnostic 登记版本，没有一个通过各自家族的 promotion 门槛；组合不清洗成分的失败边界。
- 最近三个月为各家族已揭盲的 reused holdout，组合年化降到 `1.62x`、胜率 `75.4%`；最近 `7d` 为负收益（`-1.71%`）。组合最深回撤事件恰好发生在这段近端。
- HYPE-1H-Adaptive-Regime-V4 的 K+2 延迟与 8 bps 滑点压力失败按家族结论继承，组合层未重跑压力场景。
- 没有任何资产的 production runner、重启恢复、交易所对账、missing-bar fail-closed 与 kill switch 证据。

## 成分与版本

各 sleeve 复用家族冻结交易路径，运行前逐一与主账 current full 指标核对（annual/DD/win/trades 全部一致，`0` 漂移）：

| Sleeve | 版本 | 机制 | 主账 current full |
| --- | --- | --- | --- |
| TRX | `TRX-1H-Adaptive-Regime-V3` | `macd_flip + stoch_reversal` | `5.686x / -17.17% / 92.47% / 93` |
| SOL | `SOL-1H-Adaptive-Regime-V2` | `donchian_break + vwap_revert` | `2.07x / -17.41% / 93.91% / 115` |
| HYPE | `HYPE-1H-Adaptive-Regime-V4` | `di_cross + stoch_reversal`（剪枝微调） | `22.8128x / -19.11% / 81.08% / 74` |
| ETH | `ETH-1H-Adaptive-Regime-V3` | `bb_break + rsi_reversal`（clean tuned） | `3.3084x / -15.70% / 95.65% / 46` |
| BTC | `BTC-1H-Adaptive-Regime-V4` | `keltner_break + cci_reversal`（最小等价面） | `5.27x / -17.47% / 86.49% / 74` |
| BNB | `BNB-1H-Adaptive-Regime-V3` | `ema_pullback + wick_reject` | `2.94x / -18.24% / 88.33% / 120` |

## 数据、成本与执行口径

- 市场：Binance USD-M Futures perpetual，`TRXUSDT`、`SOLUSDT`、`HYPEUSDT`、`ETHUSDT`、`BTCUSDT`、`BNBUSDT`，周期 `1h`。
- 数据：各家族冻结数据湖帧；五个两年帧至 `2026-07-03`，HYPE 帧 `2025-05-30` 至 `2026-07-02`。数据质量检查随各家族 loader 强制执行（missing/duplicate/null/OHLCV violation/raw-normalized mismatch 均 `0`，任何违规直接抛错）。
- 组合窗口：`2024-08-17T06:00Z` 至 `2026-07-02T03:00Z`（组合末端取六资产共同数据末端，即 HYPE 末端；其余五个 sleeve 裁掉最后约一天）。HYPE sleeve 自其家族计分起点 `2025-07-14T10:00Z` 起加入，此前该 sleeve 持币。
- 成本：每 sleeve `0.001` fee/fill、`4 bps` adverse slippage/fill，逐笔计入 Binance 真实 funding（与各家族冻结口径一致）。
- 执行：各 sleeve 保持家族契约——闭合 K 信号、下一根 open 成交、单仓不加仓、stop-first、gap 穿 stop 按 open 成交。
- 组合结构：六个子账户 sleeve，各分配 `1/6` 权益。主口径为小时再平衡等权（组合小时收益 = 六 sleeve 小时收益均值）；对照口径为不再平衡（各 sleeve 独立复利后取均值）。
- 权益曲线：小时级构建；持仓中用 bar close 对入场价 mark-to-market，出场时刻用冻结 `equity_ret`（含费用、滑点、funding）对齐，确保逐笔终值与家族路径一致。
- 分片用途：本报告所有窗口（含 `1d/7d/1m/3m/6m/1y`）均为冻结后审计，不参与任何选参。

## 组合结果

| Window | 再平衡年化 | 再平衡收益 | 再平衡 DD | 不再平衡年化 | 不再平衡 DD | Trades | Win | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full（2024-08-17 起） | `4.069x` | `+1284.22%` | `-4.43%` | `4.234x` | `-6.17%` | `522` | `89.66%` | `6.627` |
| 六 sleeve 齐备（2025-07-14 起） | `3.821x` | `+264.92%` | `-4.43%` | `3.504x` | `-5.46%` | `293` | `87.37%` | `5.237` |
| reused holdout（2026-04-03 起） | `1.625x` | `+12.72%` | `-4.43%` | `1.858x` | `-5.19%` | `65` | `75.38%` | `1.947` |
| `last_1d` | `7.588x` | `+0.56%` | `-0.47%` | `3.195x` | `-0.27%` | `0` | - | - |
| `last_7d` | `0.406x` | `-1.71%` | `-4.43%` | `0.826x` | `-3.44%` | `6` | `66.67%` | `0.750` |
| `last_1m` | `2.384x` | `+7.40%` | `-4.43%` | `3.150x` | `-3.44%` | `26` | `84.62%` | `2.690` |
| `last_3m` | `1.704x` | `+14.19%` | `-4.43%` | `1.907x` | `-5.19%` | `65` | `75.38%` | `1.947` |
| `last_6m` | `2.993x` | `+72.17%` | `-4.43%` | `3.455x` | `-5.19%` | `150` | `82.00%` | `3.554` |
| `last_1y` | `3.662x` | `+265.91%` | `-4.43%` | `3.315x` | `-5.46%` | `300` | `87.33%` | `5.007` |

说明：多个窗口的再平衡 DD 都是 `-4.43%`，因为组合历史最深回撤事件发生在最近三个月内，被所有右端锚定的窗口共同捕捉。`last_1d` 年化只是单日外推形状，无交易，仅为持仓 M2M。

## 组合窗口内各 sleeve 表现

| Sleeve | Annual | Return | Max DD | Win | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| TRX | `5.703x` | `+2503.89%` | `-17.17%` | `92.47%` | `93` |
| SOL | `2.069x` | `+290.00%` | `-17.41%` | `93.91%` | `115` |
| HYPE* | `5.017x` | `+1949.01%` | `-19.11%` | `81.08%` | `74` |
| ETH | `3.315x` | `+842.97%` | `-15.70%` | `95.65%` | `46` |
| BTC | `5.281x` | `+2155.40%` | `-17.47%` | `86.49%` | `74` |
| BNB | `2.948x` | `+656.84%` | `-18.24%` | `88.33%` | `120` |

*HYPE 年化按整个组合窗口摊薄（其家族口径下为 `22.81x`，因为只交易了约一年）。

## 分散性证据

- 六 sleeve 日收益相关性（六 sleeve 齐备窗口）：最大 `0.185`（HYPE-ETH），其次 `0.093`（SOL-ETH）、`0.085`（SOL-HYPE），其余绝对值 `<0.07`。
- 组合毛暴露：平均 `0.247x`，最大 `1.83x`（相对总权益；单 sleeve 内部杠杆已含在内）。
- 有持仓小时占比 `43.1%`；`>=3` 个 sleeve 同时持仓的小时占比仅 `0.61%`——回撤压缩主要来自交易时点天然错开。

## 失败边界与 NO-GO 理由

1. 成分全部 NO-GO：六个版本都是 diagnostic 登记，各自的 reused holdout 弱点（ETH holdout 为负、SOL `0.70x`、TRX 胜率 `77.78%`、BTC `1.90x`、BNB reused OOS、HYPE K+2/8bps 压力失败）不会因为组合而消失。
2. 近端走弱是共同的：组合 reused holdout 年化 `1.62x`、胜率 `75.4%`，明显低于全期 `4.07x / 89.7%`；且该段已被各家族多次揭盲，不是 fresh OOS。
3. 组合层未做 K+2 延迟、8 bps 滑点、double-cost 压力场景与邻域审计。
4. 无 production runner：六资产多账户（或单账户六 symbol）的状态机、重启恢复、对账、缺 K fail-closed、kill switch 全部缺失。
5. 小时再平衡在实盘意味着子账户间资金划转，本回测未计其摩擦；不再平衡口径（`4.23x / -6.17%`）不受此影响，可作保守参照。

## 复现与产物

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py
```

- 汇总 JSON：`../artifacts/binance_1h_ar_mae_first_backtest_2026-07-07.json`
- 小时权益曲线：`../artifacts/binance_1h_ar_mae_equity_2026-07-07.csv`
- 组合窗口逐笔交易：`../artifacts/binance_1h_ar_mae_trades_2026-07-07.csv`
