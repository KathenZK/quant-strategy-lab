# HYPE-15M-Multidimensional-Trend-Pyramiding V1 初始研究与回测

## 结论

**NO-GO / NOT PROMOTED**。完整版本没有在公平成本与时间折叠下证明相对 V35 的真实改善。

- 相对标准成本 V35：净总收益差 `-4128.27pp`，Sharpe 差 `-6.76`，最大回撤差 `-32.76pp`。
- 滚动历史伪 OOS：full 版本正收益 fold 比例 `0.00%`；这是严格时间顺序但不是未揭示 prospective OOS。
- 纸面交易判断：不值得进入带资金纸面仿真；最多保留为机制诊断，先修复失败门禁。

## 数据与 V35 冻结对照

- 主数据：Binance USD-M `HYPE/USDT:USDT` `15m`，`2025-05-30T10:30:00+00:00` 至 `2026-07-30T10:00:00+00:00`，`40895` 根已闭合 K。
- 数据质量：缺口 `0`、重复 `0`、无效 OHLCV `0`；raw/normalized 全字段逐行对齐 `True`。
- V35 当前逻辑：15m EMA96/384 定方向，ADX28 与 192 根量能过滤，上一根完整 1h ADX/DI 或 EMA 确认；K0 收盘信号、跳过 K1、K2 open 入场；ATR672 波动率仓位，long target `2.0%`、short target `1.8%`、cap `3x`；固定 `TP5ATR / SL7ATR`；ADX<22 连续 3 根时下一根 open 退出，MFE>=1.5ATR 后关闭指标退出；384 根 timeout；无固定冷却。
- V35 历史成本：每次 fill 合并 `8.5bps` + funding。公平对照另跑仓库当前 Binance 标准成本：手续费 `10bps` + adverse slippage `4bps` 每次 fill + funding。
- 新分支没有继承 V35 身份、参数或 promotion 状态。

## 新框架

- 4h：多周期波动率标准化收益、Signed Kaufman ER、Donchian 位置、方向成交量失衡、signed RVOL 等权形成方向分数；绝对分数低于阈值时空仓。
- 1h：同构分数识别萌芽、确认、成熟与缩量回调后的恢复；所有 1h/4h 特征只在完整高周期 K 结束后可见。
- 15m：上一根 15m 收盘生成目标，下一根 open 调仓。趋势分数决定方向和阶段仓位，15m 实现波动率控制实际 allocation。
- 只对盈利 campaign 加仓；过度延伸或 jump concentration 过高时禁止增加仓位，减仓与退出不受阻。
- 退出：ATR trailing、慢速 1h Donchian、4h regime 反转/空档或趋势分数衰减；无固定止盈。

## 四组主对照

| variant | total_return_pct | cagr_pct | sharpe | sortino | max_drawdown_pct | calmar | trades | win_rate_pct | payoff_ratio | profit_factor | avg_hold_hours | turnover_annualized | long_return_contribution_pct | short_return_contribution_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V35 canonical 8.5bps | 7078.2031 | 4419.4126 | 4.3139 | 2.5352 | -29.6648 | 148.9785 | 115 | 76.5217 | 0.9180 | 2.9921 | 12.4500 | 564.9506 | 240.4616 | 80.5081 |
| V35 standard 14bps | 4063.8800 | 2680.8017 | 3.7853 | 2.1808 | -32.3796 | 82.7929 | 115 | 75.6522 | 0.8493 | 2.6388 | 12.6109 | 565.0301 | 213.7559 | 73.7767 |
| price_only | -86.1620 | -84.9652 | -3.6128 | -3.4845 | -86.3966 | -0.9834 | 786 | 21.7557 | 2.1807 | 0.6063 | 5.6282 | 1264.6871 | 32.4705 | -32.8168 |
| price_volume | -79.0492 | -77.6297 | -3.1903 | -2.8309 | -79.3812 | -0.9779 | 746 | 26.0054 | 1.7741 | 0.6235 | 5.1166 | 1137.1102 | 46.2843 | -26.2639 |
| full | -64.3860 | -62.8100 | -2.9791 | -2.6521 | -65.1427 | -0.9642 | 748 | 30.8824 | 1.5057 | 0.6728 | 5.1160 | 786.6739 | 33.7720 | -16.7116 |

`V35 canonical` 仅用于历史复现；策略优劣判断使用同为 `10bps fee + 4bps slippage + funding` 的 V35 standard 与三个新版本。

