# Binance 1D MA7 P2-G Entry-Information 归因裁决

## 结论

P2-G 在 P2-F 冻结的 `236` 个 frontier pairs 上重放 `17,821` 笔实际交易，形成 `23,287` 条 pair×stratum observations 和 `1,720` 条 unique-entry×stratum observations。`QV20/TC20/RVOL7/FUND24/FUND7Z/CROWD7Z` 六个预注册特征均未通过跨 BTC/ETH、pair-weighted/unique-entry、strata effect、AUC 与 calendar leave-one-year-out 的联合门。

Passing features：`0`；selected feature：`None`。按合同关闭当前 P0 成交活跃度/funding entry-information 路径，不建立 PnL entry gate、不登记 V2、不读取 audit/prospective。

## 冻结范围

- 合同：[P2-G entry-information 归因合同](../specs/binance-1d-ma7-p2g-entry-information-attribution-contract-2026-08-12.md)
- Parent：[P2-F tail-state 归因](binance-1d-ma7-p2f-frontier-tail-state-attribution-2026-08-12.md)
- Development：`2019-12-24` 至 `2025-08-07` exclusive
- Label：实际持仓 entry 后 `48h` 内 adverse excursion `<=-8%`
- Pair-weighted：`23,287` 条展开 observations
- Unique-entry：`1,720` 条展开 observations；每 stratum 固定取最低 `pair_rank` 代表
- Funding：严格只计 `event_ts < entry_ts`；同 timestamp funding 不可见

## Outcome 基线

| Asset / side | Pair-weighted trades | Early-tail rate | Median early adverse | Account-MDD trades |
| --- | ---: | ---: | ---: | ---: |
| BTC long | `5,410` | `4.79%` | `-1.63%` | `138` |
| BTC short | `3,394` | `4.98%` | `-1.40%` | `98` |
| ETH long | `4,962` | `7.09%` | `-2.91%` | `190` |
| ETH short | `4,055` | `6.14%` | `-1.95%` | `46` |

Unique economic-entry 口径下，ETH short 的 early-tail rate 为 `12.64%`，再次确认 ETH 入场路径是共享参数的主要尾部瓶颈。

## Feature gates

表中 AUC 依次为 `BTC pair / BTC unique / ETH pair / ETH unique`；`weakest edge` 是四者中最小的 `abs(AUC-0.5)`，预注册门为 `>=0.08`。

| Feature | Overall effects 方向一致 | Strata pass BTC/ETH | AUC | Weakest edge | LOYO weakest | Final |
| --- | --- | ---: | --- | ---: | ---: | --- |
| `QV20` | NO | `0 / 0` | `.456/.552/.557/.455` | `.0438` | `0%` | FAIL |
| `TC20` | NO | `0 / 0` | `.455/.554/.580/.490` | `.0102` | `0%` | FAIL |
| `RVOL7` | NO | `0 / 0` | `.470/.617/.600/.601` | `.0297` | `0%` | FAIL |
| `FUND24` | YES | `0 / 3` | `.608/.549/.645/.606` | `.0493` | `100%` | FAIL |
| `FUND7Z` | NO | `0 / 0` | `.559/.491/.432/.506` | `.0062` | `0%` | FAIL |
| `CROWD7Z` | YES | `3 / 0` | `.674/.711/.527/.514` | `.0136` | `85.71%` | FAIL |

## 因果解释

### 成交活跃度不稳定

`QV20` 与 `TC20` 在 BTC pair-weighted 为负 effect、unique-entry 却为正；ETH 也存在类似反转。说明某些高排名配置重复产生的交易路径改变了表观相关性，信号不能跨经济 entry 复现。即使 `TC20` 的 ETH pair AUC 达 `.580`，ETH unique 只有 `.490`，不能授权过滤器。

### RVOL7 是样本权重假象

ETH 两口径 AUC约 `.60`，BTC unique 也有 `.617`，但 BTC pair-weighted 为 `.470`，且三个 strata 没有一个同时满足双口径同向 effect 门。不能把“高波动有时更危险”的直觉替代共享稳定性证据。

### Funding 只形成单资产线索

- `FUND24` 对 ETH 三个 strata 均有一致 effect，但 BTC unique AUC仅 `.549`，BTC `0/3` strata 过门；
- `CROWD7Z` 对 BTC 很强：pair/unique AUC为 `.674/.711`，三个 strata 全过；但 ETH 只有 `.527/.514`，`0/3` strata 过门；
- `FUND7Z` 两资产和两统计口径方向反复翻转。

因此 funding crowding 只能作为 BTC 专属诊断线索，不能写入本任务要求的 BTC/ETH shared parameter 策略。按合同也不允许改为资产专属阈值后冒充共享机制。

## 裁决与下一步

- P2-G：`HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 关闭：P0 volume/trade-count/RVOL/funding 单变量 entry gate
- 禁止：组合多个 FAIL 特征、放松 AUC/effect 门、只保留 BTC 或 ETH 有利子样本
- 下一步：建立 materially new price-path entry mechanism；优先检验 daily signal 后的有限 `1h` directional confirmation 是否能在真实执行顺序中拒绝早期尾部、同时保留非尾部趋势机会。先做触发时序归因，通过覆盖/保留门后才实现完整 PnL 状态机。

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_p2g_entry_information_2026-08-12.json) — SHA256 `1b8a79b2a7b2cc8ebfc85624ebd062e8ca90a9526fb8941633728d8766be9c21`
- [逐笔 entry dataset](../artifacts/binance_1d_ma7_p2g_entry_information_2026-08-12_entries.csv) — SHA256 `782018c6fe7acafb4a818caff9e62a6ced25800f2c1ed48a01c0aff6de322595`
- [汇总 metrics CSV](../artifacts/binance_1d_ma7_p2g_entry_information_2026-08-12_metrics.csv) — SHA256 `5c6cb618027965431992586f354c566c667c14f3c984e66785d70a5b4de5e1a3`
- [含 quintiles 的 metrics JSON](../artifacts/binance_1d_ma7_p2g_entry_information_2026-08-12_metrics.json) — SHA256 `68bb77c079bef78bc1f8275efe83399555ed8c0cea42175af9bc2b536547ab4c`
- [复现脚本](../scripts/audit_binance_1d_ma7_p2g_entry_information.py)
