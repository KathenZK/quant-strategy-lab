# BTC-1H-Adaptive-Regime-V1 基线规格

## 版本身份与状态

- Full name：`BTC-1H-Adaptive-Regime-V1`
- Short id：`BTC-1H-AR-V1`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：`1h`
- 状态：`diagnostic baseline / NO-GO / not promoted / not live-ready`
- 来源：2026-07-02 多指标宽搜索的 prefit 预冻结冠军；用户明确要求登记为 V1。

登记版本只冻结身份与复现边界，不改变此前 locked OOS 失败和生产 runner 缺失的结论。

## 数据与时间切分

- 原始闭合 K：`2024-07-02 10:00 UTC` 至 `2026-07-02 09:00 UTC`，共 `17,520` 根。
- warmup 后 train：`2024-08-16 10:00 UTC` 至 `2025-09-06 12:24 UTC`。
- validation：`2025-09-06 12:24 UTC` 至 `2026-04-02 10:00 UTC`。
- reused holdout：`2026-04-02 10:00 UTC` 至 `2026-07-02 10:00 UTC`；该区间已解锁，不得重新包装为 untouched OOS。

## Keltner breakout 腿

- signal：`close` 上穿/下穿 `SMA20 ± 2.5 * ATR14`。
- side：long + short。
- filter：`ADX14 >= 36`、`RVOL48 >= 0.8`、`ATR14/close <= 200 bps`、方向 `ROC24 >= 0 bps`、closed `1d` EMA spread 同向、对齐资金费 `<=2 bps`。
- exit：`TP=1.5 ATR14`、`SL=4 ATR14`、`120h` timeout、`6h` cooldown。
- sizing：固定 `3x`。

## CCI reversal 腿

- signal：CCI(20) 上穿 `-125` 做多、下穿 `+125` 做空；`side_mode=long` 后只保留多头。
- filter：`ADX14 <=36`、`RVOL48 >=1.5`、`50 <= ATR bps <=300`、价格距离 `EMA144 <=1000 bps`。
- exit：`TP=4 ATR14`、`SL=1.25 ATR14`、`96h` timeout、`24h` cooldown。
- sizing：固定 `4x`。

## Ensemble 与成交

- 两腿按各自 prefit score 排优先级；同一时段单仓，不加仓，重叠信号被已持仓路径抑制。
- 闭合 K 产生信号，下一根 `1h` open 市价入场。
- 入场即生效 stop/TP；同 K 双触发按 stop-first；open 穿越 stop 按 open 成交。
- fee `0.001/fill`、slippage `4 bps/fill`，逐笔计入 Binance 历史 funding。

## 冻结指标

| Window | Annual multiple | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | `2.58x` | `172.05%` | `-15.13%` | `68.00%` | `50` | `2.372` |
| Validation | `3.33x` | `98.46%` | `-18.68%` | `68.75%` | `32` | `2.406` |
| Prefit | `2.82x` | `439.91%` | `-18.68%` | `68.29%` | `82` | `2.385` |
| Reused holdout | `0.17x` | `-35.74%` | `-42.73%` | `38.46%` | `13` | `0.304` |
| Current full | `1.94x` | `246.95%` | `-42.73%` | `64.21%` | `95` | `1.765` |

## Promotion 边界

V1 仅作为消融和删参的正式基线。它不满足用户原始 `10x / >=50% / DD<20%` 目标，不得用于 candidate、paper-live、dry-run、handoff 或 live。

机器配置：`../artifacts/btc_1h_ar_v1_config_2026-07-02.json`。复现入口：`../scripts/btc_1h_ar_v1.py`。
