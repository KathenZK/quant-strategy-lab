# HYPE-5M-Micro-Scalp-V1.2 登记与 1-3 倍杠杆复测 2026-07-01

Family id：`HYPE-5M-Micro-Scalp`

本报告将 V1.1 微调观察行 `V1.1_tune_grid_004895` 正式登记为 `HYPE-5M-Micro-Scalp-V1.2`，并按用户指定成本对 V1.1/V1.2 做 `1x/2x/3x` 复测。

## 数据质量

- Binance HYPEUSDT perpetual `5m`：`113998` 根，UTC `2025-05-30 10:30:00+00:00` 至 `2026-06-30 06:15:00+00:00`。
- raw/normalized 分区：`397` / `397`；对齐行数 `113998`。
- missing `0`，duplicate `0`，关键空值 `0`，OHLC/VWAP/volume 违规 `0`。
- raw/normalized 的 timestamp、OHLCV、quote volume、trade count、VWAP、is_closed 均逐字段一致。

## 成本与杠杆口径

- 手续费：`0.001` / fill，即每次成交按名义价值收取 `10 bps`；完整进出约 `20 bps`。
- 滑点：entry `4 bps`、exit `4 bps`，均按不利方向；完整进出约 `8 bps`。
- 杠杆：`1x`、`2x`、`3x`；每笔名义仓位分别为当时账户权益的 `100%`、`200%`、`300%`，逐笔复利，一次只持有一个仓位。
- 账户单笔收益按 `leverage * net_ret_1x` 计算，因此杠杆同步放大价格盈亏、手续费、滑点和持仓内 MAE。
- 信号与订单时序不变：收盘 K 产生信号，下一根 open 入场，立即放固定 TP/SL；同 K 双触发按 stop-first；gap 按 open 市价；timeout 下一根 open。
- 新滑点会改变实际 entry、TP/SL 绝对价位及退出时点，进而改变冷却期占用；所以本次交易数可以与旧成本报告略有差异，不是信号参数发生变化。
- 未计资金费；未模拟 Binance maintenance margin 与强平价格。当前路径在 `3x` 下没有账户 MAE 穿越 `-100%`，但这不等于完成交易所强平审计。

## 全样本结果

| 策略 | 杠杆 | 交易数 | 年化资金倍数 | 区间收益 | 最大回撤 | 胜率 | PF | 平均单笔账户收益 | 最差单笔 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE-5M-Micro-Scalp-V1.1` | `1x` | `184` | `1.56x` | `62.12%` | `-9.84%` | `86.96%` | `1.887` | `0.27%` | `-5.23%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `2x` | `184` | `2.38x` | `156.30%` | `-19.12%` | `86.96%` | `1.887` | `0.54%` | `-10.47%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `3x` | `184` | `3.55x` | `294.58%` | `-27.82%` | `86.96%` | `1.887` | `0.81%` | `-15.70%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `1x` | `180` | `1.76x` | `84.28%` | `-9.96%` | `85.00%` | `1.934` | `0.35%` | `-4.25%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `2x` | `180` | `2.98x` | `227.11%` | `-19.90%` | `85.00%` | `1.934` | `0.70%` | `-8.49%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `3x` | `180` | `4.89x` | `458.10%` | `-29.67%` | `85.00%` | `1.934` | `1.05%` | `-12.74%` |

## 时间切片

