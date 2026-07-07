# ETH-1H-Adaptive-Regime-V3 Clean Tuned Spec

## 版本身份

- 完整名称：`ETH-1H-Adaptive-Regime-V3`。
- 家族：`ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）。
- 市场：Binance USD-M Futures `ETHUSDT` perpetual `1h`。
- 状态：`registered diagnostic clean tuned observation / NO-GO / not promoted / not live-ready`。
- 版本来源：V2.1 全参数消融后删除 `2` 个 merged-path inert 字段，在 `27` 参数 clean surface 上做严格改善微调得到的冻结 observation `ETH-1H-AR-V2-1-CLEAN-TUNE-2026-07-07`。

V3 的登记只冻结可复现身份，不代表 candidate、paper-live、dry-run、handoff 或 live。

## 数据、切分与成本

- 原始闭合 K：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，共 `17,520` 根。
- train：`2024-08-17T05:00:00Z` 至 `2025-09-07T07:24:00Z`。
- validation：`2025-09-07T07:24:00Z` 至 `2026-04-03T05:00:00Z`。
- prefit：`2024-08-17T05:00:00Z` 至 `2026-04-03T05:00:00Z`。
- reused holdout：`2026-04-03T05:00:00Z` 至 `2026-07-03T05:00:00Z`；不参与选参。
- fee：`0.001`/fill；slippage：`4 bps`/fill；计入 Binance 历史资金费。
- 数据质量：missing/duplicate/null/OHLCV violation/raw-normalized mismatch/未闭合 K 误收均为 `0`。

## 删参来源

V2.1 全参数消融判定以下字段为 `merged_path_inert_remove`，在 V3 clean surface 中硬编码为 V2.1 冻结值：

- `bb_break.ema_htf = 55`
- `bb_break.max_aligned_funding_bps = 8.0`

其余 `27` 个字段进入 V3 clean tuning surface。

## 冻结 clean 参数

### BB breakout leg（12 参数 + 2 个硬编码字段）

```json
{
  "ema_htf": 55,
  "indicator_window": 72,
  "band_k": 2.5,
  "roc_window": 24,
  "min_adx": 16.0,
  "min_rvol": 3.5,
  "min_atr_bps": 75.0,
  "min_dir_roc_bps": 200.0,
  "max_dist_ema_bps": 750.0,
  "max_aligned_funding_bps": 8.0,
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "max_hold_bars": 72,
  "fixed_leverage": 1.5
}
```

### RSI reversal leg

```json
{
  "ema_htf": 233,
  "indicator_window": 7,
  "threshold_low": 5.0,
  "threshold_high": 75.0,
  "roc_window": 6,
  "min_adx": 20.0,
  "max_adx": 45.0,
  "min_atr_bps": 125.0,
  "min_dir_roc_bps": -300.0,
  "max_dist_ema_bps": 750.0,
  "tp_atr": 2.0,
  "sl_atr": 3.0,
  "max_hold_bars": 48,
  "cooldown_bars": 24,
  "fixed_leverage": 2.5
}
```

## 冻结指标

| Window | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `4.9760x` | `445.34%` | `-12.15%` | `100.00%` | `32` |
| validation | `2.7808x` | `78.99%` | `-8.78%` | `100.00%` | `10` |
| prefit | `4.0591x` | `876.08%` | `-12.15%` | `100.00%` | `42` |
| reused holdout | `0.8706x` | `-3.39%` | `-15.70%` | `50.00%` | `4` |
| current full | `3.3084x` | `842.97%` | `-15.70%` | `95.65%` | `46` |

相对 V2.1，V3 的 prefit 与 current full 均表现为收益更高、胜率更高、回撤更小；但 reused holdout 仍为负，因此不能 promotion。

## 近期分片

| Slice | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `7d` | `11.8725x` | `4.86%` | `-7.57%` | `100.00%` | `1` |
| `1m` | `1.7813x` | `4.86%` | `-7.57%` | `100.00%` | `1` |
| `3m` | `0.8706x` | `-3.39%` | `-15.70%` | `50.00%` | `4` |
| `6m` | `1.4349x` | `19.59%` | `-15.70%` | `75.00%` | `8` |
| `1y` | `2.2425x` | `124.13%` | `-15.70%` | `90.48%` | `21` |

## 稳健性与失败边界

- `K+2` 延迟：prefit `2.7964x / -16.66% / 90.24%`，reused holdout `0.8090x / -15.85% / 25.00%`，current full `2.3716x / -16.66% / 84.44%`。
- `8 bps` slippage：prefit `3.9825x / -12.26% / 100.00%`，reused holdout `0.8581x / -15.90% / 50.00%`，current full `3.2479x / -15.90% / 95.65%`。
- `double_cost`：prefit `3.6167x / -12.76% / 100.00%`，reused holdout `0.8174x / -16.70% / 50.00%`，current full `2.9683x / -16.70% / 95.65%`。
- 最近三个月 reused holdout 仍为负收益，且只有 `4` 笔；该区间不是 fresh OOS。
- 没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 证据

- V2.1 全参数消融：`../ablations/eth-1h-ar-v2-1-full-parameter-ablation-2026-07-07.md`。
- V3 clean 微调报告：`../research-notes/eth-1h-ar-v2-1-clean-tune-2026-07-07.md`。
- 交易明细：`../artifacts/eth_1h_ar_v2_1_clean_tune_trades_2026-07-07.csv`。

## 登记结论

`ETH-1H-Adaptive-Regime-V3` 登记为 clean tuned diagnostic observation。它不是 candidate、paper-live、dry-run、handoff 或 live；下一步必须等待冻结 V3 参数后的新增 forward trades。
