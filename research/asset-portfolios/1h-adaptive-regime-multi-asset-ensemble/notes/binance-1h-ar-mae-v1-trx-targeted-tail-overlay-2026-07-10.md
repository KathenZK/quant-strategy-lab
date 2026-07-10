# BIN-1H-AR-MAE-V1：TRX MACD 定向尾部覆盖层 - 2026-07-10

## 结论

本轮只处理组合 V1 中 `TRX macd_flip` 的 `5x` 尾部风险；非 TRX 交易暴露、六 sleeve 信号/成交/退出、单仓先到先得选择与成本口径全部保持不变。目标是避免上一轮全局 ATR overlay 对所有 sleeve 的过度降杠杆。

prefit-only 选中策略：`trx_stop_0.10_dd_2%_6%_caps_3x_2x`。

- TRX MACD 计划初始止损账户风险上限：`10%`。
- 仅当账户入场前回撤达到 `2%`，TRX MACD 上限降为 `3x`；达到 `6%`，降为 `2x`。
- 所有 sizing 输入在入场前可知；reused holdout 与近期分片冻结后才读取。

## 结果

| Window | V1 baseline | Targeted | +4bps/fill stress | Double-cost stress |
| --- | --- | --- | --- | --- |
| `full` | `287.01x / +3999748.08% / -21.43% DD / 90.30% win / 371 trades` | `231.59x / +2676542.52% / -19.99% DD / 90.30% win / 371 trades` | `160.18x / +1342050.90% / -20.18% DD / 89.76% win / 371 trades` | `62.93x / +233295.07% / -27.53% DD / 85.44% win / 371 trades` |
| `reused_holdout` | `7.77x / +65.63% / -19.79% DD / 78.57% win / 42 trades` | `6.31x / +57.37% / -17.38% DD / 78.57% win / 42 trades` | `4.59x / +45.52% / -18.65% DD / 78.57% win / 42 trades` | `2.07x / +19.57% / -27.53% DD / 69.05% win / 42 trades` |
| `last_7d` | `1.27x / +0.46% / -15.92% DD / 66.67% win / 3 trades` | `1.27x / +0.46% / -15.92% DD / 66.67% win / 3 trades` | `0.98x / -0.05% / -16.16% DD / 66.67% win / 3 trades` | `0.50x / -1.31% / -16.75% DD / 66.67% win / 3 trades` |
| `last_1m` | `265.91x / +58.18% / -15.92% DD / 89.47% win / 19 trades` | `265.91x / +58.18% / -15.92% DD / 89.47% win / 19 trades` | `174.03x / +52.77% / -16.16% DD / 89.47% win / 19 trades` | `60.05x / +39.98% / -16.75% DD / 89.47% win / 19 trades` |
| `last_3m` | `7.65x / +66.01% / -19.79% DD / 78.57% win / 42 trades` | `6.23x / +57.74% / -17.38% DD / 78.57% win / 42 trades` | `4.55x / +45.86% / -18.65% DD / 78.57% win / 42 trades` | `2.07x / +19.85% / -27.53% DD / 69.05% win / 42 trades` |
| `last_6m` | `147.89x / +1089.35% / -21.43% DD / 85.15% win / 101 trades` | `126.02x / +998.70% / -18.13% DD / 85.15% win / 101 trades` | `86.07x / +809.53% / -18.65% DD / 85.15% win / 101 trades` | `33.06x / +466.10% / -27.53% DD / 77.23% win / 101 trades` |
| `last_1y` | `134.60x / +13315.39% / -21.43% DD / 88.21% win / 212 trades` | `119.71x / +11832.02% / -19.99% DD / 88.21% win / 212 trades` | `80.14x / +7890.06% / -20.18% DD / 87.26% win / 212 trades` | `28.92x / +2785.79% / -27.53% DD / 80.19% win / 212 trades` |

与上一轮全局 `1.0% ATR + 8%/12% DD guard` 相比，定向方案只缩放 TRX MACD：full 年化从全局方案的 `7.88x` 保留到 `231.59x`，reused holdout 从 `+1.70%` 保留到 `+57.37%`；代价是 DD 只能压到 `-19.99%`，不能达到全局方案的 `-14.93%`。这更符合“组合层不追 TRX 更高收益、只处理其高暴露尾部”的目标。

