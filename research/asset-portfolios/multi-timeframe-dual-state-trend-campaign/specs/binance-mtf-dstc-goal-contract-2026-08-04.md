# BIN-MTF-DSTC Goal Research Contract

## 1. Objective

为 HYPEUSDT primary 与 BTCUSDT/ETHUSDT independent controls 搜索一个可实盘执行的多周期 Trend Campaign Engine：日线提出并终止长期 Campaign，4h 确认结构，1h 等待回调，15m restart/next-open 试单；只有真实盈利和新回调重启共同出现才增加风险；单腿止损不自动终止 Campaign。

最低候选目标：base net annual equity multiple `>=2x`、MDD `<=20%`、PF `>=1.3`、effective leverage `<=3x`。`5x` 为 Tier S，`20x` 为 Stretch。若充分穷尽预声明机制仍失败，以可信 NO-GO 完成，禁止 OOS 救参。

## 2. Materially New Boundary

本家族不继承已关账 `BIN-MTF-PTC` 的 continuation probability、24h failure exit、336h timeout、参数或收益；也不继承 `HYPE-15M-MTPP` 的 RSI/KDJ 入口、动态 stop 或 prospective 数据。

实质新机制：

```text
position state：当前 lot 是否应止损、减仓或退出
campaign state：长期方向假设是否仍允许持有或重新试单
```

position stop 可以把账户变成 flat，但只要 Campaign 仍 active，状态机可在有限预算内等待下一次独立回调/restart；Campaign invalidation 才停止该方向全部重入。

## 3. 固定研究臂

### A. Baselines

1. `daily_cross1_probe`：MA7 对齐后 Probe，一次反侧收盘结束 Campaign；无加仓。
2. `dual_state_probe`：双状态、结构 stop、有限重入；无加仓。
3. `dual_state_static_full`：相同入场/退出但首笔即完整计划量，归因 Probe 价值。

### B. Entry Arms

- `immediate_probe`：4h candidate 后首个合格 1h pullback close，下一 15m open；
- `restart2`：合格回调后 15m 突破前 2 根顺势极值且 TR 高于过去 20 根中位数；
- `restart4`：同上但突破前 4 根；
- wait `12/24/36h`；未成交 plan 到期前不能预知失败并尝试下一 candidate。

### C. Campaign State

Development/validation 分阶段搜索，不一次联合穷举：

- MA family：SMA `5/7/10/14`，primary anchor SMA7；
- slope persistence `1/2/3d`；
- candidate price band `0/0.5ATR`；
- invalidation `band+4h structure`、`slope reversal+4h structure`、`wide 4h structure only`；
- hard invalidation sensitivity：wrong-side `0.5/1.0ATR` 与 `1/2` closed-day persistence。

所有候选必须先做单变量消融和参数邻域稳定性；MA长度搜索不能使用 historical final audit 排名。

### D. Pullback / Stop

- 1h minimum pullback `0.25/0.5/0.75 ATR24`；
- maximum impulse retracement `0.33/0.5/0.618`；
- original lot stop：最近 `6/12` 根完整 4h structure extreme 外 `0/0.25 ATR1h`；
- 最小 stop distance `1.5%/3%`，最大 `15%`；
- stop 成交后不得自动收紧其他 lot，Campaign state 独立更新。

### E. Probe / Add / Retry

- 每层风险中心值 `0.25% equity`，总计划风险 `1%`；
- `1/2/4` layers；四层资格序列比较 `0.5/1/2R` 与 `0.5/1.5/3R`；
- 获得资格后仍须新的 1h pullback + 15m restart；亏损中禁止 add；
- 每层 retry `0/1` 次；Campaign 累计 loss budget `1.5%/2%/3%`；
- projected stop risk 与 3x effective leverage 不允许事后超限。

### F. Profit / Campaign Exit

- `no_mfe`；
- `mfe50_all`：Campaign MFE `>=2R` 后，完整 1h close 回吐 `>50%`，下一 15m open 全退；
- `mfe50_adds`：只卸新增 layers，Probe 交给 Campaign invalidation；
- 最长持有只作安全对照 `14/30/60d`，不得用短 timeout 制造低回撤；
- 无固定 take-profit。

## 4. Hierarchical Search

1. 数据、时间可见性、账户与 baseline parity；
2. Daily Campaign state 单变量消融；
3. immediate/restart entry 归因；
4. structure stop、retry 与 Campaign invalidation；
5. Probe 对 static full；
6. add layers 与 MFE 保护；
7. 资产专属 Pareto 粗搜；
8. 稳定邻域精搜；
9. rolling validation、historical final audit、成本/延迟/杠杆压力；
10. 只有机制通过后机械风险 scaling。

每阶段冻结 experiment registry、候选数、选择指标和停止条件。主目标为约束下净对数增长；共同约束包括 MDD、PF、Calmar、campaign 数、turnover、top-N profit concentration、remove-top-N、年度/块稳定性和最近切片。

## 5. Hard Gates

- closed-bar/next-open、stop gap、funding、lot ledger、restart、same-bar conservative ordering 全部 PASS；
- base annual equity multiple `>=2x`，MDD `<=20%`，PF `>=1.3`；
- 8bps stress 净正，12bps 不发生机制崩溃；
- 至少 30 个独立 Campaign，否则 `insufficient`；
- rolling OOS 多数窗口为正，最近 3m/6m/1y 不得同时失败；
- top-1/top-3 gross-profit concentration 不得超过 `35%/65%`，remove-top-3 后不得由正转为严重负；
- 参数邻域保持同方向，单资产/方向分开；
- max fill/effective leverage `<=3x`、hard stop risk breach `0`。

## 6. Required Deliverables

- 数据质量与 split audit；
- frozen contracts、experiment registry、全候选与 Pareto frontier；
- 双状态账户引擎、逐 Campaign/lot/action/equity 账本和测试；
- 消融、rolling OOS、历史 final audit、recent slices、成本/延迟/杠杆/集中度压力；
- HYPE/BTC/ETH 独立结论与交互式 campaign HTML；
- 明确 `GO-to-prospective / NO-GO / BLOCKED`；
- 只有通过历史门禁才写 runner gap 与 handoff-ready spec，不能提前创建 live spec。
