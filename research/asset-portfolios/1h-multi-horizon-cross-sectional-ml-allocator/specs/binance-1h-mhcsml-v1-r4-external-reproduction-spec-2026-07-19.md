# BIN-1H-MHCSML-V1 freeze R4 外部独立复现规格

## 读者、用途与当前状态

本文面向没有本仓库、没有本地脚本、没有已有 artifact 的外部研究员或 AI。仅凭本文，应能从 Binance 公共数据重新构建特征、训练模型、生成信号、复现历史 OOF 审计，并在规定时间完成一次性 prospective OOS 验收。

- 家族：`Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator`
- 版本：`BIN-1H-MHCSML-V1`
- 冻结修订：`freeze R4`
- 状态：`registered / prospective OOS active / not promoted / not live-ready`
- 主冻结 SHA256：`64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11`
- 冻结时间：`2026-07-18 17:02:06 UTC`
- 禁止事项：在 prospective OOS 揭盲前，不得根据信号后的价格、收益、胜率、回撤、IC 或任何可反推表现的统计修改因子、模型、阈值、成本、币池、频率或仓位。

这不是可上线声明。最终 OOS 任一硬门槛失败，结论必须是 `HARD-GATE-FAILED / not promoted / not live-ready`。

## 一、环境与数值语义

参考环境：Python `3.12`，LightGBM `4.6.0`，scikit-learn `1.9.0`，pandas `3.0.2`，NumPy `2.4.4`，DuckDB `1.5.2`。时间统一为 UTC；所有时间戳表示 1h K 线的开盘时刻。

除非另有说明：

- `rolling(W)` 使用当前行和前 `W-1` 行，`min_periods=W`；
- pandas `std()` 使用样本标准差 `ddof=1`；DuckDB `stddev_pop()` 使用总体标准差；
- pandas rolling `skew()`、`kurt()` 保持上述版本的无偏样本语义，`kurt()` 为 excess kurtosis；
- 除 EMA/RSI 外不使用 EWMA；
- 除明示的 `shift(1)`、标签未来窗口外，任何特征不得读取未来行；
- 分母为 0 时设为 `NaN`，正负无穷转为 `NaN`；LightGBM 原生处理缺失值；
- 训练与推理均把特征转换为 `float32`；
- 同一时间横截面排序和过滤只使用当时可交易币池。

## 二、数据来源、字段与动态币池

### 2.1 数据来源

市场为 Binance USD-M、USDT 计价、`PERPETUAL`、`1h`。历史数据范围为 `2020-01-01 00:00 <= ts < 2026-07-01 00:00 UTC`，另需从 `2026-07-01` 持续获取数据供冻结 gap 和 prospective OOS 使用。

优先使用 Binance Vision：

- 普通 K 线：`https://data.binance.vision/data/futures/um/monthly/klines/{API_SYMBOL}/1h/{API_SYMBOL}-1h-{YYYY-MM}.zip`
- mark price K 线：`https://data.binance.vision/data/futures/um/monthly/markPriceKlines/{API_SYMBOL}/1h/{API_SYMBOL}-markPriceKlines-1h-{YYYY-MM}.zip`
- funding：`https://data.binance.vision/data/futures/um/monthly/fundingRate/{API_SYMBOL}/{API_SYMBOL}-fundingRate-{YYYY-MM}.zip`
- 月归档内部缺小时，依次用同结构的 `daily` 归档和 Binance FAPI 补齐；不得前值填充价格或成交量。

FAPI 根地址为 `https://fapi.binance.com`：

- 当前合约元数据：`GET /fapi/v1/exchangeInfo`
- 普通 K 线：`GET /fapi/v1/klines?symbol=...&interval=1h&startTime=...&endTime=...&limit=1500`
- mark K 线：`GET /fapi/v1/markPriceKlines?symbol=...&interval=1h&startTime=...&endTime=...&limit=1500`
- funding：`GET /fapi/v1/fundingRate`，按时间分页，不能只取最近一页。

历史 symbol 集合取 2020-01 至 2026-06 三类 Binance Vision 目录的并集，再加当前 `exchangeInfo` 中满足 `contractType=PERPETUAL`、`quoteAsset=USDT`、`status=TRADING` 且 symbol 以 `USDT` 结尾的合约。API symbol `BTCUSDT` 规范化为 `BTC/USDT:USDT`；历史退市币必须保留，不能用今天的币表倒推历史。

### 2.2 普通 K 线 schema

每个 `(ts,symbol)` 唯一，至少包含：

```text
ts, symbol, open, high, low, close,
volume, quote_volume, trade_count,
taker_buy_volume, taker_buy_quote_volume, vwap
```

`vwap = quote_volume / volume`；当 `volume=0` 时使用该 bar 的 `close`。价格和成交字段均转为数值；`open/high/low/close > 0`，成交字段不得为负。只允许使用已闭合 bar。

### 2.3 mark 与 funding schema

mark 表每个 `(ts,symbol)` 唯一，取该 1h mark K 线的 `close` 作为 `mark_price`。funding 表每个结算事件 `(ts,symbol)` 唯一，至少含 `funding_rate`；同键费率冲突是数据 blocker。

对每个小时：

