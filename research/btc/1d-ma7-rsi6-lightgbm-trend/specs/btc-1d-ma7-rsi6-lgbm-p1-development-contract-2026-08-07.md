# BTC-1D-MA7-RSI6-LGBM P1 Development 合同

## 1. 身份、范围与禁止事项

- Family：`BTC-1D-MA7-RSI6-LightGBM-Trend`
- 阶段：P1 `development-only` 事件质量研究；`explore / diagnostic-only / not promoted / not live-ready`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual，完整 UTC `1d`
- 本合同于任何 P1 模型训练、阈值选择和回测前冻结。
- P1 只允许读取 `2019-09-09` 至 `2025-08-06 UTC` 的 development 数据。
- 日线负责信号和 RSI/MA7 收盘退出；Binance 官方 `1h` K 线只用于解析固定 stop 的首次触及时段、gap fill、MFE 和 MAE，不生成额外入场信号。
- 冻结 validation `2025-08-07` 至 `2026-08-06 UTC` 不得用于计算特征分布、标签、模型、阈值、退出参数、图表或本轮结论。
- P1 不登记版本；通过 development 门禁只取得一次性揭示 validation 的资格，不构成 promotion。

## 2. MA7 候选事件与模型输出

```text
SMA7_t = mean(close[t-6:t])

cross_up_t =
  close[t-1] < SMA7[t-1] and close[t] > SMA7[t]

cross_down_t =
  close[t-1] > SMA7[t-1] and close[t] < SMA7[t]
```

- 等于 `SMA7` 不算穿越。
- `cross_up` 产生 long 候选，`cross_down` 产生 short 候选；方向不是模型预测结果。
- LightGBM 输出 `P(take)`：该候选按本合同完整执行后成本后净收益为正的概率。
- 多空使用一个合并模型，`side=+1/-1` 是输入特征；所有结果必须同时报告 combined、long-only 和 short-only。

## 3. 指标公式

### 3.1 ATR7

```text
TR_t = max(
  high_t - low_t,
  abs(high_t - close[t-1]),
  abs(low_t - close[t-1])
)
ATR7_t = mean(TR[t-6:t])
```

- `ATR7` 是简单七期均值，`min_periods=7`，不使用未来 K 线。

### 3.2 Wilder RSI6

沿用 [P0 合同](btc-1d-ma7-rsi6-lgbm-p0-data-feature-contract-2026-08-07.md)：

- 首个平均涨幅/跌幅使用前 `6` 个 close delta 的算术平均；
- 后续使用 `(prior_average * 5 + current_value) / 6`；
- `avg_loss=0, avg_gain>0` 时 RSI 为 `100`，二者都为 `0` 时为 `50`。

## 4. 冻结特征

所有特征只读取事件日 `t` 及以前的闭合 K 线。

### 4.1 MA7 几何组 `MA`

1. `side`
2. `prev_close_ma_gap_atr = (close[t-1] - SMA7[t-1]) / ATR7[t]`
3. `close_ma_gap_atr = (close[t] - SMA7[t]) / ATR7[t]`
4. `cross_span_atr = side * (close_ma_gap_atr - prev_close_ma_gap_atr)`
5. `ma7_slope_1_atr = (SMA7[t] - SMA7[t-1]) / ATR7[t]`
6. `ma7_slope_3_atr = (SMA7[t] - SMA7[t-3]) / ATR7[t]`
7. `prior_side_duration`：穿越前连续位于旧侧的严格收盘根数

### 4.2 当前 K 线与五日路径组 `K`

8. `body_atr = (close[t] - open[t]) / ATR7[t]`
9. `range_atr = (high[t] - low[t]) / ATR7[t]`
10. `upper_wick_atr = (high[t] - max(open[t], close[t])) / ATR7[t]`
11. `lower_wick_atr = (min(open[t], close[t]) - low[t]) / ATR7[t]`
12. `close_location = (close[t] - low[t]) / (high[t] - low[t])`；零振幅时取 `0.5`
13. `return_3_atr = (close[t] - close[t-3]) / ATR7[t]`
14. `return_5_atr = (close[t] - close[t-5]) / ATR7[t]`

