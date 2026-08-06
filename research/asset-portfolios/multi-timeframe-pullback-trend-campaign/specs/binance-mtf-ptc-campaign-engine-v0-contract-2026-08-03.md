# BIN-MTF-PTC Campaign Engine V0 冻结合同

本批次只回答：在 Probe Search V0 已由 development-inner 唯一选出的资产专属入口上，冻结的动态加仓与退出状态机能否在原 validation 改善净增长和趋势捕获。不得重新搜索入口，不得读取 locked historical evaluation。

## 固定入口

- BTC：onset 24h、development probability q80、pullback 0.50 ATR、最大回撤 50%、restart 4、stop buffer 0.25 ATR；
- ETH：onset 24h、development probability q90、pullback 0.50 ATR、最大回撤 60%、restart 1、stop buffer 0.25 ATR；
- HYPE：onset 24h、development probability q60、pullback 0.75 ATR、最大回撤 60%、restart 1、stop buffer 0.25 ATR；
- 模型只在各资产完整 development 拟合；validation 只运行冻结状态机；locked evaluation 不运行。

## 因果时间语义

- 1h 特征索引是完整 1h bar 的最早可见收盘时点；4h decision 只使用该时点已闭合历史；
- 1h pullback 和 15m restart 全部 closed-bar 判定，下一 15m open adverse fill；
- add 候选必须在对应 layer 已由 closed 15m bar 达到 MFE 门槛之后出现；预先计算成功/失败路径只用于加速，运行时仍按 candidate timestamp 和 execution timestamp 逐事件释放，不允许未来信息改变当前动作；
- 同 bar 顺序：已持仓 funding、gap stop、scheduled validation/timeout/risk action、pending add/probe、intrabar stop、closed-bar 状态更新；stop 与未来 high/low 冲突时 stop 优先。

## Lot 与风险

- Probe、Add-1、Add-2、Add-3 均为独立 lot 和独立结构 stop；每层请求 entry-equity 的 0.25% 完整 stop-out risk；
- 加仓资格为 campaign initial MFE 达 +0.5R、+1R、+2R；资格不是成交；
- 每层只接受资格形成后的下一个同方向强 continuation candidate；结构尝试失败最多重试一次，第二次失败关闭该层及更高层；
- 结构失败在 candidate 当下仍是未知未来：失败 plan 必须保持 pending 至 24h 到期，期间占用该层/Probe 等待槽；只有实际 restart 成交、结构到期或新出现的反方向强 candidate 才能解除，禁止预知失败后提前尝试下一信号；
- add execution 时 campaign liquidation value 必须高于 entry equity，亏损中禁止加仓；
- quantity 同时受 layer risk、总 projected operational stop-out loss `<=0.9%`、hard loss `<=1%`、effective leverage `<=3x` 约束；风险不足只做 partial add；
- funding 后若 projected loss 超 0.9%，同一 open 先 LIFO trim added lots；不能恢复且超 1% 时全退并记 blocker。

## 延续性如何驱动仓位

- 每个 4h decision 对新 impulse 重算 development-fitted continuation probability；
- 只有同方向且高于资产冻结阈值的 candidate 才能发起 add pullback attempt；
- 高分反方向 candidate 取消 pending add、永久关闭后续 adds，并在当前可执行 open 卸掉全部新增 lots；Probe 仍由自身结构 stop 管理；
- 必须在 actions/ledger 中记录 candidate probability、方向和对仓位的影响，不能只在入场时使用一次分数。

## Stop 与退出

- 每个 lot 的初始 stop 为其 pullback extreme 外冻结 buffer；stop 永不放宽；
- campaign 达 +2R 后，新 add 的 causal pullback/restart 可把旧 lot stop 收紧到新结构 stop，但不得越过当前可成交价格；
- +2R 后，仅在完整 1h close 的当前进展低于 peak MFE 50% 时，下一 15m open LIFO 卸掉所有新增 lots，Probe 保留；此后不再加仓；
- 入场 24h 未达到 +1R 全退；最长 336h 全退；无固定止盈。

## Validation 比较与停止条件

同一 validation 至少比较：

1. Probe-only；
2. Full Campaign；
3. no-add；
4. no-half-giveback-reduction；
5. no-opposite-score-reduction。

基础成本 fee 10bps/fill、slippage 4bps/fill、真实 funding；另跑 gross 与 8bps stress。报告逐 15m liquidation MDD、bar 内不利极值回撤、交易/lot/action、费用、funding、PF、胜率、正偏、top-1/top-3 concentration、方向和年份归因、最大杠杆、最大 projected stop-out risk、风险违规。若 Full Campaign 不能稳定优于 Probe-only，动态加仓机制判失败，不得靠 locked evaluation 救参。