- `funding_rate`：该时点之前最近一条已知 funding rate，按 symbol backward as-of join；
- `funding_event_rate`：只有该小时恰有结算事件时取事件费率，否则为 `0`；
- 若一个合约完全没有 funding 历史，`funding_rate=NaN`，不得把它伪装成真实的 0。

### 2.4 连续网格与数据门禁

每个 symbol 从第一根到最后一根建立完整 UTC 小时网格，`bar_present = close 非空`。缺失普通 K 线不填充。任何标签的 K1 入场到退出路径只要碰到缺 bar，就把 `label_path_valid=false` 并排除。

数据质量必须同时通过：唯一键、UTC 整点、OHLC 合法、关键字段类型、无未闭合 bar、无重复 funding、普通/mark 对齐、raw 与 normalized 可追溯、缺口有 daily/FAPI 空返回证据。参考审计规模为普通 K 线 `14,114,255` 行/`790` symbols，mark `14,308,668` 行/`788` symbols，funding `2,428,690` 行/`792` symbols；最终不可交易缺口为普通 K 线 `251` 小时、mark `72` 小时，均须按 nontradable 处理。

### 2.5 Point-in-time 动态币池

对完整小时网格逐 symbol 计算：

```text
age_hours = (ts - 第一根实际 bar 的 ts) / 1h
coverage_30d = mean(bar_present, 720)，min_periods=720
avg_daily_quote_volume_7d = sum(quote_volume, 168) / 7，min_periods=168
```

先保留 `age_hours>=720`、`coverage_30d>=0.99`、`avg_daily_quote_volume_7d>=5,000,000` 的合约。同一 ts 按 `avg_daily_quote_volume_7d` 降序、symbol 升序生成 `liquidity_rank`，只保留前 150；主模型币池 `universe_main` 再要求 `avg_daily_quote_volume_7d>=10,000,000` 且 `liquidity_rank<=100`。

## 三、时间、成交、收益与标签

### 3.1 信号与成交时序

在 K0 完全闭合后用 K0 及更早数据算特征。信号时刻 `ts=K0 open time`；在 `K1 open = ts+1h` 入场；持有 48 小时后在 `ts+49h` 的 open 退出。没有盘中止损、止盈、追踪止损或同 bar 冲突；若入场或退出 open 缺失，整条腿无效，不以相邻价格代替。

基础成本：每次成交手续费 `0.001`，每次成交不利滑点 `0.0004`，双边 `round_trip_cost=0.0028`。压力成本为基础成本的 `1.5x`，即每腿再扣 `0.0014`。

### 3.2 线性 USD-M 收益

设 `E=entry_open`，`X=exit_open`，`F=sum(funding_rate events)`，其中 funding 事件严格落在 `(entry_time, exit_time]`：

```text
gross = X/E - 1
long_net  = X/E - 1 - 0.0028 - F
short_net = 1 - X/E - 0.0028 + F
stress_short_net = short_net - 0.0014
```

做空收益可能低于 `-100%`，因为线性合约空头在标的上涨超过 100% 时损失可超过初始腿名义本金；不得把结果裁剪到 `[-1,1]`。

### 3.3 48h 三类冻结标签

对 K0 后未来 48 根持仓 bar：

```text
upside_excursion = max(high[K1..K48]) / E - 1
short_return_target = short_net_48h
short_mae_raw = min(-upside_excursion, 0)       # 非正数
short_mae_training_target = -short_mae_raw      # 非负数，越大风险越高
short_squeeze_target = 1(upside_excursion >= 0.10)
short_win_target = 1(short_net_48h > 0)
```

最终四组模型分别预测：`short_return_target`、`short_mae_training_target` 的 80% 分位、`short_squeeze_target` 的概率、`short_win_target` 的概率。

## 四、235 个 stable-full 特征与 86 个 compact 特征

### 4.1 通用记号

令 `C,O,H,L,V,Q,N,T,M` 分别为 close、open、high、low、base volume、quote volume、trade count、taker buy volume、mark price；`r_t=ln(C_t)-ln(C_{t-1})`；`SMA_W(x)`、`SUM_W(x)`、`MAX_W(x)`、`MIN_W(x)`、`STD_W(x)` 均含当前行且 `min_periods=W`。

`Z_W(x)=(x-SMA_W(x))/STD_W(x)`。EMA 使用 `adjust=False`、`min_periods=W`、`alpha=2/(W+1)`。RSI 的 gain/loss EWMA 使用 `adjust=False`、`min_periods=W`、`alpha=1/W`。

### 4.2 基础特征公式与窗口

下表按“公式族 + 窗口集合”完整定义 176 个 stable-full 基础特征；把窗口值代入名称即得实际列名。

