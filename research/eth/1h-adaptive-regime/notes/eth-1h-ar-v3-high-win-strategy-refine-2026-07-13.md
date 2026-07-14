# ETH-1H-Adaptive-Regime-V3 高胜率全策略优化 - 2026-07-13

## 结论

本轮接受“增加有效交易数，但胜率不能下降太多”的约束。上一轮已经在 27 参数 clean surface 上完成全策略搜索；本轮从其中通过 K+2/8 bps 的 33 个候选出发，对两条腿风险暴露重新组合，并以高胜率、交易数和回撤联合门槛进行 prefit-only 冻结。

- 选中 observation：`ETH-1H-AR-V3-HIGH-WIN-STRATEGY-REFINE-2026-07-13`；来源候选行 `8`；BB/RSI 杠杆 `1.50x / 2.00x`。
- 上一轮 high-win frequency prefit：`8.0199x` / `2854.16%` / `-17.71%` / `91.67%` / `60`；本轮：`5.4898x` / `1494.90%` / `-14.29%` / `91.04%` / `67`。
- 上一轮 current full：`6.1083x` / `2878.06%` / `-22.55%` / `88.41%` / `69`；本轮：`4.4124x` / `1518.25%` / `-17.08%` / `87.34%` / `79`。
- 本轮 reused holdout（冻结后只读）：`1.0601x` / `1.46%` / `-17.08%` / `66.67%` / `12`。

胜率下降被控制在较小范围：prefit 从 `91.67%` 到 `91.04%`（`-0.62` 个百分点），current full 从 `88.41%` 到 `87.34%`（`-1.07` 个百分点）；同时 prefit 交易从 `60` 增加到 `67`，current full 从 `69` 增加到 `79`，current-full DD 从 `-22.55%` 收敛到 `-17.08%`。

## 选择门槛

- 基础：prefit trades `>= 65`、validation trades `>= 15`；train/validation/prefit 胜率分别 `>= 88%/90%/90%`；prefit DD `< 15%`。
- K+2：prefit 胜率 `>= 84%`、DD `< 18%`。
- 8 bps：prefit 胜率 `>= 87%`、DD `< 16%`。
- 共评估 `990` 个风险组合，门槛命中 `78` 个；选择、排序均未读取 reused holdout。

## 选中参数

### BB breakout

- `indicator_window` = `72`
- `band_k` = `2.5`
- `roc_window` = `12`
- `min_adx` = `16.0`
- `min_rvol` = `3.5`
- `min_atr_bps` = `25.0`
- `min_dir_roc_bps` = `100.0`
- `max_dist_ema_bps` = `10000.0`
- `tp_atr` = `3.0`
- `sl_atr` = `5.0`
- `max_hold_bars` = `96`
- `fixed_leverage` = `1.5`

### RSI reversal

- `ema_htf` = `144`
- `indicator_window` = `7`
- `threshold_low` = `10.0`
- `threshold_high` = `75.0`
- `roc_window` = `12`
- `min_adx` = `12.0`
- `max_adx` = `55.0`
- `min_atr_bps` = `125.0`
- `min_dir_roc_bps` = `-500.0`
- `max_dist_ema_bps` = `1500.0`
- `tp_atr` = `2.5`
- `sl_atr` = `2.5`
- `max_hold_bars` = `36`
- `cooldown_bars` = `36`
- `fixed_leverage` = `2.0`

## 延迟与成本审计

- `base_k1`：prefit `5.4898x` / `1494.90%` / `-14.29%` / `91.04%` / `67`；reused holdout `1.0601x` / `1.46%` / `-17.08%` / `66.67%` / `12`。
- `delay_k2`：prefit `3.6815x` / `732.75%` / `-17.42%` / `84.85%` / `66`；reused holdout `1.4412x` / `9.53%` / `-12.60%` / `72.73%` / `11`。
- `delay_k3`：prefit `3.5606x` / `688.75%` / `-23.85%` / `82.35%` / `68`；reused holdout `0.8523x` / `-3.90%` / `-24.19%` / `58.33%` / `12`。
- `slip_8bps`：prefit `4.5961x` / `1094.62%` / `-14.45%` / `88.06%` / `67`；reused holdout `1.0267x` / `0.66%` / `-17.48%` / `66.67%` / `12`。
- `slip_12bps`：prefit `3.4592x` / `652.55%` / `-19.75%` / `83.58%` / `67`；reused holdout `0.9935x` / `-0.16%` / `-17.90%` / `66.67%` / `12`。
- `fee12_slip8`：prefit `4.4716x` / `1042.47%` / `-14.60%` / `88.06%` / `67`；reused holdout `0.9966x` / `-0.08%` / `-17.90%` / `66.67%` / `12`。
- `double_cost`：prefit `4.0060x` / `855.37%` / `-15.20%` / `88.06%` / `67`；reused holdout `0.8848x` / `-3.00%` / `-19.84%` / `66.67%` / `12`。

## 标准近期分片

- `last_1d`：`1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0`
- `last_7d`：`11.8725x` / `4.86%` / `-7.57%` / `100.00%` / `1`
- `last_1m`：`3.0646x` / `9.63%` / `-7.57%` / `100.00%` / `3`
- `last_3m`：`1.0601x` / `1.46%` / `-17.08%` / `66.67%` / `12`
- `last_6m`：`2.3890x` / `53.97%` / `-17.08%` / `76.19%` / `21`
- `last_1y`：`3.8574x` / `285.38%` / `-17.08%` / `84.44%` / `45`

## 研究边界

- 本轮 observation 已按用户要求登记为 `ETH-1H-Adaptive-Regime-V4`；登记不等于 promotion，也不生成 live spec。
- reused holdout 已多次揭盲，只能用于冻结后失败边界；其转正不能替代 fresh forward。
- 当前数据仍截止 `2026-07-03T05:00:00Z`。在新增数据上至少积累 `20-30` 笔或 `2-3` 个月，并完成 live-executable 审计前，状态仍为 `NO-GO / not promoted / not live-ready`。

## 机器证据

- `artifacts/eth_1h_ar_v3_high_win_strategy_refine_2026-07-13.json`
- `artifacts/eth_1h_ar_v3_high_win_strategy_refine_grid_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_strategy_refine_trades_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_strategy_refine_slices_2026-07-13.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v3_high_win_strategy_refine.py
```
