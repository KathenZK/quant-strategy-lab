# BIN-1D-BE-RCR P3 Relative-Extreme Gate 合同（2026-08-12）

## 1. 唯一机制假设

P2 的 `RELATIVE_EXTREME20` 是 `1/6 PASS`：growth/risk AUC `0.6203/0.6732`，BTC/ETH AUC `0.6049/0.5997`，四个 `anchor×asset` 高低 tercile tail-rate edge 最弱 `12.5pp`。P3 只检验该信息能否转化为共享 entry gate；不得加入其他 feature、stop、EMA、删腿或风险缩放。

## 2. 冻结 gate 与搜索空间

- `relative_extreme=abs(z_BTC(20,28)-z_ETH(20,28))`，只使用执行开盘前一完整 UTC 日。
- 当 base target 与当前实际状态不同：若 `relative_extreme<=threshold`，正常执行 base target；若更大，则平旧仓/保持 flat，不建立新仓。
- 当前实际状态与 base target 相同则继续持有；gate 不作为退出信号。
- base target 为 flat 时正常平仓。被阻止后每日重新评估，不设 cooldown。
- exact controls：P0 growth/risk anchors；阈值 `threshold∈{1.0,1.5,2.0,2.5,3.0}`，共 `10` 个配置。

数据、development/audit/prospective、费用、funding、`1x` 固定数量、next-open 与 ordered `1h` 顺序完全继承 P0。额外一日延迟时 base target 延迟一日，但 gate 仍使用实际执行开盘前一完整日的当时可知信息。

## 3. 门禁

10 个配置全部做 base ordered replay；base `>=20x/MDD<=20%` 才计算 P0 同口径 stress、delay、calendar、rolling、participation、concentration 门禁。完全同路径去重，排序沿用 P0。

若无全门禁候选：`HARD-GATE-FAILED / explore / not promoted / not live-ready`，audit/prospective 不揭示、不登记版本，且不得扩大 threshold 或叠加 P1 保护机制救援。
