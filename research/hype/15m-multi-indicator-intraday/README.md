# HYPE-15M-Multi-Indicator-Intraday

Family id：`HYPE-15M-MII`

本家族研究 Binance HYPEUSDT perpetual `15m` 多指标日内策略，允许组合趋势、动量、波动、成交量和价格结构指标，并要求闭合 K 信号、下一根 open 入场等可执行时序。

不要与以下家族混用：

- `HYPE-EMA-Crossover`：较早的 EMA 金叉/死叉家族。
- `HYPE-EMA-Trend-Breakout`：EMA96/EMA384 趋势突破家族。
- `HYPE-Candle-Count-Reversal`：K 线数量反转家族。

## 研究范围

- 数据：Binance USD-M futures HYPEUSDT `15m` 标准 raw/normalized 数据湖。
- 指标面：RSI、MACD、EMA、ADX/DI、ATR、Donchian、Bollinger、成交量、K 线结构和 regime 过滤。
- 执行面：闭合 K 信号、下一根 open 入场、显式费用与滑点、单仓不重叠、stop-first 同 K 冲突处理。

## 当前基线

`HYPE-15M-Multi-Indicator-Intraday-V1` 是本家族的首个冻结研究基线：

- 信号：`RSI(7)` 上穿 `30` 做多、下穿 `60` 做空。
- 过滤：方向化 `MACD(12,26,9) histogram >= 0`；`ATR96 pct` 在 `0.60%-2.80%`。
- 出场：`TP=0.90%`、`SL=2.80%`、最长 `16` 根 `15m` K。
- 暴露：`1.5x`。
- 状态：`diagnostic baseline only / not live-ready`。

V1 规格：`canonical-specs/hype-15m-mii-v1-baseline-spec.md`。

## 当前结论

- `2026-06-25`：首次广泛搜索完成；没有候选同时达到年化 `>=2000%`、最大回撤 `<=20%`、胜率 `>=70%`。
- `2026-06-26`：旧 cache 口径完成 `55` 行消融和 `594` 组表面改善组合优化，结果均为 NO-GO。
- `2026-06-29`：将最佳综合策略正式冻结为 V1，在标准 raw/normalized 数据湖上修复 timeout 与同仓入场时序，并补齐 MACD/ATR 指标周期消融。按 Binance 成本 `0.1000% fee/fill + 0.0400% slippage/fill` 重算后，共 `62` 行，完整 gate `0/62`。
- V1 可执行口径：年化 `18.66%`、总收益 `20.14%`、最大回撤 `-31.84%`、胜率 `75.28%`、`0.919` 笔/天、PF `1.106`、Last90 年化 `-41.44%`。
- `2026-06-30`：干净参数演化评估 `7,926` 个配置，找到 K+1 领先诊断版 `323.57%` 年化、`-18.67%` 回撤、`78.99%` 胜率、`0.608` 笔/天；但 K+2 延迟降为 `42.00%` 年化、`-38.68%` 回撤，K+2 联合通过 `0/201`。
- `2026-06-30`：放宽回撤后存在更激进版本：`DD<=25%` 首位 `337.95%` 年化、`-23.18%` 回撤、`80.71%` 胜率；`DD<=30%` 首位 `356.74%` 年化、`-26.94%` 回撤、`86.71%` 胜率，但 Last90 仅 `0.63%`，且高收益版本不具备 K+2 稳健性。
- `2026-06-30`：快速验证频率综合排名显示，严格 `1-3` 笔/天的版本收益或近期稳定性偏弱；综合第一是接近 `1` 笔/天的 `clean_rsi7_40_55_atrmin75_rvol0p75_h10_rsi14b0_tp120_sl320_hold32_x1`，K+1 年化 `97.07%`、回撤 `-20.13%`、胜率 `81.45%`，K+2 年化 `32.03%`。
- `2026-06-30`：放弃频率后，均衡观察版本选择 `clean_rsi7_40_60_atrmin105_rvol0_h10_rsi14b0_tp120_sl450_hold32_x2`；K+1 年化 `216.81%`、总收益 `244.44%`、回撤 `-15.65%`、胜率 `91.60%`，K+2 年化 `101.73%`、回撤 `-27.39%`。`3x` K+1 年化 `443.62%`，但 K+2 回撤 `-39.22%`，只作为 aggressive diagnostic。
- 实盘判断：`NO-GO`。没有生产 runner、真实 stop-market/滑点证据、资金费核算、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。

## 阅读顺序

1. `canonical-specs/hype-15m-mii-v1-baseline-spec.md`
2. `ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`
3. `live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md`
4. `research-notes/hype-15m-mii-clean-parameter-evolution-2026-06-29.md`
5. `research-notes/hype-15m-mii-delay-aware-selection-2026-06-29.md`
6. `research-notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md`
7. `research-notes/hype-15m-mii-fast-validation-frequency-ranking-2026-06-30.md`
8. `research-notes/hype-15m-mii-balanced-leverage-stress-2026-06-30.md`
9. `ablations/hype-15m-mii-v1-1-clean-lead-robustness-2026-06-29.md`
10. `diagnostics/hype-15m-mii-search-2026-06-25.md`
11. `ablations/hype-15m-mii-full-ablation-2026-06-26.md`
12. `ablations/hype-15m-mii-surface-combo-optimization-2026-06-26.md`

## 证据规则

- 研究脚本放在 `scripts/`。
- 被报告引用的 JSON/CSV 放在 `artifacts/`。
- 长期结论、消融和实盘审计保留在本家族 Markdown 中。
- V1 命名不改变 promotion 状态；没有通过 live-feasibility 审计前，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