| 策略 | 杠杆 | 窗口 | 交易数 | 年化资金倍数 | 区间收益 | 最大回撤 | 胜率 | PF | 平均单笔账户收益 | 最差单笔 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE-5M-Micro-Scalp-V1.1` | `1x` | `train_2025_05_30_to_2026_03_01` | `138` | `1.56x` | `39.64%` | `-9.84%` | `86.23%` | `1.780` | `0.25%` | `-5.23%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `1x` | `val_2026_03_01_to_2026_06_01` | `30` | `1.34x` | `7.69%` | `-7.30%` | `86.67%` | `1.803` | `0.25%` | `-5.23%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `1x` | `recent_30d` | `17` | `2.71x` | `8.52%` | `-4.30%` | `94.12%` | `4.548` | `0.48%` | `-2.32%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `1x` | `fwd_2026_06_01_to_latest` | `16` | `2.56x` | `7.81%` | `-4.30%` | `93.75%` | `4.264` | `0.47%` | `-2.32%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `2x` | `train_2025_05_30_to_2026_03_01` | `138` | `2.37x` | `91.32%` | `-19.12%` | `86.23%` | `1.780` | `0.50%` | `-10.47%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `2x` | `val_2026_03_01_to_2026_06_01` | `30` | `1.77x` | `15.40%` | `-14.45%` | `86.67%` | `1.803` | `0.51%` | `-10.47%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `2x` | `recent_30d` | `17` | `7.21x` | `17.62%` | `-8.50%` | `94.12%` | `4.548` | `0.97%` | `-4.64%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `2x` | `fwd_2026_06_01_to_latest` | `16` | `6.44x` | `16.09%` | `-8.50%` | `93.75%` | `4.264` | `0.95%` | `-4.64%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `3x` | `train_2025_05_30_to_2026_03_01` | `138` | `3.51x` | `156.91%` | `-27.82%` | `86.23%` | `1.780` | `0.75%` | `-15.70%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `3x` | `val_2026_03_01_to_2026_06_01` | `30` | `2.28x` | `23.02%` | `-21.43%` | `86.67%` | `1.803` | `0.76%` | `-15.70%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `3x` | `recent_30d` | `17` | `18.92x` | `27.32%` | `-12.61%` | `94.12%` | `4.548` | `1.45%` | `-6.97%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `3x` | `fwd_2026_06_01_to_latest` | `16` | `15.96x` | `24.85%` | `-12.61%` | `93.75%` | `4.264` | `1.42%` | `-6.97%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `1x` | `train_2025_05_30_to_2026_03_01` | `134` | `1.51x` | `36.46%` | `-9.96%` | `82.09%` | `1.532` | `0.24%` | `-4.25%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `1x` | `val_2026_03_01_to_2026_06_01` | `32` | `2.21x` | `22.15%` | `-4.89%` | `93.75%` | `5.081` | `0.63%` | `-4.23%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `1x` | `recent_30d` | `15` | `3.49x` | `10.81%` | `-3.14%` | `93.33%` | `10.455` | `0.69%` | `-1.09%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `1x` | `fwd_2026_06_01_to_latest` | `14` | `3.50x` | `10.55%` | `-3.14%` | `92.86%` | `10.245` | `0.72%` | `-1.09%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `2x` | `train_2025_05_30_to_2026_03_01` | `134` | `2.19x` | `80.31%` | `-19.90%` | `82.09%` | `1.532` | `0.49%` | `-8.49%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `2x` | `val_2026_03_01_to_2026_06_01` | `32` | `4.82x` | `48.58%` | `-9.72%` | `93.75%` | `5.081` | `1.26%` | `-8.47%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `2x` | `recent_30d` | `15` | `12.01x` | `22.65%` | `-6.29%` | `93.33%` | `10.455` | `1.38%` | `-2.18%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `2x` | `fwd_2026_06_01_to_latest` | `14` | `12.08x` | `22.09%` | `-6.29%` | `92.86%` | `10.245` | `1.44%` | `-2.18%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `3x` | `train_2025_05_30_to_2026_03_01` | `134` | `3.03x` | `130.23%` | `-29.67%` | `82.09%` | `1.532` | `0.73%` | `-12.74%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `3x` | `val_2026_03_01_to_2026_06_01` | `32` | `10.31x` | `79.97%` | `-14.50%` | `93.75%` | `5.081` | `1.89%` | `-12.70%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `3x` | `recent_30d` | `15` | `40.81x` | `35.61%` | `-9.43%` | `93.33%` | `10.455` | `2.06%` | `-3.27%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `3x` | `fwd_2026_06_01_to_latest` | `14` | `41.15x` | `34.69%` | `-9.43%` | `92.86%` | `10.245` | `2.16%` | `-3.27%` |

## 月度稳定性

| 策略 | 杠杆 | 负收益月份 | 最差月 | 最好月 |
| --- | ---: | ---: | ---: | ---: |
| `HYPE-5M-Micro-Scalp-V1.1` | `1x` | `4` | `-3.41%` | `10.67%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `2x` | `4` | `-6.92%` | `22.34%` |
| `HYPE-5M-Micro-Scalp-V1.1` | `3x` | `4` | `-10.54%` | `35.09%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `1x` | `1` | `-1.40%` | `11.07%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `2x` | `1` | `-3.31%` | `23.25%` |
| `HYPE-5M-Micro-Scalp-V1.2` | `3x` | `1` | `-5.73%` | `36.66%` |

## 参数身份

- `HYPE-5M-Micro-Scalp-V1.1`：EMA `21/192/384`，VWAP deviation `65 bps`，TP/SL `90/500 bps`，hold/cooldown `96/48`。
- `HYPE-5M-Micro-Scalp-V1.2`：EMA `21/192/192`，VWAP deviation `65 bps`，TP/SL `110/400 bps`，hold/cooldown `96/48`。

## 结论边界

- V1.2 是 `V1.1_tune_grid_004895` 的正式版本身份；本次没有重新搜索参数，只统一了版本名、成本与杠杆复测口径。
- V1.1 在 `1x/2x/3x` 下为 `1.56x` / `2.38x` / `3.55x`，maxDD 为 `-9.84%` / `-19.12%` / `-27.82%`。
- V1.2 在 `1x/2x/3x` 下为 `1.76x` / `2.98x` / `4.89x`，maxDD 为 `-9.96%` / `-19.90%` / `-29.67%`。它在三个杠杆档位收益均更高，但回撤也略深，不是 V1.1 的全指标严格替代。
- 若继续坚持“小回撤”，`1x` 是本次唯一仍把全样本 maxDD 控制在约 `10%` 的档位；`2x` 已接近 `20%`，`3x` 接近 `30%`。
- V1.2 的 train PF 明显低于后续窗口，近期高 PF 不应外推；版本登记不改变其 paper-audit observation / not live-ready 状态。
- `2x/3x` 是研究压力测试，不构成实盘仓位建议；任何 promotion 仍需逐笔路径、交易所 bracket maintenance、强平/保证金、资金费、重启恢复与 paper/live reconciliation。
- VAL/FWD 已参与前序筛选，不能视作全新独立 OOS。

## 产物

- Script：`/Users/ZK/OpenCode/quant-strategy-lab/research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_2_registration_and_leverage_retest.py`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_summary_2026-07-01.csv`
- Slice CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_slices_2026-07-01.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_monthly_2026-07-01.csv`
- Trades CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_trades_2026-07-01.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_registration_and_leverage_retest_2026-07-01.json`
- V1.2 config：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_2_baseline_config_2026-07-01.json`
