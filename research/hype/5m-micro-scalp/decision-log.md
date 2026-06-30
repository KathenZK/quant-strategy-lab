# HYPE-5M-Micro-Scalp 决策日志

家族 id：`HYPE-5M-Micro-Scalp`

历史别名：`HYPE-5M-MS`

## 当前边界

- 这是一个独立的 Binance HYPEUSDT perpetual `5m` 高频 micro-scalp 研究家族。
- 即使复用 EMA、RSI、MACD、Bollinger、Donchian、ATR、ADX 或 volume features，它也不是 `HYPE-5M-Pullback-Trail` 的版本。
- 研究结论必须保存在本目录下，持久 JSON/CSV 证据放入 `artifacts/`。
- 在完成 order timing、bracket maintenance、restart behavior、cost sensitivity 与 paper/live-dry-run reconciliation 审计前，本家族任何策略都不能称为 live-ready。

## 研究批次

- `diagnostics/hype-5m-micro-scalp-search-2026-06-26.md`：首次 executable broad search，目标是用户提出的 Binance HYPEUSDT `5m` 上 `3-5` 笔/天、高胜率、低回撤、小单笔利润。测试了 `12576` 个 curated/random EMA/RSI/MACD/Bollinger/VWAP/Donchian/ATR/ADX/volume/candle-structure 配置，执行口径为 closed-bar signal、next-open entry、immediate TP/SL bracket、stop-first same-bar ordering、next-open timeout，并使用观测到的 Binance live cost。结果：`1595` 个配置落入 `3-5` 笔/天频率区间，但 hard pass 为 `0`、audit pass 为 `0`。频率区间内最佳年化倍数只有 `0.23x`；最高胜率频率区间行达到约 `85%` 胜率，但因为 payoff 和成本吞噬小额盈利，整体仍深度为负。
- `diagnostics/hype-5m-micro-scalp-relaxed-rounds-2026-06-26.md`：严格 no-go 后按用户要求进行的 constraint-relaxation search。数据与执行模型保持不变，每轮只放宽一种约束形态。`R1_relax_frequency` 将频率降到 `0.10-1.00` 笔/天，找到 `32` 个 round-gate candidates。`R2_relax_winrate_payoff` 允许 `45%+` 胜率但要求更强 PF/payoff，找到 `20` 个 round-gate candidates。`R3_live_candidate_gate` 去掉 high-win/micro-profit 叙事，仅保留 executable positive profitability 与 split robustness，找到 `36` 个 round-gate candidates。在 `88` 个 round-gate 行中，`81` 个通过初始 monthly live-candidate screen。
- `diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`：围绕 relaxed rounds 中四个样本数较好的 candidate 做 local parameter-neighborhood robustness sweep。测试 `749` 个邻域配置；`407` 个通过 robust gate，`396` 个通过 robust + monthly gate。最均衡的 paper audit candidate 是 `R1_relax_frequency_R01242__tp_sl_0011`：`vwap_revert`，both sides，`188` 笔，`0.48` 笔/天，年化 `1.32x`，胜率 `85.11%`，PF `1.468`，avg trade `16.67 bps`，maxDD `-8.16%`，VAL PF `5.445`，FWD PF `3.550`，recent 30d `10.46%`，`3/14` 个负收益月份。
- `canonical-specs/hype-5m-micro-scalp-v1-baseline-spec.md` 与 `ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`：将 `R1_relax_frequency_R01242__tp_sl_0011` 正式记录为 `HYPE-5M-Micro-Scalp-V1` 基线，并做全参数 one-at-a-time 消融。基线参数为 `vwap_revert`、both sides、EMA `21/96/384`、VWAP 偏离 `75 bps`、`require_trend=true`、`require_body_dir=true`、TP/SL `67.5/275 bps`、最长持仓 `96` 根、冷却 `36` 根。消融共 `103` 个配置，显示 V1 关键依赖 `entry_style=vwap_revert`、`require_trend=true`、`ema_slow=96`、`vwap_dev_bps=75`；`sl_bps=400`、`max_dist_ema_bps=130`、较短 `max_hold_bars` 等变体表现更高，但不能在未完成 paper audit 前替代 V1。

## 当前决策

- `HYPE-5M-Micro-Scalp-search-2026-06-26`：原始严格形态，即 `3-5` 笔/天的高胜率 micro-profit scalping，为 no-go。
- `HYPE-5M-Micro-Scalp-relaxed-rounds-2026-06-26` 与 `HYPE-5M-Micro-Scalp-candidate-robustness-2026-06-26`：放宽频率并弱化 micro-profit 框架后，找到了 paper-audit candidate。
- `HYPE-5M-Micro-Scalp-V1`：当前 baseline 版本，仅代表可复现 paper-audit baseline，不代表 live-ready。全参数消融显示局部还有更优参数，但先不升级为 V1.1，避免在未审计逐笔路径、订单维护和重启恢复前继续追参。
- 当前证据表明，在可用 HYPEUSDT `5m` 样本、该 executable model 和观测到的 Binance cost model 下，原始高频 micro-profit 形态不可行。
- 当前最佳 relaxed candidate 不是 live-ready；最多只能推进到逐笔 paper audit、order-maintenance audit、restart-state audit 和 live-spec drafting。
- 不要提升本次搜索中的高胜率行，除非同时明确说明其 PF 为负、年化倍数为负、且回撤很深。