| 名称 | 窗口/参数 | 精确公式 |
| --- | --- | --- |
| `age_bars` | - | 当前 symbol 本地完整网格的 1-based 行号 |
| `ret_W` | `1,2,4,8,12,24,48,72,168,336,720` | `C/C.shift(W)-1` |
| `ema_spread_F_S` | `6_24,12_48,24_96,48_192,96_384,168_720` | `EMA_F(C)/EMA_S(C)-1` |
| `ma_distance_W` | `12,24,48,96,168,336,720` | `C/SMA_W(C)-1` |
| `breakout_W` | `12,24,48,96,168,336,720` | `C/MAX_W(C)-1`，rolling max 含当前 C |
| `rsi_W` | `6,12,24,48,96` | Wilder RSI：`delta=C.diff()`，gain=`max(delta,0)`，loss=`max(-delta,0)`，按上文 alpha 平滑；双零为 50，仅 loss 零为 100，仅 gain 零为 0 |
| `atr_pct_W` | `6,12,24,48,96,168,336` | `TR=max(H-L,abs(H-C.shift(1)),abs(L-C.shift(1)))`；`SMA_W(TR)/C` |
| `zscore_W` | `24,72,168,336` | `Z_W(C)` |
| `bollinger_distance_W` | `24,72,168,336` | `(C-SMA_W(C))/(2*STD_W(C))` |
| `bullish_candle_count_W` | `24,72,168,336` | `SUM_W(1(C>O))` |
| `bearish_candle_count_W` | `24,72,168,336` | `SUM_W(1(C<O))` |
| `volume_surge_W` | `6,24,72,168,336` | `V/SMA_W(V)-1` |
| `avg_dollar_volume_W` | `6,24,72,168,336` | `SMA_W(C*V)` |
| `dollar_volume_W` | `6,24,72,168,336` | `SUM_W(C*V)` |
| `amihud_illiquidity` | 2 bars | `abs(C/C.shift(1)-1)/(C*V)` |
| `vwap_distance` | 1 bar | `C/vwap-1`，`vwap=Q/V`，V=0 时 vwap=C |
| `funding_rate` | 1 bar | 截至当前 ts 最近已知 funding rate |
| `funding_zscore_W` | `24,72,168,336` | `Z_W(funding_rate)` |
| `funding_mean_W` | `24,72,168` | `SMA_W(funding_rate)` |
| `funding_event_sum_W` | `24,72,168` | `SUM_W(funding_event_rate)` |
| `candle_range_pct` | 1 bar | `(H-L)/O` |
| `candle_body_strength` | 1 bar | `(C-O)/(H-L)` |
| `close_location` | 1 bar | `(C-L)/(H-L)` |
| `upper_wick_ratio` | 1 bar | `(H-max(O,C))/(H-L)` |
| `lower_wick_ratio` | 1 bar | `(min(O,C)-L)/(H-L)` |
| `taker_imbalance_1` | 1 bar | `2*T/V-1` |
| `taker_imbalance_mean_W` | `6,12,24,72,168,336` | `SMA_W(2*T/V-1)` |
| `taker_imbalance_std_W` | `24,72,168` | `STD_W(2*T/V-1)` |
| `quote_volume_ratio_W` | `6,12,24,72,168,336` | `Q/SMA_W(Q)-1` |
| `trade_count_ratio_W` | `6,12,24,72,168,336` | `N/SMA_W(N)-1` |
| `mark_premium` | 1 bar | `M/C-1` |
| `mark_premium_zscore_W` | `24,72,168,336` | `Z_W(M/C-1)` |
| `mark_premium_max_W` | `24,72,168` | `MAX_W(M/C-1)` |
| `mark_premium_min_W` | `24,72,168` | `MIN_W(M/C-1)` |
| `realized_vol_W` | `6,12,24,72,168,336` | `STD_W(r)*sqrt(24*365)` |
| `downside_vol_W` | `6,12,24,72,168,336` | `STD_W(min(r,0))*sqrt(24*365)` |
| `upside_vol_W` | `12,24,72,168,336` | `STD_W(max(r,0))*sqrt(24*365)` |
| `max_drawdown_W` | `6,12,24,72,168,336` | `C/MAX_W(C)-1` |
| `return_skew_W` | `24,72,168,336` | pandas rolling sample skew of `r` |
| `return_kurtosis_W` | `24,72,168,336` | pandas rolling excess kurtosis of `r` |
| `extreme_return_up_W` | `6,24,72,168` | `MAX_W(r)` |
| `extreme_return_down_W` | `6,24,72,168` | `MIN_W(r)` |
| `jump_count_up_3pct_W` | `24,72,168,336` | `SUM_W(1(r>=0.03))` |
| `jump_count_down_3pct_W` | `24,72,168,336` | `SUM_W(1(r<=-0.03))` |
| `range_max_W` | `24,72,168` | `MAX_W((H-L)/O)` |

完整 176 列按冻结顺序为：

