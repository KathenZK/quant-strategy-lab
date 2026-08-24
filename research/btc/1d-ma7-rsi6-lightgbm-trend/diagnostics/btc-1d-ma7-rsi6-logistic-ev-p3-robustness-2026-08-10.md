# BTC-1D-MA7-RSI6 Logistic-EV P3 稳健性诊断

## 结论

P3 未通过新增稳健性门禁，validation 继续封存，无候选、无版本、无交易路径。

固定 `predicted EV > 1.00%` 后，combined 的表面指标仍为正：`47` 笔、`+15.10%`、PF `1.2620`、MDD `-24.82%`，原经济与排序门禁通过。但四折只有 `2/4` 绝对收益为正，`1.50%` 高 edge 压力线反而亏损 `-18.28%`，分层 bootstrap 净正概率仅 `60.94%`，远低于预注册 `95%`。

short-only 的方向一致性更好：`14` 笔、`+33.73%`、PF `2.9524`、MDD `-7.56%`，四折全正、双 edge 压力均通过、Spearman `0.2536`；但交易数低于 `30`，bootstrap 净正概率 `91.93%`，仍未过门禁。

## 数据与预注册一致性

- development 事件：`449`，event identity SHA256 与 P1/P2 完全一致。
- 外层 OOS 预测：`270`。
- P3 predicted-EV identity SHA256：`bfc70f555a464a7ce355c5df12d0485f243bd004395fdbddd87a8993b9e83ad4`。
- P3 与 P2 `logistic_ev_core` 的每个 event/fold predicted edge 最大绝对差为 `0`。
- 主 edge 固定 `1.00%`，未运行 edge 搜索；`0.50% / 1.50%` 仅作压力线。
- validation `2025-08-07` 至 `2026-08-06 UTC` 未读取；即使 P3 通过也预注册为必须人工再次批准。

完整规则见 [P3 稳健性合同](../specs/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-contract-2026-08-10.md)。

## Combined

### 主线

| Fold | 交易数 | 复合收益 | PF | 绝对正收益 | 优于 all-cross |
| --- | ---: | ---: | ---: | --- | --- |
| 1 | 9 | -5.92% | 0.766 | 否 | 是 |
| 2 | 16 | +14.28% | 1.653 | 是 | 否 |
| 3 | 9 | -11.03% | 0.626 | 否 | 是 |
| 4 | 13 | +20.33% | 2.109 | 是 | 是 |

汇总：

- 交易数 `47`
- 复合收益 `+15.10%`
- PF `1.2620`
- MDD `-24.82%`
- Spearman `0.1290`
- 最高 EV 五分位稳定折 `3/4`
- 优于 all-cross `3/4`
- 绝对正收益仅 `2/4`，失败

### Edge 压力

| Edge | 交易数 | 复合收益 | PF | 结果 |
| --- | ---: | ---: | ---: | --- |
| 0.50% | 71 | +81.68% | 1.6043 | 通过 |
| 1.50% | 26 | -18.28% | 0.5439 | 失败 |

提高 predicted edge 没有得到更好的 realized return，说明概率到 EV 的映射和尾部排序不稳定；`1.00%` 不是单调安全边界。

### 分层 bootstrap

- 迭代：`10,000`
- 交易：`47`
- `P(compounded return > 0) = 60.94%`
- `2.5% / 50% / 97.5%`：`-47.53% / +12.92% / +180.18%`

收益分布高度依赖少数大赢家，无法达到 `95%` 稳健性要求。

## 分腿

| 路线 | 交易数 | 收益 | PF | MDD | 正收益折 | Spearman | 双压力 | Bootstrap 净正概率 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| long-only | 33 | -13.93% | 0.8897 | -27.30% | 2/4 | 0.0091 | 失败 | 31.12% | 失败 |
| short-only | 14 | +33.73% | 2.9524 | -7.56% | 4/4 | 0.2536 | 通过 | 91.93% | 交易数与 bootstrap 失败 |

short-only 四折收益为 `+13.47% / +2.20% / +15.22% / +0.09%`。`0.50%` 压力为 `24` 笔、`+38.99%`、PF `2.3198`；`1.50%` 压力为 `9` 笔、`+8.09%`、PF `2.0522`。方向结构比 combined 稳定，但 `14` 笔不足以确认策略，bootstrap 仍有 `8.07%` 的负收益概率。

## 系数与“顶部/底部”解释

跨四折符号完全一致的高幅度 raw coefficient 包括：

- `close_location`：正；
- `upper_wick_atr`：正；
- `lower_wick_atr`：负；
- `ma7_slope_1_atr`、`ma7_slope_3_atr`：负；
- `rsi6_high80_last5`、`rsi6_low20_last5`：负；
- `side`：负。

这些符号稳定不等于已得到对称的顶部/底部规则。当前 Logistic 使用原始 K 线字段加一个 `side` 截距，无法表达“long 看下影线、short 看上影线”这类 `side × morphology` 交互；同一个 `upper_wick_atr` 系数会同时作用于 long 和 short。P3 的 short 优势可能来自全局方向偏置与线性边界，而不是已经识别出可泛化的镜像顶部形态。

因此不能把当前系数直接翻译成“上影线大就开空”或“下影线大就开多”。若继续研究形态，需要预注册方向对齐特征，例如：

- `side * body_atr`；
- long 使用 `close_location`、short 使用 `1-close_location` 的方向化收盘位置；
- long 的下影线 / short 的上影线作为同一个 rejection wick；
- `side * MA7 slope`；
- long 的 RSI 与 short 的 `100-RSI` 方向化阶段值。

这会构成新的特征合同，不能静默加入 P3。

## 决策

- P3：`failed robustness gate / validation not revealed / no candidate / no version / not promoted / not live-ready`。
- combined 的正收益不足以覆盖折间、edge 单调性和 bootstrap 风险。
- short-only 保留为低样本诊断线索，不取得 validation 资格。
- 不生成候选交易路径 HTML。
- 不建议继续在同一 BTC development 上微调 edge；下一步若继续，应引入预注册方向对齐特征，或建立独立多资产 pooled 研究以增加事件数，同时保留 BTC 最近一年封存。

## 复现证据

- [P3 脚本](../scripts/research_btc_1d_ma7_rsi6_logistic_ev_p3.py)
- [P3 机器摘要](../artifacts/p3_logistic_ev_robustness_2026-08-10/p3_development_summary.json)
- [P3 OOS 预测](../artifacts/p3_logistic_ev_robustness_2026-08-10/p3_outer_predictions.parquet)
- [P3 bootstrap 全样本](../artifacts/p3_logistic_ev_robustness_2026-08-10/p3_bootstrap_returns.parquet)
- [P3 系数稳定性](../artifacts/p3_logistic_ev_robustness_2026-08-10/p3_coefficient_stability.json)
- [P3 最终模型](../artifacts/p3_logistic_ev_robustness_2026-08-10/p3_final_logistic_ev_model.json)
- [P3 manifest](../artifacts/p3_logistic_ev_robustness_2026-08-10/p3_model_manifest.json)
