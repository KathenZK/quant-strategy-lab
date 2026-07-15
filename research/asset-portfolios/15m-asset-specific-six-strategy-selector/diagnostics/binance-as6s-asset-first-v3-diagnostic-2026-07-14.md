# 六币单币优先 V3 候选诊断（2026-07-14）

## 结论

本轮已把研究顺序从“先找组合形状”纠正为“先审计单币候选，再做账户组合”。当前形成两条**未登记、不可上线**的 V3 candidate observation：

- `nonpreemptive`：持仓期间绝不被其他币抢占；
- `strong-breakout-preemptive`：只有另一币的强突破候选满足冻结阈值时才允许抢占。

两条路径在当前已知数据上均满足账户层胜率 `>=80%`、最大回撤 `<20%`、8 bps 压力为正、K+2 为正以及约 `0.75` 笔/日的最低频率门槛。它们仍未通过 `[2026-07-14T09:00Z, 2026-10-14T09:00Z)` 的未来最终 OOS，因此不得登记为新版本，也不得写成 live-ready。

全六币都已上市后的可比区间从 `2025-05-30T10:30Z` 开始。该区间 nonpreemptive 为 `391` 笔、`0.954` 笔/日、胜率 `86.7%`；strong-breakout-preemptive 为 `396` 笔、`0.966` 笔/日、胜率 `86.4%`。全区间 `0.75` 笔/日主要被 HYPE 上市前的不可交易时期稀释；当前可比频率已接近目标的 `1` 笔/日下沿。

## 为什么旧流程漏掉了收益腿

旧流程每个币、每种机制只把预拟合第一名送入账户，随后直接做组合子集搜索。这会过早删除“单币排名不是第一、但跨窗口和成本压力更稳”的候选。本轮把旧预拟合前沿的 `216` 个候选逐个重放，补做实际 funding、4/8 bps、K+1/K+2、持仓内 MAE 与当前三个月诊断。

最明显的漏选是 `SOLUSDT_breakout_000222`：

| 情景 | 全区间笔数 | 胜率 | 收益 | 最大回撤 |
|---|---:|---:|---:|---:|
| 4 bps / K+1 | 77 | 90.9% | +194.9% | -12.3% |
| 8 bps / K+1 | 77 | 90.9% | +185.9% | -12.3% |
| 4 bps / K+2 | 77 | 89.6% | +182.5% | -12.7% |

这证明单币前沿审计是必要步骤；不能只看旧组合最终选中的腿来判断某个币“找不到策略”。

## 单币机制池

最终账户候选池共 `17` 条腿，组合选择 `15` 条。单币不再强制使用同一种趋势、突破或反转模板；只保留该币实际通过成本和分段诊断的机制。

| 币种 | 进入最终账户搜索的已选机制 |
|---|---|
| BTC | 1h Keltner breakout |
| ETH | 15m breakout、15m trend state、1h RSI reversal |
| SOL | 15m breakout、15m reversal、15m trend state、1h Donchian breakout |
| BNB | 15m breakout、1h wick reject |
| TRX | 1h MACD flip |
| HYPE | 15m Clean-RSI reversal、15m breakout、15m reversal、1h DI cross |

Clean-RSI 高频机制按每个币自身 ATR96 分布重新搜索，不再使用 HYPE 的绝对波动门槛。资金费与填单压力复核结果为：

| 币种 | 资金费后 hard-80 | 允许进入组合的 >=70% 候选 | 结论 |
|---|---:|---:|---|
| BTC | 0 | 0 | 全区间成本后期望为负，拒绝 |
| ETH | 0 | 0 | 全区间成本后期望为负，拒绝 |
| SOL | 0 | 0 | 由突破机制承担收益，不强塞 RSI |
| BNB | 0 | 0 | 全区间成本后期望为负，拒绝 |
| TRX | 0 | 0 | 保留 1h MACD，不强塞 RSI |
| HYPE | 11 | 13 | 保留最高稳健频率候选作为补充腿 |

HYPE Clean-RSI 补充腿的冻结候选为 `RSI7 / 40-60 / ATR96>=0.9% / rvol 不限 / TP 1.2% / SL 4.5% / 最长 48 bars`。它在 4 bps K+1 全区间约 `0.556` 笔/日、胜率 `85.5%`、收益 `+79.4%`、回撤 `-12.1%`；8 bps K+2 仍为正，但当前三个月 K+1 胜率为 `79.2%`。这符合“单腿可低于 80%，最终账户必须 >=80%”的新口径。

## 账户结果

### Nonpreemptive

账户缩放 `0.40`，实际最大单笔杠杆 `1.20x`。

| 情景 | 笔数 | 笔/日 | 胜率 | 总收益 | 年化权益倍数 | 最大回撤 | 当前三个月收益 / 胜率 / 回撤 |
|---|---:|---:|---:|---:|---:|---:|---|
| 4 bps / K+1 | 548 | 0.750 | 85.4% | +3387.6% | 5.91x | -12.9% | +72.5% / 84.8% / -7.5% |
| 8 bps / K+1 | 543 | 0.743 | 85.3% | +2417.7% | 5.02x | -13.3% | +57.1% / 84.4% / -7.6% |
| 4 bps / K+2 | 555 | 0.760 | 81.1% | +1008.7% | 3.33x | -19.3% | +49.4% / 82.5% / -15.0% |

### Strong-breakout-preemptive

账户缩放 `0.33`，实际最大单笔杠杆 `0.99x`；抢占参数为 `threshold=0.75 / margin=0.05 / min_hold=1h`。

