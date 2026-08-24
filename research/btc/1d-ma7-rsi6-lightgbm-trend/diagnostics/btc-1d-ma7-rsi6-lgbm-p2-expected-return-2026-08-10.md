# BTC-1D-MA7-RSI6-LGBM P2 Expected-Return 诊断

## 结论

P2 主模型未通过 development 门禁，最近一年 validation 继续封存，不登记版本、不生成候选交易路径。

把二分类改为直接预测成本后净收益后，核心 L2 LightGBM 不再退化为零交易，但 OOS 排序仍然太弱：combined 共 `64` 笔、复合收益 `+0.63%`、PF `1.0920`、MDD `-27.78%`；预测收益与实际收益 Spearman 仅 `0.0468`，最高五分位只在 `2/4` 折优于该折整体。PF 和两项排序门禁均失败。

P2 同时发现一个值得单独预注册的诊断线索：`logistic_ev_core` 对照达到 `70` 笔、`+80.49%`、PF `1.6132`、MDD `-26.97%`、Spearman `0.1290`，并通过 P2 的经济与排序阈值。但 P2 合同明确规定只有 `lgbm_l2_core` 可以取得 validation 资格，因此不能事后把 Logistic 对照改称 P2 主候选。

## 数据与一致性

- P2 重新生成 `449` 个 development 事件。
- Event identity SHA256：`941246a90a2fe403b6de152e1527bb4ed1890ee84fdb32095b3a2eb87a3fd529`。
- 行数和 hash 与 P1 完全一致；候选、退出、成本、funding、特征和标签均未改变。
- P2 只改变学习目标和 edge 决策：主目标为未缩尾固定 `1×` 成本后 `net_return`，主损失为 L2。
- edge 网格为 `0 / 0.25% / 0.50% / 1.00%`，严格使用 `predicted_edge > edge`。
- 每个 edge 必须在三个 inner fold 各至少 `5` 笔、合计至少 `15` 笔。
- 最近一年 `2025-08-07` 至 `2026-08-06 UTC` 未被读取、预测或画图。

完整预注册内容见 [P2 expected-return 合同](../specs/btc-1d-ma7-rsi6-lgbm-p2-expected-return-contract-2026-08-10.md)。

## 主模型结果

### Combined

- OOS 交易：`64`
- 复合收益：`+0.63%`
- PF：`1.0920`
- MDD：`-27.78%`
- long / short：`39 / 25`
- 四折收益：`-5.92% / +19.97% / +7.50% / -17.07%`
- 四折都优于各自 all-cross 基线，但绝对表现有两折为负。
- OOS Spearman：`0.0468`
- 最高预测五分位稳定折：`2/4`

### 分腿

| 路线 | 交易数 | 复合收益 | PF | MDD | Spearman | Top 五分位稳定折 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| combined | 64 | +0.63% | 1.0920 | -27.78% | 0.0468 | 2/4 | 经济与排序失败 |
| long-only | 39 | +0.69% | 1.1070 | -31.69% | -0.0335 | 2/4 | 经济与排序失败 |
| short-only | 25 | -0.05% | 1.0614 | -16.99% | 0.1253 | 4/4 | 排序通过，交易数/收益/PF失败 |

short 侧出现了比 combined 更好的排序，但没有形成可交易的绝对收益和样本覆盖，不能冻结为 short-only。

## 模型与目标消融

| 模型 | OOS Spearman | 交易数 | 复合收益 | PF | MDD | 经济门禁 | 排序门禁 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Ridge `MA+K+RSI` | 0.0767 | 55 | +5.42% | 1.149 | -26.53% | 失败 | 失败 |
| Logistic-EV `MA+K+RSI` | 0.1290 | 70 | +80.49% | 1.613 | -26.97% | 通过 | 通过 |
| LGBM L2 `MA-only` | -0.0165 | 30 | -7.58% | 0.938 | -27.10% | 失败 | 失败 |
| LGBM L2 `MA+K` | -0.0170 | 61 | -47.70% | 0.571 | -47.41% | 失败 | 失败 |
| LGBM L2 `MA+K+RSI` | 0.0468 | 64 | +0.63% | 1.092 | -27.78% | 失败 | 失败 |
| LGBM L2 `MA+K+RSI+VOL` | 0.0318 | 69 | -31.05% | 0.762 | -42.44% | 失败 | 失败 |
| LGBM Huber `MA+K+RSI` | 0.0468 | 64 | +0.63% | 1.092 | -27.78% | 失败 | 失败 |
| LGBM ATR-target diagnostic | 0.0025 | 78 | -1.31% | 1.078 | -27.66% | 失败 | 失败 |

