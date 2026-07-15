# 六币资产专属多机制组合当前三个月诊断（2026-07-14）

## 结论

本轮找到一组通过当前诊断门槛、但尚未通过未来最终 OOS 的九腿组合。推荐主路线是“不抢占”：full `307` 笔、胜率 `90.55%`、年化权益倍率 `3.611x`、累计收益 `+1012.61%`、最大回撤 `-12.37%`；reused holdout `40` 笔、胜率 `92.50%`、收益 `+42.32%`、最大回撤 `-6.25%`。

该结果不是最终合格策略。`[2026-04-14T09:00Z, 2026-07-14T09:00Z)` 是 reused holdout；真正的最终 OOS 是冻结后的 `[2026-07-14T09:00Z, 2026-10-14T09:00Z)`，当前尚无完整数据。

## 数据与研究边界

- BTC、ETH、SOL、BNB、TRX：`2024-07-14` 起的 Binance USD-M perpetual 15m 数据。
- HYPE：Binance 上市后的 `2025-05-30` 起。
- 六币 15m 和 funding 数据质量 blocker 均为 `0`。
- 选择数据截止：`2026-04-14T09:00Z`，之后三个月只用于淘汰和风险诊断。
- 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、真实 funding；压力滑点 `8 bps/fill`。
- 多空双向、允许空仓、最大有效暴露小于 `3x`。

## 研究过程

1. 在六币上分别搜索趋势状态、突破延续和短周期反转，合计 `27,000` 组预拟合参数。
2. 首轮发现 15m 引擎遗漏持仓内 MAE 回撤后，首轮结果作废；修正后使用原随机种子和原搜索空间完整重跑。
3. 冻结每币每机制预拟合第一名后，才揭示当前三个月。
4. 将旧 `BIN-1H-AR-MAE` 的资产专属机制迁到当前统一数据湖，但不继承旧杠杆或旧结论。
5. 旧 1h 腿改成逐信号无状态机会；只有账户真正执行某一腿后，才写入该腿 cooldown，消除旧组合的阻塞反事实近似。
6. 用预拟合基础、8bps、K+2 三口径共同约束单腿暴露和账户缩放，再比较不抢占与强突破抢占。

## 冻结候选腿

| Asset | Timeframe | Mechanism | 诊断角色 | 腿暴露 | 不抢占有效暴露 | Reused evidence |
|---|---:|---|---|---:|---:|---|
| BTC | 1h | Keltner breakout | strong survivor | `1.0x` | `0.75x` | `8` 笔，`100%`，`+6.85%` |
| ETH | 15m | short reversal | insufficient evidence | `1.5x` | `1.125x` | `0` 笔 |
| ETH | 1h | RSI reversal | insufficient evidence | `1.0x` | `0.75x` | `1` 笔，`+0.92%` |
| SOL | 15m | breakout | strong survivor | `1.0x` | `0.75x` | `13` 笔，`92.31%`，`+11.21%` |
| BNB | 15m | breakout | insufficient evidence | `1.5x` | `1.125x` | `1` 笔，`+0.77%` |
| TRX | 1h | MACD flip | K+2 warning survivor | `2.5x` | `1.875x` | base `7` 笔、`100%`、`+7.09%`；K+2 reused 为负 |
| HYPE | 15m | trend state | conditional survivor | `1.0x` | `0.75x` | `7` 笔，`71.43%`，`+11.12%` |
| HYPE | 15m | long reversal | strong survivor | `0.5x` | `0.375x` | `8` 笔，`100%`，`+2.64%` |
| HYPE | 1h | DI cross | strong survivor | `1.5x` | `1.125x` | `9` 笔，`88.89%`，`+19.40%` |

“insufficient evidence”只表示当前三个月样本太少，不代表该腿独立通过最终门槛。它们进入冻结组合的依据是预拟合基础、8bps、K+2 均为正且回撤受控；最终去留只能由未来 OOS 决定。

## 两种账户路线

### 不抢占（推荐主路线）

- 账户缩放：`0.75`。
- 有仓期间忽略所有新信号；平仓后重新查看当前新信号，不使用积压信号。
- 旧 1h 腿的 cooldown 只在该腿真实成交后生效。

