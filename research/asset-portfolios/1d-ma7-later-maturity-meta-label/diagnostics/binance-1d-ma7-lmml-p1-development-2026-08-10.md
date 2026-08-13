# BIN-1D-MA7-LMML P1 非 HYPE Development 诊断

## 结论

P0 数据与事件容量通过，P1 pooled meta-label 失败，HYPE 保持锁定且未被脚本读取。模型在部分资产降低了全量 maturity 的亏损与事件序列回撤，但没有形成可跨资产、跨时间迁移的正向排序，因此不得生成 HYPE score 或组合结果。

状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。

## 数据与标签

- 训练资产：BTC/ETH/BNB/SOL/TRX Binance USD-M perpetual。
- 时间：各资产上市后至 `2025-05-30 UTC`，早于 HYPE 完整日线起点。
- 数据质量：五资产 direct `1h` 无缺口，UTC `1d` 与 24 根小时 K 重算完全一致，funding 动态间隔无 blocker。
- raw crosses：`2,053`；成熟事件：`1,482`；完整特征与成本标签：`1,448`。
- 其中 long `771`、short `677`、later maturity `753`，`8 bps + fee + actual funding` 正标签率 `34.60%`。
- HYPE rows consumed：`0`。

## 严格 OOF 结果

外层使用 `leave-one-asset-out × 4 expanding-time folds`，内层选择 `C / threshold / route`；共 `847` 个 OOF 事件，接受 `132` 笔：

- 主压力 `8 bps`：平均每笔 `+0.0446%`（固定 `0.25x`），PF `1.069`，事件序列复合 `+3.94%`，MDD `−21.57%`；
- `4 bps`：平均 `+0.0649%`，PF `1.103`；
- funding-off：平均 `+0.0481%`，PF `1.075`；
- lag `+1d`：121 笔，平均 `+0.1526%`，PF `1.262`。

表面总均值为正，但泛化结构失败：

- positive assets：`2/5`，仅 BNB、SOL 为正；BTC、ETH、TRX 仍为负；
- positive outer folds：`10/20`；
- probability 对 `z_8bps` Spearman：`−0.0030`；
- `asset × 90d` cluster bootstrap：`P(mean>0)=61.78%`；
- PF 未达到 `1.15`，bootstrap 未达到 `90%`；
- 最终选择在 20 折中不稳定，众数 `C=1.0 / threshold=0.50 / combined` 只出现 6 次。

## 失败原因

1. **没有跨资产排序能力**：概率与连续经济结果近零负相关；选中事件的微弱正均值不是稳定 ranking。
2. **资产异质性主导**：SOL 自身 all-matured 已为正，BNB 可被筛出；同一关系迁移到 BTC/ETH/TRX 后仍亏损。
3. **snapshot 不足以定位 entry timing**：日线 maturity 加单个闭合日内路径快照仍把“趋势已成熟”和“短持有 entry 有利”混在一起。
4. **合同有一处非决定性设计缺陷**：40% initial 的 OOF 只可能覆盖 13 个 90 日时间块，预设 `>=15` 不可达。该门需要未来合同修正，但即使完全移除，main economics、positive assets、positive folds、ranking、bootstrap 五条独立硬门仍失败，不能据此重开。

## 决定

- P1 `HARD-GATE-FAILED`；不拟合/保存 frozen model，不读取 HYPE，不进行 target transfer。
- 不继续调整同一 maturity snapshot 的 threshold、route、特征子集或树容量。
- 下一步另立 `1h` root-level hazard timing：daily raw cross 只建立 root，之后逐根闭合小时 K 判断首次可交易时点；每个 root 总训练权重固定为 1，并继续只在非 HYPE 数据上完成 gate。

## 证据

- [P0/P1 合同](../specs/binance-1d-ma7-lmml-p0-p1-contract-2026-08-10.md)
- [P0 容量与数据质量](../artifacts/p1_development_2026-08-10/p0_data_capacity.json)
- [P1 摘要](../artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 完整报告](../artifacts/p1_development_2026-08-10/p1_report.json)
- [OOF predictions](../artifacts/p1_development_2026-08-10/p1_oof_predictions.parquet)
- [事件表](../artifacts/p1_development_2026-08-10/p0_p1_events.parquet)
- [证据 manifest](../artifacts/p1_development_2026-08-10/manifest.json)
- [研究脚本](../scripts/research_binance_1d_ma7_lmml_p1.py)
