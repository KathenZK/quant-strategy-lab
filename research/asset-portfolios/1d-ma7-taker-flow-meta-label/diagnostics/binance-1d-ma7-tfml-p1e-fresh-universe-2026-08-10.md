# BIN-1D-MA7-TFML P0E/P1E Fresh-Universe 诊断

## 复核更正（优先于下文原始输出）

- 当前证据状态：P0E flow ZIP/caches 可审计，但 price/funding feature 的内嵌 generator SHA `37c3936d…` 无对应保留源码（现有 base 为 `25361566…`），因此 P0E 整体 fail closed；P1E `invalidated evidence / diagnostic-only / not promoted / not live-ready`。
- 实现先用13资产全局数据生成 market price/flow aggregates，之后才从 train/inner 删除 fresh held asset 的 event rows；held asset 的 source history 仍进入其他资产训练行，违反“held asset 全历史排除”。
- 旧 price/funding manifest 还存在 post-hoc family 重贴和错误 cutoff provenance；现已改为原生 P0E schema，准确记录 cutoff、完整 feature/source hashes、内嵌 generator SHA 与 HYPE `0/0/0`，并因 generator source 未保留明确报 blocker。
- 下文 P1E 数值只保留为受污染历史输出，不能证明 flow universal increment 为正或为负。八资产 outcome 已揭示，因此不得在同一篮子修复后重新声称 fresh OOS；脚本现已 fail closed。

## 原始结论（已撤回）

`HARD-GATE-FAILED / explore / diagnostic-only / not promoted / not live-ready`

八个未见资产的 fresh outer test 明确否定了 taker flow 的 universal increment。Full 305 笔 mean `-0.0681%`、PF `0.900`；相同 price expected-utility control 为 mean `+0.1664%`、PF `1.257`。Common OOF 上 flow 增量为 `-0.04392%/event`，bootstrap `P(Δutility>0)=0.84%`，95% 区间全负。

因此不是“flow 有弱信号但样本不足”，而是加入 flow 后显著破坏已有 price ranking。TFML 全路线关闭，不保存模型、不运行 P2、不读取 HYPE。

## Fresh 设计

- Legacy training：BTC/ETH/BNB/SOL/TRX。
- Fresh outer：XRP/DOGE/ADA/LINK/LTC/DOT/AVAX/UNI。
- 八个 fresh assets 的 outcome 在 [P0E/P1E 合同](../specs/binance-1d-ma7-tfml-p0e-p1e-universe-expansion-contract-2026-08-10.md) 冻结时尚未读取。
- 13 资产全部重新生成 maturity event 和 leave-target-out price/flow market features；没有拼接旧五资产 panel，但 aggregates 不是 fold-local。
- Outer 的 event/outcome rows 确实只计八个 fresh assets、共 `32` folds；held asset rows 从 train/inner 删除，但 held source history 未从其他训练行的 aggregates 排除。
- HYPE requests/files/rows/features/train/evaluation：`0/0/0/0/0/0`。

## P0E 数据与容量

Price/funding：

- 八个 fresh assets direct `1h`、UTC `1d`、funding/mark 全部通过完整网格、daily rebuild、funding interval 与 source identity。

Native `5m` flow：

- `491` 个 Binance Vision monthly ZIP，`169,255,752 bytes`。
- DOGE/ADA/LINK/AVAX/UNI 全 source range 零缺口。
- XRP/LTC 各有官方共同 5 日缺段；逐 event fail closed。
- DOT `2023-11-14 11:15 UTC` 一行出现 `taker_buy_volume > volume`，但 quote 字段未超界；整行删除并形成显式 5m gap，未修复或替代。

Event/panel：

- 13 资产重算 event：`3,683`。
- Fresh raw：`2,228`；每资产 `246–307`；long/short `1,147/1,081`。
- Flow accepted fresh：`2,109（94.66%）`；每资产 `246–275`；long/short `1,083/1,026`。
- 至少 `8/12` peers 后：local reject `32`、初始 market reject `2`、peers<8 reject `206`。
- 历史运行曾报告 P0E 通过；复核后因 price/funding provenance blocker 改为 fail closed。

## P1E Full

- Selected：`305`；long/short `122/183`；`59` 个 asset×90d blocks。
- `z_8bps`：mean `-0.0681%`，PF `0.900`，compound `-23.56%`，MDD `-38.60%`。
- Positive assets：`4/8`；positive folds：`10/32`。
- Ranking Spearman：`0.0339`，但仅 `4/8` 资产为正。
- Cluster bootstrap `P(mean>0)=26.20%`。
- `12/32` folds 为 `NO_SELECTION`；只有 20 folds 可形成 permutation，低于合同 `24` folds。

