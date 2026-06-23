# HYPE-5M-PBTR 指标组合 Ensemble 搜索

日期：2026-06-22

家族 id：`HYPE-5M-PBTR`

这是一轮 Binance HYPE 永续合约 `5m` 指标组合研究批次。它不是新的 `V35` 或 `V36` 定义，也不应并入更早的 `HYPE-EMA-X` EMA 金叉/死叉家族。

## 目标

在 `2025-06-01` 到 `2026-06-01` 的 Binance HYPE `5m` 数据上，搜索满足以下约束的策略：

- 胜率约 `80%`
- 年化倍数高于 `20x`
- 最大回撤优于 `-20%`

## 数据

- 交易所：Binance
- 市场：永续合约
- 标的：`HYPE/USDT:USDT`
- 周期：`5m`
- 窗口：`2025-06-01 00:00:00 UTC` 到 `2026-06-01 00:00:00 UTC`，右开
- 最终行数：`105120` 根 K 线
- 补齐后缺失 K 线：`0`

本地数据湖已有大部分 `5m` 数据。本轮补拉了 `2026-05-27 09:10:00 UTC` 到 `2026-06-01 00:00:00 UTC` 的尾部缺口。由于第一次尾部补拉覆盖了 `2026-05-27` 的局部分区，随后重新拉取并验证了完整的 `2026-05-27` 日分区。

## 执行假设

- 信号在当前 K 线收盘后确认。
- 下一根 K 线开盘进场。
- 基础模拟计入单边 `0.04%` 手续费和单边 `0.01%` 滑点。
- 如果同一根 `5m` K 线内同时触发止损和止盈，按先触发止损处理。
- 回撤计算包含收盘权益曲线和交易内 MAE 近似。
- Ensemble 模式同一时间只允许一笔持仓；跳过重叠交易和重复的 `signal_ts + side` 信号。

## 脚本

- `archive/scripts/research/research_hype_5m_indicator_search.py`
- `archive/scripts/research/research_hype_5m_filter_refinement.py`
- `archive/scripts/research/research_hype_5m_ensemble_combo.py`
- `archive/scripts/research/research_hype_5m_ensemble_ablation.py`
- `archive/scripts/research/render_hype_5m_ensemble_specs.py`

## 报告产物

本地报告文件位于 `reports/`，该目录下产物不进入 git：

- `hype_5m_indicator_search.json`
- `hype_5m_indicator_search_ranking.csv`
- `hype_5m_indicator_search_target_hits.csv`
- `hype_5m_indicator_search_top_trades.csv`
- `hype_5m_filter_refinement.json`
- `hype_5m_filter_refinement_ranking.csv`
- `hype_5m_filter_refinement_target_hits.csv`
- `hype_5m_filter_refinement_top_trades.csv`
- `hype_5m_ensemble_combo.json`
- `hype_5m_ensemble_combo_ranking.csv`
- `hype_5m_ensemble_combo_legs.csv`
- `hype_5m_ensemble_combo_selected_trades.csv`
- `hype_5m_ensemble_ablation.json`
- `hype_5m_ensemble_ablation_summary.csv`
- `hype_5m_ensemble_ablation_drop_leg.csv`
- `hype_5m_ensemble_ablation_leverage.csv`
- `hype_5m_ensemble_ablation_execution.csv`

## 搜索路径

第一阶段：

- 测试 `8000` 组人工设定和随机生成的 `5m` 指标配置。
- 生成 `64272` 行杠杆评估结果。
- 指标族包括 EMA 趋势状态、Donchian/通道状态、RSI、MACD、ADX、Choppiness、ATR 扩张、相对成交量、CMF、OBV、Bollinger 位置/宽度，以及 squeeze/reversion 变体。
- 没有任何单条原始策略同时满足三项目标。

第二阶段：

- 将最高收益和最高胜率候选送入入场时点过滤精炼。
- 围绕 `18` 个 base 候选评估约 `1.70M` 行近似过滤组合。
- 对 `216` 个过滤候选做 exact 复测。
- 没有任何单条精炼腿同时满足三项目标，但多个精炼腿达到 `85%` 到 `95%` 胜率，回撤接近或低于 `20%`。

第三阶段：

- 用精炼后的高胜率腿构建 one-position ensemble。
- 该 ensemble 是本轮搜索中第一个满足 full-period 三项目标的结果。

## 达标 Ensemble 结果

当前 ensemble 网格里一共只有以下 `7` 个 `target_pass=True` 组合；不是从更多达标组合里只摘取前 7 个。它们共享同一批精筛子腿，只是子腿数量和杠杆不同。

