# Binance 1D MA7 P2-F Frontier Tail-State 归因裁决

## 结论

P2-F 对 P2-E growth、risk、balanced 三个 frontier strata 各取固定前 `100`，去重得到 `236` 个共享 pair、`472` 条资产路径，并逐条重放真实 ordered `1h` 最大回撤事件。预注册的三个机制方向均未达到跨 BTC/ETH、跨三个 strata 的最低 `60%` 覆盖门：

| Mechanism | 最低 asset×stratum 覆盖 | Gate |
| --- | ---: | --- |
| `SLOW_REGIME_SMA30` | `43%` | FAIL |
| `SLOW_REGIME_SMA90` | `38%` | FAIL |
| `SLOW_REGIME_SMA200` | `22%` | FAIL |
| `VOL_STATE` | `11%` | FAIL |
| `LIFECYCLE` | `18%` | FAIL |

因此不把 slow MA、NATR 高波动锁或 HYPE 式 OAPP/lifecycle 直接移植为下一候选，也不把多个弱标签组合救参。本轮状态为 `explore / not promoted / not live-ready`；无版本登记、无 audit/prospective 读取。

## 冻结范围

- 合同：[P2-F frontier tail-state 归因合同](../specs/binance-1d-ma7-p2f-frontier-tail-state-attribution-contract-2026-08-12.md)
- Parent：[P2-E hard-MDD 裁决](binance-1d-ma7-p2e-hard-mdd-shared-search-2026-08-12.md)
- Development：`2019-12-24` 至 `2025-08-07` exclusive
- Growth：两资产较低终值最高前 `100`
- Risk：两资产最差 ordered MDD 最好前 `100`
- Balanced：预注册 log-equity / excess-MDD score 前 `100`
- 去重：`236` pairs；每个资产只取全账户最深 ordered MDD event

## 跨层覆盖率

### BTCUSDT

| Stratum | SMA30 conflict | SMA90 conflict | SMA200 conflict | NATR>=P80 | Closed-daily lifecycle |
| --- | ---: | ---: | ---: | ---: | ---: |
| growth | `44%` | `48%` | `73%` | `40%` | `33%` |
| risk | `52%` | `38%` | `50%` | `11%` | `18%` |
| balanced | `48%` | `48%` | `74%` | `33%` | `31%` |

### ETHUSDT

| Stratum | SMA30 conflict | SMA90 conflict | SMA200 conflict | NATR>=P80 | Closed-daily lifecycle |
| --- | ---: | ---: | ---: | ---: | ---: |
| growth | `46%` | `68%` | `22%` | `15%` | `46%` |
| risk | `43%` | `53%` | `30%` | `20%` | `34%` |
| balanced | `54%` | `70%` | `25%` | `16%` | `35%` |

SMA200 在 BTC growth/balanced 有高覆盖，但 ETH 只有 `22%–30%`，明显不具备共享机制一致性；SMA90 在 ETH 较高，但 BTC 最低 `38%`。按合同不能分别挑资产专属 horizon 后再称为共享参数。

## Lifecycle 口径修复

初始重放若把事件小时的 favorable extreme 计入 MFE，会得到伪 `100%` lifecycle 覆盖；原因是 ordered MDD 的小时内部本就采用保守 `favorable -> adverse` 顺序。同一小时 high/low 的真实先后未知，且事件发生前无法用完整小时 high/low 执行利润保护。

最终门只使用事件日前一根完整日线 close 之前的 MFE；事件小时 high/low 仅保留为描述字段。修复后 lifecycle 最低覆盖由伪 `100%` 降至真实 `18%`，因此不能用该初值授权 OAPP。

## 更关键的因果线索

| Asset / side | Events | Median trade age | Median ordered MDD | Median prior-daily-close MFE | Lifecycle coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC long | `138` | `1.00d` | `-29.46%` | `0.00%` | `42.03%` |
| BTC short | `98` | `0.83d` | `-31.06%` | `0.00%` | `4.08%` |
| ETH long | `190` | `1.83d` | `-35.43%` | `0.00%` | `44.21%` |
| ETH short | `46` | `1.67d` | `-31.14%` | `0.00%` | `17.39%` |

最大回撤事件的中位发生时间只有入场后 `0.83–1.83d`，四个 asset×side 的 prior-daily-close MFE 中位数均为 `0`。这说明 frontier 尾部更像是**入场后的早期方向/时机错误**，不是已有浮盈被长期回吐；利润保护天然来不及覆盖大部分事件。

事件也不是单一 crash regime：BTC 主要分散于 2021、2022、2023，ETH 虽有 `2020-04` 和 `2020-11` 聚类，仍跨到 2021、2022、2024。单纯封锁高波动或某个 calendar episode 不是稳定解释。

## 后续边界

- 关闭：把 `SMA30/90/200` level+slope gate、NATR percentile lock 或 closed-daily MFE giveback 单独作为 P2-G；
- 禁止：把这些未过 `60%` 的弱标签组合，或按 BTC/ETH 分别选最有利阈值；
- 保留结论：风险主要发生在入场后前两天，应优先寻找能在 entry 前观察到的新增信息；
- 下一步：先审计 P0 中 funding、成交量及可得衍生品字段的历史覆盖/无泄漏可用性；只有覆盖完整且跨资产一致，才预注册新的 entry-quality signal family。若数据不足，则必须转向新的 price-path entry mechanism，而非继续调旧 MA7 阈值。

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_p2f_frontier_tail_states_2026-08-12.json) — SHA256 `c5662adfac8b6de5784a123cb3bf238573b9513cd1ccfe9053233d63ec221858`
- [Frontier manifest](../artifacts/binance_1d_ma7_p2f_frontier_tail_states_2026-08-12_manifest.csv) — SHA256 `0bc9434face9886b9403731b762b4d9c710cc5968dfe562ca1107c0cfe7d10ce`
- [MDD events](../artifacts/binance_1d_ma7_p2f_frontier_tail_states_2026-08-12_events.csv) — SHA256 `6f2f59cf482d0a379405a5dfb1eba8115d1ddb4fb7848fe95e6bf6586097b06c`
- [Coverage table](../artifacts/binance_1d_ma7_p2f_frontier_tail_states_2026-08-12_coverage.csv) — SHA256 `6141f1dee2000225fbdbf9860c7965a50e7016ca00ec55a28e3116e49d0a898c`
- [复现脚本](../scripts/audit_binance_1d_ma7_p2f_frontier_tail_states.py)