```text
age_bars, amihud_illiquidity,
atr_pct_12, atr_pct_168, atr_pct_24, atr_pct_336, atr_pct_48, atr_pct_6, atr_pct_96,
avg_dollar_volume_168, avg_dollar_volume_24, avg_dollar_volume_336, avg_dollar_volume_6, avg_dollar_volume_72,
bearish_candle_count_168, bearish_candle_count_24, bearish_candle_count_336, bearish_candle_count_72,
bollinger_distance_168, bollinger_distance_24, bollinger_distance_336, bollinger_distance_72,
breakout_12, breakout_168, breakout_24, breakout_336, breakout_48, breakout_720, breakout_96,
bullish_candle_count_168, bullish_candle_count_24, bullish_candle_count_336, bullish_candle_count_72,
candle_body_strength, candle_range_pct, close_location,
dollar_volume_168, dollar_volume_24, dollar_volume_336, dollar_volume_6, dollar_volume_72,
downside_vol_12, downside_vol_168, downside_vol_24, downside_vol_336, downside_vol_6, downside_vol_72,
ema_spread_12_48, ema_spread_168_720, ema_spread_24_96, ema_spread_48_192, ema_spread_6_24, ema_spread_96_384,
extreme_return_down_168, extreme_return_down_24, extreme_return_down_6, extreme_return_down_72,
extreme_return_up_168, extreme_return_up_24, extreme_return_up_6, extreme_return_up_72,
funding_event_sum_168, funding_event_sum_24, funding_event_sum_72,
funding_mean_168, funding_mean_24, funding_mean_72, funding_rate,
funding_zscore_168, funding_zscore_24, funding_zscore_336, funding_zscore_72,
jump_count_down_3pct_168, jump_count_down_3pct_24, jump_count_down_3pct_336, jump_count_down_3pct_72,
jump_count_up_3pct_168, jump_count_up_3pct_24, jump_count_up_3pct_336, jump_count_up_3pct_72,
lower_wick_ratio,
ma_distance_12, ma_distance_168, ma_distance_24, ma_distance_336, ma_distance_48, ma_distance_720, ma_distance_96,
mark_premium, mark_premium_max_168, mark_premium_max_24, mark_premium_max_72,
mark_premium_min_168, mark_premium_min_24, mark_premium_min_72,
mark_premium_zscore_168, mark_premium_zscore_24, mark_premium_zscore_336, mark_premium_zscore_72,
max_drawdown_12, max_drawdown_168, max_drawdown_24, max_drawdown_336, max_drawdown_6, max_drawdown_72,
quote_volume_ratio_12, quote_volume_ratio_168, quote_volume_ratio_24, quote_volume_ratio_336, quote_volume_ratio_6, quote_volume_ratio_72,
range_max_168, range_max_24, range_max_72,
realized_vol_12, realized_vol_168, realized_vol_24, realized_vol_336, realized_vol_6, realized_vol_72,
ret_1, ret_12, ret_168, ret_2, ret_24, ret_336, ret_4, ret_48, ret_72, ret_720, ret_8,
return_kurtosis_168, return_kurtosis_24, return_kurtosis_336, return_kurtosis_72,
return_skew_168, return_skew_24, return_skew_336, return_skew_72,
rsi_12, rsi_24, rsi_48, rsi_6, rsi_96,
taker_imbalance_1,
taker_imbalance_mean_12, taker_imbalance_mean_168, taker_imbalance_mean_24, taker_imbalance_mean_336, taker_imbalance_mean_6, taker_imbalance_mean_72,
taker_imbalance_std_168, taker_imbalance_std_24, taker_imbalance_std_72,
trade_count_ratio_12, trade_count_ratio_168, trade_count_ratio_24, trade_count_ratio_336, trade_count_ratio_6, trade_count_ratio_72,
upper_wick_ratio,
upside_vol_12, upside_vol_168, upside_vol_24, upside_vol_336, upside_vol_72,
volume_surge_168, volume_surge_24, volume_surge_336, volume_surge_6, volume_surge_72,
vwap_distance, zscore_168, zscore_24, zscore_336, zscore_72
```

### 4.3 48 个横截面排名特征

对同一 ts 的 broad universe 前 150 合约，对下列 48 个基础列生成 `cs_rank_X`：按 X 升序使用 SQL `rank()`（并列取最小名次），`cs_rank=(rank-1)/(non_null_count-1)`；X 为空则结果为空。

```text
ret_4, ret_12, ret_24, ret_72, ret_168,
ema_spread_6_24, ema_spread_24_96, ema_spread_96_384,
ma_distance_24, ma_distance_96, rsi_24,
atr_pct_24, atr_pct_168, realized_vol_24, realized_vol_168,
max_drawdown_72, max_drawdown_336,
quote_volume_ratio_24, trade_count_ratio_24, taker_imbalance_mean_24,
funding_rate, funding_zscore_168, mark_premium, mark_premium_zscore_168,
ret_8, ret_48, upside_vol_24, upside_vol_168,
return_kurtosis_24, return_kurtosis_168,
extreme_return_up_24, extreme_return_up_168,
extreme_return_down_24, extreme_return_down_168,
jump_count_up_3pct_24, jump_count_up_3pct_168,
jump_count_down_3pct_24, jump_count_down_3pct_168,
range_max_24, range_max_168,
taker_imbalance_std_24, taker_imbalance_std_168,
funding_event_sum_24, funding_event_sum_168,
mark_premium_max_24, mark_premium_max_168,
mark_premium_min_24, mark_premium_min_168
```

### 4.4 11 个横截面上下文特征

全部在同一 ts 的 broad universe 前 150 上计算：

```text
liquidity_rank = 按 avg_daily_quote_volume_7d 降序、symbol 升序的 1-based row_number
avg_daily_quote_volume_7d = 2.5 节定义
coverage_30d = 2.5 节定义
relative_to_btc_24 = ret_24 - BTC/USDT:USDT 的 ret_24
relative_to_btc_168 = ret_168 - BTC/USDT:USDT 的 ret_168
market_breadth_ret24_positive = mean(1(ret_24>0))
market_breadth_trend_positive = mean(1(ema_spread_24_96>0))
market_median_realized_vol_24 = median(realized_vol_24)
market_dispersion_ret24 = stddev_pop(ret_24)
market_dispersion_vol24 = stddev_pop(realized_vol_24)
market_positive_funding_share = mean(1(funding_rate>0))
```