| 腿数 | 杠杆 | 年化倍数 | 最大回撤 | 胜率 | 交易数 | 样本内年化 | 样本内最大回撤 | 样本内胜率 | OOS 年化 | OOS 最大回撤 | OOS 胜率 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 4.0 | `121.31x` | `-19.22%` | `85.79%` | 570 | `258.92x` | `-19.22%` | `85.09%` | `12.79x` | `-18.35%` | `88.60%` |
| 16 | 2.5 | `50.29x` | `-18.85%` | `85.46%` | 839 | `95.66x` | `-18.81%` | `85.05%` | `7.46x` | `-18.85%` | `87.06%` |
| 8 | 3.0 | `37.65x` | `-14.49%` | `85.79%` | 570 | `66.63x` | `-14.49%` | `85.09%` | `6.92x` | `-13.98%` | `88.60%` |
| 12 | 2.5 | `36.43x` | `-17.63%` | `86.01%` | 686 | `71.96x` | `-17.63%` | `85.45%` | `4.83x` | `-15.48%` | `88.11%` |
| 5 | 3.0 | `25.22x` | `-16.67%` | `87.06%` | 456 | `46.87x` | `-16.67%` | `86.86%` | `4.01x` | `-11.31%` | `87.95%` |
| 16 | 2.0 | `23.34x` | `-15.29%` | `85.46%` | 839 | `39.10x` | `-15.26%` | `85.05%` | `5.05x` | `-15.29%` | `87.06%` |
| 8 | 2.5 | `20.82x` | `-12.18%` | `85.79%` | 570 | `33.53x` | `-12.18%` | `85.09%` | `5.06x` | `-11.73%` | `88.60%` |

## 实盘规格文档与消融

每个达标组合都有一份中文实盘代码规格文档，包含指标定义、信号生成、开仓、持有、平仓、子腿参数和消融实验。

- 规格索引：`docs/research/hype/families/ema-trend-breakout/ensemble-specs/README.md`
- `HYPE-5M-ENS-S01`: `ensemble-specs/hype-5m-ensemble-s01-8l-4x-live-spec.md`
- `HYPE-5M-ENS-S02`: `ensemble-specs/hype-5m-ensemble-s02-16l-2p5x-live-spec.md`
- `HYPE-5M-ENS-S03`: `ensemble-specs/hype-5m-ensemble-s03-8l-3x-live-spec.md`
- `HYPE-5M-ENS-S04`: `ensemble-specs/hype-5m-ensemble-s04-12l-2p5x-live-spec.md`
- `HYPE-5M-ENS-S05`: `ensemble-specs/hype-5m-ensemble-s05-5l-3x-live-spec.md`
- `HYPE-5M-ENS-S06`: `ensemble-specs/hype-5m-ensemble-s06-16l-2x-live-spec.md`
- `HYPE-5M-ENS-S07`: `ensemble-specs/hype-5m-ensemble-s07-8l-2p5x-live-spec.md`

消融覆盖三类：

- 删除单条子腿：逐一移除组合中每条精筛腿，重新按 one-position 规则评估。
- 杠杆消融：保持信号不变，只测试相邻杠杆。
- 执行门槛消融：比较单仓执行和取消单仓门槛后的去重信号序列。

## 更干净的候选

更适合作为后续研究候选的是 `5` 腿、`3x` 杠杆的 ensemble：

- 全周期：`25.22x` 年化，`-16.67%` 最大回撤，`87.06%` 胜率，`456` 笔交易。
- 样本内（`2025-06-01` 到 `2026-03-01`）：`46.87x`，`-16.67%`，`86.86%`，`373` 笔交易。
- 样本外切片（`2026-03-01` 到 `2026-06-01`）：`4.01x`，`-11.31%`，`87.95%`，`83` 笔交易。

这五条腿都属于 EMA 趋势状态下的回撤/偏离修复，或 Bollinger/EMA reversion 过滤：

1. `HYPE_5M_C0410`：EMA96/384 偏离回归，`stop_atr=6`，`tp_atr=1`；过滤条件为强 higher-timeframe 方向、成熟趋势年龄，以及未崩坏的 48-bar 方向 ROC。
2. `HYPE_5M_C0355`：EMA21/96 偏离回归，`stop_atr=4`，`tp_atr=0.75`；过滤条件为回撤 RSI、相对成交量和 Bollinger 宽度。
3. `HYPE_5M_C0332`：EMA12/96 Bollinger 回归，`stop_atr=6`，`tp_atr=1`；过滤条件为 EMA 距离和受控的 higher-timeframe 方向。
4. `HYPE_5M_C0337`：EMA12/96 偏离回归，`stop_atr=4`，`tp_atr=0.75`；过滤条件为 MACD 回撤、ADX 上限和 higher-timeframe 方向。
5. `HYPE_5M_C0230`：EMA96/384 偏离回归，`stop_atr=6`，`tp_atr=1`；过滤条件为高相对成交量、非低 choppiness，以及 ATR 百分比上限。

## 解释

单规则 `5m` 策略没有满足用户设定的三项约束。只有在把搜索转成“高胜率过滤腿的排序 ensemble”之后，目标才被 full-period 命中。

这个结果有研究价值，但也明显脆弱：

- 达标结果是在同一个完整年度样本上发现并评估的。
- OOS 切片保住了高胜率和低回撤，但没有保住 `20x` 年化。
- Ensemble 组成来自大量搜索试验，存在明显过拟合风险。
- 当前应视为研究候选，需要在未参与搜索的未来窗口和其他交易所数据上压力测试后，才有资格进入 promoted/live 讨论。

## 下一步

- 将 `5` 腿、`3x` ensemble 冻结为更干净的研究候选。
- 随着未来 Binance HYPE `5m` 新数据积累，滚动复测未见样本。
- 如果能拿到可比的 HYPE `5m` 永续数据，做交易所 holdout。
- 将过滤发现过程转成事件质量数据集，而不是继续手工扩展参数。
