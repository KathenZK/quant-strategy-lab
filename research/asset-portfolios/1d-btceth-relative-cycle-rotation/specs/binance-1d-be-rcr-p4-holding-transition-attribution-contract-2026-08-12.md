# BIN-1D-BE-RCR P4 Holding-Transition 归因合同（2026-08-12）

## 1. 因果问题

P3 证明 entry-context gate 没有改变最大回撤。P4 只检验：在仓至少一个完整 UTC 日后，能否用当时已闭合数据识别未来三日内、且发生在 base state 改变前的 `>=8%` adverse path。

P4 只做 attribution，不允许直接平仓、搜索阈值或改变 P0 controls；只读 development，audit/prospective 保持封存。

## 2. 冻结 landmarks 与标签

- exact controls：P0 growth/risk anchors，必须完成 equity/MDD/trade parity。
- landmark：实际 base state 连续持有至少一日后的每个日开盘；特征只使用该开盘前一完整日及更早数据。
- 标签：从 landmark open 起，至未来三日或 base state 首次改变（取较早者）的最不利 high/low 收益 `<=-8%` 为 `danger=1`。
- 每行记录 anchor、asset、side、episode id 与 holding age；未来路径只进入 label，不进入 feature。

## 3. 六个预注册 risk scores

数值越大表示预期风险越高：

1. `FAST_OPPOSE5`：`-side × selected z-momentum(5,28)`；
2. `MARKET_OPPOSE5`：`-side × mean(BTC,ETH z-momentum(5,28))`；
3. `ROLE_VIOLATION20`：`-side × (selected z20 - other z20)`；
4. `REL_EXTREME_RISE3`：`abs(relative z20)_t - abs(relative z20)_{t-3}`；
5. `GIVEBACK_ATR14`：入场后最有利 closed-day close 到当前 close 的逆向回吐 / ATR14；
6. `ENTRY_LOSS_ATR14`：当前 close 相对 entry open 的逆向浮亏 / ATR14。

## 4. 固定通过门槛

每个 feature 计算 growth/risk AUC、BTC/ETH pooled AUC，以及四个 `anchor×asset` 高低 tercile danger-rate edge。只有同时满足才 PASS：

- 两 anchor AUC 均 `>=0.60`；BTC/ETH AUC 均 `>=0.58`；
- 四 strata 各 `>=60` landmarks、至少 `8` 个 danger labels；
- 四 strata danger-rate edge 均 `>=10pp`；
- danger episodes 在两 anchor 中各 `>=8`，避免重复 landmarks 伪造容量。

若 `0/6` PASS，停止该状态转换方向，不建退出规则。若有 PASS，只允许另立 P5 exact exit/rearm 合同；不得从本轮 tercile 反推阈值。
