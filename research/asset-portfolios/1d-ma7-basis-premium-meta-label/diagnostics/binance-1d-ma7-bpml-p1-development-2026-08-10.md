# BIN-1D-MA7-BPML P0/P1 开发诊断

## 结论

`HARD-GATE-FAILED / explore / diagnostic-only / not promoted / not live-ready`

官方 premium-index 与 mark/index basis 没有在冻结 LMML maturity target 上形成跨资产、跨时间可选择的稳定增量。Full 在 `19/20` outer folds 的 inner development 中找不到任何同时满足容量、三折正收益和 PF 门的候选；唯一一次选择只在 `TRX / fold 4` 做空一笔，`z_8bps=-1.5633%`。Price control 与 basis-only 均为 `20/20 NO_SELECTION`。

因此不保存模型、不读取 HYPE、不生成 transfer 或 V6 组合路径。

## 数据与 P0

- Event substrate：冻结 LMML `1,448` events，identity `f224974f…a777`。
- Source：Binance Vision monthly `1h` premiumIndex/markPrice/indexPrice，共 `948` 个 ZIP；ETag/MD5、ZIP CRC、SHA256、schema、OHLC 与 timestamp identity 通过。
- 官方源并非完整连续：各 asset/dataset 缺 `48–288` 根，完整缺口见 [P0 data quality](../artifacts/p0_data_2026-08-10/p0_data_quality.json)。Gapful 拼接只存 cache，未进入 accepted feature。
- 原连续 `30d+24h` P0 接受 `1,233/1,448（85.15%）`，未达到 `>=1,300 / >=90%`，明确失败；证据见 [原 30 日容量](../artifacts/p0_data_2026-08-10/p0_original_30d_capacity.json)。
- 在未读取 outcome 时冻结的 14 日 P0R 接受 `1,335/1,448（92.20%）`；BTC/ETH/BNB/SOL/TRX 为 `283/288/264/227/273`，long/short 为 `718/617`。`89` 个 local window 与 `24` 个 peer-capacity event fail closed。
- 每个 accepted target 与至少三个 peers 均有 premium/mark/index 共同连续 `360h`；无插值、nearest、round 或 missingness feature。
- HYPE rows/files/requests：`0/0/0`。

## P1 严格 OOF

共同 panel 上分别运行：

1. `price_plus_basis`：47 个冻结 LMML price features + 22 个 basis features；
2. `price_control`：原 47 个 price features；
3. `basis_only`：方向/成熟年龄 + 22 个 basis features。

每条路线使用相同 nested LOAO × expanding-time folds、L2 Logistic、`C={0.03,0.10,0.30,1.00}`、threshold `0.50–0.70` 与 `combined/long/short`。Inner 候选必须三折均正、总 PF `>=1.05`，不允许 outer 结果反向选参。

### Full 结果

- Outer choice：`19/20 NO_SELECTION`。
- 唯一 choice：`TRX / fold 4 / C=0.30 / threshold=0.50 / short_only`。
- Accepted：`1` 笔，`z_8bps=-1.5633%`，PF `0`，MDD `-1.5633%`。
- Threshold `-0.05`：`3` 笔全部亏损，mean `-0.9579%`。
- Positive assets/folds：`0/5`、`0/20`。
- Cluster bootstrap `P(mean>0)=0`。
- Stress：`z_4bps=-1.5421%`、funding-off `-1.5454%`、lag1 `-1.9703%`。

### Control 与增量

- Price control：`20/20 NO_SELECTION`，没有可执行 OOF trade。
- Basis-only：`20/20 NO_SELECTION`。
- 共同 OOF universe：`780` events、`63` 个 `asset×90d` clusters。
- Full-control mean utility delta：`-0.002004%/event`。
- Bootstrap `P(Δutility>0)=0`，`97.5%` 分位也为 `0`。
- 只有一个 fold 产生 permutation，不能构成跨 fold importance；按合同“至少 15 folds”后，合格 basis feature 为 `0`。

## 失败归因

1. **不是容量不足**：P0R 保留 1,335 个事件，资产与方向均超过冻结门。
2. **不是 price control 被 full 挤掉**：control 自身 20 folds 都无法满足稳定 inner economics；full 只多得到一次错误选择。
3. **不是滑点单点造成**：唯一 OOF trade 在 `4bps/8bps/funding-off/lag1` 全部为负。
4. **不是可通过调 threshold 修复**：放宽 `0.05` 后新增两笔仍全部亏损。
5. **核心问题是 target 条件可分性**：冻结 maturity events 在 OOF 区间除 SOL 外 all-matured mean 均为负；premium/basis 未能把稀少正例稳定排序出来。

`0` trade 相对负收益 baseline 会机械显示“收益/MDD 双改善”；实现已修正为每资产至少 15 笔才允许计入 dual-improvement，避免空仓假胜利。单 fold permutation 也已修正为至少 15 folds 才可通过 importance 门；这些是证据口径纠正，不改变 P1 失败。

## 决策

- 关闭本 family 的 `maturity + public basis/premium + binary meta-label` 路线。
- 禁止按 outer 结果放宽 inner 三折正收益、把 threshold 降到 `0.45`、只留 TRX short、再缩 z-window 或增加树模型。
- HYPE 继续锁定；没有 frozen model。
- 下一步只考虑与现有信息集正交的成交微观结构（真实 taker flow / aggressor imbalance / liquidation）或改变经济 target（组合级机会成本、cross-sectional allocation），不能继续叠加 MA7 snapshot 指标。

## 证据

- [P0/P1 原合同](../specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md)
- [P0R 14 日修订合同](../specs/binance-1d-ma7-bpml-p0r-14d-basis-contract-2026-08-10.md)
- [P0 source manifest](../artifacts/p0_data_2026-08-10/p0_source_manifest.json)
- [P0 data quality](../artifacts/p0_data_2026-08-10/p0_data_quality.json)
- [P0R/P1 capacity](../artifacts/p1_development_2026-08-10/p0_capacity.json)
- [P1 summary](../artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 full report](../artifacts/p1_development_2026-08-10/p1_report.json)
- [P1 manifest](../artifacts/p1_development_2026-08-10/manifest.json)
