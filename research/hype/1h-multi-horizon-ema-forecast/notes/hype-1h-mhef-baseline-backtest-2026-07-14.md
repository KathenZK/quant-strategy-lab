# HYPE-1H-Multi-Horizon-EMA-Forecast 多周期 EMA Forecast 基线回测（2026-07-14）

- Family：`HYPE-1H-Multi-Horizon-EMA-Forecast`（`HYPE-1H-MHEF`）
- 状态：`explore / not promoted / not live-ready`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，`1h`
- 数据区间：`2025-05-30T10:00:00+00:00` → `2026-07-14T02:00:00+00:00`；回测从首个完整 forecast 后的 `2025-06-20T18:00:00+00:00` 开始
- 成本：每单位换手手续费 `0.001` + adverse slippage `0.0004`；纳入实际 Binance funding
- 切片用途：仅作事后审计，不用于参数选择

## 结论

`HYPE-1H-Multi-Horizon-EMA-Forecast` 在本次未调参基线上未形成可用 alpha。精确调仓净收益为 `-35.70%`，固定 `0.10` 缓冲后为 `-23.39%`，同期 1x 永续买入持有为 `68.59%`。缓冲降低了换手，但组合毛收益仍为 `-1.22%`，因此问题不只是手续费：这组 EMA 参数在该周期上的方向预测本身也没有足够优势。

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
| `ensemble_buffer_0.00` | -9.07% | -35.70% | -48.37% | -0.46 | 0.458 | 246.5 | 25.75% |
| `ensemble_buffer_0.10` | -1.22% | -23.39% | -40.40% | -0.17 | 0.453 | 180.7 | 20.74% |
| `sleeve_8_32` | -2.24% | -55.76% | -63.18% | -0.90 | 0.527 | 564.8 | 47.03% |
| `sleeve_16_64` | 6.97% | -29.39% | -44.27% | -0.20 | 0.531 | 295.3 | 32.41% |
| `sleeve_32_128` | -15.67% | -32.76% | -50.71% | -0.26 | 0.528 | 161.4 | 17.70% |
| `sleeve_64_256` | -41.86% | -49.36% | -58.38% | -0.66 | 0.519 | 97.9 | 9.20% |
| `perpetual_buy_hold_1x` | 83.97% | 68.59% | -66.49% | 0.99 | 1.000 | 1.0 | 0.14% |

## 最近区间

| 窗口 | 精确调仓收益 | 精确调仓回撤 | 0.10 缓冲收益 | 0.10 缓冲回撤 | 缓冲换手 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | 2.88% | -0.92% | 2.87% | -0.91% | 0.9 |
| `7d` | -2.10% | -5.61% | -1.58% | -5.19% | 4.1 |
| `1m` | -1.46% | -18.15% | 0.60% | -16.07% | 14.6 |
| `3m` | 2.12% | -18.15% | 3.49% | -16.41% | 40.1 |
| `6m` | -2.05% | -38.11% | 2.60% | -34.40% | 82.7 |
| `1y` | -37.15% | -47.80% | -25.84% | -40.40% | 169.7 |

## 数据质量与执行审计

- 标准数据湖 normalized rows：`9833`，expected `9833`，missing `0`，blocker `0`。
- Raw/normalized unmatched：`0`；字段 mismatch：`0`。
- Funding：`2457` 条，`2025-05-30T12:00:00.006000+00:00` → `2026-07-14T00:00:00+00:00`，最大间隔 `8.0h`，blocker `0`。
- 正 funding 由多头支付、空头收取；`(previous open, current open]` 的 funding 在当前开盘调仓前按上一持仓结算。
- 连续目标仓位会产生频繁小额订单；本回测未模拟最小名义、数量步长和拒单，因此即使收益转正也仍非 live-ready。

## 证据

- Summary：[../artifacts/hype-1h-mhef-baseline-2026-07-14-summary.json](../artifacts/hype-1h-mhef-baseline-2026-07-14-summary.json)
- Forecast path：[../artifacts/hype-1h-mhef-baseline-2026-07-14-forecasts.csv](../artifacts/hype-1h-mhef-baseline-2026-07-14-forecasts.csv)
- Equity / turnover paths：[../artifacts/hype-1h-mhef-baseline-2026-07-14-paths.csv](../artifacts/hype-1h-mhef-baseline-2026-07-14-paths.csv)
- 共享内核：[../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py](../../../_shared-kernels/multi-horizon-ema-forecast/v1/engine.py)，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`

## 后续状态

`explore / not promoted / not live-ready`。本轮只回答“这组多周期 EMA forecast 在 HYPE 上表现如何”，不构成版本登记、live spec 或 runner handoff。