以上 `176+48+11=235` 列构成 `stable_full`，顺序为基础列、48 个 `cs_rank_` 列、11 个上下文列。

### 4.5 compact 86 列

确认分类器和 Ridge 基线严格使用以下顺序：

```text
age_bars, atr_pct_24, atr_pct_168,
ema_spread_6_24, ema_spread_24_96, ema_spread_96_384,
funding_rate, funding_zscore_168,
ma_distance_24, ma_distance_96,
mark_premium, mark_premium_zscore_168,
max_drawdown_72, max_drawdown_336,
quote_volume_ratio_24, realized_vol_24, realized_vol_168,
ret_4, ret_8, ret_12, ret_24, ret_48, ret_72, ret_168,
rsi_24, taker_imbalance_mean_24, trade_count_ratio_24,
cs_rank_ret_4, cs_rank_ret_12, cs_rank_ret_24, cs_rank_ret_72, cs_rank_ret_168,
cs_rank_ema_spread_6_24, cs_rank_ema_spread_24_96, cs_rank_ema_spread_96_384,
cs_rank_ma_distance_24, cs_rank_ma_distance_96, cs_rank_rsi_24,
cs_rank_atr_pct_24, cs_rank_atr_pct_168,
cs_rank_realized_vol_24, cs_rank_realized_vol_168,
cs_rank_max_drawdown_72, cs_rank_max_drawdown_336,
cs_rank_quote_volume_ratio_24, cs_rank_trade_count_ratio_24,
cs_rank_taker_imbalance_mean_24, cs_rank_funding_rate,
cs_rank_funding_zscore_168, cs_rank_mark_premium, cs_rank_mark_premium_zscore_168,
cs_rank_ret_8, cs_rank_ret_48,
cs_rank_upside_vol_24, cs_rank_upside_vol_168,
cs_rank_return_kurtosis_24, cs_rank_return_kurtosis_168,
cs_rank_extreme_return_up_24, cs_rank_extreme_return_up_168,
cs_rank_extreme_return_down_24, cs_rank_extreme_return_down_168,
cs_rank_jump_count_up_3pct_24, cs_rank_jump_count_up_3pct_168,
cs_rank_jump_count_down_3pct_24, cs_rank_jump_count_down_3pct_168,
cs_rank_range_max_24, cs_rank_range_max_168,
cs_rank_taker_imbalance_std_24, cs_rank_taker_imbalance_std_168,
cs_rank_funding_event_sum_24, cs_rank_funding_event_sum_168,
cs_rank_mark_premium_max_24, cs_rank_mark_premium_max_168,
cs_rank_mark_premium_min_24, cs_rank_mark_premium_min_168,
liquidity_rank, avg_daily_quote_volume_7d, coverage_30d,
relative_to_btc_24, relative_to_btc_168,
market_breadth_ret24_positive, market_breadth_trend_positive,
market_median_realized_vol_24, market_dispersion_ret24,
market_dispersion_vol24, market_positive_funding_share
```

6 个 `donchian_breakout_strength_{12,24,48,96,168,336}` 因历史覆盖不足 80% 被排除，不得在 R4 中补回。

## 五、历史切分、模型训练与冻结参数

### 5.1 历史 OOF

开发候选只使用 `ts < 2026-04-01 00:00 UTC`。7 个 outer validation fold 为：

```text
wf_2023_h1: [2023-01-01, 2023-07-01)
wf_2023_h2: [2023-07-01, 2024-01-01)
wf_2024_h1: [2024-01-01, 2024-07-01)
wf_2024_h2: [2024-07-01, 2025-01-01)
wf_2025_h1: [2025-01-01, 2025-07-01)
wf_2025_h2: [2025-07-01, 2026-01-01)
wf_2026_q1: [2026-01-01, 2026-04-01)
```

每个 fold 的训练集是该 validation start 之前所有可用历史，但训练终点为 `validation_start-48h`，形成 48h purge。训练集内部最后 120 天用于 early stopping；inner fit 又在这 120 天之前留 48h purge。最多 500 棵树，early stopping patience 50。随机切分、同窗训练同窗预测、跨 fold 拼接 in-sample 预测均禁止。

### 5.2 最终 refit 数据

冻结参数确定后，最终模型可使用 `ts<2026-07-01` 的历史及已揭示 2026Q2 做 refit，但 2026Q2 不再宣称独立 OOS。只取 UTC 小时 `%4==0`、`universe_main=true`、48h path 完整且三类标签齐全的行。参考结果：`1,239,909` 行、`626` symbols，首行 `2020-01-31 00:00 UTC`，最后 feature ts `2026-06-28 20:00 UTC`。

final early-stopping 子切分：inner 从 `2026-02-28 20:00 UTC` 开始，fit 截止 `2026-02-26 20:00 UTC`；取得最佳迭代数后，用该固定迭代数在全部 `1,239,909` 行重训。

### 5.3 LightGBM 通用参数

