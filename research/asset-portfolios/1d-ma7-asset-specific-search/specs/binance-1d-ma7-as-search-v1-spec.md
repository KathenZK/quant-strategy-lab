# Binance-1D-MA7-Asset-Specific-Search V1 规格

## 身份

- Family：`Binance-1D-MA7-Asset-Specific-Search`
- Version：`V1`
- Alias：`BIN-1D-MA7-AS-SEARCH-V1`
- 状态：`registered / not promoted / not live-ready`
- 市场/周期：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual，UTC `1d`
- 机制：固定 `SMA7/ATR7` 的 BTC/ETH shared 参数；long 使用 `reclaim`，short 使用 `pullback_reclaim`
- 证据角色：历史已揭示 development / holdout / fresh aligned diagnostic；不是 clean OOS，不构成 promotion

## 冻结参数

| Field | Long | Short |
| --- | ---: | ---: |
| `side` | `1` | `-1` |
| `entry_mode` | `reclaim` | `pullback_reclaim` |
| `slope_lookback` | `5` | `5` |
| `slope_min_atr` | `0.0` | `0.0` |
| `confirm_days` | `1` | `1` |
| `entry_buffer_atr` | `0.25` | `0.1` |
| `pullback_lookback` | `10` | `5` |
| `pullback_touch_atr` | `0.1` | `-0.5` |
| `breakout_lookback` | `7` | `10` |
| `exit_confirm_days` | `2` | `2` |
| `exit_buffer_atr` | `1.0` | `0.75` |
| `slope_exit_lookback` | `5` | `0` |
| `hard_stop_atr` | `0.0` | `1.5` |
| `trail_atr` | `0.0` | `5.0` |
| `max_hold_days` | `0` | `10` |
| `cooldown_days` | `0` | `2` |

## 信号与执行

- Indicator：`SMA7` 和 `ATR7` 使用闭合 UTC 日K计算。
- Entry：在闭合日 `t` 识别信号，下一日 open 执行；short 的 `pullback_reclaim` 要求此前回到上方/反弹带后重新跌破入场带。
- Exit：日线 MA7 迟滞、斜率退出、short hard stop、short trailing、short max hold 按冻结 engine 执行；stop 使用真实 `1h` 路径。
- 仓位：约 `1x`、单仓、非加仓；long / short 共用账户权益。
- 成本：fee `0.001/fill`，base slippage `4 bps/fill`，stress slippage `8 bps/fill`。
- Funding：Binance fundingRate event-time，持仓方向按真实 funding 现金流计入。

## 冻结指标

### 原搜索 full 窗口

| Target | Combined Net | MDD | Holdout | Stress / Delay |
| --- | ---: | ---: | ---: | --- |
| `BTCUSDT` | `+112.34%` | `-17.96%` | `+0.49%` | `8bps +107.67%`；`+1d lag +155.15%` |
| `ETHUSDT` | `+161.46%` | `-29.29%` | `+27.14%` | `8bps +156.55%`；`+1d lag +182.32%` |

### HYPE 对齐 fresh 窗口

窗口：`2025-05-31` 至 `2026-08-11` 完整日K，terminal open `2026-08-12 00:00 UTC`。

| Target | Combined Net | MDD | Sharpe | PF | Trades | Buy-and-hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `BTCUSDT` | `+48.86%` | `-14.78%` | `1.74` | `3.28` | `15` | `-43.28%` |
| `ETHUSDT` | `+55.29%` | `-27.02%` | `1.32` | `2.36` | `10` | `-30.73%` |
| `HYPEUSDT` control | `-65.15%` | `-73.47%` | `-1.38` | `0.29` | `14` | `+52.01%` |

## 决策边界

- V1 只登记 BTC/ETH shared 参数身份；不代表 HYPE 可迁移，不代表 runner handoff。
- HYPE control 大幅亏损，说明 V1 不能替代 HYPE V7.1。
- ETH `12h` 相位在旧 full phase check 中翻负，作为证据置信度风险提示；按当前治理不是独立 hard gate。
- Promotion 前仍缺 clean prospective OOS、CPCV/robustness review、runner parity、实盘执行时序审计和线上开平仓对账。

## 证据

- [主账](../binance-1d-ma7-as-search-core-ledger.md)
- [搜索诊断](../diagnostics/binance-btc-eth-1d-ma7-asset-specific-search-2026-08-05.md)
- [BTC/ETH HYPE aligned复算](../diagnostics/binance-ma7-shared-params-btc-eth-hype-aligned-2026-08-12.md)
- [HYPE aligned control](../diagnostics/binance-ma7-shared-params-on-hype-fresh-aligned-2026-08-12.md)
- [BTC V1交易路径](../artifacts/binance_ma7_shared_params_v1_btc_trade_path_2026-08-12.html)
- [ETH V1交易路径](../artifacts/binance_ma7_shared_params_v1_eth_trade_path_2026-08-12.html)
- [机器摘要](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)
