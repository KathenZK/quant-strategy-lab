# BIN-1D-BE-DASE P0 固定资本双 Sleeve 裁决

## 结论

两个 controls 与三个冻结 ensemble weights 均完成 base/stress/delay 逐小时重放。`0/3` ensemble 达到 `20x/20%`，P0 `HARD-GATE-FAILED`，research line关闭；audit/prospective 未读取，无版本、无 handoff。

三个 ensemble 中收益最高与风险最低均为 `75% CBCT + 25% RCR`：

- base `21.2681x/-34.34% ordered MDD`；
- stress `20.6032x/-34.35%`，log-growth retention `98.96%`；
- `+1d` delay `7.8895x/-34.48%`，log-growth retention `67.56%`；
- 完整年正收益比例 `100%`，rolling 365d 正收益比例 `95.50%`；
- 最大单笔加权正 log-growth 占比 `25.92%`；
- CBCT/RCR 小时 close-return correlation `0.4484`。

收益保持成功，但 MDD仍比硬门差 `14.34pp`；delay 同时未达到 `8x` 与 `70%` retention。CBCT 正 log contribution 为 `75.0029%`，也略超冻结的 `75%` sleeve concentration gate。

## 为什么静态分散没有解决回撤

CBCT 与 RCR 的小时收益相关性只有中等，但两者同时处于各自历史峰值以下的小时占 `96.64%`。也就是说，它们的逐小时波动并不完全同步，长期 underwater period 却高度重叠；固定权重只能把 CBCT MDD `-37.20%` 降到 `-34.34%`，无法压到 `-20%`。

Growth/risk frontier 再次 path-equal，证明冻结三权重没有形成可继续插值的风险前沿。按合同禁止增加 `0.1` 权重、最小方差、vol parity或用低收益 risk sleeve 后加杠杆。

## 分歧准入诊断

仅用当时可知的两个 shadow position state 分类后：

- opposite-direction 只有 `13` 个日样本，未来 7 日平均 log return反而 `+4.81%`，没有“分歧即空仓”依据；
- same-direction 共 `354` 日，未来 7 日均值 `+2.57%`，但 2022/2023/2025 为负、2020/2021/2024 为正；
- 跨年份方向不稳定，不能冻结动态 consensus gate。

该诊断不产生新配置，也不改变 P0 裁决。下一机制只能使用经济含义独立的 crisis override；不能把开发集的 state disagreement 直接写成路由器。

## 会计与因果验证

- CBCT base exact parity：`21.270651982678306/-37.19612846945293%`；
- RCR base exact parity：`21.260522820421354/-69.6600350089438%`；
- 每个权重 terminal 与两个独立 sleeve terminal 的固定权重和绝对误差 `<=1e-12`；
- 组合 MDD 使用同小时两 sleeve favorable/adverse 同时发生的保守上界，不使用日末相关性近似；
- 两 sleeve 无再平衡、无资本转移、无动态缩放。

## 证据

- [冻结合同](../specs/binance-1d-be-dase-p0-contract-2026-08-12.md)
- [机器摘要](../artifacts/binance_1d_be_dase_p0_2026-08-12.json) — SHA256 `9725408a4fd66b15973c798d9b390944f70387627eb5eed5ea0090aae3015ef1`
- [五权重表](../artifacts/binance_1d_be_dase_p0_2026-08-12_weights.csv) — SHA256 `89d4afc2193ad75f757173fd949f724a42934a85cf2045572c71000db5d3783b`
- [完整双 sleeve 交易路径](../artifacts/binance_1d_be_dase_p0_growth_frontier_trade_path_2026-08-12.html) — 30 笔 CBCT + 74 笔 RCR 均连线
- [研究脚本](../scripts/research_binance_1d_be_dase_p0.py) · [HTML 脚本](../scripts/render_binance_1d_be_dase_p0_trade_paths.py) · [测试](../../../../tests/test_binance_1d_be_dase_p0.py)