### 4.3 RSI 阶段组 `RSI`

15. `rsi6`
16. `rsi6_delta_1`
17. `rsi6_min_5`
18. `rsi6_max_5`
19. `rsi6_low20_last5`：最近五根是否出现 `RSI6 <= 20`
20. `rsi6_high80_last5`：最近五根是否出现 `RSI6 >= 80`

### 4.4 成交量消融组 `VOL`

21. `quote_volume_ratio_7 = quote_volume[t] / median(quote_volume[t-6:t])`
22. `trade_count_ratio_7 = trade_count[t] / median(trade_count[t-6:t])`

- `VOL` 不进入 P1 主模型，只用于 `MA+K+RSI+VOL` 独立消融。
- 分母为零或非有限时该事件不进入对应模型。

## 5. 入场、仓位与成本

- 事件日收盘确认，最早在 `t+1` UTC 日开盘成交。
- 固定目标仓位 `1×` 当前权益，单仓、不加仓、无概率缩放。
- long entry fill：`open[t+1] * (1 + 4 bps)`。
- short entry fill：`open[t+1] * (1 - 4 bps)`。
- 每次成交手续费为 filled notional 的 `0.001`。
- 实际 funding rate 来自 Binance USD-M funding history；持仓数量为入场时 `1×` 权益除以 entry fill。
- funding endpoint 的 `markPrice` 非空时直接使用；历史空值只允许用 Binance 官方 `markPriceKlines 8h` 在同一名义 funding bucket 的 open 补齐，并记录 `mark_price_source`。funding settlement timestamp 相对 `00/08/16 UTC` 网格的实测滞后必须在 `[0, 1]` 秒内，之后才可 floor 到名义 `8h` bucket；不存在对应官方 mark 时，涉及该 funding 事件的候选不得进入 P1。
- funding cash return：`-side * funding_rate * mark_price / entry_fill`。
- 只结算严格满足 `entry_ts < funding_ts < exit_ts` 的 funding 事件；与开平仓同 timestamp 的 funding 不计入主口径，作为后续边界压力项。

## 6. 三类退出及优先级

### 6.1 固定灾难止损

- long stop：`entry_fill - 3 * ATR7[signal_t]`
- short stop：`entry_fill + 3 * ATR7[signal_t]`
- 止损从入场成交后立即生效，不跟踪、不更新。
- 使用完整 Binance `1h` 路径寻找首次 stop touch；小时 open 已越过 stop 时按该小时 open 再施加 `4 bps` 不利滑点，否则按 stop 再施加不利滑点。
- stop 的研究侧 exit timestamp 取首次触发小时的 open timestamp；严格 funding 边界因此不计与该小时 open 同 timestamp 的 funding，另保留单事件 funding 边界压力项。
- 只有止损，没有日内止盈，因此小时 high/low 不存在双 barrier 先后顺序歧义；不得退回日 K 猜测 stop 首次触发时段。

### 6.2 RSI6 极值后反向确认

- long：持仓状态曾观察到闭合日 `RSI6 >= 80` 后，首次闭合日 `RSI6 < 80`，下一日开盘退出。
- short：持仓状态曾观察到闭合日 `RSI6 <= 20` 后，首次闭合日 `RSI6 > 20`，下一日开盘退出。
- 事件信号日的 RSI 极值状态由新仓继承；触及极值只武装退出，不立即退出。

### 6.3 反向 MA7 穿越

- long 遇 `cross_down`、short 遇 `cross_up` 后，下一日开盘退出。
- 同一闭合日若 RSI 和反向 MA7 同时触发，只有一个次日开盘退出。
- 日内止损优先于当日收盘后才能确认的 RSI/MA7 退出。
- RSI 或止损退出后保持空仓，必须等待下一次新严格 MA7 穿越。
- 若反向 MA7 候选通过模型阈值，同一开盘先平旧仓并直接建立反向仓；平仓和开仓分别计费、计滑点。
- 不使用止盈、trailing stop、模型概率日常退出、同方向重入或最长持仓。

## 7. 标签

