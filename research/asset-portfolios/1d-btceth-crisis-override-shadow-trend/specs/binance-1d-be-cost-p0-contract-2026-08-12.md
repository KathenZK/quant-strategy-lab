# BIN-1D-BE-COST P0 冻结合同

## 1. 研究身份与 exact shadow

- Family：`Binance-1D-BTCETH-Crisis-Override-Shadow-Trend`
- Exact shadow：CBCT P1 growth，固定 `entry20/exit10/EMA50/trail5ATR/confirm2/cooldown7/maxhold120` + `1ATR/35%/2d` profit protection。
- Shadow 始终按冻结规则独立推进信号、仓位和退出；账户是否分配资本不反向修改 shadow 状态。
- 研究问题：双资产慢周期 crisis state 能否在不改变 shadow alpha、不增加总 gross 的前提下，替换危机阶段的错误方向并达到 `20x/20%`。

## 2. Crisis state

对 BTC/ETH 各计算完整 span 的 `EMA(crisis_ema)`：

- raw crisis：两资产均 `close<EMA`，且各自 `EMA[t]<EMA[t-slope_days]`；
- 其余 raw neutral；
- state 初始 neutral；raw 与当前 state 不同时，连续 `confirm_days` 个完整日相同才更新；
- 当日收盘 state 只在下一 UTC 日 open 生效；delay audit 再延迟一日。

冻结参数：

- `crisis_ema ∈ {100,200,300}`；
- `slope_days ∈ {20,60}`；
- `confirm_days ∈ {1,3}`；
- 共 `12` 个配置，不搜索跌幅、波动率、funding或回撤阈值。

## 3. 账户路由

- Normal：账户 flat 时，只在 shadow 产生 fresh entry 的同一时点复制该 entry；复制后按 shadow 的 exit timestamp/reason退出。
- Crisis enter：下一 open 先关闭账户已有 shadow position，再以当时总权益各分 `50%` 建 BTC/ETH short，两个数量持有期固定，总初始 gross约`1x`。
- Crisis hold：双腿只计真实 fee/slippage/funding与价格；不 resize、不加仓、不设结果后 stop。
- Crisis exit：下一 open 同时平两 short，账户转 flat；同一 open 不接回 shadow。
- 若 shadow 在 crisis 期间开仓或仍持仓，账户忽略；只有 crisis exit 之后的下一笔 fresh shadow entry 才可复制，禁止中途加入旧 shadow trade。
- Crisis 与 shadow position 互斥，不存在 `1x+1x`叠加。

## 4. 小时顺序与保守风险

- 日开盘路由/订单 → funding → shadow intrahour stop → favorable → adverse → close；
- dual short favorable 使用两腿 low、adverse 使用两腿 high，并保守假设同时发生；
- shadow daily exit按open，stop按冻结 stop mark/gap；override 强制退出按当小时 open；
- terminal open 强平所有账户仓位。

Control 的 crisis state 全 neutral 时，账户 terminal、trades与 ordered MDD 必须与 exact CBCT shadow在 `1e-12` 内一致。

## 5. 成本、压力与门禁

- base/stress `4/8bps/fill`，fee `0.001/fill`，actual funding；
- delay：shadow 所有 daily orders 与 crisis state execution 均额外延迟一天，小时 stop仍因果执行；
- base hard target `>=20x/MDD<=20%`；
- stress `>=16x/MDD<=22%`；
- delay `>=8x/MDD<=25%` 且 log-growth retention `>=70%`；
- 完整年/rolling 365d 正收益比例均 `>=70%`；
- closed account trades `>=20`，crisis episodes `>=2`，BTC/ETH crisis legs逐笔对账；
- 最大单笔正 log-growth占比 `<=30%`，无 sleeve/leg bankruptcy；
- 同路径去重后按 MDD、stress retention、equity、交易数、参数字典序选唯一候选。

## 6. 停止规则与交付

- `0` hard-pass：`HARD-GATE-FAILED`并关闭 family；不扩 EMA/slope/confirm，不新增 return/vol阈值，不加 stop/TP/leverage。
- 交付12路JSON/CSV、control parity、crisis episode/leg ledger、完整交易路径HTML、测试、中文诊断、主账和索引。
- 只有 development 全门通过才可一次性打开 audit；否则 audit/prospective始终未读取。
