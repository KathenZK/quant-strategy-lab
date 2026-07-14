# HYPE-15M-Multi-Horizon-EMA-Forecast 多周期 EMA Forecast 基线回测（2026-07-14）

- Family：`HYPE-15M-Multi-Horizon-EMA-Forecast`（`HYPE-15M-MHEF`）
- 状态：`explore / not promoted / not live-ready`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，`15m`
- 数据区间：`2025-05-30T10:30:00+00:00` → `2026-07-14T03:00:00+00:00`；回测从首个完整 forecast 后的 `2025-06-04T18:30:00+00:00` 开始
- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`；纳入实际 Binance funding
- 切片用途：仅作事后审计，不用于参数选择

## 结论

`HYPE-15M-Multi-Horizon-EMA-Forecast` 在本次未调参基线上未形成可用 alpha。精确调仓净收益为 `-87.97%`，固定 `0.10` 缓冲后为 `-80.21%`，同期 1x 永续买入持有为 `56.71%`。缓冲降低了换手，但组合毛收益仍为 `-41.87%`，因此问题不只是手续费：这组 EMA 参数在该周期上的方向预测本身也没有足够优势。

当前结果不应登记版本，也不应进入 promotion gate。若继续研究，优先检查更低频调仓、forecast 持有/滞后结构或更长 EMA 参数，而不是在本基线上加杠杆。

## 策略定义

- 四条 EMA：`8/32`、`16/64`、`32/128`、`64/256`；权重依次为 `0.2/0.3/0.3/0.2`。
- EMA：`close.ewm(span=N, adjust=False, min_periods=N).mean()`。
- 每条 raw forecast：`(EMA_fast / EMA_slow - 1) / EWMAStd(log_return, span=64)`。
- 因果校准：用该 raw forecast 过去 `4 × slow` 根的绝对值滚动中位数（至少 `slow` 个有效值，并 `shift(1)`）把历史中位绝对 forecast 对齐到 `0.5`，再裁剪到 `[-1, 1]`。
- 最终 forecast：四条 forecast 加权求和并裁剪到 `[-1,1]`；目标仓位直接等于 forecast，最大绝对仓位 `1x`。
- 当前闭合 K 收盘计算 forecast，下一根 K 开盘调整仓位；按 `abs(target - current)` 收取换手成本。
- `ensemble_buffer_0.10` 只有当目标仓位与当前仓位相差至少 `0.10` 才调仓；其余逻辑不变。
- 无固定止盈、止损、timeout 或额外过滤；样本末按最后一根开盘 mark，不强制平仓。

## 全区间结果

| 运行 | 毛收益 | 净收益 | 最大回撤 | Sharpe | 平均绝对仓位 | 总换手 | 成本/初始权益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ensemble_buffer_0.00` | -47.18% | -87.97% | -88.69% | -3.08 | 0.463 | 1053.3 | 50.79% |
| `ensemble_buffer_0.10` | -41.87% | -80.21% | -81.98% | -2.33 | 0.459 | 766.5 | 43.55% |
| `sleeve_8_32` | -81.40% | -99.43% | -99.46% | -6.61 | 0.527 | 2485.5 | 52.80% |
| `sleeve_16_64` | -64.52% | -93.88% | -94.31% | -3.55 | 0.523 | 1251.5 | 45.23% |
| `sleeve_32_128` | -12.88% | -65.07% | -70.51% | -1.19 | 0.529 | 649.7 | 49.83% |
| `sleeve_64_256` | -0.52% | -42.71% | -55.46% | -0.48 | 0.532 | 390.5 | 39.52% |
| `perpetual_buy_hold_1x` | 72.83% | 56.71% | -66.63% | 0.91 | 1.000 | 1.0 | 0.14% |

## 最近区间

| 窗口 | 精确调仓收益 | 精确调仓回撤 | 0.10 缓冲收益 | 0.10 缓冲回撤 | 缓冲换手 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | 3.66% | -1.31% | 3.58% | -1.30% | 0.9 |
| `7d` | -4.04% | -7.57% | -2.61% | -6.55% | 13.5 |
| `1m` | -15.88% | -30.73% | -12.70% | -27.71% | 57.1 |
| `3m` | -12.97% | -30.73% | -3.26% | -27.71% | 156.5 |
| `6m` | -33.24% | -55.52% | -16.56% | -46.44% | 316.9 |
| `1y` | -85.06% | -85.69% | -76.16% | -77.72% | 688.7 |

## 数据质量与执行审计

- 标准数据湖 normalized rows：`39331`，expected `39331`，missing `0`，blocker `0`。
- Raw/normalized unmatched：`0`；字段 mismatch：`0`。
- Funding：`2457` 条，`2025-05-30T12:00:00.006000+00:00` → `2026-07-14T00:00:00+00:00`，最大间隔 `8.0h`，blocker `0`。
- 正 funding 由多头支付、空头收取；`(previous open, current open]` 的 funding 在当前开盘调仓前按上一持仓结算。
- 连续目标仓位会产生频繁小额订单；本回测未模拟最小名义、数量步长和拒单，因此即使收益转正也仍非 live-ready。

## 证据

- Summary：[../artifacts/hype-15m-mhef-baseline-2026-07-14-summary.json](../artifacts/hype-15m-mhef-baseline-2026-07-14-summary.json)
- Forecast path：[../artifacts/hype-15m-mhef-baseline-2026-07-14-forecasts.csv](../artifacts/hype-15m-mhef-baseline-2026-07-14-forecasts.csv)
- Equity / turnover paths：[../artifacts/hype-15m-mhef-baseline-2026-07-14-paths.csv](../artifacts/hype-15m-mhef-baseline-2026-07-14-paths.csv)
- 共享内核：[../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py](../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py)，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`

## 后续状态

`explore / not promoted / not live-ready`。本轮只回答“这组多周期 EMA forecast 在 HYPE 上表现如何”，不构成版本登记、live spec 或 runner handoff。
