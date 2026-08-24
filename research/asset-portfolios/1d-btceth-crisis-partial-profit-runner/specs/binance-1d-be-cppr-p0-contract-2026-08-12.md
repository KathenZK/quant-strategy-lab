# BIN-1D-BE-CPPR P0 冻结合同

## 1. Exact control

- Family：`Binance-1D-BTCETH-Crisis-Partial-Profit-Runner`
- Control：COST P0 `EMA200/slope60/confirm3`，其shadow为CBCT growth + `1ATR/35%/2d` full profit protection。
- Control冻结指标：base `23.13209027523642x/-35.22258089123961%`；neutral router仍须复现CBCT exact control。
- Crisis routing、fresh-shadow join、成本、funding、stop、channel、timeout与优先级全部不变。

## 2. 唯一新增机制

- 新增 early partial signal：entry `ATR14`固定，MFE达到`1ATR`后，若一个完整UTC日close回吐至保留峰值盈利的`80%`以下，则次日open执行一次partial close。
- `partial_fraction ∈ {0.25,0.50,0.75}`；fraction指当时剩余quantity的比例。
- partial只触发一次；执行后剩余runner保持原entry fill、chandelier extreme、channel、timeout与`35%/2d` full protection。
- partial fill计`0.001` fee与不利slippage；已锁现金留在账户，不用于同笔runner加仓。
- 若同日已产生原full exit/channel/timeout，full exit优先，不安排partial；crisis enter open优先于scheduled partial并直接关闭全仓。
- crisis期间不做partial；dual-short basket完全沿用COST。

## 3. 执行与会计

- closed-day signal，next-open partial；delay审计再延迟一日。
- 日开盘顺序：crisis route/full exit → scheduled partial → fresh shadow entry → funding → stop → favorable/adverse/close。
- partial后每小时funding、PnL和风险只按剩余quantity；realized cash与runner未实现PnL共同构成equity。
- control fraction `0`、三条实验臂共4路；fraction0必须精确复现COST最佳路径。

## 4. 门禁

- base `>=20x/MDD<=20%`；
- stress `>=16x/MDD<=22%`；
- delay `>=8x/MDD<=25%`且log-growth retention `>=70%`；
- 完整年/rolling365d正收益比例均`>=70%`；
- partial events `>=3`，closed trades `>=20`，最大单笔正log-growth占比`<=30%`；
- partial数量、fee、realized PnL、runner quantity、funding与最终平仓逐项对账；无bankruptcy。
- 同路径去重后按MDD、stress retention、equity、交易数、fraction升序选唯一候选。

## 5. 停止与交付

- `0` hard-pass即`HARD-GATE-FAILED`并关闭family；不增加fraction网格、不改信号、不做第二次partial或trailing resize。
- 输出control parity、四路metrics、partial ledger、完整小时路径与HTML、测试、中文诊断、主账和索引。
- 只有development全门通过才揭示一次audit；否则audit/prospective保持sealed。
