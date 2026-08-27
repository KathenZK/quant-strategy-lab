# BIN-1D-MA7-RC-P0 全历史市场结构结果（2026-08-24）

## 结论先行

**结论：`PARTIAL YES`，但不是一个稳定、平滑、可直接部署的三维 regime engine。**

1. `Normalized Slope` 是唯一在多空两侧、MA5/7/10 与 major/long-tail 中持续保留方向区分力的变量；主要价值是识别多头假突破与空头延续。
2. `ER20` 不是“越高越容易延续”的通用过滤器：它在多头 1–10D 边际上有一定改善，但均值仍多为负；在空头 3–20D 反而大体随 ER 升高而恶化。
3. `RV percentile` 没有稳定单调关系；它更像与行情方向/阶段交互，而不是独立 continuation score。
4. 精确三维表中存在经济差异很大的 cells，并发现一个较强的空头候选 `Slope Q1 × ER Q3 × RV Q5`：20D mean `+11.77%`、`+1.08 ATR`、胜率 `78.86%`，raw/ATR 均通过 cell 内双向聚类与 BH-FDR，且 pre/post-2024、MA5/7/10 同号。但这是已揭示历史中的 cell，不能直接注册成策略规则。
5. 完整 125-cell 表面在 MA5/7/10 之间相关性高（10/20D raw `0.86–0.93`），但 `<2024` 与 `>=2024` 的相关性仅 `-0.03–0.26`，没有通过“跨时间稳定表面”要求。

因此，本轮支持“regime 能显著筛掉一部分 MA7 假突破，且能识别部分空头延续环境”，不支持“ER + Slope + RV 已形成对称、平滑、普适的 long/short 过滤器”。状态保持 `explore / diagnostic-only / not promoted / not live-ready`。

## 冻结合同与数据

- Frozen config SHA256：`15bc78f14bf3f7026440d778d849252e8ff0d1af1aa80d3d064bd569e850a84b`。
- 研究范围：Binance USD-M perpetual；官方 Binance Vision 月归档 + immutable Binance API legacy partitions。
- UTC 数据：`2019-09-08 17:45` 至 `2026-06-30 23:45`；全市场一致 cutoff `<2026-07-01`。
- 输入：选后 `56,358,042` 根 `15m` K，790 个 canonical contracts。
- ETH 的 `158,976` 个跨源重叠键固定 Vision 优先；来源内部重复、选后重复、critical null、未闭合 K、OHLC 违规均为 `0`。
- UTC 日聚合：`586,612` 个完整日 K；`817` 个不满 96 根的 partial UTC days 排除。
- `657/790` 个合约至少有 120 个完整日；完整 252-RV warm-up 后实际 eligible 为 `549` 个合约、`351,335` 个日状态。
- 历史退市合约保留，不用当前 `exchangeInfo` 回填历史 universe。

完整数据审计见 [data quality JSON](../artifacts/binance_1d_ma7_rc_p0_data_quality_audit.json) 与 [universe inventory](../artifacts/binance_1d_ma7_rc_p0_universe_inventory.csv)。

## 样本与无条件基线

| MA | Long events | Short events |
| ---: | ---: | ---: |
| 5 | 46,514 | 46,649 |
| 7 | 37,916 | 38,018 |
| 10 | 30,924 | 31,054 |

MA7 无条件 raw expectancy：

| Horizon | Long mean | Long win rate | Long clustered t | Short mean | Short win rate | Short clustered t |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1D | +0.04% | 46.73% | 0.22 | +0.10% | 50.91% | 0.55 |
| 5D | -0.60% | 43.95% | -1.41 | +0.44% | 54.43% | 1.07 |
| 10D | -0.90% | 43.17% | -1.55 | +0.69% | 56.90% | 1.12 |
| 20D | -0.99% | 39.82% | -1.14 | +1.21% | 59.95% | 1.48 |
| 40D | -2.27% | 37.09% | -1.76 | +2.72% | 63.60% | 2.25 |

这说明历史动态合约池本身存在明显 long/short 非对称；regime 结果必须相对该基线解释，不能把所有空头正收益都归因于三维过滤器。

## 单变量分桶

### Normalized Slope

Slope 的内部 quintile edges 为 `[-0.13088, -0.06192, -0.00448, 0.05726] ATR/day`。Q1 最负，Q5 最正。

| Direction / horizon | Direction-aligned bucket | Mean | 95% clustered CI | t-stat | Win rate | Opposite bucket mean | Q spread |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long 10D | Q5 | +0.71% | [-0.84%, +2.26%] | 0.90 | 45.09% | Q1 -3.20% | +3.91% |
| Long 20D | Q5 | +0.82% | [-1.53%, +3.17%] | 0.69 | 40.57% | Q1 -4.07% | +4.90% |
| Short 10D | Q1 | +2.68% | [+0.89%, +4.47%] | 2.93 | 60.88% | Q5 -0.83% | +3.52% |
| Short 20D | Q1 | +3.87% | [+1.48%, +6.27%] | 3.17 | 64.59% | Q5 -1.11% | +4.98% |

