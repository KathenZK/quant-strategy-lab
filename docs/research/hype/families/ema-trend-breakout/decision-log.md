# HYPE-EMA-TB Decision Log

This is the family-level reading path for HYPE EMA trend-breakout research.

## Current Boundary

- This family is research/specification material.
- Active package code contains only data and research dataset infrastructure.
- Use the canonical specs plus current data lake to regenerate backtests when needed.

## Version Notes

- `HYPE-EMA-TB-V2P`: early 15m trend breakout with 1h confirmation.
- `HYPE-EMA-TB-V30`: baseline aligned trend-family checkpoint.
- `HYPE-EMA-TB-V34`: high-return low-drawdown candidate.
- `HYPE-EMA-TB-V35`: timeout-relaxed candidate.
- `HYPE-EMA-TB-V36`: Binance signal, Hyperliquid execution variant.

## Research Batch Notes

- `hype-5m-indicator-ensemble-search.md`: Binance HYPE perpetual 5m indicator-combination search over `2025-06-01` to `2026-06-01`. No single raw or refined strategy hit `20x annualized / >=80% win / >-20% DD`; a one-position ensemble of refined high-win-rate EMA/Bollinger reversion legs did hit the full-period target. Treat as a research candidate with material overfit risk, not a promoted live version.
- `ensemble-specs/README.md`: 将当前全部 `7` 个 `target_pass=True` 的 HYPE Binance `5m` one-position ensemble 组合写成中文实盘代码规格文档。每份文档都记录了指标公式、信号生成、开仓、持有、平仓、子腿参数，以及删除子腿、杠杆、单仓执行门槛三类消融实验。它们共享同一批精筛子腿，只是子腿数量和杠杆不同；仍应视为研究候选，而不是 promoted live version。
- `hype-5m-ensemble-forward-oos-2026-06-23.md`: 补拉 `2026-06-01` 到 `2026-06-23 04:00 UTC` 的 Binance HYPE `5m` 数据后做 forward OOS。新增段 `6385` 根 K 线无缺口，区间收益 `-7.13%`。此前 7 个配置实际为 `5/8/12/16` 腿的 4 条交易路径；新增段所有原杠杆配置均未继续满足 `>=80%` 胜率和 `<20%` 回撤。12 腿 `2.5x` 新增胜率 `73.58%`、回撤 `-28.97%`，只适合降杠杆 dry-run 继续观察。
- `hype-5m-positive-payoff-search-2026-06-23.md`: 按 `payoff_ratio > 1`、每切片胜率 `>=60%`、每切片年化 `>=20x` 重跑 Binance HYPE `5m` 全量数据。基础搜索 `6000` 配置无命中；针对最接近候选精炼后有 `41` 行满足三项数学指标，但全部最差切片回撤劣于 `-80%`。结论是三项指标本身不足以定义可实盘策略；若加入任何合理生存回撤约束，本轮命中为 `0`。
- `hype-5m-survival-frontier-2026-06-23.md`: 改用生存前沿分析，要求每切片 `payoff_ratio > 1`、交易数达标、胜率下限 `55%/58%/60%`、回撤优于 `-20%/-25%/-30%`。结果显示：`60%` 胜率下真实全样本年化约 `2.65x-4.29x`；`58%` 胜率且 `-30%` 回撤下全样本年化可到 `29.07x`，最差切片年化约 `9.75x`；`55%` 胜率且 `-30%` 回撤下可到 `69.37x`，但属于激进杠杆候选。后续应优先研究 `HYPE_PP_R05732__dir_htf_ge_0.688442`，而不是继续硬凑每切片 `20x`。
- `hype-5m-r05732-strategy-ablation-2026-06-23.md`: 将 `HYPE_PP_R05732__dir_htf_ge_0.688442` 写成完整策略说明，并做逐参数消融。按真实持仓路径 MAE/MFE 口径，基线全样本 `1340` 笔、胜率 `59.18%`、payoff `2.58`、年化 `29.07x`、最大回撤 `-7.70%`。消融显示 `trail_atr=0.75` 与 `min_hold_bars=6` 是核心持仓参数；删除 final `dir_htf` 过滤会把交易数增至 `5380` 且收益暴涨，但最差切片胜率降到 `54.66%`；`pullback_buffer=0.01` 和更远/删除固定止盈是后续最值得研究的改良方向。

## Evidence Policy

Use family docs first, Cursor Canvas ledgers second, and archived scripts/code only for reproduction archaeology.
