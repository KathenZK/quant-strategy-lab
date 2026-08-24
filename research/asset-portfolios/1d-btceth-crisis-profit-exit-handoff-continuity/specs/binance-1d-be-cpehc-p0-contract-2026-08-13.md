# BIN-1D-BE-CPEHC P0 冻结合同

## 1. 控制与单一研究问题

- Family：`Binance-1D-BTCETH-Crisis-Profit-Exit-Handoff-Continuity`
- External exact control：COST `EMA200/slope60/confirm3`，`23.1321x/-35.22%`。
- H0 internal control：将shadow full protection固定为`1ATR activation / 20% giveback / 1d close confirm`，不允许handoff；其余COST路由完全不变。
- H1：H0 early full exit后，flat shadow可在有限窗口内单次同方向continuation handoff。
- 研究问题：handoff能否在保留early exit风险收益的同时，因果收回被截断的大趋势。

## 2. Handoff状态机

- 仅regular shadow trade因`profit_protection`退出时armed；stop/channel/timeout/crisis override不armed。
- 冻结level为该笔退出前已知的favorable extreme：long为最高high，short为最低low。
- 从profit-exit当日完整close开始观察；long须`close>level`，short须`close<level`，连续`handoff_confirm`日后下一open入场。
- `handoff_window_days ∈ {7,14,30}`；`handoff_confirm ∈ {1,2}`，共6个H1配置。
- window过期即消费；期间若更早出现regular signal，执行更早者并消费handoff；同一entry day时handoff优先。
- handoff保持原资产/方向、约`1x`，沿用H0 early full protection、channel/chandelier/timeout；handoff trade即使profit exit也不得再次armed，一个root最多一次handoff。
- standard cooldown不阻止handoff，但仍约束regular entry。

## 3. Crisis与账户路由

- 固定COST crisis `EMA200/slope60/confirm3`及`0.5x+0.5x`short basket。
- Crisis state优先：账户不复制crisis期间任何regular/handoff shadow entry；exit后只等未来fresh shadow entry，禁止中途加入。
- H0/H1 shadow始终独立推进；账户routing不得反向改变shadow。

## 4. 数据、成本与prospective

- development `[2019-12-24,2025-08-07)`；researcher-exposed audit `[2025-08-07,2026-08-10)`继续sealed。
- 本合同冻结日`2026-08-13`；不读取冻结日后行情。首个prospective eligible close `>=2026-08-14`，最早next-open execution `>=2026-08-15 00:00 UTC`。
- fee `0.001/fill`、base/stress `4/8bps/fill`、actual funding；delay所有daily orders再延迟一天，小时stop因果不变。

## 5. 门禁

- base `>=20x/MDD<=20%`；stress `>=16x/MDD<=22%`；
- delay `>=8x/MDD<=25%`且log-growth retention `>=70%`；
- 完整年/rolling365d正收益比例均`>=70%`；
- handoff entries `>=2`、closed trades `>=20`、最大单笔正log-growth占比`<=30%`；
- handoff level、armed/expired/consumed、next-open fills、crisis collision、funding与restart state可对账；无bankruptcy。
- 同路径去重后按MDD、stress retention、equity、交易数、window/confirm字典序选唯一候选。

## 6. 停止与交付

- `0` hard-pass即`HARD-GATE-FAILED`并关闭family；不扩window/confirm，不加buffer/pending/repeated handoff，不用杠杆或risk scaling。
- 输出COST/H0 parity、6路H1、handoff ledger、完整小时路径HTML、测试、中文诊断、主账与索引。
- 只有development全门通过才允许一次性打开audit；否则audit/prospective保持未读取。