```text
learning_rate=0.04
num_leaves=31
max_depth=-1
min_child_samples=300
subsample=0.80
subsample_freq=1
colsample_bytree=0.75
reg_alpha=0.10
reg_lambda=1.00
n_jobs=8
deterministic=true
force_col_wise=true
verbosity=-1
seeds=[7,17,29,42]
```

short-return regression：`objective=regression_l1, metric=l1`。short-MAE：`objective=quantile, metric=quantile, alpha=0.80`。两种分类器：`objective=binary, metric=binary_logloss`。每个任务的四个 seed 预测做算术平均。

### 5.4 16 个最终模型

| 模型 | 特征 | seed | trees | 模型 SHA256 |
| --- | ---: | ---: | ---: | --- |
| short return regression | 235 | 7 | 176 | `cba48c0f4be70e452ecb0c201bb5312738489d623e28a705e009fa8db9d1e026` |
| short return regression | 235 | 17 | 199 | `3c8d51a7fd99b41010b336b5b12bff076e452138b1442ff22a5544fe0234b02d` |
| short return regression | 235 | 29 | 292 | `1ce996dbc43d84568ad006ce850b951a42416c3ae03410cc0f0c8339892e64b0` |
| short return regression | 235 | 42 | 181 | `36534d7e1e31cee1de0084cc6c8cfdf7927a1005eb3259ded36c752b75001865` |
| short MAE q80 | 235 | 7 | 499 | `03ee0e46da32ce512100f475124981d4884bb806ce99eb1a3d8ee89534e80c02` |
| short MAE q80 | 235 | 17 | 483 | `90957218b574de42aab670c57acb329d5f2083ac03d5b499ae2d1b300c332adf` |
| short MAE q80 | 235 | 29 | 500 | `27900b185a6fb5ca7dd0c1bba8c092e83cfd72b1b365fc1d9582d83737a0e9c8` |
| short MAE q80 | 235 | 42 | 493 | `840c704c5062c3876439dde4c63abb7530d0d875d4fcbb93a29d2926f46e25ae` |
| short squeeze classifier | 235 | 7 | 140 | `9d0a49eff9a80f86b08ee619cc7bc2d49975beaf00b8150d6c4448a8f9c9cf51` |
| short squeeze classifier | 235 | 17 | 219 | `7d7b0e17bdbe84cb6e2bae08161f41ed167713352e6a9775a282605ab51282ff` |
| short squeeze classifier | 235 | 29 | 258 | `af2ecf628cefa8b8689a8bee6dc07a7fc6d970ef72700885a6923fb56ce1a930` |
| short squeeze classifier | 235 | 42 | 171 | `b0f98c36ae00f9918f6c9616c255ff4623f9e39d0919c22b9a12b6d83c50ab14` |
| short win classifier | 86 | 7 | 113 | `d202012fe67901273af4fe8824895546007b5f0960c939db587edffd1c64d6c3` |
| short win classifier | 86 | 17 | 118 | `9ebf4eec05cef361ae89c20bbaf28fe3c7d09a7e6a1eb8efe20b5f650343f061` |
| short win classifier | 86 | 29 | 93 | `0ebc301098ce632eaf150d488775641e643839b7c73353d55cbcb51222ffae84` |
| short win classifier | 86 | 42 | 172 | `483f275d0138774e3e1aef440890fca2d289eafbc71e3dff950fef3fb434b33f` |

LightGBM 跨机器的文本模型 SHA 只有在版本、特征顺序、行顺序和线程行为完全一致时才应强制相等；若 SHA 不等，必须先逐项对齐数据行数、最佳迭代、OOF IC 和锚点，不得直接接受近似结果。

## 六、R4 信号、allocator 与仓位

### 6.1 横截面稳健标准化

对同一 ts、`universe_main` 中每个分数 x：

```text
robust_z(x) = clip((x - median(x)) / sample_std(x), -10, 10)
```

标准差为 0 或结果为空时填 0。注意这里虽然名为 robust z-score，分母是样本标准差，不是 MAD。

### 6.2 R4 打分

```text
return_score       = 四个 short-return regression 预测的平均
mae_score          = 四个 short-MAE q80 预测的平均
event_score        = 四个 short-squeeze 概率的平均
confirmation_score = 四个 short-win 概率的平均

return_z_raw  = robust_z(return_score)
mae_z         = robust_z(mae_score)
event_z       = robust_z(event_score)
confirm_z     = robust_z(confirmation_score)
return_z      = return_z_raw + 0.25 * confirm_z
raw_utility   = return_z - 1.00 * mae_z - 0.50 * event_z
utility       = robust_z(raw_utility)
```

每 4 小时决策一次，仅处理 `ts.hour % 4 == 0`。只做空。保留 `utility>=1.75` 的币，按 `utility` 降序、symbol 升序取最多 5 个；没有通过项时空仓。没有额外 confirmation 最低门槛。

### 6.3 仓位与重叠 sleeve

冻结 gross cap 为 `0.375`，持有 48h、每 4h 开一批，因此每个决策批次：

```text
decision_sleeve_exposure = 0.375 * 4 / 48 = 0.03125
leg_exposure = 0.03125 / 当批入选腿数
maximum_overlapping_sleeves = 12
maximum_scheduled_open_gross = 0.375
```

