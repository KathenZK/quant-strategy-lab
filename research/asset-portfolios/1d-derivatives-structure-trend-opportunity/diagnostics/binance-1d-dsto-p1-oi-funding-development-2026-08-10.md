# BIN-1D-DSTO P1 OI + Funding Development 诊断

## 复核更正（优先于下文原始输出）

- 当前证据状态：`explore / diagnostic-only / not promoted / not live-ready`；P0R 容量仍有效，P1 经济与增量裁决已撤回。
- 实现先在五资产全局 panel 上预计算 market aggregate，之后才删除 outer/inner held asset 的 event rows；held asset 的 OI/funding 因而仍进入训练行的 market features，严格 LOAO 不成立。
- 五资产合同还存在不可同时满足的容量约束：训练行排除 target、outer-held、inner-held 后只剩 `2` 个 peers，低于冻结的 `>=3`。
- 下文数值只保留为**受污染历史输出**，不得再解释为“OI/funding 无增量”或有效 hard-gate failure。研究脚本现已 fail closed；若继续必须另立新 universe/aggregate 合同，并使用未揭示时间窗确认。

## 原始结论（已撤回）

`DEVELOPMENT_HARD_GATE_FAILED`。P0R 容量通过，但 OI + funding full 模型在严格 nested `LOAO × expanding time` 下显著亏损，而且相对 price-only control 的增量为负；该路线不保存 frozen model、不读取 HYPE、不 transfer。

## P0R

- accepted anchors：`6,118`
- per asset：BTC `1,218`、ETH `1,226`、BNB `1,225`、SOL `1,222`、TRX `1,227`
- label：long `2,552`、flat `1,301`、short `2,265`
- source archives：`6,385`
- market peers：每个 accepted anchor 至少 `3`
- HYPE rows/files/requests：全部 `0`

所有端点按 [P0R OI + Funding 合同](../specs/binance-1d-dsto-p0r-oi-funding-contract-2026-08-10.md)精确接受；没有对坏源做插值或 timestamp 对齐。

## Full OOF

| 指标 | 结果 | 门槛 |
| --- | ---: | ---: |
| Trades | 186 | >=300 |
| Long / short | 65 / 121 | 各 >=100 |
| Mean `z_4bps` | -0.2274% | >0 |
| Profit factor | 0.676 | >=1.15 |
| Compound | -36.21% | 报告项 |
| Event-sequence MDD | -43.47% | 报告项 |
| 正收益资产 | 1/5 | >=4/5 |
| 正收益 outer folds | 3/20 | >=15/20 |
| Confidence/return Spearman | 0.0192 | >0.03 |
| 正 Spearman 资产 | 2/5 | >=4/5 |
| Bootstrap `P(mean>0)` | 1.86% | >=90% |

只有 `7/20` outer folds 的 inner gate 选出模型；ETH 全部 OOF fold 无可执行选择。按资产看，BTC、BNB、SOL 均为负，TRX 仅接近零。

## Full 相对 Price Control

Price-only control 本身有 `94` 笔、mean `+0.1666%`、PF `1.264`、bootstrap `P(mean>0)=90.02%`，但只在 `4/20` folds 出现选择、只有两个资产为正、三个 folds 为正，且 long/short 为 `71/23`；它未通过覆盖、方向、资产和 fold 门，不能视为可复现候选。

在双方共同的 `3,668` 个 outer OOF anchors 上：

- full mean utility：`-0.01153%/anchor`
- control mean utility：`+0.00427%/anchor`
- delta：`-0.01580%/anchor`
- bootstrap `P(Δutility>0)`：`0.24%`
- 95% bootstrap 区间：`[-0.03032%, -0.00393%]`

因此 OI/funding 不是“有增量但门槛略严”，而是在共同样本上稳定拖累 control。

## 压力与稳定性

- `8bps`：mean `-0.2477%`，PF `0.652`
- `12bps`：mean `-0.2680%`，PF `0.630`
- funding-off：mean `-0.2405%`，PF `0.661`
- lag `+1h`：mean `-0.2091%`，PF `0.705`
- threshold `-0.05`：mean `-0.0352%`，PF `0.945`
- threshold `+0.05`：mean `-0.1300%`，PF `0.809`
- 最近 `1y`：95 笔，mean `-0.1537%`，PF `0.786`；最近 `6m` 及更短窗口没有 OOF 选择。

十个 derivatives feature 的 permutation importance 中位数为正，只说明部分 fold 的分类 loss 会用到这些字段；它没有转化为方向覆盖、经济收益或相对 control 增量，不能单独构成成功证据。

## 失败归因与决定

1. 原 full-field route 首先因官方 positioning/taker 历史质量失败；精确 OI + funding 修订解决了数据容量问题。
2. 修订后 P0R 和 label 容量均充足，因此本轮失败不是“小样本无法训练”。
3. Full 在受污染的共同 anchors 上落后 control；该现象可用于定位方向/覆盖问题，但不能归因成 OI/funding 的严格 OOF 负增量。
4. price-only control 的局部正结果集中在少数后期 fold/资产，不具备当前合同要求的可迁移性；不得把它结果后裁成 SOL/BTC 专属策略。
5. 原“关闭并证伪”裁决撤回；由于 outcome 已揭示且冻结五资产合同不可执行，本历史窗不允许修后重称盲测。Family 保持 `explore / diagnostic-only / not promoted / not live-ready`，下一次有效检验需要新合同与未见时间窗。

## 证据

- [P1 summary](../artifacts/p1_oi_funding_development_2026-08-10/p1_summary.json)
- [P1 full report](../artifacts/p1_oi_funding_development_2026-08-10/p1_report.json)
- [P0R capacity](../artifacts/p1_oi_funding_development_2026-08-10/p0_data_capacity.json)
- [P1 artifact manifest](../artifacts/p1_oi_funding_development_2026-08-10/manifest.json)
- [研究脚本](../scripts/research_binance_1d_dsto_p1.py)
- [P0 source-quality 诊断](binance-1d-dsto-p0-source-quality-2026-08-10.md)
