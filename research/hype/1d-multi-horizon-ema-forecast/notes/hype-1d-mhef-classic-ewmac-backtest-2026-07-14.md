# HYPE-1D-Multi-Horizon-EMA-Forecast 经典 EWMAC 日线回测（2026-07-14）

- Family：`HYPE-1D-Multi-Horizon-EMA-Forecast`（`HYPE-1D-MHEF`）
- 状态：`explore / not promoted / not live-ready`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，UTC `1d`
- 日线数据：`2025-05-31T00:00:00+00:00` → `2026-07-13T00:00:00+00:00`；回测从 `2026-02-11T00:00:00+00:00` 开始
- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`；纳入实际 funding
- 切片仅作事后审计，不用于参数选择

## 结论

`0.10` 缓冲组合净收益为 `11.17%`，但有效回测区间不足一年，只能视为短样本观察，不能登记或推进。
同期 1x 永续买入持有净收益为 `129.69%`；精确调仓组合为 `10.12%`。

HYPE 上市历史较短，EMA `64/256` 使前 256 个交易日只能用于 warmup，剩余有效区间有限。无论结果正负，都不能据此判断跨 regime 稳健性。

## 日线适配

- 保留 EMA `8/32`、`16/64`、`32/128`、`64/256` 与权重 `0.2/0.3/0.3/0.2`。
- 由于原 intraday 滚动校准需要约 511 根日 K、超过 HYPE 全部历史，日线改用经典 CTA/EWMAC 固定 scalar。
- `daily_price_vol = close × EWMAStd(log_return, span=35)`。
- `raw = (EMA_fast - EMA_slow) / daily_price_vol`。
- scalar 依次为 `5.30 / 3.75 / 2.65 / 1.87`；标准 forecast 裁剪到 `[-20,20]`，再除以 `20` 映射到 `[-1x,1x]`。
- 当前日 K 收盘确认，下一日 open 调仓；同时测试精确跟踪与 `0.10` no-trade buffer。

## 全区间结果

| 运行 | 毛收益 | 净收益 | 最大回撤 | Sharpe | 平均绝对仓位 | 总换手 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `ensemble_buffer_0.00` | 10.93% | 10.12% | -14.80% | 0.92 | 0.279 | 2.5 |
| `ensemble_buffer_0.10` | 11.76% | 11.17% | -15.25% | 1.03 | 0.255 | 1.2 |
| `sleeve_8_32` | 1.52% | 0.23% | -19.76% | 0.21 | 0.306 | 6.3 |
| `sleeve_16_64` | 17.51% | 16.38% | -18.05% | 1.18 | 0.356 | 3.1 |
| `sleeve_32_128` | 15.75% | 14.89% | -13.10% | 1.22 | 0.312 | 2.6 |
| `sleeve_64_256` | 2.41% | 2.01% | -12.15% | 0.33 | 0.199 | 1.9 |
| `perpetual_buy_hold_1x` | 133.35% | 129.69% | -28.60% | 2.66 | 1.000 | 1.0 |

## 最近区间（0.10 缓冲）

| 窗口 | 收益 | 最大回撤 | Sharpe | 换手 |
| --- | ---: | ---: | ---: | ---: |
| `1d` | 0.26% | 0.00% | 0.00 | 0.0 |
| `7d` | -1.88% | -2.14% | -13.44 | 0.0 |
| `1m` | 4.53% | -5.54% | 2.27 | 0.0 |
| `3m` | 11.57% | -15.25% | 1.41 | 0.8 |
| `6m` | 11.17% | -15.25% | 1.03 | 1.2 |
| `1y` | 11.17% | -15.25% | 1.03 | 1.2 |

## 数据质量

- 输入为已通过 raw/normalized 对齐门的标准 `1h` 数据湖，聚合为完整 UTC 日：`409` 根，missing `0`，blocker `0`。
- Funding：`2457` 条，最大间隔 `8.0h`，blocker `0`。

## 证据

- Summary：[../artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-summary.json](../artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-summary.json)
- Forecast path：[../artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-forecasts.csv](../artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-forecasts.csv)
- Equity / turnover paths：[../artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-paths.csv](../artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-paths.csv)
- 脚本：[../scripts/research_hype_1d_multi_horizon_ema_forecast.py](../scripts/research_hype_1d_multi_horizon_ema_forecast.py)
- 共享执行内核：[../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py](../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py)，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`

## 状态

`explore / not promoted / not live-ready`。日线历史长度不足以覆盖多个市场 regime，本结果不构成版本登记或 runner 输入。