每个 sleeve 在入场时按当时账户权益确定名义本金，48h 后独立结算；同一 symbol 在不同决策时点可形成重叠的独立腿。基础版本不得加 3 倍杠杆。策略没有 bracket、gap-open 替代、trailing 或 timeout 之外的退出：唯一退出就是固定 48h 的 open。

### 6.4 端到端伪代码

```python
for k0 in every_closed_1h_bar:
    update_raw_data_without_filling_missing_prices()
    panel = build_features_using_only_data_at_or_before(k0)
    universe = panel[(universe_main) & (hour(k0) % 4 == 0)]

    p_ret = mean(predict(short_return_model_seed, stable_full) for seed in seeds)
    p_mae = mean(predict(short_mae_q80_seed, stable_full) for seed in seeds)
    p_evt = mean(predict_proba(short_squeeze_seed, stable_full) for seed in seeds)
    p_win = mean(predict_proba(short_win_seed, compact) for seed in seeds)

    return_z = rz(p_ret) + 0.25 * rz(p_win)
    raw_u = return_z - rz(p_mae) - 0.50 * rz(p_evt)
    utility = rz(raw_u)
    chosen = sort(utility >= 1.75, key=(-utility, symbol))[:5]

    if chosen is empty:
        record_flat_decision(k0)
    else:
        sleeve = 0.03125 * current_equity
        for symbol in chosen:
            short(symbol, notional=sleeve/len(chosen), at=open[k0+1h])
            close_short(symbol, at=open[k0+49h])
```

## 七、受控基线

LightGBM 必须在同一 OOS 信号窗、成本、tail 风险模型、确认模型、utility 校准、持有期和仓位口径下超过两条基线。

### 7.1 Ridge compact

用同一 `1,239,909` 行和 compact 86 特征训练：`SimpleImputer(strategy=median) -> StandardScaler() -> Ridge(alpha=10, solver=lsqr)`，目标为 `short_net_48h`。仅把 R4 的 `return_score` 替换为 Ridge 预测，其余 `mae_z/event_z/confirm_z` 仍用冻结 LightGBM；utility 阈值改为 `0.82`，最多 5 腿、每批 3.125%。

### 7.2 carry-momentum 规则

```text
rule_return_score = -(
    0.50*cs_rank_ret_24
  + 0.30*cs_rank_ret_168
  + 0.20*cs_rank_ema_spread_24_96
  - 0.20*cs_rank_funding_rate
)
```

仅把 R4 的 `return_score` 替换为该值，其余风险/确认模型相同；utility 阈值为 `1.16`，最多 5 腿、每批 3.125%。不同阈值只用于在 `2026-07-01..2026-07-18` 无标签 freeze gap 匹配 R4 的信号密度，校准过程不得读取收益。

## 八、prospective OOS 盲测协议

信号窗严格为 `2026-07-19 00:00 <= K0 ts < 2026-10-19 00:00 UTC`，共 552 个 4h 计划节点；最后合法 K0 为 `2026-10-18 20:00 UTC`，入场 `21:00`，退出 `2026-10-20 21:00 UTC`。揭盲时间不得早于 `2026-10-20 21:05 UTC`。

每个节点必须在 K1 open 后 25 分钟内固化 signal-only 快照和 SHA 链；逾期记 `MISSED`，不得回填。节点只能包含模型分数、阈值结果、入选腿、计划入场/退出和仓位，不得包含入场后的价格、funding、收益或表现统计。已知首节点 `2026-07-19 00:00 UTC` 因启动同步逾期，必须保持 `MISSED`；`04:00 UTC` 节点已按时冻结。

揭盲时一次性验证 552 节点链、快照 SHA、主冻结 SHA，然后才允许加载每条腿的 entry/exit open 与 `(entry,exit]` funding。报告 R4、Ridge 和规则基线的完整结果，不得只报告最优者。

## 九、绩效计算与最终硬门槛

### 9.1 组合计算

每个有效决策的 `portfolio_return` 是当批各腿 `short_net` 的等权平均；空仓为 0。每批 PnL 为入场时权益乘 `0.03125*portfolio_return`，在该批 48h 退出时计入权益。最大回撤在每个 sleeve 退出事件后的权益曲线上计算。

决策胜率只统计 active decisions，定义为 `portfolio_return>0`。PF 为 active decision 正收益之和除以负收益绝对值之和。Sharpe 使用退出事件收益，年化因子 `sqrt(24*365.25/4)`。三个月收益为最终权益减 1；年化按首个 K0 到最后腿退出的实际年数复利折算。

固定三个月段为 `[2026-07-19,2026-08-19)`、`[2026-08-19,2026-09-19)`、`[2026-09-19,2026-10-19)`。币种和月份集中度的分母均为全部正 PnL，分子取最大单币或单月正 PnL。

### 9.2 必须全部通过

- 三个月累计收益 `>=18.92%` 且折算年化 `>=100%`；
- 最大回撤 `<=20%`；active decision 胜率 `>=55%`；Sharpe `>=1.5`；PF `>=1.30`；
- active decisions `>=45`，完成腿 `>=300`；
- 固定三个自然段中至少 2 段盈利；
- 1.5 倍成本下总收益为正且最大回撤 `<=25%`；
- 最大单一币种正利润贡献 `<=25%`；最大单月正利润贡献 `<=35%`；
- 历史 7 个 outer folds 中多数盈利；
- 历史因子组与 tail IC 方向稳定；
- R4 OOS 累计收益严格高于 Ridge compact 与 carry-momentum 规则基线。