| Scenario | Window | Annual | Return | Max DD | Trades | Win |
|---|---|---:|---:|---:|---:|---:|
| base | full | `3.611x` | `+1012.61%` | `-12.37%` | `307` | `90.55%` |
| base | all-six-active | `4.652x` | `+364.50%` | `-12.37%` | `188` | `90.96%` |
| base | reused holdout | `4.12x` | `+42.32%` | `-6.25%` | `40` | `92.50%` |
| 8bps | full | `3.303x` | `+841.33%` | `-14.51%` | `303` | `90.10%` |
| K+2 | full | `2.207x` | `+341.52%` | `-18.47%` | `307` | `85.99%` |

### 强突破抢占（对照路线）

- 账户缩放：`0.50`。
- 只有其他币的 breakout 才能抢占。
- 挑战腿强度 `>=0.70`、高于当前腿至少 `0.05`，且当前仓至少持有 `8h`。
- full base 只发生 `4` 次抢占；reused holdout 为 `0` 次。

| Scenario | Window | Annual | Return | Max DD | Trades | Win |
|---|---|---:|---:|---:|---:|---:|
| base | full | `2.486x` | `+452.38%` | `-9.29%` | `321` | `89.41%` |
| base | all-six-active | `2.896x` | `+189.60%` | `-8.35%` | `194` | `90.21%` |
| base | reused holdout | `2.53x` | `+26.76%` | `-4.18%` | `40` | `92.50%` |
| 8bps | full | `2.337x` | `+391.90%` | `-9.83%` | `317` | `88.96%` |
| K+2 | full | `1.708x` | `+172.91%` | `-14.59%` | `322` | `83.85%` |

抢占路线通过当前诊断门槛，但为了让 K+2 回撤低于 `20%`，账户缩放必须从 `0.75` 降到 `0.50`。它的基础收益也低于不抢占路线，而且最近三个月没有发生抢占，因此当前不作为首选。

## 硬门槛判定

两条路线在当前 diagnostic 口径都满足：

- full trades `>=200`；
- reused trades `>=30`；
- full/reused 胜率 `>=80%`；
- full/reused 最大回撤严格 `<20%`；
- full/reused 收益为正；
- 8bps 与 K+2 full 收益为正且最大回撤 `<20%`。

未来最终 OOS 尚未产生，因此 `final_future_oos_pass = null`，禁止写成已最终达标、可 dry-run 或可实盘。

## 风险与下一门禁

- ETH 和 BNB 在 reused holdout 的独立交易数不足，未来 OOS 可能直接淘汰这些腿。
- TRX MACD 的 reused K+2 为负，虽然全窗 K+2 为正，仍需重点观察延迟风险。
- full 从其他五币可交易的 `2024-08-28` 开始；`all-six-active` 从 `2025-07-14` 开始，只有 `188/194` 笔。full 最低交易数已通过，但全六币共同历史的样本仍较短。
- 尚未完成 production runner、订单状态恢复、交易所过滤器、保护单、kill switch 和实盘滑点审计。

## 证据

- 冻结规格：[../specs/binance-as6s-future-oos-freeze-2026-07-14.md](../specs/binance-as6s-future-oos-freeze-2026-07-14.md)
- 组合结果：[`../artifacts/binance_hybrid_asset_specific_account_2026-07-14.json`](../artifacts/binance_hybrid_asset_specific_account_2026-07-14.json)
- 组合交易：[`../artifacts/binance_hybrid_asset_specific_account_trades_2026-07-14.csv`](../artifacts/binance_hybrid_asset_specific_account_trades_2026-07-14.csv)
- 预拟合搜索：[`../artifacts/binance_15m_as6s_prefit_search_2026-07-14.json`](../artifacts/binance_15m_as6s_prefit_search_2026-07-14.json)
- Reused reveal：[`../artifacts/binance_15m_as6s_reused_holdout_2026-07-14.json`](../artifacts/binance_15m_as6s_reused_holdout_2026-07-14.json)
- 旧 1h 机制迁移：[`../artifacts/binance_legacy_asset_specific_1h_sleeves_2026-07-14.json`](../artifacts/binance_legacy_asset_specific_1h_sleeves_2026-07-14.json)
