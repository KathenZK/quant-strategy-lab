# SOL-1H-Adaptive-Regime

`SOL-1H-Adaptive-Regime`（短 id：`SOL-1H-AR`）是 Binance USD-M Futures `SOLUSDT` perpetual `1h` 多指标自适应 regime 策略研究家族，与 BTC、HYPE 或其他资产的同类研究没有版本继承关系。

## 研究目标

- 数据：运行时最近两年的全部闭合 `1h` K，直接刷新自 Binance FAPI，并保存 raw/normalized 数据湖分区、资金费历史和合约过滤器快照。
- OOS：最后三个月固定为 locked out-of-sample；参数生成、搜索、排序和 ensemble 冻结不得读取该区间。
- 硬门槛：年化权益倍率 `>=10.0x`（即年化收益 `>=900%`）、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 成本：`0.001` fee/fill、`4 bps` adverse slippage/fill，并逐笔计入 Binance 历史资金费。
- 执行：闭合 K 产生信号，下一根 `1h` open 市价成交；入场后保护性 bracket 立即生效；同 K 双触发 stop-first；跳空穿越 stop 按 open 成交；trailing 只在完整 K 闭合后更新并从下一根 K 生效。

## 指标与搜索面

搜索覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、成交量、动量、wick/body 结构、`4h/12h/1d` 闭合 regime、资金费过滤、固定/风险预算仓位、固定 bracket/trailing exit 及 long/short/both。

## 当前状态

`SOL-1H-Adaptive-Regime-V2 registered diagnostic observation / NO-GO / not promoted / not live-ready`。

`V1` 是 2026-07-03 百万组广搜按 prefit 规则冻结的最终基线：`donchian_break + bb_revert` ensemble（`ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318`）。它的登记只用于固定诊断边界，不代表候选或交接。

广搜结论为 `NO-GO`：finalists `700`，prefit pass `0`，locked target pass `0`；最佳冻结 V1 full annual `2.18x`、DD `-18.86%`、win `76.60%`，但最近三个月 locked OOS annual `0.71x`、return `-8.09%`、DD `-16.19%`、win `50.00%`、trades `8`，未通过 `10x / 50% / <20% DD` 硬门槛。

V1 clean tune 只形成未登记观察值：prefit annual `5.7104x`、DD `-18.81%`、win `85.71%`，但 reused holdout annual `0.1607x`、DD `-42.87%`，current full DD `-42.87%`。该观察不创建 `V1.1/V2`，也不改变 `NO-GO` 结论。

2026-07-07 高胜率硬目标（`10x / 80% / <20% DD`）重新搜索：`600768` configs、评估 `370589`，prefit pass `0`，reused-holdout target pass `0`，结论仍为 `NO-GO`。最佳观察值已登记为 `SOL-1H-Adaptive-Regime-V2`：`donchian_break + vwap_revert` ensemble，full annual `2.07x`、DD `-17.41%`、win `93.91%`；last `1y` annual `1.60x`、win `92.31%`；但最近三个月 reused holdout annual `0.70x`、return `-8.53%`、win `66.67%`。V2 只固定高胜率观察参数，不构成新鲜 OOS 证据或 promotion。

本家族目前没有 production runner；在新增 forward trades、完整 live-executable 审计和生产状态机证据前，不得标记为 candidate、paper-live、dry-run、handoff 或 live。

## 入口

- `sol-1h-ar-core-ledger.md`：家族主账。
- `decision-log.md`：研究决策与状态变化。
- `scripts/fetch_sol_binance_1h.py`：最近两年 K 线、资金费、合约快照抓取与质量审计。
- `scripts/research_sol_1h_adaptive_regime_search.py`：locked OOS 多指标宽搜索。
- `scripts/audit_sol_1h_adaptive_regime_boundary.py`：成交延迟、成本、仓位缩放、单腿、参数邻域、月度、bootstrap 和实盘缺口审计。
- `scripts/sol_1h_ar_v1.py`：`V1` 冻结配置、复现指标和标准近期分片的登记 wrapper。
- `scripts/research_sol_1h_ar_v1_full_ablation.py`：V1 每条腿全部 `StrategyConfig` 字段槽的 one-at-a-time 全参数消融与删参分类。
- `ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`：V1 全参数消融持久报告；`78/78` 字段槽覆盖，clean surface 保留 `40` 个 active tunable 字段槽。
- `scripts/sol_1h_ar_v1_clean.py`：读取消融结果构建只暴露 `active_tunable` 的 clean-equivalent 配置面，并校验逐笔等价。
- `research-notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`：V1 clean interface 等价报告；原始 `78` 个字段槽收敛为 `40` 个 clean tunable 字段槽，逐笔交易签名相等。
- `scripts/research_sol_1h_ar_v1_clean_tune.py`：只在 clean surface 上做 train/validation/prefit 微调，并前置 K+2 与 8 bps 稳健性筛选。
- `research-notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`：V1 clean 参数微调报告；样本内/prefit 改善但 reused holdout 与 current full 回撤恶化，只能作为 diagnostic observation。
- `scripts/research_sol_1h_ar_high_win_target_search.py`：`10x / 80% / <20% DD` 高胜率硬目标搜索；选择只用 train/validation，reused holdout 仅审计。
- `diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`：高胜率硬目标搜索报告；`0` 硬门槛命中，结论 `NO-GO`。
- `canonical-specs/sol-1h-ar-v2-parameter-spec-2026-07-07.md`：`SOL-1H-Adaptive-Regime-V2` 参数规格；记录 `donchian_break + vwap_revert` 双腿 ensemble 的完整配置和 promotion 边界。
- `artifacts/`：Parquet、JSON、CSV 等可复现证据；默认由 `.gitignore` 忽略。
