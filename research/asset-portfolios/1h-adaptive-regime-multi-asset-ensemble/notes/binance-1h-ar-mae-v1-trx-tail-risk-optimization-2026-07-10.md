# BIN-1H-AR-MAE-V1：TRX MACD 尾部风险优化 - 2026-07-10

## 结论

本轮不再追求扩大 TRX V3 参数收益，而是在已登记的组合 V1 上处理 `TRX macd_flip` 的 `5x` 高暴露尾部风险。六个 sleeve 的冻结信号、入场、出场、成本、funding、单仓先到先得选择均保持不变；只使用入场前可知的 signal ATR 与账户历史回撤决定账户暴露。

prefit-only 选中的风险策略：`hybrid_all_atr_0.010_dd_8%_12%_caps_2x_1x`。

- 规则：Portfolio-wide signal-ATR risk budget plus drawdown-responsive exposure caps.
- 具体口径：每笔账户暴露先限制为 `exposure × signal ATR <= 1.0%`；若入场前账户回撤达到 `8%`，再把暴露上限压到 `2x`；达到 `12%`，压到 `1x`。所有变量在入场前可知。
- 选参门槛：prefit 基准 DD `<19%`、额外 `4 bps/fill` DD `<20%`、TRX MACD 最差单笔 MAE `<12%`、prefit annual `>=10x`。
- reused holdout 与近期分片只在策略冻结后读取。

## 为什么固定 TRX cap 不够

V1 中选 TRX MACD `37` 笔，只有 `2` 笔最终亏损，但原始最差单笔账户 MAE 达到 `-17.17%`。组合最深回撤由连续 BNB 亏损先造成账户下沉，随后 TRX `5x` 盈利交易在到达止盈前继续承受浮亏而加深。风险既来自单笔计划止损，也来自账户已经处于回撤时仍允许高暴露。

## 基线与选中策略

| Window | V1 baseline | Selected | +4bps/fill stress | Double-cost stress |
| --- | --- | --- | --- | --- |
| `full` | `287.01x / +3999748.08% / -21.43% DD / 90.30% win / 371 trades` | `7.88x / +4670.33% / -14.93% DD / 90.30% win / 371 trades` | `6.59x / +3311.65% / -15.78% DD / 89.76% win / 371 trades` | `4.10x / +1305.79% / -19.72% DD / 85.44% win / 371 trades` |
| `reused_holdout` | `7.77x / +65.63% / -19.79% DD / 78.57% win / 42 trades` | `1.07x / +1.70% / -14.93% DD / 78.57% win / 42 trades` | `0.99x / -0.30% / -15.78% DD / 78.57% win / 42 trades` | `0.66x / -9.80% / -19.72% DD / 69.05% win / 42 trades` |
| `last_7d` | `1.27x / +0.46% / -15.92% DD / 66.67% win / 3 trades` | `0.33x / -2.12% / -7.81% DD / 66.67% win / 3 trades` | `0.30x / -2.25% / -7.90% DD / 66.67% win / 3 trades` | `0.25x / -2.60% / -8.13% DD / 66.67% win / 3 trades` |
| `last_1m` | `265.91x / +58.18% / -15.92% DD / 89.47% win / 19 trades` | `4.86x / +13.86% / -7.81% DD / 89.47% win / 19 trades` | `3.99x / +12.04% / -7.90% DD / 89.47% win / 19 trades` | `2.28x / +7.02% / -8.13% DD / 89.47% win / 19 trades` |
| `last_3m` | `7.65x / +66.01% / -19.79% DD / 78.57% win / 42 trades` | `1.08x / +1.83% / -14.93% DD / 78.57% win / 42 trades` | `0.99x / -0.17% / -15.78% DD / 78.57% win / 42 trades` | `0.66x / -9.69% / -19.72% DD / 69.05% win / 42 trades` |
| `last_6m` | `147.89x / +1089.35% / -21.43% DD / 85.15% win / 101 trades` | `4.31x / +106.25% / -14.93% DD / 85.15% win / 101 trades` | `3.68x / +90.80% / -15.78% DD / 85.15% win / 101 trades` | `2.29x / +50.63% / -19.72% DD / 77.23% win / 101 trades` |
| `last_1y` | `134.60x / +13315.39% / -21.43% DD / 88.21% win / 212 trades` | `5.32x / +430.99% / -14.93% DD / 88.21% win / 212 trades` | `4.41x / +340.56% / -15.78% DD / 87.26% win / 212 trades` | `2.65x / +164.81% / -19.72% DD / 80.19% win / 212 trades` |

## 风险—收益前沿（冻结后审计）

| Policy | Full annual / DD | Holdout return / DD | Double-cost full DD | TRX MACD worst MAE |
| --- | --- | --- | ---: | ---: |
| `all_cap_2_5x` | `122.81x / -18.68%` | `+49.97% / -15.92%` | `-25.58%` | `-8.58%` |
| `hybrid_all_atr_0.010_dd_8%_12%_caps_2x_1x` | `7.88x / -14.93%` | `+1.70% / -14.93%` | `-19.72%` | `-7.09%` |
| `hybrid_all_atr_0.012_dd_8%_12%_caps_2x_1x` | `11.71x / -16.28%` | `+4.66% / -16.28%` | `-18.94%` | `-8.50%` |
| `hybrid_all_atr_0.015_dd_8%_12%_caps_2x_1x` | `19.50x / -18.22%` | `+6.01% / -18.22%` | `-20.97%` | `-10.63%` |

风险优先的 `1.0% ATR + 8%/12% DD guard` 在冻结后 full 为 `7.88x / -14.93% DD`，但低于家族 `10x` 年化目标；reused holdout 仅 `+1.70%`，额外滑点后转负，因此不能冻结为下一版本。
较均衡的 `1.2% ATR + 8%/12% DD guard` full 为 `11.71x / -16.28% DD`，但 holdout 只有 `+4.66%`，额外滑点后接近零；同样只能作为 forward-test 方向。

## TRX MACD 风险变化

| Metric | V1 baseline | Selected |
| --- | ---: | ---: |
| avg exposure | `5.00x` | `2.30x` |
| max exposure | `5.00x` | `4.58x` |
| max planned stop risk | `24.72%` | `6.28%` |
| worst equity MAE | `-17.17%` | `-7.09%` |

## 执行与边界

- 风险预算使用 signal K 已知 ATR 和账户历史权益，不使用未来 MAE/MFE。
- 不改变 entry/exit K、stop/target 路径或单仓选择，因此不存在新增未来函数或价格穿越。
- 成本压力仍是账户层扣减，不是 K 级重新成交；阻塞后的 sleeve cooldown 反事实仍继承 V1 近似。
- 本轮是未编号 diagnostic observation，不登记新版本，不改变 `NO-GO / not promoted / not live-ready`。

## 机器证据

- `artifacts/binance_1h_ar_mae_v1_trx_tail_risk_2026-07-10.json`
- `artifacts/binance_1h_ar_mae_v1_trx_tail_risk_matrix_2026-07-10.csv`
- `artifacts/binance_1h_ar_mae_v1_trx_tail_risk_trades_2026-07-10.csv`
- `scripts/research_binance_1h_ar_mae_v1_trx_tail_risk_optimization.py`

复现：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_v1_trx_tail_risk_optimization.py
```