prefit 冻结指标为 `399.43x annual / -19.99% DD`；额外 `4 bps/fill` 为 `274.16x / -20.18% DD`，double-cost 为 `105.51x / -20.72% DD`。选择没有读取 reused holdout 或近期分片。

## TRX MACD 风险变化

| Metric | V1 baseline | Targeted |
| --- | ---: | ---: |
| reduced entries | `0/37` | `34/37` |
| average exposure | `5.00x` | `3.03x` |
| max planned stop risk | `24.72%` | `10.00%` |
| worst single-trade MAE | `-17.17%` | `-9.71%` |
| worst account-state + trade-MAE DD | `-23.10%` | `-18.80%` |

## 风险—收益前沿（prefit）

| Stop budget | DD soft/hard | Caps | Annual | Close DD | TRX worst MAE | TRX account-tail DD |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| `0.2` | `10%/15%` | `3x/2x` | `489.84x` | `-19.99%` | `-17.17%` | `-18.94%` |
| `0.15` | `10%/15%` | `3x/2x` | `455.38x` | `-19.99%` | `-14.23%` | `-18.94%` |
| `0.12` | `10%/15%` | `3x/2x` | `424.96x` | `-19.99%` | `-13.48%` | `-18.94%` |
| `0.12` | `2%/6%` | `4x/1x` | `417.27x` | `-19.99%` | `-11.66%` | `-17.37%` |
| `0.1` | `2%/6%` | `4x/1x` | `400.17x` | `-19.99%` | `-10.79%` | `-17.37%` |
| `0.1` | `2%/6%` | `3x/2x` | `399.43x` | `-19.99%` | `-9.71%` | `-18.80%` |
| `0.08` | `2%/6%` | `3.5x/1x` | `381.20x` | `-19.99%` | `-9.44%` | `-17.37%` |
| `0.08` | `2%/6%` | `3x/2x` | `383.20x` | `-19.99%` | `-8.09%` | `-18.80%` |

## 剩余风险与边界

TRX 定向覆盖层把 close-marked DD 压到约 `-19.99%` 后，回撤下限转移到此前连续 BNB 亏损；在整个 TRX-only 网格中，额外 `4 bps/fill` 的最佳 prefit DD 仍为 `-20.18%`。因此继续缩 TRX 无法解决成本压力，下一步应单独处理 BNB loss cluster 或采用轻量账户级总风险上限。

从更保守的“入场前账户状态 + 单笔 MAE”口径看，TRX MACD 最差值已从 `-23.10%` 降至 `-18.80%`，不再是组合最差尾部；剩余最差转为 HYPE `di_cross -21.81%` 与 SOL `donchian_break -21.13%`。因此下一轮不应继续单独压低 TRX，而应把同一风险预算推广为轻量、跨 sleeve 的 account-tail guard，并避免上一轮全局 `1% ATR` 那种过度降杠杆。

- 最差 MAE/账户尾部指标只用于评估与选参，不参与实时 sizing，不构成未来函数。
- overlay 不改变 entry/exit K、stop/target 路径，不新增价格穿越假设。
- 成本压力仍为账户层扣减，不是逐 K 成交重演；阻塞 cooldown 反事实近似仍存在。
- 本轮是未编号 diagnostic observation，不登记新版本，不改变 `NO-GO / not promoted / not live-ready`。

## 机器证据

- `artifacts/binance_1h_ar_mae_v1_trx_targeted_tail_2026-07-10.json`
- `artifacts/binance_1h_ar_mae_v1_trx_targeted_tail_matrix_2026-07-10.csv`
- `artifacts/binance_1h_ar_mae_v1_trx_targeted_tail_trades_2026-07-10.csv`
- `scripts/research_binance_1h_ar_mae_v1_trx_targeted_tail_overlay.py`

复现：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_v1_trx_targeted_tail_overlay.py
```