任何一项失败均不得通过其它指标补偿，也不得通过杠杆放大达标。

## 十、复现验收锚点

### 10.1 历史 OOF 组合

四 seed OOF 集成应得到：累计 `+354.6416%`，年化 `59.3020%`，最大回撤 `17.7740%`，决策胜率 `53.6699%`，Sharpe `4.4909`，PF `1.5458`，active decisions `4,496`，腿 `10,199`，`7/7` folds 盈利；1.5 倍成本累计 `+273.7635%`，最大回撤 `19.7020%`。历史胜率低于最终 55% 是已披露风险，不能改阈值掩盖。

### 10.2 历史腿锚点

以下时间均为 K0 UTC，entry=K0+1h，exit=K0+49h；net 已含 0.28% 双边成本和 funding：

| K0 | symbol | entry open | exit open | funding sum | short net | utility |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2023-01-01 00:00 | BCH/USDT:USDT | 96.31 | 99.43 | -0.00201132 | -0.03720671 | 1.8102608 |
| 2023-01-01 00:00 | MATIC/USDT:USDT | 0.7502 | 0.7827 | -0.00012889 | -0.04625067 | 1.8200041 |
| 2026-03-30 20:00 | Q/USDT:USDT | 0.009458 | 0.008507 | 0.00116846 | 0.09891826 | 2.3879986 |
| 2026-03-31 04:00 | PTB/USDT:USDT | 0.001071 | 0.000720 | 0.00325122 | 0.32818231 | 1.9435694 |
| 2026-03-31 12:00 | NOM/USDT:USDT | 0.003068 | 0.009367 | -0.01125213 | -2.06718120 | 1.8937329 |

NOM 锚点故意保留了低于 `-100%` 的空头损失，用于发现错误裁剪或误用 `entry/exit-1` 的实现。

### 10.3 无标签 freeze-gap 锚点

`2026-07-01 00:00..2026-07-18 12:00 UTC` 应有 106 个计划决策，R4 active 63 个、选中 95 腿；该锚点只校验信号密度，不得读取对应收益。Ridge 和规则基线在同一无标签窗分别为 97 和 92 腿。

### 10.4 历史因子稳定性

置乱消融（不是重训消融）参考结果：short-return seed42 的平均横截面 IC `0.082296` 且 `7/7` folds 为正；short-MAE 的 28 个 fold-seed IC 全正，均值 `0.37870`、最小 `0.31939`；squeeze 的 28 个 fold-seed IC 全正，均值 `0.30497`、最小 `0.24056`。funding、lifecycle、trend、volatility-tail 四组至少在 `5/7` folds 有正 IC drop；volatility-tail 占全部正 IC drop 的约 `87.62%`，这是集中依赖风险，不是事后新增的 OOS 硬门槛。

## 十一、no-repo 自检清单

交付复现结果前，逐项确认：

1. 不需要任何未在本文定义的变量、文件或阈值；
2. symbol 历史集合来自 PIT 归档，不是当前币表回填；
3. K0 特征、K1 open 入场、K49 open 退出无偏移一小时；
4. funding 区间为 `(entry,exit]`；
5. short 公式为 `1-X/E-cost+funding`，且不裁剪；
6. 235/86 特征顺序、缺失值和横截面 rank 语义一致；
7. outer/inner purge 均为 48h，未随机切分；
8. 四 seed 预测是等权平均，utility 又做一次横截面 robust z；
9. 每批 exposure 是 3.125%，不是整账户 37.5%；
10. OOS 在 `2026-10-20 21:05 UTC` 前没有读取任何 outcome；
11. 最终同时报告 R4、Ridge、规则基线和全部失败门槛。

## 附录：仓库内校验（非复现依赖）

本附录只方便本仓库维护者定位证据；外部复现不得依赖这些路径。

- 主冻结：[`../artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json`](../artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json)
- 模型冻结：[`../artifacts/freeze/bin-1h-mhcsml-v1-model-freeze-r4.json`](../artifacts/freeze/bin-1h-mhcsml-v1-model-freeze-r4.json)
- 受控基线：[`../artifacts/freeze/bin-1h-mhcsml-v1-baseline-freeze-r4.json`](../artifacts/freeze/bin-1h-mhcsml-v1-baseline-freeze-r4.json)
- 数据质量：[`../diagnostics/binance-1h-mhcsml-data-quality-2026-07-18.md`](../diagnostics/binance-1h-mhcsml-data-quality-2026-07-18.md)
- 历史 OOF：[`../diagnostics/binance-1h-mhcsml-oof-model-allocator-2026-07-18.md`](../diagnostics/binance-1h-mhcsml-oof-model-allocator-2026-07-18.md)
- 因子消融：[`../ablations/binance-1h-mhcsml-factor-group-ablation-2026-07-19.md`](../ablations/binance-1h-mhcsml-factor-group-ablation-2026-07-19.md)
- 核心账本：[`../binance-1h-mhcsml-core-ledger.md`](../binance-1h-mhcsml-core-ledger.md)
