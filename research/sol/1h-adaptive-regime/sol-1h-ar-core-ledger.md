# SOL-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`SOL-1H-Adaptive-Regime`
- Short id：`SOL-1H-AR`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Version lineage：独立家族；不得引用 BTC/HYPE 的裸版本号或继承其版本身份

## 当前状态

`active diagnostic search / no registered version / not promoted / not live-ready`。

## 硬门槛

- 年化权益倍率 `>=10.0x`，等价于年化收益 `>=900%`。
- 胜率 `>=50%`。
- 最大回撤严格小于 `20%`。
- 最近三个月 locked OOS 必须按预冻结规则一次性评估。
- 进入任何 promotion 状态前必须通过 live-executable 审计，并具备可复现的生产状态机证据。

## 版本表

当前没有登记版本。广搜冠军或硬门槛命中都只构成 diagnostic observation；除非用户明确要求登记/冻结/promote，且证据满足对应状态要求，否则不得分配 `Vx`。

## 证据索引

- 数据抓取与质量检查：`scripts/fetch_sol_binance_1h.py`
- 多指标宽搜索：`scripts/research_sol_1h_adaptive_regime_search.py`
- prefit Pareto 邻域精调：`scripts/research_sol_1h_adaptive_regime_refine.py`
- 冻结边界与实盘可执行审计：`scripts/audit_sol_1h_adaptive_regime_boundary.py`
- 数据与搜索产物：`artifacts/`
