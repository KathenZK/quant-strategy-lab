# ETH-1H-Adaptive-Regime-V2.1 High-Win Tuned Spec

## 版本身份

- 完整名称：`ETH-1H-Adaptive-Regime-V2.1`。
- 家族：`ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）。
- 市场：Binance USD-M Futures `ETHUSDT` perpetual `1h`。
- 状态：`registered high-win tuned observation / NO-GO / not promoted / not live-ready`。
- 版本来源：`ETH-1H-Adaptive-Regime-V2` 全参数消融后的 high-win 组合微调观察值；选择只使用 train/validation/prefit，reused holdout 与近期分片只作冻结后审计。

V2.1 的登记只冻结可复现身份，不代表 candidate、paper-live、dry-run、handoff 或 live。

## 数据、切分与成本

- 原始闭合 K：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，共 `17,520` 根。
- train：`2024-08-17T05:00:00Z` 至 `2025-09-07T07:24:00Z`。
- validation：`2025-09-07T07:24:00Z` 至 `2026-04-03T05:00:00Z`。
- prefit：`2024-08-17T05:00:00Z` 至 `2026-04-03T05:00:00Z`。
- reused holdout：`2026-04-03T05:00:00Z` 至 `2026-07-03T05:00:00Z`；不参与选参。
- fee：`0.001`/fill；slippage：`4 bps`/fill；计入 Binance 历史资金费。
- 数据质量：missing/duplicate/null/OHLCV violation/raw-normalized mismatch/未闭合 K 误收均为 `0`。

## 冻结 clean 参数

### BB breakout leg

```json
{
  "ema_htf": 55,
  "indicator_window": 32,
  "band_k": 2.0,
  "roc_window": 12,
  "min_adx": 36.0,
  "min_rvol": 3.0,
  "min_atr_bps": 50.0,
  "min_dir_roc_bps": 100.0,
  "max_dist_ema_bps": 10000.0,
  "max_aligned_funding_bps": 8.0,
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "max_hold_bars": 48,
  "fixed_leverage": 3.0
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
| train | `3.7405x` | `303.31%` | `-14.98%` | `88.00%` | `25` |
| validation | `3.8699x` | `116.03%` | `-8.78%` | `100.00%` | `11` |
| prefit | `3.7853x` | `771.27%` | `-14.98%` | `91.67%` | `36` |
| reused holdout | `0.7048x` | `-8.35%` | `-19.55%` | `50.00%` | `4` |
| current full | `3.0277x` | `698.55%` | `-19.55%` | `87.50%` | `40` |

## 近期分片

| Slice | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `7d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `1m` | `2.1132x` | `6.34%` | `-1.47%` | `100.00%` | `1` |
| `3m` | `0.7048x` | `-8.35%` | `-19.55%` | `50.00%` | `4` |
| `6m` | `1.2291x` | `10.76%` | `-19.55%` | `71.43%` | `7` |
| `1y` | `2.7494x` | `174.75%` | `-19.55%` | `85.71%` | `21` |

## 近期失败解释

- 最近三个月只有 `4` 笔交易，样本极薄，胜率从 prefit 的 `91.67%` 退化到 `50.00%`。
- 最近三个月的 `4` 笔全是 `BB_BREAK` 多头，没有 RSI reversal 和空头分散风险。
- 两笔亏损分别为 `2026-04-11` stop-market `-11.65%` equity 和 `2026-05-23` timeout `-6.26%` equity；两笔盈利为 `+4.07%` 与 `+6.34%` equity。亏损单笔幅度大于盈利，导致三个月总收益为负。
- V2.1 为了达到高胜率目标使用更窄、更少的信号和更高杠杆（BB `fixed_leverage=3.0`），在近期低交易数环境中对少数失败突破非常敏感。
- 延迟和成本压力也暴露脆弱性：K+2 prefit DD `-20.34%`，double-cost full DD `-21.40%`。

## 证据

- V2 全参数消融：`../ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md`。
- V2.1 微调报告：`../notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md`。
- 交易明细：`../artifacts/eth_1h_ar_v2_ablation_guided_tune_trades_2026-07-06.csv`。

## 登记后消融与微调

- V2.1 全参数消融：`../ablations/eth-1h-ar-v2-1-full-parameter-ablation-2026-07-07.md`；`bb_break.ema_htf` 与 `bb_break.max_aligned_funding_bps` 判定为 merged-path inert，clean surface 收敛到 `27` 个可调参数。
- V2.1 clean 微调：`../notes/eth-1h-ar-v2-1-clean-tune-2026-07-07.md`；observation `ETH-1H-AR-V2-1-CLEAN-TUNE-2026-07-07` 后续按用户要求登记为 `ETH-1H-Adaptive-Regime-V3`，其 prefit 为 `4.0591x / -12.15% / 100.00% / 42`、current full `3.3084x / -15.70% / 95.65% / 46`，三项均优于 V2.1，但 reused holdout 仍为负（`0.8706x / -3.39%`），不 promotion。
- V3 参数说明：`eth-1h-ar-v3-clean-tuned-spec-2026-07-07.md`。V3 不修改本 V2.1 version spec。

## 登记结论

`ETH-1H-Adaptive-Regime-V2.1` 登记为 high-win tuned diagnostic observation。它满足 current-full 的高胜率形状，但近期 reused holdout、近期分片、成本/延迟压力均显示不可 promotion；下一步必须等待冻结 V2.1 参数后的新增 forward trades。