结论：

1. K 线组加入 MA-only 后显著恶化，RSI6 再加入只能把收益拉回接近持平；仍没有稳定非线性 edge。
2. volume 再次没有增量，且明显恶化收益和 MDD。
3. ATR 目标没有改善跨时期可比性。
4. Huber 在本轮冻结的小数收益尺度上与 L2 产生完全相同的 OOS 预测和交易，未提供稳健性增量。
5. 简单 Logistic-EV 明显优于 LightGBM 和 Ridge，说明当前少量日线事件更适合低容量线性分类边界，而不是复杂收益幅度回归。

## Logistic-EV 线索的边界

Logistic-EV 的 combined OOS：

- 四折 edge：`1.00% / 0.50% / 0.00% / 1.00%`
- 四折收益：`-5.92% / +18.37% / +34.69% / +20.33%`
- 四折交易数：`9 / 22 / 26 / 13`
- 完整 development 的诊断 edge：`1.00%`
- long：`46` 笔、`+35.58%`、PF `1.4590`
- short：`24` 笔、`+33.12%`、PF `2.1022`

风险点：

- 第一折仍亏损；
- 四折使用的 edge 不固定；
- 每次 inner 选择中，所有合格 edge 的最差 inner-fold 收益仍为负，当前算法只是选择“最不差”的 edge；
- Logistic 是 P2 对照，不是预注册主模型；直接揭示 validation 会把事后模型替换混入一次性验证。

因此它只能作为 P3 预注册线索，不能直接取得 validation 使用权。

## 可解释性

核心 L2 LightGBM 的 mean-absolute SHAP 前项为：

1. `rsi6_max_5`
2. `ma7_slope_1_atr`
3. `prev_close_ma_gap_atr`
4. `range_atr`
5. `rsi6`

但主模型最高预测五分位的实际平均收益为 `-0.10%`，全局 Spearman 仅 `0.0468`。这些特征重要性只说明树使用了哪些字段，不证明存在稳定顶部/底部规律。`side`、`rsi6_low20_last5` 和 `rsi6_high80_last5` 仍未形成有效 split。

证据见 [SHAP 汇总](../artifacts/p2_expected_return_2026-08-10/p2_core_shap_summary.csv)与[特征分箱](../artifacts/p2_expected_return_2026-08-10/p2_core_feature_dependence.json)。

## 决策

- P2：`failed development gate / validation not revealed / no version / not promoted / not live-ready`。
- 完整 development 的 L2 诊断 edge 为 `1.00%`，但 `edge_for_future_validation=null`。
- 不生成候选交易路径 HTML。
- 不允许把 Logistic 对照事后替换为 P2 主模型并直接揭示 validation。
- 若继续，应建立 P3 Logistic-EV 合同，保持事件、特征和执行不变，先冻结最终 edge 与额外稳定性检查，再决定是否取得 validation 揭示资格。

## 复现证据

- [P2 研究脚本](../scripts/research_btc_1d_ma7_rsi6_lgbm_p2_expected_return.py)
- [P2 机器摘要](../artifacts/p2_expected_return_2026-08-10/p2_development_summary.json)
- [P2 事件](../artifacts/p2_expected_return_2026-08-10/p2_events.parquet)
- [P2 外层 OOS 预测](../artifacts/p2_expected_return_2026-08-10/p2_outer_predictions.parquet)
- [P2 外层 OOS SHAP](../artifacts/p2_expected_return_2026-08-10/p2_outer_shap.parquet)
- [P2 最终模型 manifest](../artifacts/p2_expected_return_2026-08-10/p2_final_core_model_manifest.json)
