# Nasdaq100-1D-MA7-Regime-Continuation Core Ledger

## Family Identity

- Full family name：`Nasdaq100-1D-MA7-Regime-Continuation`
- Alias：`NDX100-1D-MA7-RC`
- Market / source / timeframe：historical Nasdaq-100 securities，Massive split-adjusted OHLCV，XNAS regular session `1d`
- Mechanism：对称 MA7 close cross 后，检验 Slope / ER / RV regime 与 1–40 个交易日方向收益的条件关系。
- Boundary：与 `Binance-1D-MA7-Regime-Continuation` 严格可比但身份独立；不是 MA7 策略、指数择时或 QQQ 策略。

## Current State

- Current observation：`NDX100-1D-MA7-RC-P0`，冻结 observation，不登记策略版本。
- Current status：`explore / diagnostic-only / not promoted / not live-ready`。
- Membership：2010-01-04 至 2026-08-21 共 4,184 个 XNAS sessions、252 个历史 ticker、247 个冻结 entity lineage；反推末端与 revision-pinned 当前表一致，完整性 finding 为 0。
- Price/results：`BLOCKED_DATA_ACCESS`；用户提供的 legacy Polygon / Massive key 可认证，ticker details、当前日线与 ticker events 通过，但 `2010-01-04` 历史日线不可用，实测长区间只返回最近 `499` 根（`2024-08-26` 至 `2026-08-21`），不足以运行 historical P0。
- Yahoo current Y0：用户显式授权后完成 `102` 条 terminal-snapshot 证券回填诊断；`405,060` 行日线、`77,066` 个 MA7 事件。ER/Slope/RV 未形成时间稳定且与 Binance 同向的结构，状态为 `diagnostic complete / survivorship-biased / not promoted`。
- Yahoo historical Y1：`252` 个历史 ticker 全部请求；历史退出的 `152` 个 ticker 中 `95` 个至少有部分直接/同实体 lineage 覆盖。member stock-day 覆盖 `348,462 / 429,268 = 81.18%`，仍缺 `80,806`；低于冻结 `99.5%` 门槛，故事件和 expectancy 结果未运行，状态为 `BLOCKED_INCOMPLETE_YAHOO_HISTORY`。
- Yahoo current Y2：将 Crypto P2 的 `ATR20` 十日路径、trailing-60 causal quintile、burst 与两个方向格零调参迁移至 Y0。`77,957` 个 MA7 事件；long Q5+burst 20D 为 `+3.68%`，但相对其余事件增量仅 `+0.52pp / t=0.45` 且 10D/40D 不保持；short Q1+burst 为 `-2.39% / t=-5.56`。ATR-path 五档分离弱于 RV252，裁决为未形成稳定可迁移优化。
- Yahoo current Y3：建立不用 ML、个股横截面相对强弱或结果选参的突破前结构图谱。`355,038` 个 eligible stock-days、`110,154` 个 MA7/MA30 事件。20D 通过正方向、正增量及 FDR10 门槛的均为多头修复结构：MA7 深回撤修复 `+8.53% / +5.93pp incremental`，MA7 仍在 MA30 下方的早期修复 `+7.06% / +4.32pp`；MA30 同类结构及空头排列反转也通过。优势主要在 10–40D 展开，剔除绝对 gap >1% 后仍为正。低波底座和牛市浅回踩显著弱于其余多头突破；所有具名空头状态方向收益仍为负。
- Cross-market：historical P0 股票端仍缺失；Y0 对照表只能标为 `Nasdaq100CurrentYahoo`，不能冒充 point-in-time Nasdaq-100。
- Runner：无 live spec、无 runner、无交易授权。
- Live-readiness blockers：研究本身不是策略；Massive entitlement、FIGI/ticker-events 审计、价格完整性、统计结果与跨市场复核均未完成。
- Next gate：获得覆盖 2010 年的 Massive 历史 entitlement 后运行冻结 P0；只有数据/标识审计通过才允许生成 historical 事件和 cross-market 表。

## Version Rules

- `P0` 是冻结诊断 observation，不是 `V1`，不产生 promotion 含义。
- 修改 universe、日期、数据商、触发、regime 变量、quintile、forward horizon 或 gap 阈值都必须建立新的 observation，不可覆盖 P0。
- MA5/MA10 与 gap 阈值仅是预定义 robustness，不可用来选择主参数。
- 任何盈利策略设计都属于新 family，不能继承本研究的诊断身份。

## Version Table

