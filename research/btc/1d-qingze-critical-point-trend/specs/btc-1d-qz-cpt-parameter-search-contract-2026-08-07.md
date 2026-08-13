# BTC 日线青泽临界点趋势参数搜索合同（2026-08-07）

## 目标与边界

- Family：`BTC-1D-Qingze-Critical-Point-Trend`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 目标：只使用 `2024-07-31` 至 `2026-01-01` 搜索一次参数，再以 `2026-01-02` 至 `2026-07-29` 做锁定验证。
- 本轮不登记版本；验证结果不得用于把其他候选重新选成“正式第一名”。
- 继续沿用无 OI 代理口径：本地 open interest 只有 8 天，不能进入搜索，也不以成交量冒充 OI。

## 固定数据与执行

- 市场：Binance USD-M perpetual `BTCUSDT`
- 周期：可信 `1h` 聚合的完整 UTC `1d`
- 手续费：每 fill `0.001`
- 不利滑点：每 fill `0.0004`
- Funding：实际事件率按日求和，对日末仍持有的名义仓位计提
- 信号、加码、反向趋势退出：闭合日 K 确认，下一 UTC 日开盘成交
- Stop：日内 OHLC gap-aware；每日收盘后的新 trailing level 下一日才生效
- 仓位：初始 `20%`；若启用 pyramiding，则按 `+1 ATR / +2 ATR` 增加 `12% / 8%`

## 数据切分

- Development：`2024-07-31 00:00 UTC` 至 `2026-01-01 00:00 UTC`，520 根日 K。
- Validation：`2026-01-02 00:00 UTC` 至 `2026-07-29 00:00 UTC`，209 根日 K。
- Development 内部折：
  1. `2024-07-31` 至 `2025-01-31`
  2. `2025-02-01` 至 `2025-07-31`
  3. `2025-08-01` 至 `2026-01-01`
- 每个折和 validation 都从空仓开始；边界前一根已闭合 K 的信号可在边界首日开盘执行。

## 搜索空间

| 参数 | 候选值 |
| --- | --- |
| `ma_days` | `40, 55, 60` |
| `confirm_days` | `1, 2, 3` |
| `deviation_min` | `0, 0.5%, 1.0%, 1.5%, 2.0%` |
| `breakout_days` | `10, 15, 20, 30` |
| `impulse_min` | `1.0%, 1.5%, 2.0%, 3.0%` |
| `volume_lookback` | `3, 5, 10` |
| `volume_multiplier` | `1.0, 1.25, 1.5, 1.75` |
| `narrow_days` | `3, 5, 7` |
| `narrow_range_max` | `1.5%, 2.0%, 2.5%, 3.0%` |
| `b_impulse_max` | `1.5%, 2.0%, 3.0%` |
| `signal_mode` | `A, B, AB` |
| `atr_days` | `10, 14, 20` |
| `stop_atr` | `2, 3, 4, 5` |
| `pyramiding` | `false, true` |

## 采样与选择

- 随机种子：`20260807`
- 去重后采样：20,000 个参数组合，并强制加入原始基线
- Development 资格：
  - 完整段至少 6 笔交易；
  - MDD 不差于 `-20%`；
  - 至少两个内部折有交易。
- 排序分数：

```text
min(三折净收益)
+ median(三折净收益)
+ 0.25 × development 全段净收益
- 0.50 × abs(development 全段 MDD)
```

- 先按分数、development 净收益、MDD 排序，冻结 rank 1。
- 只在冻结后打开 validation。Top-20 validation 仅用于检查参数邻域是否同向，不得据此替换 rank 1。

## 解释限制

- 20,000 次搜索面对 520 根 K 和低个位数交易，数据挖掘风险很高；内部三折不能替代真正 OOS。
- 多组参数可能生成完全相同的交易路径；参数表不同不等于独立证据。
- Validation 只有 209 根 K，仍不足以证明长期稳健性。
- 任何 validation 正收益都不能跳过 OI、CPCV/Monte Carlo、压力测试、执行审计与 runner parity。