## 成本拆分

完整 gross / fee-only / fee+slippage / net 结果见 [JSON](../artifacts/hype_15m_mdtp_v1_research_2026-07-31.json) 与 [metrics CSV](../artifacts/hype_15m_mdtp_v1_metrics_2026-07-31.csv)。拆分使用顺序反事实，因费用会改变复利路径，各项差值不应机械相加。

## 严格时间顺序滚动测试

- 初始上下文 180 天；随后每 60 天一个不重叠 test fold；固定参数，fold 内不选参。
- 所有标准化仅使用当时之前的滚动数据；MFE/MAE/未来收益标签只在事后诊断生成。
- 由于仓库此前已研究过 HYPE 同一历史，以下只能称 chronological pseudo-OOS，不能称 prospective OOS。

| variant | positive_fold_ratio | total_return_pct | cagr_pct | max_drawdown_pct | sharpe | calmar |
| --- | --- | --- | --- | --- | --- | --- |
| price_only | 0.0000 | -68.2628 | -81.7865 | -69.7478 | -3.2135 | -1.1726 |
| price_volume | 0.0000 | -62.5807 | -76.7442 | -64.4743 | -3.1076 | -1.1903 |
| full | 0.0000 | -42.6561 | -56.1845 | -45.8566 | -2.4689 | -1.2252 |

## 模块消融

| variant | total_return_pct | cagr_pct | max_drawdown_pct | sharpe | calmar | trades | turnover_annualized |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_no_jump | -64.9553 | -63.3797 | -65.6266 | -3.0200 | -0.9658 | 746 | 785.8311 |
| full_no_extension | -78.9381 | -77.5161 | -79.2719 | -3.1796 | -0.9779 | 748 | 1166.6239 |
| full_no_recovery_add | -64.2837 | -62.7076 | -65.0425 | -2.9709 | -0.9641 | 748 | 780.2170 |
| full_no_score_decay | -64.3534 | -62.7774 | -65.1108 | -2.9763 | -0.9642 | 748 | 786.6739 |
| full_no_staging | -85.7393 | -84.5255 | -86.2022 | -3.2478 | -0.9805 | 688 | 1395.3144 |

模块有效性由相对 full 的收益、回撤、Sharpe、Calmar、换手共同判断；单一收益提升不自动视为有效。

## 参数与窗口稳定性

阈值网格覆盖 regime `0.14/0.18/0.22`、confirm `0.20/0.24/0.28`、ATR trail `3.5/4.0/4.5`，extension 固定为预声明的 `2.5ATR`，共 27 行；未从中挑选替代默认参数。完整网格见 [CSV](../artifacts/hype_15m_mdtp_v1_parameter_stability_2026-07-31.csv)，二维稳定区汇总见 [heatmap CSV](../artifacts/hype_15m_mdtp_v1_stability_heatmap_2026-07-31.csv)。

相邻窗口：

| window_variant | total_return_pct | cagr_pct | max_drawdown_pct | sharpe | calmar | trades |
| --- | --- | --- | --- | --- | --- | --- |
| shorter_0.8x | -73.1862 | -71.6643 | -73.3521 | -3.6871 | -0.9770 | 799 |
| base_1.0x | -64.3860 | -62.8100 | -65.1427 | -2.9791 | -0.9642 | 748 |
| longer_1.2x | -53.3436 | -51.8277 | -54.3215 | -2.1645 | -0.9541 | 696 |

## 趋势分数单调性

Signed score 五分组（未来 24h 原始收益应随分数上升）：

| quintile | count | score_mean | future_return_mean_pct | future_return_median_pct |
| --- | --- | --- | --- | --- |
| 1 | 1988 | -0.3713 | -0.0157 | -0.3222 |
| 2 | 1987 | -0.1531 | 0.2957 | 0.2244 |
| 3 | 1988 | -0.0109 | 0.2156 | -0.0302 |
| 4 | 1987 | 0.1348 | 0.2637 | -0.0446 |
| 5 | 1988 | 0.3663 | 0.1723 | -0.5060 |

绝对强度五分组（按分数方向计算未来 24h 净方向收益、MFE、MAE）：

