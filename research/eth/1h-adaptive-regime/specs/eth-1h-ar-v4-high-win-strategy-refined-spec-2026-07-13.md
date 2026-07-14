# ETH-1H-Adaptive-Regime-V4 High-Win Strategy Refined Spec

## 版本身份

- 完整名称：`ETH-1H-Adaptive-Regime-V4`。
- 家族：`ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）。
- 市场：Binance USD-M Futures `ETHUSDT` perpetual `1h`。
- 状态：`registered high-win strategy refined observation / NO-GO / not promoted / not live-ready`。
- 版本来源：在 V3 的 `27` 参数 clean surface 上先做高胜率频率搜索，再对通过 K+2/8 bps 的稳健候选做两腿杠杆重配；冻结 observation `ETH-1H-AR-V3-HIGH-WIN-STRATEGY-REFINE-2026-07-13`。

V4 的登记只冻结可复现身份，不代表 candidate、paper-live、dry-run、handoff 或 live。

## 数据、切分与成本

- 原始闭合 K：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，共 `17,520` 根。
- train：`2024-08-17T05:00:00Z` 至 `2025-09-07T07:24:00Z`。
- validation：`2025-09-07T07:24:00Z` 至 `2026-04-03T05:00:00Z`。
- prefit：`2024-08-17T05:00:00Z` 至 `2026-04-03T05:00:00Z`。
- reused holdout：`2026-04-03T05:00:00Z` 至 `2026-07-03T05:00:00Z`；不参与选参。
- fee：`0.001`/fill；slippage：`4 bps`/fill；计入 Binance 历史资金费。
- 数据质量：missing/duplicate/null/OHLCV violation/raw-normalized mismatch/未闭合 K 误收均为 `0`。

## 参数面

- 继承 V3 clean surface：`27` 个可调参数。
- BB 硬编码（V2.1 消融判定 inert）：`ema_htf = 55`，`max_aligned_funding_bps = 8.0`。
- 相对 V3：放宽部分过滤阈值、调整出场与杠杆，目标是“交易数上升、胜率只允许小幅下降、DD 尽量压在 `20%` 内”。

## 冻结 clean 参数

### BB breakout leg（12 参数 + 2 个硬编码字段）

```json
{
  "ema_htf": 55,
  "indicator_window": 72,
  "band_k": 2.5,
  "roc_window": 12,
  "min_adx": 16.0,
  "min_rvol": 3.5,
  "min_atr_bps": 25.0,
  "min_dir_roc_bps": 100.0,
  "max_dist_ema_bps": 10000.0,
  "max_aligned_funding_bps": 8.0,
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "max_hold_bars": 96,
  "fixed_leverage": 1.5
}
```

### RSI reversal leg

```json
{
  "ema_htf": 144,
  "indicator_window": 7,
  "threshold_low": 10.0,
  "threshold_high": 75.0,
  "roc_window": 12,
  "min_adx": 12.0,
  "max_adx": 55.0,
  "min_atr_bps": 125.0,
  "min_dir_roc_bps": -500.0,
  "max_dist_ema_bps": 1500.0,
  "tp_atr": 2.5,
  "sl_atr": 2.5,
  "max_hold_bars": 36,
  "cooldown_bars": 36,
  "fixed_leverage": 2.0
}
```

## 冻结指标

| Window | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `4.9314x` | `440.17%` | `-14.29%` | `88.64%` | `44` |
| validation | `6.7001x` | `195.26%` | `-7.03%` | `95.65%` | `23` |
| prefit | `5.4898x` | `1494.90%` | `-14.29%` | `91.04%` | `67` |
| reused holdout | `1.0601x` | `1.46%` | `-17.08%` | `66.67%` | `12` |
| current full | `4.4124x` | `1518.25%` | `-17.08%` | `87.34%` | `79` |

相对 V3，V4 交易数明显增加（prefit `42 -> 67`，full `46 -> 79`），current-full 胜率从 `95.65%` 回落到 `87.34%`，但仍维持高胜率；reused holdout 只读转正，但不是 fresh OOS。

## 近期分片

| Slice | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `7d` | `11.8725x` | `4.86%` | `-7.57%` | `100.00%` | `1` |
| `1m` | `3.0646x` | `9.63%` | `-7.57%` | `100.00%` | `3` |
| `3m` | `1.0601x` | `1.46%` | `-17.08%` | `66.67%` | `12` |
| `6m` | `2.3890x` | `53.97%` | `-17.08%` | `76.19%` | `21` |
| `1y` | `3.8574x` | `285.38%` | `-17.08%` | `84.44%` | `45` |

## 稳健性与失败边界

- `K+2`：prefit `3.6815x / -17.42% / 84.85% / 66`；reused holdout 只读仍为正。
- `8 bps`：prefit `4.5961x / -14.45% / 88.06% / 67`。
- `K+3`：prefit DD `-23.85%`，reused holdout 只读为负。
- `12 bps`、`fee12_slip8`、`double_cost`：reused holdout 只读略为负。
- reused holdout 已多次揭盲，不能替代 `2026-07-03T05:00:00Z` 之后的 fresh forward。
- 没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 证据

- 高胜率频率搜索：[../notes/eth-1h-ar-v3-high-win-frequency-tune-2026-07-13.md](../notes/eth-1h-ar-v3-high-win-frequency-tune-2026-07-13.md)
- 高胜率全策略风险优化：[../notes/eth-1h-ar-v3-high-win-strategy-refine-2026-07-13.md](../notes/eth-1h-ar-v3-high-win-strategy-refine-2026-07-13.md)
- 复现入口：`../scripts/eth_1h_ar_v4.py`
- 交易明细：`../artifacts/eth_1h_ar_v3_high_win_strategy_refine_trades_2026-07-13.csv`

## 登记结论

`ETH-1H-Adaptive-Regime-V4` 登记为 high-win strategy refined diagnostic observation。它不是 candidate、paper-live、dry-run、handoff 或 live；下一步必须等待冻结 V4 参数后的新增 forward trades。
