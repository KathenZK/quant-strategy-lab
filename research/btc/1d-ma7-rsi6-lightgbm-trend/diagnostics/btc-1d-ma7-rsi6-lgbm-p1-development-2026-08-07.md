# BTC-1D-MA7-RSI6-LGBM P1 Development 诊断

## 结论

P1 未通过 development 门禁，最近一年 validation 保持封存，不能登记版本、生成候选交易路径或进入 promotion。

失败不是因为样本为空：development 内形成 `449` 个完整 MA7 穿越事件，外层 walk-forward 有 `270` 个 OOS 事件。核心 `MA+K+RSI` LightGBM 的四折平均 ROC AUC 仅 `0.5043`，概率与标签的 OOS Spearman 相关仅 `0.0307`，没有稳定排序能力；预注册阈值最终没有选择任何 OOS 交易。

## 数据与执行口径

- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 日线：`2019-09-09` 至 `2025-08-06 UTC`，`2,159` 根，只用于闭合日信号和指标。
- 小时路径：`2019-09-08 18:00` 至 `2025-08-06 23:00 UTC`，`51,822` 根，只用于 stop 首次触发、gap fill、MFE 和 MAE。
- funding：`2019-12-23 08:00` 至 `2025-08-06 16:00 UTC`，`6,161` 条；实际 rate，优先使用 funding endpoint mark，历史空值使用同一名义 `8h` bucket 的官方 mark-price kline open。
- 成本：每 fill 手续费 `0.001`，每 fill 不利滑点 `4 bps`，另计 funding。
- 仓位：固定 `1×`；事件日收盘确认，次日开盘入场。
- 退出：RSI6 `80/20` 极值后反向确认、反向严格 MA7 穿越、固定入场 `3×ATR7` stop，三者最先发生者。
- 最近一年 `2025-08-07` 至 `2026-08-06 UTC` 未被模型、阈值、图表或本报告读取。

完整公式与预注册门禁见 [P1 development 合同](../specs/btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)；数据质量见 [日 K 审计](../artifacts/btcusdt_perp_1d_data_quality_2026-08-07.json)、[1h stop-path 审计](../artifacts/btcusdt_perp_1h_stop_path_quality_2026-08-07.json)和[funding/mark 审计](../artifacts/btcusdt_funding_mark_quality_2026-08-07.json)。

## 标签与退出结构

`449` 个完整事件中，正标签 `124` 个，正标签率 `27.62%`；long `224` 个，short `225` 个。平均正收益为 `+7.20%`，平均非正收益为 `-3.23%`，按全样本平均盈亏描述性计算的 break-even 正标签概率约为 `30.96%`。

| 退出原因 | 事件数 | 正标签率 | 平均净收益 | 中位净收益 |
| --- | ---: | ---: | ---: | ---: |
| 反向 MA7 穿越 | 388 | 17.27% | -2.20% | -2.17% |
| RSI6 极值后反向确认 | 53 | 96.23% | +12.34% | +10.42% |
| RSI6 与 MA7 同时触发 | 6 | 100.00% | +10.56% | +8.84% |
| 固定 `3×ATR7` stop | 2 | 0.00% | -10.73% | -10.73% |

RSI6 退出在实际发生后对应的交易几乎都盈利，但这是事后退出分类，不是可用于入场的先验特征。P1 的真正问题是：穿越发生时的 MA7/K 线/RSI6 状态无法稳定预测该趋势之后是否会走到 RSI 极值并产生大赢家。不得把未来 `exit_reason` 回填为输入特征。

## 模型与消融

以下全部为四个外层 walk-forward fold 的 OOS 结果。`Selected` 是按每折过去数据从 `0.50/0.55/0.60/0.65` 预注册网格选择后的交易数和复合收益。

