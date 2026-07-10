# ETH-1H-Adaptive-Regime-V3 频率与 fresh forward 诊断 - 2026-07-10

## 结论

V3 的高胜率主要来自过强筛选和极少交易，不适合作为 promotion 依据。优化方向不应继续追求 `95%-100%` 胜率，而应改成“有效交易数优先”：在 train/validation/prefit 内提高交易密度、允许胜率回落到约 `65%-80%`，同时保持 DD 不穿 `20%`；冻结少量候选后等待 `2026-07-03` 之后的 fresh forward。

- V3 当前 prefit：`4.0591x` / `876.08%` / `-12.15%` / `100.00%` / `42`；reused holdout：`0.8706x` / `-3.39%` / `-15.70%` / `50.00%` / `4`；current full：`3.3084x` / `842.97%` / `-15.70%` / `95.65%` / `46`。
- BB breakout 单腿 prefit：`1.7449x` / `147.27%` / `-11.73%` / `100.00%` / `22`；reused holdout：`0.8706x` / `-3.39%` / `-15.70%` / `50.00%` / `4`。
- RSI reversal 单腿 prefit：`2.0346x` / `217.45%` / `-16.75%` / `90.91%` / `22`；reused holdout：`1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0`。

## 交易太少的直接原因

- BB 过滤链（prefit/holdout 信号数）：raw 138/17 -> adx 129/16 -> rvol 38/12 -> atr 26/4 -> dir_roc 26/4 -> dist_ema 22/4 -> funding 22/4。主要瓶颈是 `min_rvol`、`min_atr_bps` 与 `max_dist_ema_bps`。
- RSI 过滤链（prefit/holdout 信号数）：raw 362/60 -> adx 253/39 -> rvol 253/39 -> atr 59/1 -> dir_roc 38/0 -> dist_ema 27/0 -> funding 27/0 -> body_dir 27/0。holdout 原始 RSI 信号有 `60` 个，但 `min_atr_bps=125`、`min_dir_roc_bps=-300`、`max_dist_ema_bps=750` 后变成 `0` 个，所以近三个月完全靠 BB 多头。
- holdout 4 笔全是 BB long；其中 2026-04 的 3 笔合计为负，`2026-04-17` 一笔 stop-market `-7.77%` equity 是主要伤害。
- holdout 逐笔：2026-04-07 23:00:00+00:00 bb_break 1.02% timeout_open；2026-04-13 23:00:00+00:00 bb_break -1.12% timeout_open；2026-04-17 14:00:00+00:00 bb_break -7.77% stop_market；2026-06-29 18:00:00+00:00 bb_break 4.86% take_profit

## 单项放松诊断

- `RSI min_atr_bps=75`：prefit `2.642x / -19.95% / 72.50% / 109`，reused holdout 只读为 `+6.07% / 10` 笔。这说明“让 RSI 在较低波动下恢复交易”是最值得继续研究的频率方向，但它牺牲了高胜率外观。
- `RSI min_dir_roc_bps=-10000`：prefit `3.453x / -14.51% / 91.84% / 49`，reused holdout 只读为 `+2.80% / 5` 笔。方向 ROC 过滤也可能过强。
- `BB min_rvol=3.0 + min_atr_bps<=50 + max_dist_ema_bps>=2500` 的频率优先网格冠军：prefit `5.100x / -12.15% / 92.19% / 64`，validation `4.288x / -8.78% / 100.00% / 17`，reused holdout 只读仍为 `-4.03% / 7` 笔。它能增加 prefit 交易数，但没有解决近期失败。

## 优化路线

1. 停止用 `win>=90%` 或“比 V3 胜率更高”做目标；改成 `prefit trades >= 80-120`、`validation trades >= 15`、`win >= 65%-70%`、`DD > -20%`、train/validation 同正。
2. 下一轮只放宽有限参数面：BB 的 `min_rvol`、`min_atr_bps`、`max_dist_ema_bps`；RSI 的 `min_atr_bps`、`min_dir_roc_bps`、`max_dist_ema_bps`、`threshold_low/high`。不要先收紧 BB `sl_atr` 或 `max_hold_bars`，本次诊断里收紧它们会恶化 holdout 或 prefit。
3. 生成 3-5 个候选而不是单一冠军：`V3 baseline`、`BB-frequency`、`RSI-ATR75`、`RSI-direction-relaxed`、`mixed-frequency`。这些候选必须在 reused holdout 揭盲后冻结，不能再用 holdout 排序。
4. fresh forward 从 `2026-07-03T05:00:00Z` 之后开始，至少等待 `20-30` 笔新交易或 `2-3` 个月；通过条件应是净收益为正、DD 不穿 `15%-20%`、交易来源不是单腿单方向、执行模型与 live runner 一致。

## 机器证据

- 摘要 JSON：`artifacts/eth_1h_ar_v3_frequency_forward_diagnostic_2026-07-10.json`
- 单项放松 CSV：`artifacts/eth_1h_ar_v3_frequency_forward_single_relax_2026-07-10.csv`
- 频率网格 CSV：`artifacts/eth_1h_ar_v3_frequency_forward_grid_2026-07-10.csv`
- 复现脚本：`scripts/research_eth_1h_ar_v3_frequency_forward_diagnostic.py`

## 状态

`ETH-1H-Adaptive-Regime-V3` 仍是 `NO-GO / not promoted / not live-ready`。本诊断只给出下一轮优化面，不登记 V4，也不生成 live spec。
