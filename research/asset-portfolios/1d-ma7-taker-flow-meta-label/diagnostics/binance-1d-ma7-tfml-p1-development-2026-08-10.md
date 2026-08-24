# BIN-1D-MA7-TFML P0/P1 开发诊断

## 复核更正（优先于下文原始输出）

- 当前证据状态：P0 source/capacity 有效；P1 `invalidated evidence / diagnostic-only / not promoted / not live-ready`。
- P1 在全五资产 panel 上预计算 price/flow market aggregate，之后才排除 held asset event rows；严格 LOAO 的 source-history isolation 未实现。
- 更根本地，训练行排除 target、outer-held、inner-held 后只剩 `2` peers，无法满足冻结 `>=3` peers，五资产 nested 合同不可执行。
- 下文 P1 数字仅保留为受污染历史输出，不能支持 flow 正增量或负增量。脚本已 fail closed；不得在同一已揭示 outcome 上修复后重新宣称 OOS。

## 原始结论（已撤回）

`HARD-GATE-FAILED / explore / diagnostic-only / not promoted / not live-ready`

原生 taker flow 与 continuous expected utility 明显优于此前 binary/basis 路线：Full OOF 有 `171` 笔、mean `+0.0997%`、PF `1.187`，并通过主经济性、4/5 资产正收益、收益排序、stress 与三资产双改善。但它没有证明为稳定的 universal increment：只有 `7/20` folds 为正、`10/20` folds 无合格 inner choice，cluster bootstrap 仅 `75.80%`，相对 price control 的增量 bootstrap 仅 `60.88%`，且 TRX 显著反向。

因此 P1 仍失败，不冻结模型、不进入 post-cutoff P2、不读取 HYPE。

## P0 数据质量与容量

- Source：Binance Vision monthly native `5m` futures klines，`316` 个 canonical ZIP，压缩 `116,012,918 bytes`。
- ETag/MD5、ZIP CRC、SHA256、schema、OHLC、taker-buy<=total 与 timestamp identity 通过。
- BTC/ETH/BNB 在各自 source start 至 `2025-05-30 23:55 UTC` 零缺口。
- SOL/TRX 共同缺 `2022-02-26` 起 `1,440` 根（5 日）；无插值，逐 event fail closed。
- Accepted：`1,413/1,448（97.58%）`；BTC/ETH/BNB/SOL/TRX `301/307/275/240/290`；long/short `759/654`。
- Rejected：local `13`、peers `22`。
- HYPE requests/files/rows：`0/0/0`。

## P1 Full

- Selected：`171`；long/short `102/69`；`31` 个 asset×90d blocks。
- Main `z_8bps`：mean `+0.0997%`，PF `1.187`，compound `+15.39%`，MDD `-19.00%`，win rate `37.43%`。
- Ranking Spearman：`0.0448`；`4/5` 资产为正。
- Positive assets：`4/5`；positive folds：`7/20`。
- Choice coverage：`10/20` outer folds 有 choice，另 `10/20 NO_SELECTION`。
- Bootstrap `P(mean>0)=75.80%`，未达到 `90%`。

Stress：

- `z_4bps`：mean `+0.1198%`，PF `1.230`；
- funding-off：mean `+0.1272%`，PF `1.241`；
- lag1：147 笔，mean `+0.0868%`，PF `1.154`，可执行率 `85.96%`。

Threshold sensitivity：

- `-0.0005`：179 笔，mean `+0.0597%`，PF `1.110`；
- frozen：171 笔，mean `+0.0997%`，PF `1.187`；
- `+0.0005`：154 笔，mean `+0.1019%`，PF `1.186`。

## 资产与时间异质性

| Asset | Trades | Mean | PF | Ranking Spearman |
| --- | ---: | ---: | ---: | ---: |
| BTC | 28 | `+0.1570%` | `1.569` | `0.213` |
| ETH | 30 | `+0.0964%` | `1.214` | `0.116` |
| BNB | 10 | `+0.7785%` | `14.296` | `0.593` |
| SOL | 38 | `+0.6575%` | `1.837` | `0.034` |
| TRX | 65 | `-0.3541%` | `0.416` | `-0.171` |

