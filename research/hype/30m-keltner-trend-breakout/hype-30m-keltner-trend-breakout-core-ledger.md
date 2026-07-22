# HYPE-30M-Keltner-Trend-Breakout Core Ledger

## Family Identity

- Full family name：`HYPE-30M-Keltner-Trend-Breakout`
- Alias：`K2-FQ-V2-ATRVT-OFF`
- Market / exchange / symbol / timeframe：Binance USDM 永续 `HYPEUSDT`；`1m` 闭合 K 线重采样为 `30m` 信号周期与 `1h` 趋势周期。
- Mechanism summary：`1h` EMA trend regime + `30m` Keltner 突破，下一根 `30m` open 入场，固定 TP/SL/time exit，ATRVT 动态杠杆。
- Boundary / collision warnings：同事外部 K2/Keltner 规格复现线，不是 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。

## Current State

- Current version(s)：`HYPE-30M-Keltner-Trend-Breakout-V3`。
- Current status：`V3 registered / not promoted / not live-ready`（状态词见 [strategy-status-glossary.md](../../../docs/research-governance/strategy-status-glossary.md)）。
- Runner / dry-run / live status：无 runner handoff、无 dry-run、无 live。
- Latest validity：截至最新闭合 `15m` bar `2026-07-21 08:45 UTC` 的 clean prospective 为 `+18.11% / -7.26% MaxDD / 2 笔`；最近 1 天无交易，正向但样本不足，不改变状态。
- Live-readiness blockers：V3 全参数邻域与交易 bootstrap 为正，但多周期迁移失败；现行门禁 5 的 30m 相位收益比 `13.97%`、CV `1.167`、MDD 比 `2.10x`，明确失败；close-location 风险贡献未证明，空头腿明显偏弱；真实未来 OOS 样本不足、Gate 4 与 live-executable 证据未完成。
- Next decision gate：继续积累冻结参数未来 OOS，并解释或消除 30m 原生边界依赖；门禁 0–5 与 live-executable promotion review 通过后才可进入 `live spec`。

## Version Rules

- `V2.0` / 外部 `K2-FQ-V2-ATRVT-OFF`：同事规格复现锚点，只作为来源观察，不追认成本仓库正式版本。
- `V2.1`：本仓库首个 registered 版本；精简外部 V2 冗余逻辑并微调 regime/ATRVT 参数；保留为 parent 对照，不代表 live-ready。
- `V3`：在 V2.1 上增加入场 ATR cap 与方向化 close-location 过滤；信号/执行语义变化，故升主版本而非 `V2.2`。
- 后续 `V3.x` / `V4`：参数、过滤或执行语义变化必须新增版本行；不得覆盖已冻结的 V2.1 / V3 规格。
- Observation / diagnostic rows：外部规格复现、样本截止对账、成本压力和执行审计可作为观察行记录，不代表 promotion。
- New version trigger：信号逻辑、过滤条件、相位组合、杠杆目标、成本/funding 口径或 runner 可执行合同发生变化。

## Version Table

| Version / Observation | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `K2-FQ-V2-ATRVT-OFF` external observation | `explore / not promoted / not live-ready` | 外部 30m Keltner + 1h EMA regime + ATRVT 进攻档复现 | `2025-05-30 10:30` 至 `2026-07-06 23:59 UTC`；单相位 6 bps `+7516.88% / MDD -26.08% / 114 笔`；剔除最新一笔后对齐外部 `+7698.66% / 113 笔` | [notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md) | 复现可信，但不提升；需完成 funding、滑点和 live-executable 审计 |
| `K2-FQ-V2-ATRVT-OFF` strict-gate observation | `explore / not promoted / not live-ready` | 按项目 Gate 0–7、真实 funding、手续费 0.001/fill、滑点 0.0004/fill 严格审计 | `2025-05-30 10:30` 至 `2026-07-10 06:43 UTC`；`+4827.01% / MDD -27.97% / 114 笔`；数据前置与 Gate 0/1/2 通过，Gate 3/5/6/7 失败，Gate 4/live-executable 未完成 | [notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md) | 不登记正式版本、不 promotion；30m 非原生/原生中位 CAGR 比仅 `7.70%` |
| `HYPE-30M-Keltner-Trend-Breakout-V2.1` | `registered / not promoted / not live-ready` | 去掉两项冗余 regime 条件与最低杠杆 floor；`slow 48→44`、`slope 4→5`、`ATR96→84`、`target 3.0%→2.7%` | `+4638.01% / MDD -25.84% / Sharpe 4.22 / 胜率 56.64% / 113 笔`；收益保留 `96.09%`；Gate 5 通过，Gate 3/6/7 失败 | [specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)，[notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)，[notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md](notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md)，[notes/hype-30m-k2-v2-1-rsi-macd-filter-study-2026-07-13.md](notes/hype-30m-k2-v2-1-rsi-macd-filter-study-2026-07-13.md) | Parent 对照；固定 TP/SL 冻结；RSI/MACD 未同时改善三目标；不 promotion |
| `HYPE-30M-Keltner-Trend-Breakout-V3` | `registered / not promoted / not live-ready` | V2.1 + `ATR84/entry<=1.25%` + 方向化 close location `>=65%` | `+6328.98% / MDD -22.68% / Sharpe 5.05 / 胜率 67.95% / 78 笔`；参数邻域与 MC 为正，但多周期与 30m 相位稳健性失败 | [specs/hype-30m-keltner-trend-breakout-v3-spec.md](specs/hype-30m-keltner-trend-breakout-v3-spec.md)，[ablations/hype-30m-k2-v3-full-parameter-ablation-timeframe-robustness-2026-07-17.md](ablations/hype-30m-k2-v3-full-parameter-ablation-timeframe-robustness-2026-07-17.md)，[notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md](notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md) | 当前家族正式版本；相位门禁失败，不 promotion |
| `V3 latest-validity 2026-07-21` observation | `registered / not promoted / not live-ready` | V3 参数不变；冻结点后 clean prospective 与连续持仓审计 | clean prospective `+18.11% / -7.26% / 2 笔`；连续口径 `+28.34% / -7.26% / 3 笔`；双输入冻结交易路径与指标精确对齐 | [diagnostics/hype-30m-keltner-v3-latest-validity-2026-07-21.md](diagnostics/hype-30m-keltner-v3-latest-validity-2026-07-21.md) | 正向但样本不足；不新增版本、不 promotion |

