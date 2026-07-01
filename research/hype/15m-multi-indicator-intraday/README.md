# HYPE-15M-Multi-Indicator-Intraday

Family id：`HYPE-15M-MII`

本家族研究 Binance HYPEUSDT perpetual `15m` 多指标日内策略，允许组合趋势、动量、波动、成交量和价格结构指标，并要求闭合 K 信号、下一根 open 入场等可执行时序。

主账：`hype-15m-mii-core-ledger.md`。

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

## 当前观察基线

`HYPE-15M-MII-V1base` 当前记录为：

- 名称：`clean_rsi7_40_60_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x2`。
- 参数：`RSI(7)` 上穿 `40` 做多、下穿 `60` 做空；`MACD(12,26,9)` 方向过滤；`ATR96 pct >= 0.75%`；`min_rvol96=1.0`；无 `1h confirm`；无 `RSI14 band`；`TP=1.20%`、`SL=3.60%`、最长 `16` 根 `15m` K；权益暴露 `2x`。
- 表现：K+1 年化 `272.30%`、回撤 `-21.12%`、胜率 `80.75%`、PF `2.158`、Last90 年化 `457.15%`；K+2 年化 `96.51%`、回撤 `-36.28%`、胜率 `78.01%`、PF `1.446`。
- 状态：`V1base diagnostic observation only / not live-ready`；不改变本家族 `NO-GO` 状态。

`HYPE-15M-MII-V1.2` 记录为 `V1.1` 的 ATR 动态止盈止损观察版：

- 入场过滤：沿用 `V1.1` 的 `RSI(7)`、`MACD(12,26,9)`、`ATR96 pct` 与 `RVOL96` 规则。
- 出场：入场时按信号 K 已知 `ATR96%` 设置固定 bracket：`TP = 1.25 * ATR96%`、`SL = 5.0 * ATR96%`、最长 `24` 根 `15m` K。
- 表现：K+1 年化 `311.35%`、回撤 `-17.74%`、胜率 `84.78%`、PF `2.179`；K+2 年化 `154.96%`、回撤 `-34.81%`、胜率 `82.01%`、PF `1.612`。
- 状态：`diagnostic observation only / not live-ready`；属于同样本出场参数再优化，不改变本家族 `NO-GO` 状态。

## 当前结论