| 情景 | 笔数 | 笔/日 | 胜率 | 总收益 | 年化权益倍数 | 最大回撤 | 当前三个月收益 / 胜率 / 回撤 |
|---|---:|---:|---:|---:|---:|---:|---|
| 4 bps / K+1 | 557 | 0.763 | 85.5% | +2005.5% | 4.59x | -8.3% | +57.1% / 84.8% / -6.2% |
| 8 bps / K+1 | 553 | 0.757 | 85.2% | +1501.6% | 4.00x | -8.7% | +45.4% / 84.4% / -6.2% |
| 4 bps / K+2 | 570 | 0.780 | 80.9% | +797.6% | 3.00x | -17.2% | +36.3% / 81.5% / -14.5% |

抢占路线的基准收益低于 nonpreemptive，主要原因不是策略较差，而是为了让 K+2 回撤也低于 `20%`，账户缩放从 `0.40` 降到了 `0.33`。它的优势是基准回撤更低，不应只比较未风险归一化的总收益。

## 基准路径近期切片

| 路径 | 区间 | 收益 | 胜率 | 交易数 | 最大回撤 |
|---|---|---:|---:|---:|---:|
| nonpreemptive | 1d | 0.0% | 无交易 | 0 | 0.0% |
| nonpreemptive | 7d | -3.2% | 66.7% | 3 | -5.3% |
| nonpreemptive | 1m | +13.3% | 79.2% | 24 | -7.5% |
| nonpreemptive | 3m | +72.5% | 84.8% | 79 | -7.5% |
| nonpreemptive | 6m | +289.8% | 87.6% | 170 | -8.0% |
| nonpreemptive | 1y | +1146.6% | 87.1% | 348 | -8.0% |
| strong-breakout-preemptive | 1d | 0.0% | 无交易 | 0 | 0.0% |
| strong-breakout-preemptive | 7d | -2.6% | 66.7% | 3 | -4.4% |
| strong-breakout-preemptive | 1m | +11.0% | 79.2% | 24 | -6.2% |
| strong-breakout-preemptive | 3m | +57.1% | 84.8% | 79 | -6.2% |
| strong-breakout-preemptive | 6m | +219.6% | 87.7% | 171 | -6.7% |
| strong-breakout-preemptive | 1y | +726.8% | 86.9% | 351 | -6.7% |

最近 `1m` 和 `7d` 的胜率低于账户硬门槛，且最近 `7d` 为负；硬门槛当前只对全区间与锁定的三个月诊断执行，不能把短切片样本不足掩盖掉。

## 执行与数据口径

- 信号仅使用闭合 K；15m 信号默认下一根开盘成交，另做 K+2；
- 高周期特征按 known-time 合并，不读取未闭合 1h/4h K；
- gap stop 按实际开盘不利成交；同根同时触发止盈止损时 stop-first；
- timeout 在目标 K 线开盘执行，不读取该 K 线高低；
- Binance funding 使用数据湖实际记录，按持仓区间和方向逐笔结算；
- 手续费 `0.1%/fill`，基准滑点 `4 bps/fill`，压力滑点 `8 bps/fill`；
- 全局同时最多一笔仓位，持仓期间信号不排队，平仓后重新计算当前候选；
- 两条路径实际最大杠杆分别为 `1.20x` 与 `0.99x`，低于 `3x` 上限。
- 合成执行语义审计验证 K+2、gap stop、stop-first、timeout open 和 1h known-time，结果为 `PASS`。
- Funding 在“入场时点包含/退出时点排除”和相反事件排序之间做边界压力；逐笔取两种结算中较差值后，三条执行情景的账户门槛仍全部通过。

## 状态边界

本文件是 current diagnostic，不是版本登记。当前三个月已经参与候选淘汰和账户路由，因此不能再称首次 OOS。唯一最终 OOS 仍为未来新增的 `[2026-07-14T09:00Z, 2026-10-14T09:00Z)`；在该窗口完整结束并一次性揭示前，V3 只能标记为 `not registered / not promoted / not live-ready`。

## 复现入口

- 单币前沿复核：[../scripts/audit_binance_as6s_prefit_frontier_asset_first.py](../scripts/audit_binance_as6s_prefit_frontier_asset_first.py)
- 单币 Clean-RSI 搜索：[../scripts/research_binance_as6s_clean_rsi_hf_search.py](../scripts/research_binance_as6s_clean_rsi_hf_search.py)
- Clean-RSI 资金费/压力审计：[../scripts/audit_binance_as6s_clean_rsi_hf_robustness.py](../scripts/audit_binance_as6s_clean_rsi_hf_robustness.py)
- 账户组合与双路线：[../scripts/research_binance_as6s_asset_first_v3.py](../scripts/research_binance_as6s_asset_first_v3.py)
- 账户 artifact：[../artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json](../artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json)
- 逐笔账户交易：[../artifacts/binance_as6s_asset_first_v3_candidate_trades_2026-07-14.csv](../artifacts/binance_as6s_asset_first_v3_candidate_trades_2026-07-14.csv)
- 执行语义审计：[../artifacts/binance_as6s_v3_execution_semantics_2026-07-14.json](../artifacts/binance_as6s_v3_execution_semantics_2026-07-14.json)
- Funding 边界审计：[../artifacts/binance_as6s_v3_funding_boundary_2026-07-14.json](../artifacts/binance_as6s_v3_funding_boundary_2026-07-14.json)
- 未来揭示程序冻结期复现：[../artifacts/binance_as6s_v3_reveal_reproduction_2026-07-14.json](../artifacts/binance_as6s_v3_reveal_reproduction_2026-07-14.json)
- 未来 OOS 冻结：[../specs/binance-as6s-v3-future-oos-freeze-2026-07-14.md](../specs/binance-as6s-v3-future-oos-freeze-2026-07-14.md)