除 TRX 外四资产事后合并为 106 笔、mean `+0.3779%`；TRX 单独显著亏损。但这是 outer 结果揭示后的子集，不能用于删资产、改 threshold 或生成 HYPE transfer。时间上，BTC/ETH/BNB/SOL 的 choice 主要集中在前两个 folds，后段普遍 `NO_SELECTION`；TRX 四个 folds 均有 choice，却三折亏损，说明不是单纯样本不足，而是方向和制度不稳定。

## Control 与独立增量

Price expected-utility control：

- 93 笔，mean `+0.1239%`，PF `1.258`，compound `+11.07%`，MDD `-14.46%`；
- 仅 `7/20` folds 有 choice，positive folds `4/20`，bootstrap `74.46%`。

Flow-only：

- 193 笔，mean `-0.0886%`，PF `0.827`，compound `-16.99%`；
- 说明 flow 不能脱离 price state 独立交易。

Common OOF 未选 utility=0：

- full mean utility `+0.02058%/event`；
- control `+0.01392%/event`；
- delta `+0.00666%/event`；
- bootstrap `P(Δutility>0)=60.88%`，95% 区间跨零，远低于 `90%`。

Full 只有 10 folds 产生模型与 permutation，合同要求至少 15 folds；因此没有 flow feature 获得有效跨 fold importance。

## Gate 复盘

通过：

- P0 capacity；
- direction/time-block coverage；
- main economics；
- positive assets；
- ranking；
- stress；
- 三资产 return/MDD dual improvement；
- HYPE lock。

失败：

- per-asset coverage：BNB 仅 10 笔；
- positive folds：`7/20 < 15/20`；
- bootstrap：`75.80% < 90%`；
- full-control increment：`60.88% < 90%`；
- permutation：`10 < 15` folds。

这不是“差一点就可降门通过”。经济性主要来自资产/早期折集中，且 price control 自身已贡献大部分收益；按结果删除 TRX 或只留早期 regime 会把 universal transfer 变成后验资产选择。

## 决策

- 关闭当前五资产 universal `maturity + taker-flow expected utility` P1，不运行 P2，不保存 frozen model。
- 禁止删除 TRX、按资产设 alpha/threshold、降低 fold/bootstrap/delta 门或把 flow-only 负结果隐藏。
- 该结果仍保留一个未解决信号：flow 对 BTC/ETH 的增量为正，且四个非 TRX 资产经济性强。下一轮只能在**结果前**扩大未见资产 universe、预定义资产相似度/层级结构，或转为 prospective online calibration；不能用现有五资产 outer outcome 直接指定 HYPE 类似 SOL/BNB。

## 证据

- [P0/P1 合同](../specs/binance-1d-ma7-tfml-p0-p1-contract-2026-08-10.md)
- [P0 source manifest](../artifacts/p0_data_2026-08-10/p0_source_manifest.json)
- [P0 data quality](../artifacts/p0_data_2026-08-10/p0_data_quality.json)
- [P0/P1 accepted panel](../artifacts/p1_development_2026-08-10/p0_accepted_events.parquet)
- [P0 capacity](../artifacts/p1_development_2026-08-10/p0_capacity.json)
- [Full OOF](../artifacts/p1_development_2026-08-10/p1_price_plus_flow_oof.parquet)
- [Price control OOF](../artifacts/p1_development_2026-08-10/p1_price_utility_control_oof.parquet)
- [Flow-only OOF](../artifacts/p1_development_2026-08-10/p1_flow_only_oof.parquet)
- [P1 summary](../artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 full report](../artifacts/p1_development_2026-08-10/p1_report.json)
- [P1 manifest](../artifacts/p1_development_2026-08-10/manifest.json)
