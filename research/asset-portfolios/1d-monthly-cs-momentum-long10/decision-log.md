# Decision Log

## 2026-08-18 — 建立独立 Long10 诊断，不继承 LS3 身份

按用户字面规则建立 Binance 月频 Top10 long-only 家族。全历史收益显著为正，但最大回撤超过 92%、年度集中且峰值尚未完全恢复，因此不登记、不晋升；证据见[诊断](diagnostics/binance-1d-mcsm-long10-diagnostic-2026-08-18.md)。外部现货美股混合版本因缺少点时全市场数据未运行；Binance 原生股票/TradFi 永续本来就属于本回测合约池。

## 2026-08-19 — Top10/20/30/40/50 宽度诊断与股票永续审计

按用户指定的五个宽度运行全上市与 `ADV≥1000万` 两个宇宙。共同起点 `2020-12-01` 后，收益与 Sharpe 随 Top N 扩大整体下降，Top10 仍为本次已揭示扫描中的历史最优宽度；但它依旧有约 `-93%` 回撤，不登记、不晋升。点时持仓审计确认 `MU` 在 `2026-06` 被所有 Top N 组合持有；`SNDK` 和 `SKHYNIX` 因形成期历史不足未入选，而非被资产类别过滤。证据见[宽度诊断](diagnostics/binance-1d-mcsm-long-breadth-diagnostic-2026-08-19.md)。

## 2026-08-19 — 固定 20% 波动目标有效，10/20 缓冲不采纳为改善

用户事前固定的 20% 组合目标波动将全上市 MDD 从 `-93.79%` 降至 `-42.33%`，但 10/20 缓冲只把年化换手从 `4.58x` 降至 `4.17x`，同时降低 CAGR/Sharpe 且未改善 MDD；本轮只保留诊断，不登记、不晋升。证据见[风险与缓冲诊断](diagnostics/binance-1d-mcsm-long10-risk-buffer-diagnostic-2026-08-19.md)。

## 2026-08-19 — 正收益限定仅局部改善，不登记

Top10 全部不大于零只出现1个月；正收益限定使全上市 target20 的 CAGR/MDD 小幅改善，但 ADV target20 的 Sharpe、MDD与水下期反而变差，未形成跨宇宙一致证据。停止门槛搜索，不登记、不晋升；证据见[正收益与现金缺口诊断](diagnostics/binance-1d-mcsm-long10-positive-cash-diagnostic-2026-08-19.md)。

## 2026-08-20 — BTC 市场 gate 与 MH136 均不采纳

事前冻结的 `BTC SMA200 + target15 + 月中退出` 未过 Sharpe、CAGR和后段 MDD 参考线，删除月中退出反而更好；`1M/3M/6M` 等资本袖套未过 Sharpe、MDD和 12m cohort 门禁，且删除 6M 后整体改善。两个机制均停止，不从 SMA 邻域或袖套消融中挑 winner，不登记、不晋升；证据见[可实盘化审计](diagnostics/binance-1d-mcsm-long10-liveability-audit-2026-08-20.md)。

## 2026-08-20 — target12 只保留为风险预算假设

原 `ADV Top10` 信号的无杠杆 `target12` 在旧引擎中接近风险参考线，但五个完整 12m cohort 只有两个为正。`12%` 不作为新增 alpha、不回扫相邻风险目标，也不构成 promotion；只有执行修复后才允许按原冻结值重跑。

## 2026-08-20 — 执行审计使既有绩效失效

真实 15m 审计发现原 `00:00` 同 bar 成交不可因果复现，并存在零成交占位 K 线入场、不可成交退出和持仓缺价被 `.fillna(0)` 静默成零收益。原 target12 路径有 41 个 blocker，按 `00:15 UTC` 可成交入选后仍有 15 个；裁决为 `HARD_BLOCKER / PERFORMANCE_INVALIDATED`。已冻结[执行语义修复合同](specs/binance-1d-mcsm-long10-execution-repair-contract-2026-08-20.md)，四类 blocker 清零前停止一切 promotion、runner handoff 和参数搜索。

## 2026-08-20 — 赚钱效应方向部分成立，但月频 2×2 状态失败

按用户纠正后的目标，停止以 MDD 为主的 gate/波动率搜索，冻结诊断 Binance breadth、市场收益中位数、leader spread、3M strength、流动性与 rank alignment。`strong/strong` 的下一月平均 Top10 超额为 `+12.16%`，且超额从入场后 1 日持续累积到月末，支持“赚钱效应扩散 + 领涨延续”方向；但它在完整价格标签中只捕获 `42.0%` 正 PnL和 `40.1%` 固定右尾 PnL，四个完整 12m cohort 仅一个为正。原利润来自广谱牛市 beta、V 型赚钱效应启动和窄幅 leader continuation 三类稀疏 episode，月初一次性 AND gate 无法统一捕获。冻结候选失败，不改 OR gate、不删特征救援；post-reveal 的 leader-strong 消融只作归因，不登记。证据见[赚钱效应与领涨延续诊断](diagnostics/binance-1d-mcsm-money-effect-continuation-diagnostic-2026-08-20.md)。
