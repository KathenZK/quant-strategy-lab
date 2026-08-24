# BIN-1D-MA7-RSI6-DAPML P0 数据与方向对齐特征合同

## 1. 研究身份

- Family：`Binance-1D-MA7-RSI6-Direction-Aligned-Pooled-ML`
- Alias：`BIN-1D-MA7-RSI6-DAPML`
- 市场：Binance USD-M Futures perpetual
- 信号周期：完整 UTC `1d`
- 路径周期：官方 `1h`，只解析 fixed stop、gap fill、MFE/MAE
- 当前阶段：`explore / diagnostic-only / not promoted / not live-ready`

## 2. 资产池

固定 universe：

```text
BTCUSDT
ETHUSDT
BNBUSDT
SOLUSDT
TRXUSDT
```

选择规则：

- USDT 线性永续，避免混用 inverse/coin-margined 合约；
- 2020 年内已上线，可提供约五年或更长的共同日线研究；
- 属于既有六资产研究基础中的长期高流动性标的；
- 不纳入 HYPE：历史过短且会把单一新币 regime 混入 pooled 训练；
- 不按当前成交额扫描“全币安”，避免幸存者偏差、短历史币和事后 universe 选择。

P0 后不得在看到模型结果后增删资产；资产池变化必须建立新合同。

## 3. 数据来源与构建

### 3.1 小时 K

- Binance FAPI `/fapi/v1/klines`
- `interval=1h`
- 从各合约 `onboardDate` 起分页抓取
- 只接受 `close_time < Binance serverTime` 的完整小时 K
- 每个资产必须独立检查 24/7 网格、重复、OHLC、关键空值、闭合状态和 raw/normalized 对齐

### 3.2 UTC 日 K

统一从已接受 direct `1h` 数据聚合，不混用现有来源不一致的日线：

```text
open  = first hourly open
high  = max hourly high
low   = min hourly low
close = last hourly close
volume / quote_volume / trade_count = hourly sum
vwap = quote_volume / volume
```

- 每个 UTC 日必须恰有 `24` 根连续小时 K；
- 合约首日或末日不足 `24` 根时丢弃；
- 日线 timestamp 为 `00:00 UTC`，`is_closed=true`；
- 日线 OHLCV 必须与小时输入逐日重算对齐。

### 3.3 Funding 与 mark

- funding rate：Binance FAPI `/fapi/v1/fundingRate`，从合约上线起独立分页；
- endpoint `markPrice` 非空时直接使用；
- 历史空值只允许用官方 `/fapi/v1/markPriceKlines?interval=1h` 的实际 funding 小时 bucket open；
- funding timestamp 必须落在完整 UTC 小时，结算滞后在 `[0,1]` 秒；
- 不假定所有资产固定 `8h`：保留 Binance 在极端行情中实际采用的 `2h/4h/8h` 事件；相邻事件不得超过 `8h`，否则视为缺失 blocker；
- 无官方 mark 的早期 funding 事件不补代理值；涉及未解析 funding 的交易不得进入标签。

## 4. 统一时间边界

- development：各资产从首个完整、funding 可解析的 UTC 日开始，统一截止 `2025-08-06 UTC`。
- sealed period：所有资产共同封存 `2025-08-07` 至 `2026-08-06 UTC`。
- 任何 pooled 训练、特征分布、asset normalization、模型、edge 和诊断不得读取 sealed period。
- 其他资产不得使用 `2025-08-07` 之后的数据训练，因为它会通过共同加密市场 regime 间接侧漏 BTC 冻结年。

## 5. 基础指标

- `SMA7`、简单 rolling `ATR7`、Wilder `RSI6` 公式与单资产 [BTC P1 合同](../../../btc/1d-ma7-rsi6-lightgbm-trend/specs/btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)一致。
- 严格穿越仍要求前收与当收分别严格位于 SMA7 两侧；等于不算。
- 所有连续价格特征以本资产 signal-day `ATR7` 归一化，不做跨资产全样本 z-score。

## 6. 方向对齐特征

令 long `side=+1`、short `side=-1`。保留资产、方向与时间作为审计字段，但 universal 主模型不输入 asset id。

### 6.1 MA7

```text
aligned_prev_gap_atr  = side * prev_close_ma_gap_atr
aligned_close_gap_atr = side * close_ma_gap_atr
aligned_cross_span_atr = aligned_close_gap_atr - aligned_prev_gap_atr
aligned_ma7_slope_1_atr = side * ma7_slope_1_atr
aligned_ma7_slope_3_atr = side * ma7_slope_3_atr
prior_side_duration = 穿越前连续位于旧侧的严格收盘根数
```

### 6.2 K 线与五日路径

```text
aligned_body_atr = side * body_atr
aligned_close_location = 0.5 + side * (close_location - 0.5)
rejection_wick_atr = lower_wick_atr if long else upper_wick_atr
opposition_wick_atr = upper_wick_atr if long else lower_wick_atr
aligned_return_3_atr = side * return_3_atr
aligned_return_5_atr = side * return_5_atr
range_atr = 原值
```

`aligned_close_location` 越高表示收盘越靠近候选方向一端；`rejection_wick` 表示候选方向入场前对反方向价格的拒绝。

### 6.3 RSI6

```text
aligned_rsi6 = rsi6 if long else 100 - rsi6
aligned_rsi6_delta_1 = side * rsi6_delta_1
directional_rsi_extreme_5 = rsi6_max_5 if long else 100 - rsi6_min_5
counter_rsi_extreme_5 = rsi6_min_5 if long else 100 - rsi6_max_5
directional_rsi80_last5 = rsi6_high80_last5 if long else rsi6_low20_last5
counter_rsi20_last5 = rsi6_low20_last5 if long else rsi6_high80_last5
```

这些字段只统一几何语义，不预先断言高 RSI 或影线必然有利。

### 6.4 资产与流动性诊断

- `asset` 不进入 universal 主模型；只用于分资产审计与 leave-one-asset-out。
- quote volume、trade count 和资产 id 可作独立消融，但不能进入首个主模型。
- 禁止跨资产使用未经 point-in-time 处理的当前市值、未来成交额排名或全样本 z-score。

## 7. P1 前置验证结构

P1 模型合同必须在训练前进一步冻结：

- pooled temporal walk-forward；
- leave-one-asset-out 五折；
- 每资产最少事件数和分资产门禁；
- Logistic-EV 与 LightGBM 的角色；
- fixed edge 或 nested edge；
- portfolio 同时信号仲裁与总杠杆；
- BTC 单资产 sealed year 的人工揭示权限。

P0 只完成数据、事件容量和方向对齐特征审计，不产生 pooled 策略收益结论。