- `2026-06-25`：首次广泛搜索完成；没有候选同时达到年化 `>=2000%`、最大回撤 `<=20%`、胜率 `>=70%`。
- `2026-06-26`：旧 cache 口径完成 `55` 行消融和 `594` 组表面改善组合优化，结果均为 NO-GO。
- `2026-06-29`：将最佳综合策略正式冻结为 V1，在标准 raw/normalized 数据湖上修复 timeout 与同仓入场时序，并补齐 MACD/ATR 指标周期消融。按 Binance 成本 `0.1000% fee/fill + 0.0400% slippage/fill` 重算后，共 `62` 行，完整 gate `0/62`。
- V1 可执行口径：年化 `18.66%`、总收益 `20.14%`、最大回撤 `-31.84%`、胜率 `75.28%`、`0.919` 笔/天、PF `1.106`、Last90 年化 `-41.44%`。
- `2026-06-30`：干净参数演化评估 `7,926` 个配置，找到 K+1 领先诊断版 `323.57%` 年化、`-18.67%` 回撤、`78.99%` 胜率、`0.608` 笔/天；但 K+2 延迟降为 `42.00%` 年化、`-38.68%` 回撤，K+2 联合通过 `0/201`。
- `2026-06-30`：放宽回撤后存在更激进版本：`DD<=25%` 首位 `337.95%` 年化、`-23.18%` 回撤、`80.71%` 胜率；`DD<=30%` 首位 `356.74%` 年化、`-26.94%` 回撤、`86.71%` 胜率，但 Last90 仅 `0.63%`，且高收益版本不具备 K+2 稳健性。
- `2026-06-30`：快速验证频率综合排名显示，严格 `1-3` 笔/天的版本收益或近期稳定性偏弱；综合第一是接近 `1` 笔/天的 `clean_rsi7_40_55_atrmin75_rvol0p75_h10_rsi14b0_tp120_sl320_hold32_x1`，K+1 年化 `97.07%`、回撤 `-20.13%`、胜率 `81.45%`，K+2 年化 `32.03%`。
- `2026-06-30`：放弃频率后，均衡观察版本选择 `clean_rsi7_40_60_atrmin105_rvol0_h10_rsi14b0_tp120_sl450_hold32_x2`；K+1 年化 `216.81%`、总收益 `244.44%`、回撤 `-15.65%`、胜率 `91.60%`，K+2 年化 `101.73%`、回撤 `-27.39%`。`3x` K+1 年化 `443.62%`，但 K+2 回撤 `-39.22%`，只作为 aggressive diagnostic。
- `2026-06-30`：按用户指定，将 `clean_rsi7_40_60_atrmin75_rvol1_h10_rsi14b0_tp120_sl360_hold16_x2` 记录为 `HYPE-15M-MII-V1base` 诊断观察基线；K+1 收益高、Last90 强，但 K+2 回撤扩大到 `-36.28%`，因此仍不是 promotion。
- `2026-06-30`：将干净参数登记为 `HYPE-15M-MII-V1.1`：仅保留 RSI、MACD、ATR/RVOL、固定 TP/SL/hold、2x 暴露和成本项；分窗口回测显示 K+1 最近 `1w` 无交易、最近 `1m` 总收益 `34.40%`、最近 `3m` 总收益 `52.69%`、全样本总收益 `309.54%`，但 K+2 全样本回撤仍为 `-36.28%`。另生成 HTML 交易路径图，可逐笔对照 K 线、RSI(7) 和 MACD(12,26,9)。
- `2026-06-30`：测试 V1.1 动态止盈（取消固定 `TP=1.20%`，activation 后 trailing stop）。`264` 个动态 trailing 配置中 `0` 个同时超过固定 TP baseline 的收益、回撤和胜率形状；综合第一 `trail_act150_trail30_sl360_hold16` K+1 年化 `205.74%`、回撤 `-36.08%`、胜率 `71.35%`，弱于固定 TP baseline。结论：V1.1 更像短促反转，不适合单纯放开利润奔跑。
- `2026-06-30`：按用户指定，将 ATR 动态止盈止损的联合通过配置记录为 `HYPE-15M-MII-V1.2`。该版本沿用 `V1.1` 入场过滤，入场时按信号 K 已知 `ATR96%` 设置固定 bracket：`TP = 1.25 * ATR96%`、`SL = 5.0 * ATR96%`、`hold=24`。`600` 个 ATR bracket 配置中，`3` 个 K+1 收益/回撤/胜率同时超过固定百分比 baseline，`1` 个 K+1/K+2 联合超过 baseline；K+1 年化 `311.35%`、回撤 `-17.74%`、胜率 `84.78%`；K+2 年化 `154.96%`、回撤 `-34.81%`、胜率 `82.01%`。结论：`V1.2` 比 trailing 更值得继续审计，但仍只是 diagnostic variant。
- `2026-06-30`：补充 `V1.2` 固定窗口、滚动窗口和随机切片回测。固定窗口 K+1 全样本 `184` 笔、总收益 `355.78%`、回撤 `-17.74%`、Sharpe `4.13`；K+2 全样本 `189` 笔、总收益 `172.87%`、回撤 `-34.81%`、Sharpe `2.46`。滚动 `30d` 仍存在负收益切片：K+1 最差 `-10.68%`，K+2 最差 `-29.03%`，因此不提升状态。
- `2026-06-30`：补充 `V1.2` 的 `ATR96 >= 0.75%` 与 `RVOL96 >= 1.0` 过滤消融。去掉 ATR 下限后 K+1 交易数从 `184` 增至 `342`，但总收益降到 `21.93%`、回撤恶化到 `-43.93%`，K+2 转为 `-21.09%`；去掉 RVOL 后 K+1 `388` 笔、总收益 `244.08%`、回撤 `-32.29%`；两个都去掉后 K+1 `711` 笔、总收益 `-78.36%`、回撤 `-84.73%`。结论：不能靠简单放开过滤解决交易频率偏低。
- `2026-06-30`：把 V1.1 直接套到 Binance USD-M `BTCUSDT`、`ETHUSDT` `15m` API 数据做跨资产诊断。BTC K+1 全样本只有 `2` 笔，年化 `3.46%`、总收益 `3.71%`，交易数过少；ETH K+1 全样本年化 `-37.95%`、总收益 `-40.06%`、回撤 `-42.74%`。结论：HYPE 参数没有自然迁移到 BTC/ETH。
- 实盘判断：`NO-GO`。没有生产 runner、真实 stop-market/滑点证据、资金费核算、重启恢复、交易所对账、missing-bar fail-closed 和 kill switch。

## 阅读顺序

1. `hype-15m-mii-core-ledger.md`
2. `canonical-specs/hype-15m-mii-v1-baseline-spec.md`
3. `ablations/hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md`
4. `live-specs/hype-15m-mii-v1-live-feasibility-2026-06-29.md`
5. `research-notes/hype-15m-mii-clean-parameter-evolution-2026-06-29.md`
6. `research-notes/hype-15m-mii-delay-aware-selection-2026-06-29.md`
7. `research-notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md`
8. `research-notes/hype-15m-mii-fast-validation-frequency-ranking-2026-06-30.md`
9. `research-notes/hype-15m-mii-balanced-leverage-stress-2026-06-30.md`
10. `research-notes/hype-15m-mii-v1-1-window-backtest-2026-06-30.md`
11. `research-notes/hype-15m-mii-v1-1-trade-paths-2026-06-30.md`
12. `research-notes/hype-15m-mii-v1-1-dynamic-take-profit-2026-06-30.md`
13. `live-specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md`
14. `research-notes/hype-15m-mii-v1-2-atr-bracket-exit-2026-06-30.md`
15. `research-notes/hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md`
16. `research-notes/hype-15m-mii-v1-2-atr-rvol-filter-ablation-2026-06-30.md`
17. `research-notes/hype-15m-mii-v1-1-btc-eth-cross-asset-2026-06-30.md`
18. `ablations/hype-15m-mii-v1-1-clean-lead-robustness-2026-06-29.md`
19. `diagnostics/hype-15m-mii-search-2026-06-25.md`
20. `ablations/hype-15m-mii-full-ablation-2026-06-26.md`
21. `ablations/hype-15m-mii-surface-combo-optimization-2026-06-26.md`

## 证据规则

- 研究脚本放在 `scripts/`。
- 被报告引用的 JSON/CSV 放在 `artifacts/`。
- 长期结论、消融和实盘审计保留在本家族 Markdown 中。
- V1 命名不改变 promotion 状态；没有通过 live-feasibility 审计前，不得标记为 candidate、paper-live、dry-run、handoff 或 live。