- 每个候选事件按第 5–6 节独立模拟至实际退出。
- 若事件在 development 结束前没有完整退出，丢弃该事件，不读取 validation 完成标签。
- `label=1`：手续费、滑点与 funding 后净收益严格 `> 0`。
- `label=0`：成本后净收益 `<= 0`。
- 同时记录净收益、ATR 收益倍数、MFE、MAE、持仓日数与退出原因；分类准确率不是策略通过条件。

## 8. 模型与消融

### 8.1 Logistic baseline

- `StandardScaler + LogisticRegression`
- `L2`、`C=1.0`、`lbfgs`、`max_iter=2000`、无 class weight
- 使用 `MA+K+RSI`，作为线性可解释模型对照。

### 8.2 LightGBM 固定容量

```text
objective=binary
n_estimators=120
learning_rate=0.03
num_leaves=7
max_depth=3
min_child_samples=20
subsample=0.8
subsample_freq=1
colsample_bytree=0.8
reg_alpha=0.5
reg_lambda=2.0
random_state=20260807
n_jobs=1
deterministic=true
force_col_wise=true
```

- 不搜索模型容量、不使用 class weight、不使用 validation early stopping。
- 主模型：`MA+K+RSI`。
- 必须消融：`MA-only`、`RSI-only`、`MA+K`、`MA+K+RSI`、`MA+K+RSI+VOL`。

## 9. Nested walk-forward 与阈值

- eligible development events 按信号时间排序。
- 外层：最早 `40%` 作为初始训练，其余 `60%` 顺序切为四个等事件数测试块；每折只使用更早事件训练。
- 每个外层训练集内：最早 `50%` 作为初始训练，其余顺序切为三个 inner 测试块。
- 任何训练事件若其退出时间不早于测试块首个信号时间，必须 purge。
- 候选阈值固定为 `0.50 / 0.55 / 0.60 / 0.65`。
- inner 选择目标：先最大化三个 inner fold 中最差净收益；并列时选择更低阈值，再按更多交易数。
- 外层 OOS 门禁使用每折仅由该折过去数据选择的阈值。
- P1 结束后在完整 development 上重复 inner 流程，冻结未来 validation 使用的单一阈值和完整 development 拟合模型。

## 10. Development 门禁与路线选择

主路线 `MA+K+RSI` 必须同时满足：

1. 外层 OOS 关闭交易数 `>= 30`；
2. 手续费、滑点、funding 后净收益 `> 0`；
3. Profit Factor `>= 1.20`；
4. 日频 mark-to-market MDD 不差于相同方向范围的 all-cross 基线；
5. 四个外层 fold 中至少三个净收益优于对应 all-cross 基线。

路线优先级：

- combined 通过则冻结 combined，不因单边历史更漂亮改选单边。
- combined 未通过时，允许 long-only 或 short-only 按相同门禁独立取得候选资格；失效侧必须在揭示 validation 前禁用。
- 两个单边都通过而 combined 未通过时，选择最差 fold 净收益更高的一侧；并列时选择交易数更多的一侧。
- 所有路线未通过则 P1 失败，不揭示最近一年。

## 11. Validation 预注册门禁

本节只预注册，不授权 P1 脚本读取 validation。未来获准揭示时，冻结路线必须同时满足：

1. 关闭交易数 `>= 10`；
2. 成本后净收益 `> 0`；
3. Profit Factor `>= 1.10`；
4. 收益高于同期同方向 all-cross 基线；
5. MDD 不差于同期同方向 all-cross 基线。

任何一项失败即 validation failed；不得根据该年结果重选特征、模型、方向或阈值。

## 12. 必须交付的解释与证据

- 各模型/消融的外层 OOS 分类指标、概率分布和交易指标；
- combined、long、short 分腿与 all-cross 基线；
- LightGBM `pred_contrib` SHAP 汇总、跨 fold 特征方向稳定性和关键阈值关系；
- 典型成功/失败事件及其 MA7、五日 K 线、RSI6 状态；
- 尝试提炼可读简化规则，但简化规则只作诊断，不自动替换模型；
- 若形成 coherent development candidate，生成完整 self-contained 交易路径 HTML；否则只保留失败诊断和机器证据。