| Observation | Status | Role / Core Idea | Key Frozen Evidence | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `NDX100-1D-MA7-RC-P0` | `explore / diagnostic-only / not promoted / not live-ready` | historical NDX point-in-time MA7 regime cross-market validation | membership reconstructed；credential 有效但 2010 history entitlement 不足；historical stock/cross-market result not run | [合同](specs/ndx100-1d-ma7-regime-continuation-p0-contract-2026-08-24.md) · [阻塞报告](diagnostics/ndx100-1d-ma7-regime-continuation-blocker-2026-08-24.md) | 只完成可复现脚手架；不形成 historical 结构结论 |
| `NDX100-1D-MA7-RC-Y0` | `explore / diagnostic-only / survivorship-biased / not promoted / not live-ready` | Yahoo 当前成分 terminal snapshot 回填快速诊断 | `102` securities；MA7 `77,066` events；ER 不单调、surface 跨时期弱、与 Crypto 不同向 | [Y0 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-contract-2026-08-24.md) · [Y0 诊断](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-2026-08-24.md) | 数据可用；核心结构未复现；不替代 P0 |
| `NDX100-1D-MA7-RC-Y1` | `explore / diagnostic-only / BLOCKED_INCOMPLETE_YAHOO_HISTORY / not promoted / not live-ready` | Yahoo 历史 PIT membership 与退出成分覆盖诊断 | `252` tickers 全请求；`95/152` 历史退出 ticker 有部分覆盖；member stock-days `81.18%`，缺 `80,806` | [Y1 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-contract-2026-08-25.md) · [Y1 覆盖审计](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-coverage-2026-08-25.md) | 保存已取得的退市历史；覆盖门槛失败，不运行结果、不替代 P0/Y0 |
| `NDX100-1D-MA7-RC-Y2` | `explore / diagnostic-only / survivorship-biased / not promoted / not live-ready` | Crypto P2 ATR-path 外部假设零调参迁移 | `77,957` MA7 events；long 外部格 20D 局部改善但增量不显著、10D/40D 不保持；short 外部格 expectancy 为负；ATR path 不优于 RV252 | [Y2 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-contract-2026-08-25.md) · [Y2 结果](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-2026-08-25.md) | 外部迁移未形成稳定优化；不调股票参数、不 promotion |
| `NDX100-1D-MA7-RC-Y3` | `explore / diagnostic-only / survivorship-biased / hypothesis-generation / not promoted / not live-ready` | 突破前价格路径与市场结构图谱 | `110,154` MA7/MA30 events；深回撤后的早期修复在 10–40D 有正增量且通过 FDR10；去掉 >1% gap 后仍为正；低波/牛市浅回踩不占优；空头状态均无正方向 expectancy | [Y3 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-contract-2026-08-25.md) · [Y3 结果](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-2026-08-25.md) | 锁定“受创后的修复/反转”作为待独立验证机制；不把全样本图谱直接写成策略 |

## Shared Assumptions

- Data：Massive adjusted daily aggregates；2010-01-01 至 2026-08-21 最新完整 session；XNAS regular calendar；历史成分 point-in-time join。
- Returns：只统计 split-adjusted price return，不含 dividend、delisting return、费用、滑点、借券或融资；缺失 feature/forward session fail closed，禁止 `fillna(0)`。
- Trigger：昨日 close 在 MA 另一侧或相等，今日 close 严格跨越；MA7 为主，MA5/10 仅邻域检查。
- Regime：`(SMA30[t]-SMA30[t-1])/ATR14[t]`、`ER20`、`RV20` 的 252-session security-local percentile；结果无关的 pooled quintiles。
- Inference：security/date 双向聚类；三变量 125 cells 在方向×horizon×metric 内做 BH-FDR。

## Evidence Map

- [冻结合同](specs/ndx100-1d-ma7-regime-continuation-p0-contract-2026-08-24.md)
- [成分来源说明](specs/ndx100-membership-reconstruction-sources-2026-08-24.md)
- [阻塞报告](diagnostics/ndx100-1d-ma7-regime-continuation-blocker-2026-08-24.md)
- [成分重建脚本](scripts/reconstruct_ndx100_membership.py)
- [研究脚本](scripts/research_ndx100_1d_ma7_regime_continuation.py)
- [机器证据目录](artifacts/README.md)
- [决策记录](decision-log.md)
- [Yahoo 当前成分 Y0 诊断](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-2026-08-24.md)
- [Yahoo 历史成分 Y1 覆盖审计](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-coverage-2026-08-25.md)
- [Yahoo 当前成分 Y2 ATR 路径迁移](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-2026-08-25.md)
- [Yahoo 当前成分 Y3 突破前结构图谱](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-2026-08-25.md)
