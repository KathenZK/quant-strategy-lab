# BIN-15M-EMAX 特征/标签双消融契约（归档后死因复核）

> 状态：本家族保持 `archived / HARD-GATE-FAILED`，本契约**不重开研究线、不支持任何 promotion**。目的只有一个：正面检验用户提出的"特征构造有问题"假设——15m 交叉的可分性到底是（a）被行情状态特征淹没了、还是（b）局部形态信息本身不存在。契约在跑数前冻结；已揭示的 `2026-01`–`2026-06` 窗口完全不使用。

## 1. 数据（全部冻结、零重算）

- [`event_dataset_dev.parquet`](../artifacts/event_dataset_dev.parquet)：426,815 个 15m EMA21/96 交叉事件（2021–2025 开发窗），bracket `b4_2`（TP 4×ATR / SL 2×ATR / 96 根超时），`net_atr` 已含手续费 0.001/边 + 滑点 4 bps/边 + as-of funding。
- 训练与评估都只用 `in_trading_pool == True` 的事件（约 29.2 万）。
- 训练权重沿用数据集冻结的 `weight` 列（币种平衡 + 同时性降权 + 截断）。

## 2. 特征划分（预注册清单）

- **LOCAL（局部形态，用户假设的载体）**：`side` + 交叉几何（`gap_atr, fast_slope_4/16, slow_slope_16/96, slope_diff_16, entangle_96, gap_pre_atr, bars_since_prev_cross, crosses_384`）+ 本币价格/趋势（`price_to_fast_atr, price_to_slow_atr, ret_1/4/8/16/32/96, adx_14, efficiency_96, dist_high_24h, dist_low_24h, donchian_pos_96, color_run`）+ 本币波动（`atr_frac, rv_ratio, bb_width_atr, atr_pos_30d, tr_over_atr`）+ 本币量能/流动性（`vol_z_96, vol_ratio_4_24, qv_rel_30d, taker_bias, tc_z_96, impact_rel_96`）+ `cost_atr`。
- **MARKET（行情状态及其他）**：BTC/相关性（`beta_btc_30d, corr_btc_30d, btc_*`）、市场横截面（`csd_24h, universe_count, breadth_*, rel_strength_24h, mkt_funding_mean`）、本币 funding（`funding_*`, `bars_to_next_funding`）、结构（`adv_30d, adv_rank_pct, listing_age_log, vol_rank_pct`）、日历（`hour_*, day_of_week`）、拥挤度（`cross_count_1h_same_side, cross_ratio_24h_same_side`）。
- FULL = LOCAL + MARKET。

## 3. 变体（2×2，一次跑完，无搜索）

| 变体 | 特征 | 标签 |
|---|---|---|
| `ref`  | FULL | 绝对：`b4_2_net_atr` 回归 |
| `a_local_abs` | LOCAL | 绝对：`b4_2_net_atr` 回归 |
| `b_full_rel` | FULL | 相对：`b4_2_net_atr` 在同 (UTC 日, side) 组内的百分位（组内事件 ≥ 8 才参与训练） |
| `c_local_rel` | LOCAL | 相对：同上（最纯"这根交叉比同时刻同向的别的交叉好在哪"表述） |

模型统一 `LGBMRegressor`（`n_estimators=800, learning_rate=0.02, num_leaves=31, max_depth=6, min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_alpha=1.0, reg_lambda=5.0, seed=42`），四个变体只有特征列和标签变换不同。

## 4. 验证协议

扩窗 purged 时序 CV，年度 OOF 折 2022/2023/2024/2025：折 Y 训练用 `entry_ts < Y-01-01 − 2 天`（96 根 15m 标签窗 + 缓冲）的事件，OOF 打分年 Y 全部池内事件。2021 只作训练。

## 5. 预注册判定

对每个变体：OOF 分数在**各折年内**十分位分桶（声明：年内分位属机制检验口径，非可部署阈值），统计各桶 `b4_2_net_atr`（含成本）均值：

- **Gate A（排序有效）**：合并十分位序号与桶均值的 Spearman 相关 > 0.8；
- **Gate B（可变现）**：顶部十分位合并均值 > 0，且 4 个 OOF 年中 ≥ 3 年该桶均值 > 0。

**"特征假设成立" 当且仅当 `a_local_abs` 或 `c_local_rel` 同时过 Gate A+B**（局部形态特征独立支撑超成本分层）。`ref`/`b_full_rel` 为归因参照。无论结果如何，家族维持 `archived`；若局部变体通过，结论写为"死因修正：特征表达不充分"并注明任何重开须以新机制线立项。

## 6. 产物

`artifacts/feature_ablation/` 下：报告 JSON（含四变体分桶表、逐年顶桶、特征重要性 top15）、OOF 分数 parquet。诊断报告一份入 `diagnostics/`。