## Shared Assumptions

- Data：冻结研究使用 Binance futures `1m` 闭合 K 线；最新延伸使用标准 `15m` 闭合 K 线加经重叠区逐字段对账的 Binance API 尾部增量无损聚合，并在冻结区间完成 `19,623` 根 30m OHLC 与 78 笔交易路径精确对账；重采样后只保留完整 `30m` / `1h` bar。
- Cost：原始复现为 `6 bps/side` 与 `15 bps/side`；严格门禁使用手续费 `0.001/fill` + 不利滑点 `0.0004/fill`，并单独施加到实际成交价/名义。
- Execution timing：`30m` 收盘确认，下一根 `30m` open 入场；入场 bar 起检查固定 TP/SL，SL 优先；`hold=30` 在该 bar close 平仓。
- Position sizing：账户复利；每笔名义为入场时权益乘以 ATRVT 杠杆，杠杆冻结到平仓。
- Funding / carry：2026-07-10 严格门禁已计入 Binance 历史 funding；runner 对账仍未完成。

## Evidence Map

- Specs：[specs/hype-30m-keltner-trend-breakout-v3-spec.md](specs/hype-30m-keltner-trend-breakout-v3-spec.md)，[specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)；外部来源文件不作为仓库内复现依赖。
- Diagnostics / ablations：[diagnostics/hype-30m-keltner-v3-latest-validity-2026-07-21.md](diagnostics/hype-30m-keltner-v3-latest-validity-2026-07-21.md)，[diagnostics/hype-30m-k2-v3-30m-hourly-aggregation-parity-2026-07-21.md](diagnostics/hype-30m-k2-v3-30m-hourly-aggregation-parity-2026-07-21.md)，[diagnostics/hype-30m-k2-v2-v2-1-v3-period-comparison-2026-07-17.md](diagnostics/hype-30m-k2-v2-v2-1-v3-period-comparison-2026-07-17.md)，[ablations/hype-30m-k2-v3-full-parameter-ablation-timeframe-robustness-2026-07-17.md](ablations/hype-30m-k2-v3-full-parameter-ablation-timeframe-robustness-2026-07-17.md)，[notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)，[notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)，[notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)，[notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md](notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md)，[notes/hype-30m-k2-v2-1-rsi-macd-filter-study-2026-07-13.md](notes/hype-30m-k2-v2-1-rsi-macd-filter-study-2026-07-13.md)，[notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md](notes/hype-30m-k2-v2-1-loss-regime-filter-optimization-2026-07-13.md)
- Live specs：无。
- Forward tracking：无。
- Scripts / artifacts：[scripts/audit_hype_30m_keltner_v3_latest.py](scripts/audit_hype_30m_keltner_v3_latest.py)，[artifacts/hype_30m_keltner_v3_latest_audit_2026-07-21.json](artifacts/hype_30m_keltner_v3_latest_audit_2026-07-21.json)，[scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)，[scripts/research_hype_30m_k2_strict_validation_gates.py](scripts/research_hype_30m_k2_strict_validation_gates.py)，[scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py](scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py)，[scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py](scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py)，[scripts/research_hype_30m_k2_v2_1_rsi_macd_filters.py](scripts/research_hype_30m_k2_v2_1_rsi_macd_filters.py)，[scripts/research_hype_30m_k2_v2_1_loss_regime_filters.py](scripts/research_hype_30m_k2_v2_1_loss_regime_filters.py)，[artifacts/hype_30m_k2_v2_1_loss_regime_filters_2026-07-13.json](artifacts/hype_30m_k2_v2_1_loss_regime_filters_2026-07-13.json)