| 模型 | 四折平均 AUC | P 与标签 Spearman | P 与净收益 Spearman | Selected | Selected 收益 | 最高概率五分位平均净收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic `MA+K+RSI` | 0.5697 | 0.1289 | 0.1303 | 2 | -2.25% | +0.90% |
| LGBM `MA-only` | 0.4749 | -0.0455 | -0.0407 | 0 | 0.00% | -0.71% |
| LGBM `RSI-only` | 0.4913 | 0.0364 | -0.0227 | 5 | -10.80% | +0.31% |
| LGBM `MA+K` | 0.4458 | -0.0792 | -0.0615 | 0 | 0.00% | -0.95% |
| LGBM `MA+K+RSI` | 0.5043 | 0.0307 | 0.0356 | 0 | 0.00% | +0.10% |
| LGBM `MA+K+RSI+VOL` | 0.5078 | 0.0250 | 0.0289 | 0 | 0.00% | -0.21% |

结论：

1. LightGBM 主模型没有学到可迁移的事件排序，加入 K 线形态、RSI6 或成交量均未形成稳定增量。
2. 成交量消融未改善排序；不能把 volume 升为主特征。
3. Logistic 的排序略好于 LightGBM，但仍很弱，且预注册交易只有两笔、全部亏损，不能据此形成候选。
4. 由于正标签基准率仅 `27.62%` 且平均赢家大于平均输家，`P(take) >= 0.50` 对本标签非常保守；不过核心 LightGBM 的概率排序本身接近随机，因此仅把阈值下调不能被解释为已解决问题。

## 基线与门禁

核心模型对应的全部外层 OOS 严格穿越基线：

- combined：`270` 笔，收益 `-72.07%`，PF `0.8375`，MDD `-73.53%`；
- long-only：`135` 笔，收益 `-25.67%`，PF `0.9773`，MDD `-49.54%`；
- short-only：`135` 笔，收益 `-62.42%`，PF `0.6953`，MDD `-69.64%`。

核心模型 combined、long-only、short-only 都选择 `0` 笔，未满足 development 最少 `30` 笔和 PF `>=1.20`。空仓相对亏损基线看似“更好”不是策略通过：零交易不具备趋势策略证据。

完整 development 上的阈值排序结果因 `0.60/0.65` 都产生零交易而选出较低的诊断阈值 `0.60`；由于路线门禁失败，该阈值没有 validation 使用权，机器 manifest 中 `validation_authorized=false`。

## 可解释性

OOS mean-absolute SHAP 前四项为：

1. `rsi6_max_5`
2. `upper_wick_atr`
3. `ma7_slope_3_atr`
4. `range_atr`

但这些特征的五分位标签率和净收益都不是稳定单调关系，四折 AUC 也没有相应改善。`rsi6_low20_last5`、`rsi6_high80_last5` 与 `side` 没有进入核心树的有效 split。当前证据不支持提炼“某个 RSI6 值 + 某种影线就是可靠顶部/底部”的简化规则。

SHAP 明细与分箱关系见 [SHAP 汇总](../artifacts/p1_development_2026-08-07/p1_core_shap_summary.csv)和[特征分箱](../artifacts/p1_development_2026-08-07/p1_core_feature_dependence.json)。

## 决策与后续边界

- P1：`failed development gate / validation not revealed / no version / not promoted / not live-ready`。
- 不生成候选交易路径 HTML，因为没有 coherent candidate。
- 不允许在现有 P1 名义下事后降低阈值并揭示 validation。
- 若继续 P2，应先写新合同，并仍只使用 development。合理方向是把经济目标改为 expected net return：使用收益回归，或用校准后的 `P(win) × avg_win + P(loss) × avg_loss` 决策；Logistic 可作为主对照，因为本轮它比 LightGBM 更稳定。任何 P2 仍需重新通过完整 development 门禁，才能取得一次性 validation 揭示资格。

## 复现证据

- [P1 研究脚本](../scripts/research_btc_1d_ma7_rsi6_lgbm_p1.py)
- [P1 机器摘要](../artifacts/p1_development_2026-08-07/p1_development_summary.json)
- [事件与标签](../artifacts/p1_development_2026-08-07/p1_events.parquet)
- [外层 OOS 预测](../artifacts/p1_development_2026-08-07/p1_outer_predictions.parquet)
- [外层 OOS SHAP](../artifacts/p1_development_2026-08-07/p1_outer_shap.parquet)
- [最终 development 诊断模型 manifest](../artifacts/p1_development_2026-08-07/p1_final_core_model_manifest.json)
