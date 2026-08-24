# Binance 1D MA7 P2-I Entry-Shape 归因与 P2 Campaign 最终裁决

## 结论

P2-I 对 `17,821` 笔冻结 actual entries 检验入场前最后完整日线的 `BODY_ATR/BODY_SHARE/CLV/ER7/RANGE_ATR/ADVERSE_WICK_ATR`。Passing features 为 `0`，selected feature 为 `None`。

依据预注册停止规则，当前 V1→P2-I 的 MA7 substrate 扩展正式停止：

- P2 campaign：`HARD-GATE-FAILED / explore / not promoted / not live-ready`；
- BTC/ETH shared V1 保持原登记身份，不登记 V2；
- researcher-exposed audit 与 prospective 从未读取；
- 不得继续追加 P2-J 指标、组合多个 FAIL feature 或用杠杆放大未达标收益；
- 若继续追求 `>=20x / MDD<=20%`，必须新建身份独立、机制实质不同且重新锁定 prospective OOS 的策略家族。

## 冻结范围

- 合同：[P2-I entry-shape 归因合同](../specs/binance-1d-ma7-p2i-entry-shape-attribution-contract-2026-08-12.md)
- Parent：[P2-H finite hourly confirmation](binance-1d-ma7-p2h-finite-hourly-entry-confirmation-2026-08-12.md)
- Features：仅入场前最后完整 UTC 日线及截至该日的 ATR7/close path
- Label：actual holding entry 后 `48h EARLY_TAIL<=-8%`
- Pair-weighted / unique-entry / strata / LOYO 门：完全沿用 P2-G
- Feature timestamp 不含 entry 当日 open 或任何 entry 后信息

## Feature gates

| Feature | Direction gate | Strata pass BTC/ETH | AUC BTC pair/unique | AUC ETH pair/unique | Weakest edge | Final |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `BODY_ATR` | FAIL | `0 / 0` | `.534 / .631` | `.558 / .468` | `.0323` | FAIL |
| `BODY_SHARE` | FAIL | `0 / 0` | `.616 / .656` | `.594 / .491` | `.0086` | FAIL |
| `CLV` | PASS | `2 / 1` | `.630 / .661` | `.609 / .535` | `.0345` | FAIL |
| `ER7` | FAIL | `0 / 0` | `.669 / .621` | `.534 / .461` | `.0344` | FAIL |
| `RANGE_ATR` | FAIL | `0 / 0` | `.493 / .569` | `.493 / .451` | `.0068` | FAIL |
| `ADVERSE_WICK_ATR` | FAIL | `0 / 0` | `.530 / .446` | `.484 / .492` | `.0085` | FAIL |

预注册最弱 AUC edge 门为 `.08`；六个特征最佳也只有 `.0345`。样本量均充足，失败来自跨资产/双口径效果不一致，不是 missing 或交易数不足。

## 最接近线索：CLV

方向化 close-location (`CLV`) 是唯一 overall effect 在 BTC/ETH、pair/unique 四组同向的特征，LOYO最弱方向一致率也有 `85.71%`。但它仍失败：

- BTC growth/balanced 过 effect 门，risk 不过；
- ETH 只有 growth 过门，balanced unique effect仅 `.130`，risk pair/unique方向冲突；
- ETH unique AUC只有 `.535`，远低于 `.58`；
- 最弱 AUC edge `.0345`，不足冻结门的一半。

因此 CLV 只能作为“部分 frontier 的形态描述”，不能授权 quantile gate。把门降到 `.03` 或只保留 growth stratum 都属于结果后救参。

## P2 全链路失败归因

P2 已完成而非跳过以下层次：

1. V1 长历史复现：BTC `1.665x/-60.41%`，ETH `2.675x/-65.67%`；
2. `121` 项全参数消融：无 hard target；
3. episode attribution 与静态 stop/MA7 exit：无 soft-continue；
4. 每方向 `20,000` 配置、`3,600` shared pairs hard-MDD 广搜：ordered MDD-safe `0`；
5. frontier tail-state：slow/vol/lifecycle 覆盖门全部失败；
6. volume/funding entry-information：`0/6` feature通过；
7. finite hourly confirmation：弱确认拒绝不了 tail，强确认删除大部分机会；
8. entry-shape：`0/6` feature通过。

现有 price-only MA7 参数面最佳收益 frontier 仅 BTC `7.62x`、ETH `9.33x`且回撤约 `39%`；风险 frontier 仅 `2.90x/4.75x`且最差 MDD `-25.47%`。当前证据不是“差一个阈值”，而是收益与风险目标之间存在结构缺口。

## 治理裁决

- V1：继续 `registered / not promoted / not live-ready`
- P2：`HARD-GATE-FAILED / explore / not promoted / not live-ready`，不形成 V2
- Audit/prospective：继续 sealed
- Leverage：继续锁定；风险缩放不能创造 alpha
- HTML：无版本冻结，不生成误导性的 candidate trade-path HTML
- 下一机制：必须另立 family name、独立 contract、独立主账身份与 clean prospective；不得把新机制静默写成 V2

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_p2i_entry_shape_2026-08-12.json) — SHA256 `ab83d40bf45f527efd51913108276b23a03129d6ded599c3bbd40f0b248c0194`
- [带 shape 的 entry dataset](../artifacts/binance_1d_ma7_p2i_entry_shape_2026-08-12_entries.csv) — SHA256 `cc416813fadf959fcadab8df060e1cc91154655cc45cbae8df441fee079718d8`
- [Metrics CSV](../artifacts/binance_1d_ma7_p2i_entry_shape_2026-08-12_metrics.csv) — SHA256 `4dfc12a0dac5cfcbff9b9971da0e73e3805f155d35f9aa2f64a3eecef4783c26`
- [含 quintiles 的 metrics JSON](../artifacts/binance_1d_ma7_p2i_entry_shape_2026-08-12_metrics.json) — SHA256 `b6bbe426fb5608e05183d7c4f2f4b979e5572d913109e17a576045d898b456b2`
- [复现脚本](../scripts/audit_binance_1d_ma7_p2i_entry_shape.py)