解释：Slope 对 5–20D 的顺序关系强，但多头侧更像“Q1 明确失败、Q5 只回到接近零或弱正”，而不是 Q5 已有强正 alpha；空头侧 Q1 的正 expectancy 更清楚。

稳健性：

- MA5/7/10 的 10D slope spread，long 为 `+3.46% / +3.91% / +4.18%`，short 为 `+2.82% / +3.52% / +4.05%`。
- Major 10D long Q5/Q1 为 `+2.18% / -4.55%`，long-tail 为 `+0.38% / -3.08%`。
- Major 10D short Q1/Q5 为 `+2.61% / -1.60%`，long-tail 为 `+2.69% / -0.65%`。
- 逐年不稳定：2022、2024、2026 的部分方向/期限出现 spread 缩小或翻转；不能把全样本 slope monotonicity 当成每年恒定规律。

### ER20

- Long：1–10D 的 aligned Spearman 多为 `0.7`，但 10D Q1→Q5 mean 仅从 `-0.84%` 改善到 `-0.22%`；20D 非单调，40D 反转。
- Short：3–10D 的 aligned Spearman 为 `-0.9` 左右；10D ER Q1/Q2/Q3/Q4/Q5 mean 为 `+1.12% / +1.26% / +1.11% / +0.64% / -1.69%`。
- 结论：高 ER 不等于 MA cross 后必然延续；在 short cross 中，高 ER 可能对应旧趋势末端或反转后的迟到信号。

### RV percentile

- Long 10D 五桶均值全部为负；20D 中间桶接近零，高低两端更差。
- Short 10D 没有单调关系；20D/40D 高 RV 桶更强，但这种关系与样本的下行阶段/退市资产暴露纠缠。
- 结论：RV 只能作为交互变量，不能单独形成稳定 admission rule。

单变量全表见 [single-variable CSV](../artifacts/binance_1d_ma7_rc_p0_single_variable_stats.csv) 与 [marginal SVG](../figures/binance_1d_ma7_rc_p0_single_variable_expectancy.svg)。

## 三维 Conditional Expectancy

下表列出经济意义最清楚的 exposed historical cells；它们不是预先选择的候选。

| Direction / horizon | Slope / ER / RV | n / symbols / dates | Raw mean | ATR mean | Win rate | Raw clustered t / BH q | ATR clustered t / BH q | 解释 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Long 10D | Q5 / Q5 / Q3 | 193 / 133 / 105 | +4.94% | +0.56 | 53.37% | 2.03 / 0.263 | 2.19 / 0.206 | 方向/效率高、RV 中等；正向但未过 FDR |
| Long 10D | Q1 / Q1 / Q3 | 216 / 154 / 67 | -11.55% | -1.37 | 16.20% | -5.70 / 0.000002 | -6.42 / <0.000001 | 明确假突破集中区 |
| Long 20D | Q4 / Q4 / Q4 | 126 / 106 / 87 | +9.27% | +1.12 | 49.21% | 1.54 / 0.340 | 1.53 / 0.418 | 右尾抬均值，median 仍 -0.82%；不稳健 |
| Long 20D | Q1 / Q3 / Q5 | 111 / 82 / 58 | -12.46% | -1.26 | 22.52% | -3.52 / 0.006 | -3.36 / 0.017 | 负 slope + high RV 的假多头 |
| Short 10D | Q1 / Q1 / Q1 | 189 / 134 / 83 | +7.07% | +1.24 | 73.02% | 3.27 / 0.044 | 2.50 / 0.164 | raw 通过 FDR，ATR 未通过；次强候选 |
| Short 20D | Q1 / Q3 / Q5 | 175 / 129 / 62 | +11.77% | +1.08 | 78.86% | 6.20 / <0.000001 | 5.67 / <0.000001 | 最强支持的短延续 cell |
| Short 20D | Q5 / Q5 / Q2 | 178 / 109 / 100 | -12.72% | -1.84 | 38.20% | -2.39 / 0.175 | -2.51 / 0.116 | 方向反向 + 高 ER；经济上差但 FDR 未过 |

`Short 20D S1/E3/R5` 的补充稳定性：

- MA5 / MA7 / MA10 full means：`+11.50% / +11.77% / +10.12%`。
- MA7 `<2024 / >=2024`：`+13.84% / +11.06%`。
- 六个事件年中 5 年为正；2023 为 `-7.72%`，但只有 11 个 events。2025 占 85/175 events，仍存在年份集中风险。

`Long 10D S1/E1/R3` 的负向结果在 MA5/7/10 与 pre/post-2024 均为负，是比任何 long 正向 cell 更稳定的结论。

完整三维表见 [three-way CSV](../artifacts/binance_1d_ma7_rc_p0_three_way_stats.csv)；交互检查见 [dashboard](../artifacts/binance_1d_ma7_rc_p0_interactive_dashboard.html)。