Full stress 同向失败：

- `z_4bps`：mean `-0.0482%`，PF `0.928`；
- funding-off：mean `-0.0637%`，PF `0.906`；
- lag1：254 笔，mean `-0.1378%`，PF `0.812`；
- threshold `-0.0005 / frozen / +0.0005` 的 mean 全为负。

## 资产结果

| Asset | Trades | Mean | PF | Ranking Spearman |
| --- | ---: | ---: | ---: | ---: |
| XRP | 53 | `+0.0092%` | `1.018` | `0.177` |
| DOGE | 53 | `+0.4360%` | `1.716` | `0.095` |
| ADA | 35 | `+0.0179%` | `1.027` | `0.260` |
| LINK | 37 | `-0.4789%` | `0.407` | `0.045` |
| LTC | 19 | `-0.5506%` | `0.399` | `-0.161` |
| DOT | 42 | `-0.1370%` | `0.817` | `-0.037` |
| AVAX | 37 | `+0.0237%` | `1.039` | `-0.196` |
| UNI | 29 | `-0.4118%` | `0.486` | `-0.094` |

没有单一 outlier 可以解释失败；四个资产亏损，且 ranking 正负各半。

## Control 与 Flow 增量

Price expected-utility control：

- 218 笔，mean `+0.1664%`，PF `1.257`，compound `+35.63%`，MDD `-22.40%`；
- positive assets `4/8`、positive folds `13/32`；
- ranking Spearman `0.0916`，`6/8` 资产为正；
- bootstrap `86.36%`，仍未达 hard gate。

Flow-only：

- 404 笔，mean `+0.0362%`，PF `1.056`；
- positive assets `6/8`、positive folds `16/32`；
- bootstrap `64.14%`，lag1 近零且 PF `<1`。

Common OOF、未选 utility=0：

- Full：`-0.015996%/event`；
- Price control：`+0.027925%/event`；
- delta：`-0.043921%/event`；
- `P(Δutility>0)=0.84%`；
- 95% interval：`[-0.08144%, -0.00687%]`。

Flow permutation 没有任何 feature 满足 `>=24` folds 且 median importance 正；即使忽略 fold 数，正 importance 也不稳定，不能解释为可复现增量。

## 决策与剩余线索

- 撤回“fresh test 已证伪 flow increment”的归因；当前 P1E 既不是 PASS，也不是有效 FAIL。
- 不得删 LINK/LTC/DOT/UNI、按资产 threshold、减少 peers、改树模型或在相同 fresh outcomes 上重开 flow 搜索。
- 不保存模型，不运行 post-cutoff P2，不读取 HYPE。
- 受污染输出中的 price-only 与 flow 相对表现均不构成 OOS 证据，也不支持 HYPE transfer；若继续，只能另立机制与全新资产/时间 holdout，并在每个 outer/inner fold 内重建 aggregates。

## 证据

- [P0E/P1E 合同](../specs/binance-1d-ma7-tfml-p0e-p1e-universe-expansion-contract-2026-08-10.md)
- [Fresh flow source manifest](../artifacts/p0e_data_2026-08-10/p0_source_manifest.json)
- [Fresh flow quality](../artifacts/p0e_data_2026-08-10/p0_data_quality.json)
- [Fresh price/funding quality](../artifacts/p0e_price_data_2026-08-10/p0_data_quality_manifest.json)
- [13-asset events](../artifacts/p0e_events_2026-08-10/p0e_events.parquet)
- [P0E event capacity](../artifacts/p0e_events_2026-08-10/p0e_event_capacity.json)
- [P0E accepted panel](../artifacts/p1e_development_2026-08-10/p0e_accepted_events.parquet)
- [P0E capacity](../artifacts/p1e_development_2026-08-10/p0e_capacity.json)
- [Full fresh OOF](../artifacts/p1e_development_2026-08-10/p1e_price_plus_flow_oof.parquet)
- [Price control fresh OOF](../artifacts/p1e_development_2026-08-10/p1e_price_utility_control_oof.parquet)
- [Flow-only fresh OOF](../artifacts/p1e_development_2026-08-10/p1e_flow_only_oof.parquet)
- [P1E summary](../artifacts/p1e_development_2026-08-10/p1e_summary.json)
- [P1E full report](../artifacts/p1e_development_2026-08-10/p1e_report.json)
- [P1E manifest](../artifacts/p1e_development_2026-08-10/manifest.json)