| quintile | count | abs_score_mean | directional_return_mean_pct | mfe_mean_pct | mae_mean_pct |
| --- | --- | --- | --- | --- | --- |
| 1 | 1988 | 0.0347 | 0.1720 | 3.3065 | -3.0042 |
| 2 | 1987 | 0.1058 | 0.0179 | 3.1929 | -3.1614 |
| 3 | 1988 | 0.1827 | -0.1899 | 3.0256 | -3.1519 |
| 4 | 1987 | 0.2772 | -0.1251 | 3.0045 | -2.9956 |
| 5 | 1988 | 0.4608 | 0.3808 | 3.5126 | -2.8898 |

- signed future return 单调：`False`。
- conviction directional return 单调：`False`。

## 跨币种固定参数迁移

以下全部直接使用 HYPE V1 固定参数，没有按币种调参。`post180` 仅表示每个币种前 180 天作为历史上下文后的时间段，不是未揭示 prospective OOS。若 raw loader/schema 不能完成 raw-normalized parity，该币种结果标记为 `explore / untrusted`，不得用于 promotion。

| symbol | evidence_status | full_return_pct | full_mdd_pct | full_sharpe | full_trades | post180_return_pct | post180_mdd_pct | post180_sharpe | post180_trades |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BTC/USDT:USDT | explore / untrusted: raw-normalized parity unavailable | -99.9993 | -99.9994 | -6.5068 | 5279 | -99.9990 | -99.9990 | -6.6885 | 4986 |
| ETH/USDT:USDT | explore / untrusted: raw-normalized parity unavailable | -96.3432 | -96.3655 | -5.9552 | 1546 | -94.1856 | -94.3418 | -6.3483 | 1277 |
| SOL/USDT:USDT | explore / untrusted: raw-normalized parity unavailable | -95.4927 | -95.5755 | -5.2235 | 1508 | -93.1514 | -93.9109 | -5.6349 | 1222 |
| BNB/USDT:USDT | explore / untrusted: raw-normalized parity unavailable | -97.4152 | -97.4937 | -7.0668 | 1523 | -94.3536 | -94.4954 | -6.8571 | 1214 |
| TRX/USDT:USDT | explore / untrusted: raw-normalized parity unavailable | -95.8331 | -95.8595 | -7.7877 | 1534 | -94.7317 | -94.9044 | -9.6745 | 1248 |

## 年份、市场状态与近期分片

逐版本的 `2025/2026`、strong-up/strong-down/range/transition，以及最近 `1d/7d/1m/3m/6m/1y` 明细保存在 [JSON](../artifacts/hype_15m_mdtp_v1_research_2026-07-31.json)。HYPE 历史只有约 14 个月，不足以证明跨年度稳定。

## 改善来源与限制

- 风险调整后改善门禁失败：full 未能同时提高 Sharpe、Calmar 并控制回撤。
- 滚动 fold 稳定性：正收益比例 0.00%。
- 可采信跨币种 post-180d 正收益 0/0；固定参数迁移不支持普适性。
- jump、extension、recovery、staging 与 score-decay 的独立作用以消融表为准；不因理论好看而保留。

限制：

- HYPE Binance perp history begins 2025-05-30, so HYPE has only partial 2025 and 2026 year buckets.
- Historical HYPE data in this repository was already examined by prior projects; rolling folds are chronological pseudo-OOS, not untouched prospective OOS.
- Only OHLCV and funding are used. Order-book depth, taker buy volume, open interest, liquidation flow, and basis are outside V1.
- V35 is HYPE-specific and historically selected on this sample; its matched-window results are a benchmark, not fresh OOS evidence.

## 证据

- [完整结果 JSON](../artifacts/hype_15m_mdtp_v1_research_2026-07-31.json)
- [主指标 CSV](../artifacts/hype_15m_mdtp_v1_metrics_2026-07-31.csv)
- [交易明细](../artifacts/hype_15m_mdtp_v1_trades_2026-07-31.csv)
- [调仓动作](../artifacts/hype_15m_mdtp_v1_actions_2026-07-31.csv)
- [权益曲线](../artifacts/hype_15m_mdtp_v1_equity_2026-07-31.csv)
- [参数稳定性](../artifacts/hype_15m_mdtp_v1_parameter_stability_2026-07-31.csv)
- [相邻窗口](../artifacts/hype_15m_mdtp_v1_window_stability_2026-07-31.csv)
- [跨币种](../artifacts/hype_15m_mdtp_v1_cross_asset_2026-07-31.csv)
- [复现脚本](../scripts/research_hype_15m_mdtp.py)