## 表面平滑与跨期稳定

| Direction / horizon | Reliable cells | FDR-significant positive / negative | Neighbor roughness / cell SD | Pre/Post Spearman | MA5/MA7 | MA10/MA7 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long 10D | 115/125 | 0 / 10 | 0.693 | 0.080 | 0.872 | 0.863 |
| Long 20D | 115/125 | 0 / 9 | 0.792 | 0.100 | 0.913 | 0.905 |
| Short 10D | 115/125 | 2 / 0 | 0.742 | 0.257 | 0.929 | 0.907 |
| Short 20D | 115/125 | 6 / 0 | 0.711 | -0.028 | 0.894 | 0.878 |

相邻 cell 的平均跳变约为 cell 横截面标准差的 `69%–79%`，不算平滑；更关键的是 pre/post rank correlation 接近零。MA 周期邻域相关性高，说明结构不是只对 MA7 的偶然，但时间稳定门仍失败。

## 数据质量、样本偏差与解释限制

1. **全市场 cutoff 滞后。** 为保持 790 合约同源全市场完整性，本轮截止 `2026-06-30`，没有混入只有 7 币更新到 8 月的尾部。
2. **历史左截断。** 3 个早期合约在 archive 起点附近左截断；252-RV warm-up 让它们的首段信号更保守，但不能声称拥有交易所上线以来的绝对完整历史。
3. **新合约 warm-up 排除。** 790 个 archive symbols 中只有 549 个具备完整 regime context；这是因果可用性要求，不是按结果筛币。
4. **Informative censoring。** 40D 有效样本从 long `37,916` 降至 `36,052`（-4.92%）、short `38,018` 降至 `35,941`（-5.46%）。退市或数据末端缺少 future close 的事件不会进入该 horizon，可能低估退市尾部风险。
5. **不是可执行回测。** 收益从 trigger close 到 future close，不含 next-open、fee、slippage、funding、借币/空头可执行性、容量和同日多信号账户约束。
6. **分位边界是 exposed historical 描述。** Slope/ER edges 由全历史 eligible state 分布一次性生成，不是部署时的 expanding/rolling causal calibration；若转成 filter 必须另冻 calibration 与 prospective OOS。
7. **资产类型混合。** 按用户口径保留全部 USDT-style perpetual contracts，不用当前 metadata 事后剔除；对 crypto、稳定币暴露、指数/代币化资产没有另做类型选择。
8. **依赖与多重检验。** 推断已按 symbol 与 event date 双向聚类，三维 cell 已做 BH-FDR；仍不能消除 post-hoc 解读与跨 horizon 重复观察。

## 最终判定与下一门禁

- **正 expectancy：** 最强 historical evidence 是 `Short / Slope Q1 / ER Q3 / RV Q5 / 20D`；`Short / Q1/Q1/Q1 / 10D` 次之但 ATR-FDR 不通过。Long 正向 cells 仅为候选，均未同时通过 raw/ATR FDR。
- **近似随机：** 大部分中间 slope 桶与 RV 中间桶的 cluster CI 跨 0；它们不能提供稳定 admission。
- **假突破/负 expectancy：** Long 的 Slope Q1 是最稳定集中区，尤以 `Q1/Q1/Q3 10D` 与 `Q1/Q3/Q5 20D` 明显；方向与慢 slope 相反时应优先视为 rejection signal。
- **三维稳定性：** 精确 cells 有强差异，但完整表面不平滑、跨时间相关性低，故未通过“稳定、平滑、可解释三维 regime”门禁。

推荐的下一步不是在本结果上搜更多 cell，而是预先冻结两个最小增量问题：

1. `Slope-only` rejection control 对比固定 `Short S1/E3/R5`，检验 ER/RV 是否真正提供 slope 之外的增量；
2. 从 `2026-07-01` 之后开始 prospective observation，使用预先冻结的 causal quantile calibration，不得按这次的逐年结果回调边界。

在新证据完成前，本线保持 `NO-GO for promotion / not live-ready`。

## 产物地图

- [Machine summary](../artifacts/binance_1d_ma7_rc_p0_summary.json)
- [Artifact manifest](../artifacts/binance_1d_ma7_rc_p0_artifact_manifest.json)
- [Event panel](../artifacts/binance_1d_ma7_rc_p0_events.parquet)
- [Robustness CSV](../artifacts/binance_1d_ma7_rc_p0_robustness_stats.csv)
- [Surface diagnostics CSV](../artifacts/binance_1d_ma7_rc_p0_surface_diagnostics.csv)
- [MA-neighborhood SVG](../figures/binance_1d_ma7_rc_p0_ma_neighborhood_robustness.svg)
- [Long 10D heatmap](../figures/binance_1d_ma7_rc_p0_long_10d_three_way.svg)
- [Short 20D heatmap](../figures/binance_1d_ma7_rc_p0_short_20d_three_way.svg)
