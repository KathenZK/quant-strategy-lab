# BIN-1D-MA7-RSI6-DAPML P1 Pooled Development 诊断

## 结论

P1 失败，不具备 validation 揭示资格。五资产把事件数从 BTC 单资产 `449` 扩到 `2,091`，但方向对齐 Logistic-EV 在新时间和未见资产上都没有正向排序能力；方向对齐改写也没有优于 raw 特征对照。

共同 sealed period 保持未揭示：`validation_eligible=false`，`validation_authorized=false`。

## 研究口径

- 市场：Binance USD-M perpetual；BTC/ETH/BNB/SOL/TRX
- signal / path：完整 UTC `1d` / direct `1h`
- development：各资产起点至 `2025-08-06 UTC`
- 成本：每 fill fee `0.001`、不利 slippage `4 bps`、官方实际 funding
- 样本：`2,091` 个严格 SMA7 穿越事件；event hash 与 P0 完全一致
- 模型：asset-balanced Logistic-EV aligned 主候选；raw Logistic 对照；aligned LightGBM 诊断
- edge：combined / long-only / short-only 每条路线独立、每折只在过去数据内从 `0 / 0.50% / 1.00%` nested 选择
- 指标边界：以下复合收益是 equal-event 诊断，不是考虑同时持仓和总杠杆后的组合收益

## 主模型：Temporal OOS

| Route | Trades | Compound | PF | Mean/trade | Positive folds | Spearman | Bootstrap P(>0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| combined | 520 | −85.11% | 0.932 | −0.158% | 1/4 | −0.044 | 9.32% |
| long-only | 256 | −41.53% | 1.013 | +0.032% | 3/4 | −0.112 | 30.09% |
| short-only | 166 | −35.70% | 0.965 | −0.077% | 1/4 | +0.031 | 26.94% |

没有路线通过：

- combined 的事件数和资产覆盖充足，但绝对收益、PF、正收益折、排名和 bootstrap 同时失败。
- long-only 虽有 `3/4` 正收益折，平均每笔仅 `+0.032%`，明显低于同期 all-cross long 的 `+0.441%`；复合仍为负，Spearman 反向。
- short-only 只是在部分亏损基线上少亏，不能形成绝对正 edge。

## Leave-one-asset + Time OOS

| Route | Trades | Compound | PF | Mean/trade | Positive assets | Spearman |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| combined | 506 | −80.08% | 0.960 | −0.095% | 1/5 | −0.030 |
| long-only | 291 | −22.08% | 1.071 | +0.168% | 2/5 | −0.089 |
| short-only | 228 | −44.86% | 0.969 | −0.069% | 2/5 | +0.033 |

主模型未学到可迁移的 universal 事件质量关系。Combined 只有 held-out BNB 为正；long-only 只有 ETH/BNB 为正；short-only 只有 BTC/SOL 为正。

## 方向对齐消融

| Route | Temporal aligned / raw mean | LOAO aligned / raw mean | Aligned 胜出资产 |
| --- | ---: | ---: | ---: |
| combined | −0.158% / +0.023% | −0.095% / +0.027% | 1/5 |
| long-only | +0.032% / +0.241% | +0.168% / +0.142% | 3/5 |
| short-only | −0.077% / +0.018% | −0.069% / −0.895% | 4/5 |

方向对齐并没有解决此前怀疑的结构问题：

- combined 在 temporal 与 LOAO 都显著差于 raw；
- long-only 只在 LOAO 有改善，temporal 明显退化；
- short-only 只在 LOAO 少亏，temporal 反而差于 raw；
- 三条路线的预注册消融门禁全部失败。

因此，不能把失败归因于“只差一个 side-aligned 变换”；更根本的问题是这些 MA7/K 线/RSI6 状态对完整交易收益缺乏稳定的跨时期排序关系。

## LightGBM 诊断

Aligned LightGBM 也未通过：

- temporal combined：`370` 笔、`−63.18%`、PF `0.994`、Spearman `−0.038`；
- temporal long-only：`220` 笔、`+9.02%`、PF `1.137`、仅 `2/4` 正收益折、平均每笔 `+0.340%` 低于 baseline `+0.441%`、Spearman `−0.058`、bootstrap `52.18%`；
- LOAO long-only：`245` 笔、`+12.05%`、PF `1.146`、仅 `3/5` 资产为正，Spearman 仍为 `−0.065`。

LOAO long 的经济表面不能单独升级为候选：它没有时间稳定性，预测值排序方向仍错误，本合同也明确规定 LightGBM 只是诊断对照。

## 可解释性

Logistic 四折中符号稳定且幅度最大的关系是：

- `aligned_rsi6`：四折均正，平均系数 `+0.462`；
- `directional_rsi_extreme_5`：四折均负，平均 `−0.403`；
- `aligned_ma7_slope_3_atr`：四折均正，平均 `+0.150`；
- `counter_rsi20_last5`：四折均负，平均 `−0.142`。

这看似描述“候选方向 RSI 较强、但最近五日过度极端不利”的局部关系；然而主模型 OOS Spearman 为负，不能提炼为可用简化规则。

用户关注的顶部/底部 K 线形态也不稳定：

- `rejection_wick_atr` 只有 `3/4` 折同号；
- `opposition_wick_atr` 为 `2/4`；
- `aligned_close_location` 为 `2/4`。

目前没有证据支持一套跨资产通用的“影线/收盘位置 + MA7”顶部底部判定规则。

## Development-end recent slices

窗口锚定统一 development 数据末日 `2025-08-06`，只作 audit：

| Slice | Trades | Compound | PF |
| --- | ---: | ---: | ---: |
| 1d | 0 | 0.00% | 0.000 |
| 7d | 1 | −3.50% | 0.000 |
| 1m | 4 | −0.88% | 0.930 |
| 3m | 36 | +17.83% | 1.403 |
| 6m | 91 | −44.13% | 0.864 |
| 1y | 153 | −42.34% | 0.959 |

短暂的 `3m` 正结果被 `6m/1y` 明确否定，不能作为继续推进理由。

## 决定

- P1 `HARD-GATE-FAILED / explore / not promoted / not live-ready`。
- 不揭示 BTC 或其他资产的共同 sealed year。
- 不在同一 `MA7 + 5日K线 + RSI6 + 当前退出标签` 上继续 edge、树容量或特征符号微调。
- LightGBM LOAO-long 只保留为非平稳性诊断，不登记版本、不生成交易路径 HTML。
- 若未来重开，必须改变可辨识目标或交易机制，而不是在本批 development 结果上继续挑参数。

## 证据

- [P1 合同](../specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-contract-2026-08-10.md)
- [P1 compact summary](../artifacts/p1_pooled_development_2026-08-10/p1_summary.json)
- [P1 full report](../artifacts/p1_pooled_development_2026-08-10/p1_report.json)
- [P1 interpretability](../artifacts/p1_pooled_development_2026-08-10/p1_interpretability.json)
- [P1 model states](../artifacts/p1_pooled_development_2026-08-10/p1_model_states.json)
- [P1 engine](../scripts/research_binance_1d_ma7_rsi6_dapml_p1.py)
