# Binance 1D MA7 P2-D Long Risk / Exit 机制裁决

## 结论

P2-C 归因支持的 `2 ATR` initial stop、单日 `close<MA7` 结构退出及二者组合，均未在 BTC/ETH 上形成共享的风险修复。`0/4` 臂达到 `>=20x / MDD<=20%`，`0/3` 修复臂通过预注册 soft-continue 门。

`H2` 只轻微改善 BTC，却显著恶化 ETH；`X0` 改善 BTC 回撤与年度正收益比例，但大幅破坏 ETH 收益且未降低其尾部风险；组合继承两者缺点。按冻结合同关闭该 risk/exit 修复路径，不追加 `1.5/2.5/3 ATR`、其它 MA buffer 或 cooldown 救参。

## 冻结范围

- 合同：[P2-D 机制合同](../specs/binance-1d-ma7-p2d-long-risk-exit-mechanisms-contract-2026-08-12.md)
- Parent：[P2-C episode 归因](binance-1d-ma7-p2c-long-pullback-episode-attribution-2026-08-12.md)
- Development：`2019-12-24` 至 `2025-08-07` exclusive
- 成本：`0.001/fill + 4 bps`，压力 `8 bps`，实际 funding
- 执行：closed daily signal、next-open、真实 `1h` stop path、约 `1x`
- audit/prospective：未读取

## Full development

| Arm | BTC equity / MDD | ETH equity / MDD | Hard target | Soft continue |
| --- | ---: | ---: | --- | --- |
| `P0_PULLBACK` | `6.316x / -52.80%` | `6.016x / -56.76%` | FAIL | parent control |
| `H2_INITIAL_STOP` | `5.380x / -50.88%` | `4.327x / -64.67%` | FAIL | FAIL |
| `X0_STRUCTURE_EXIT` | `5.395x / -46.52%` | `2.258x / -60.59%` | FAIL | FAIL |
| `H2_X0_COMBINED` | `4.780x / -46.52%` | `1.563x / -65.03%` | FAIL | FAIL |

## 压力与延迟

| Arm | BTC 8bps / +1d | ETH 8bps / +1d |
| --- | ---: | ---: |
| `P0_PULLBACK` | `5.753x / 2.137x` | `5.482x / 4.615x` |
| `H2_INITIAL_STOP` | `4.893x / 1.886x` | `3.939x / 2.570x` |
| `X0_STRUCTURE_EXIT` | `4.764x / 1.694x` | `1.972x / 3.732x` |
| `H2_X0_COMBINED` | `4.217x / 1.729x` | `1.365x / 2.621x` |

全部压力终值仍为正，但额外一天延迟下 BTC parent MDD 为 `-74.91%`；H2 仍为 `-74.05%`，X0 也有 `-57.69%`。收益为正不能覆盖路径风险与硬门失败。

## Calendar / rolling 稳定性

| Arm | BTC calendar positive | ETH calendar positive | BTC rolling-365 positive | ETH rolling-365 positive |
| --- | ---: | ---: | ---: | ---: |
| `P0_PULLBACK` | `71.43%` | `42.86%` | `78.95%` | `73.68%` |
| `H2_INITIAL_STOP` | `71.43%` | `42.86%` | `78.95%` | `68.42%` |
| `X0_STRUCTURE_EXIT` | `85.71%` | `57.14%` | `84.21%` | `68.42%` |
| `H2_X0_COMBINED` | `85.71%` | `57.14%` | `78.95%` | `57.89%` |

X0 的 calendar 正收益比例改善，但 ETH rolling 比例下降且全段收益/回撤明显恶化；按合同不能用一个稳定性维度掩盖另一个资产的退化。

## 因果复盘

### H2 initial stop

- BTC protective stop 从 11 次增至 34 次，收益下降 `0.936x`，MDD只改善 `1.93pp`；
- ETH protective stop从12次增至41次，收益下降`1.690x`，MDD反而恶化`7.91pp`；
- MAE 分布能区分历史 winner/loser，但动态账户路径中止损后重新入场、错过后续趋势与 short 时序改变，说明“逐笔分离点”不能直接推导账户级 MDD 改善。

### X0 structure exit

- BTC MDD改善`6.28pp`，但交易数由117增至156、turnover升至`940.6x`；
- ETH交易数增至169，终值从`6.016x`降至`2.258x`，MDD仍`-60.59%`；
- 原迟滞退出确实是坏结果标签，但把它整体替换成单日 cross 会频繁平仓/重入，破坏大趋势持有。需要状态化 lifecycle，而不是更紧的静态 exit。

### Combined

H2+X0 未产生互补：ETH 仅 `1.563x/-65.03%`，rolling 正收益比例降至 `57.89%`。两个局部合理机制叠加后仍路径恶化，符合 HYPE 演进中“单点修复不能替代状态连续性”的经验，但本轮结论来自 BTC/ETH 自身 development 证据。

## 裁决与下一步边界

- Hard target hits：`0`
- Soft continue hits：`0`
- P2-D：`HARD-TARGET-FAILED / explore / not promoted / not live-ready`
- 关闭：当前 long pullback 上的静态 initial-stop / static cross-exit 修复
- 禁止：按本轮结果继续搜索 stop ATR、exit buffer、confirm days、cooldown
- 下一步：回到完整共享参数状态机层，执行预冻结的跨资产 hard-MDD 广搜；选择目标必须在排名前 hard reject `MDD>20%`，不能沿本轮局部最优继续堆模块

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_p2d_long_risk_exit_mechanisms_2026-08-12.json) — SHA256 `9a5baf0a74fdc33f616fa02a2c06623e87c66c5334b532adbf885237a8b86844`
- [全段/年度/滚动指标](../artifacts/binance_1d_ma7_p2d_long_risk_exit_mechanisms_2026-08-12_metrics.csv) — SHA256 `a8c4a81f9ff5b237c70817e85da270cd02531b79c90484f336a5cfefbe412987`
- [复现脚本](../scripts/audit_binance_1d_ma7_p2d_long_risk_exit_mechanisms.py)

