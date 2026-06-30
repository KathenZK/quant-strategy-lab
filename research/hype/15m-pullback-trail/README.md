# HYPE-15M-Pullback-Trail

Family id：`HYPE-15M-Pullback-Trail`

本 family 是独立的 Binance HYPEUSDT `15m` 研究线。它最初用于判断 `HYPE-5M-Pullback-Trail` V3.3 的回踩/恢复 + delayed trailing 机制迁移到 `15m` 后是否能改善；2026-06-30 后，新增一条更实盘可执行的研究方向：保留 15m 回踩信号作为事件源，但把退出重构为入场即存在的 fixed bracket / emergency stop / timeout。

它独立于：

- `HYPE-5M-Pullback-Trail`：V3.3 的原始 `5m` family。
- `HYPE-15M-Multi-Indicator-Intraday`：`15m` 宽指标搜索 family。
- `HYPE-EMA-Crossover`、`HYPE-EMA-Trend-Breakout`、`HYPE-Candle-Count-Reversal`。

## Canonical Entrypoints

- `diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md`：15m 回踩事件源 + 入场即 fixed bracket / emergency stop / timeout 的可执行搜索报告。
- `diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`：V3.3 delayed trailing 机制的 15m 迁移诊断。
- `decision-log.md`：本 family 的长期决策记录。

## Current Status

当前状态：`paper-audit candidate only`，不是 paper-live、dry-run、handoff 或真仓 live 版本。

- V3.3 delayed trailing 直接迁移到 `15m` 后仍是 `NO-GO`；它降低了噪音和交易频率，但没有修复 trailing 解锁后 stop 可执行性问题。
- bracket 搜索找到一个相对均衡候选：`ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl4_tx24`。
- 该候选全样本 `70` 笔，收益 `39.56%`，年化 `1.36x`，胜率 `62.86%`，PF `1.677`，payoff `0.991`，最大回撤 `-12.49%`。
- OOS `2026-06-01 -> latest` 为 `9` 笔，收益 `11.39%`，胜率 `77.78%`，PF `5.167`；但 OOS 样本仍太短，不能直接提升为 live spec。
- 主要弱点是 `2025-09-01 -> 2025-12-01` 切片收益 `-9.58%`、PF `0.514`，说明该信号/退出结构对部分震荡或反转环境仍敏感。

## 当前候选机制

- 信号周期：严格使用已闭合 `15m` K 线。
- 入场：信号在 K 线收盘后确认，下一根 `15m` open 开多。
- 方向：只做多，要求 `EMA21 > EMA96`。
- 回踩/恢复事件：`low <= EMA21 * 1.015` 且 `close > EMA21`。
- 质量筛选：`ret32>=600`，即最近 `32` 根 `15m` K 的方向收益至少 `600 bps`。
- 退出：入场后立即存在 reduce-only TP/SL bracket；`TP = 2 * ATR14(signal_bar)`，`SL/emergency stop = 4 * ATR14(signal_bar)`，timeout 为 `24` 根 `15m` K。
- 执行保守口径：同根同时触及 TP/SL 时按 stop first；开盘跳过 stop 按 open 市价止损；timeout 到期按 open 市价退出；持仓期间忽略新信号。

## Scripts

- `scripts/research_hype_15m_pbtr_bracket_search.py`：把本地 Binance HYPE `5m` 标准数据重采样为闭合 `15m`，搜索 15m 回踩事件源、质量筛选与入场即 bracket / emergency stop / timeout 的可执行组合，并输出报告、切片、月度、交易明细和成本压力表。
- `scripts/research_hype_15m_pbtr_v33_migration.py`：重采样本地 Binance HYPE `5m` 数据为闭合 `15m`，复现 V3.3 回踩/trailing 逻辑，对比 legacy stop-price fill 与 live-realistic trailing execution，并运行小范围 15m 邻域网格。

## Artifacts

- `artifacts/hype_15m_pbtr_bracket_search_2026-06-30.json`
- `artifacts/hype_15m_pbtr_bracket_search_prescreen_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_bracket_search_summary_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_bracket_search_slices_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_bracket_search_monthly_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_bracket_search_best_trades_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_bracket_search_cost_stress_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_2026-06-30.json`
- `artifacts/hype_15m_pbtr_v33_migration_summary_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_slices_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_trades_2026-06-30.csv`
- `artifacts/hype_15m_pbtr_v33_migration_diag_2026-06-30.csv`

## Naming Notes

不要单独引用裸 `V3.3`。在本目录下应写作 `HYPE-15M-Pullback-Trail V3.3 migration diagnostic`，或明确说明它是 `HYPE-5M-Pullback-Trail-V3.3` 的 15m transplant。

bracket 搜索候选也不要写成 “V3.3 修复版”。它只是复用了类似的 15m 回踩/恢复事件源，退出结构已经变为入场即存在的 bracket / emergency stop / timeout。
