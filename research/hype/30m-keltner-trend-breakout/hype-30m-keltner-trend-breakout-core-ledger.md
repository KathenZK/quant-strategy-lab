# HYPE-30M-Keltner-Trend-Breakout Core Ledger

## Family Identity

- Full family name：`HYPE-30M-Keltner-Trend-Breakout`
- Alias：`K2-FQ-V2-ATRVT-OFF`
- Market / exchange / symbol / timeframe：Binance USDM 永续 `HYPEUSDT`；`1m` 闭合 K 线重采样为 `30m` 信号周期与 `1h` 趋势周期。
- Mechanism summary：`1h` EMA trend regime + `30m` Keltner 突破，下一根 `30m` open 入场，固定 TP/SL/time exit，ATRVT 动态杠杆。
- Boundary / collision warnings：同事外部 K2/Keltner 规格复现线，不是 `HYPE-EMA-Trend-Breakout`、`HYPE-EMA-Crossover` 或 `HYPE-15M-Multi-Indicator-Intraday` 的版本。

## Current State

- Current version(s)：`HYPE-30M-Keltner-Trend-Breakout-V2.1`。
- Current status：`V2.1 registered / not promoted / not live-ready`（状态词见 [strategy-status-glossary.md](../../../docs/research-governance/strategy-status-glossary.md)）。
- Runner / dry-run / live status：无 runner handoff、无 dry-run、无 live。
- Live-readiness blockers：数据质量前置已修复并通过；Gate 3 Monte Carlo、Gate 5 统计显著性、Gate 6 启动时间、Gate 7 30m 相位仍失败；Gate 4 与 live-executable runner 运维证据未完成。
- Next decision gate：解释或消除 30m 原生边界依赖，并降低交易重排后的回撤尾部；Gate 3/6/7 通过后才可评估进入 `audit`。

## Version Rules

- `V2.0` / 外部 `K2-FQ-V2-ATRVT-OFF`：同事规格复现锚点，只作为来源观察，不追认成本仓库正式版本。
- `V2.1`：本仓库首个 registered 版本；精简外部 V2 冗余逻辑并微调 regime/ATRVT 参数，不代表 live-ready。
- 后续 `V2.x`：参数、过滤或执行语义变化必须新增版本行；TP/SL/hold/ATRVT target/杠杆上限变化不得覆盖 V2.1。
- Observation / diagnostic rows：外部规格复现、样本截止对账、成本压力和执行审计可作为观察行记录，不代表 promotion。
- New version trigger：信号逻辑、相位组合、杠杆目标、成本/funding 口径或 runner 可执行合同发生变化。

## Version Table

| Version / Observation | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `K2-FQ-V2-ATRVT-OFF` external observation | `explore / not promoted / not live-ready` | 外部 30m Keltner + 1h EMA regime + ATRVT 进攻档复现 | `2025-05-30 10:30` 至 `2026-07-06 23:59 UTC`；单相位 6 bps `+7516.88% / MDD -26.08% / 114 笔`；剔除最新一笔后对齐外部 `+7698.66% / 113 笔` | [notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md) | 复现可信，但不提升；需完成 funding、滑点和 live-executable 审计 |
| `K2-FQ-V2-ATRVT-OFF` strict-gate observation | `explore / not promoted / not live-ready` | 按项目 Gate 0–7、真实 funding、手续费 0.001/fill、滑点 0.0004/fill 严格审计 | `2025-05-30 10:30` 至 `2026-07-10 06:43 UTC`；`+4827.01% / MDD -27.97% / 114 笔`；数据前置与 Gate 0/1/2 通过，Gate 3/5/6/7 失败，Gate 4/live-executable 未完成 | [notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md) | 不登记正式版本、不 promotion；30m 非原生/原生中位 CAGR 比仅 `7.70%` |
| `HYPE-30M-Keltner-Trend-Breakout-V2.1` | `registered / not promoted / not live-ready` | 去掉两项冗余 regime 条件与最低杠杆 floor；`slow 48→44`、`slope 4→5`、`ATR96→84`、`target 3.0%→2.7%` | `+4638.01% / MDD -25.84% / Sharpe 4.22 / 胜率 56.64% / 113 笔`；收益保留 `96.09%`；Gate 5 通过，Gate 3/6/7 失败 | [specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)，[notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)，[notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md](notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md) | 正式登记研究身份；ATR 动态 bracket 未满足三目标，固定 TP/SL 继续冻结；不 promotion |

## Shared Assumptions

- Data：Binance futures `1m` 闭合 K 线；2026-07-10 已补齐标准 raw/normalized data lake 全区间并完成 cache/lake 零差异对拍；重采样后只保留完整 `30m` / `1h` bar。
- Cost：原始复现为 `6 bps/side` 与 `15 bps/side`；严格门禁使用手续费 `0.001/fill` + 不利滑点 `0.0004/fill`，并单独施加到实际成交价/名义。
- Execution timing：`30m` 收盘确认，下一根 `30m` open 入场；入场 bar 起检查固定 TP/SL，SL 优先；`hold=30` 在该 bar close 平仓。
- Position sizing：账户复利；每笔名义为入场时权益乘以 ATRVT 杠杆，杠杆冻结到平仓。
- Funding / carry：2026-07-10 严格门禁已计入 Binance 历史 funding；runner 对账仍未完成。

## Evidence Map

- Specs：[specs/hype-30m-keltner-trend-breakout-v2-1-spec.md](specs/hype-30m-keltner-trend-breakout-v2-1-spec.md)；外部来源文件 `/Users/ZK/Downloads/2-k2-fq-v2-atrvt-off-20260707.md` 不作为仓库内复现依赖。
- Diagnostics / ablations：[notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md](notes/hype-30m-k2-fq-v2-atrvt-off-backtest-2026-07-08.md)，[notes/hype-30m-k2-strict-validation-gates-2026-07-10.md](notes/hype-30m-k2-strict-validation-gates-2026-07-10.md)，[notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md](notes/hype-30m-k2-v2-full-ablation-pruned-tune-2026-07-10.md)，[notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md](notes/hype-30m-k2-v2-1-dynamic-atr-bracket-2026-07-10.md)
- Live specs：无。
- Forward tracking：无。
- Scripts / artifacts：[scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py](scripts/research_hype_30m_k2_fq_v2_atrvt_off_backtest.py)，[scripts/research_hype_30m_k2_strict_validation_gates.py](scripts/research_hype_30m_k2_strict_validation_gates.py)，[scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py](scripts/research_hype_30m_k2_v2_full_ablation_and_tune.py)，[scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py](scripts/research_hype_30m_k2_v2_1_dynamic_atr_bracket.py)，[scripts/repair_hype_1m_standard_data_lake.py](scripts/repair_hype_1m_standard_data_lake.py)，[artifacts/hype_30m_k2_v2_full_ablation_tune_2026-07-10.json](artifacts/hype_30m_k2_v2_full_ablation_tune_2026-07-10.json)，[artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_2026-07-10.json](artifacts/hype_30m_k2_v2_1_dynamic_atr_bracket_2026-07-10.json)
