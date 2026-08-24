# BTC-1D-MA7-RSI6-LGBM P0 数据与特征合同

## 1. 研究身份

- Family：`BTC-1D-MA7-RSI6-LightGBM-Trend`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：完整 UTC `1d`
- 当前阶段：P0 数据和首批特征冻结；`explore / diagnostic-only / not promoted / not live-ready`
- 决策时序：第 `t` 根日 K 闭合后计算特征，任何交易最早在第 `t+1` 根日 K 开盘成交。

## 2. 数据冻结

- 来源：Binance FAPI `/fapi/v1/klines`
- source id：`binance_futures_kline_api_direct`
- 接受范围：`2019-09-09 00:00:00` 至 `2026-08-06 00:00:00 UTC`
- 接受行数：`2,524`
- development：`2019-09-09` 至 `2025-08-06 UTC`，`2,159` 根
- 冻结 validation：`2025-08-07` 至 `2026-08-06 UTC`，`365` 根
- validation 禁止用于特征选择、标签选择、模型容量、超参数、概率阈值、退出规则或失败后的二次调整。
- 数据质量、来源、分区和 hash 见[数据质量证据](../artifacts/btcusdt_perp_1d_data_quality_2026-08-07.json)。

## 3. MA7 严格跨越特征

定义：

```text
SMA7_t = mean(close[t-6:t])

cross_up_t =
  1, if close[t-1] < SMA7[t-1] and close[t] > SMA7[t]
  0, otherwise

cross_down_t =
  1, if close[t-1] > SMA7[t-1] and close[t] < SMA7[t]
  0, otherwise
```

- 等于 `SMA7` 时不算上穿或下穿，不做隐式方向归类。
- `cross_up`、`cross_down` 是两个互斥离散特征；它们不是未经模型过滤就必须开仓的规则。
- 同时保留连续信息：前收与当收距离各自 `SMA7` 的 ATR 归一化值，以及穿越幅度。这样模型既能识别“是否穿越”，也能区分轻微穿越和强穿越。
- 只允许使用当时已闭合的 `close` 和相应 `SMA7`，不存在用第 `t+1` 根数据确认第 `t` 根穿越的做法。

## 4. RSI6 阶段特征

主特征使用 Wilder `RSI(6)`，不以简单 rolling RSI 或库默认值静默替换：

```text
delta_t = close_t - close[t-1]
gain_t = max(delta_t, 0)
loss_t = max(-delta_t, 0)

初始 avg_gain / avg_loss = 前 6 个 delta 的算术平均
后续 avg_t = (avg[t-1] * 5 + current_t) / 6
RSI6_t = 100 - 100 / (1 + avg_gain_t / avg_loss_t)
```

- `avg_loss = 0` 且 `avg_gain > 0` 时取 `100`；二者同时为 `0` 时取 `50`。
- 首批 RSI 特征为 `rsi6` 与 `rsi6_delta_1`。LightGBM 直接学习阈值，不预先把 `20/30/70/80` 指定为真理。
- RSI6 只能作为阶段状态输入，不能因为开发期某个阈值漂亮就事后改写为确定性底部或顶部。

## 5. 必须消融

开发期至少比较：

1. MA7 连续几何特征，不含跨越事件和 RSI6；
2. MA7 几何 + 严格跨越事件；
3. RSI6-only；
4. MA7 几何 + 严格跨越事件 + RSI6；
5. 第 4 组再加入日 K 实体、影线和收盘位置。

只有第 4 或第 5 组在多个 development walk-forward fold 中稳定优于 MA7-only，才能声称 RSI6 或 K 线形态提供增量信息。

## 6. 尚未冻结的 P1 项目

- 预测输出是 `long/short/flat` 分类、收益回归还是 MA7 事件 meta-label；
- 主预测 horizon 和标签阈值；
- LightGBM 深度、叶子数、最小叶样本和概率校准方式；
- 开仓概率阈值、持仓期限、MA7 退出或反手状态机；
- funding 对齐、完整成本后回测和交易路径。

上述项目必须在读取冻结 validation 前写入新的 P1 合同。P0 不产生策略收益或可推广结论。
