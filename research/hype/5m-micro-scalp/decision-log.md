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
- `diagnostics/hype-5m-micro-scalp-candidate-robustness-2026-06-26.md`：围绕 relaxed rounds 中四个样本数较好的 candidate 做 local parameter-neighborhood robustness sweep。测试 `749` 个邻域配置；`407` 个通过 robust gate，`396` 个通过 robust + monthly gate。最均衡的 audit candidate 是 `R1_relax_frequency_R01242__tp_sl_0011`：`vwap_revert`，both sides，`188` 笔，`0.48` 笔/天，年化 `1.32x`，胜率 `85.11%`，PF `1.468`，avg trade `16.67 bps`，maxDD `-8.16%`，VAL PF `5.445`，FWD PF `3.550`，recent 30d `10.46%`，`3/14` 个负收益月份。
- `specs/hype-5m-micro-scalp-v1-baseline-spec.md` 与 `ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md`：将 `R1_relax_frequency_R01242__tp_sl_0011` 正式记录为 `HYPE-5M-Micro-Scalp-V1` 基线，并做全参数 one-at-a-time 消融。基线参数为 `vwap_revert`、both sides、EMA `21/96/384`、VWAP 偏离 `75 bps`、`require_trend=true`、`require_body_dir=true`、TP/SL `67.5/275 bps`、最长持仓 `96` 根、冷却 `36` 根。消融共 `103` 个配置，显示 V1 关键依赖 `entry_style=vwap_revert`、`require_trend=true`、`ema_slow=96`、`vwap_dev_bps=75`；`sl_bps=400`、`max_dist_ema_bps=130`、较短 `max_hold_bars` 等变体表现更高，但不能在未完成 audit 前替代 V1。
- `research-notes/hype-5m-micro-scalp-v1-simplified-combo-search-2026-06-30.md` 与 `research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md`：按用户要求精简 V1 参数并组合搜索。精简后固定 `vwap_revert` 下不生效的 dormant 字段，只搜索 `19` 个有效字段。当前数据覆盖到 `2026-06-30 06:15:00+00:00`，raw/normalized `113998` 行逐字段一致。V1 当前复现为 `189` 笔、`0.48` 笔/天、年化 `1.34x`、胜率 `85.71%`、PF `1.490`、maxDD `-8.16%`。组合搜索评估 `49016` 个配置，`633` 个同时高于 V1 年化且回撤更浅；五个前排 seed 的邻域稳健性再评估 `13389` 个配置。优先 audit observation `V1S_rand_016782__N00596` 后续被记录为 `HYPE-5M-Micro-Scalp-V1.1`：`182` 笔、`0.46` 笔/天、年化 `2.13x`、胜率 `87.91%`、PF `2.660`、avg trade `45.88 bps`、maxDD `-8.06%`、VAL PF `2.441`、FWD PF `5.739`、recent30 `11.86%`、`2` 个负收益月份；仍不是 live-ready。
- `specs/hype-5m-micro-scalp-v1-1-baseline-spec.md`、`ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md` 与 `research-notes/hype-5m-micro-scalp-v1-1-micro-tune-2026-06-30.md`：将 `V1S_rand_016782__N00596` 正式记录为 `HYPE-5M-Micro-Scalp-V1.1`，并做 V1.1 全参数消融与有效字段微调。V1.1 消融 `103` 组，确认 `bb_z`、`breakout_bps`、`min_dir_roc_bps`、`max_counter_roc_bps`、`pullback_bps`、`rsi_high`、`rsi_low`、`donchian`、`rsi_window`、`wick_atr` 在当前 `vwap_revert` 下完全无影响。微调搜索 `44001` 组，`2` 个 strict-improve rows；优先观察行 `V1.1_tune_grid_004895` 后续登记为 V1.2。
- `specs/hype-5m-micro-scalp-v1-2-baseline-spec.md` 与 `research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md`：按用户要求将 `V1.1_tune_grid_004895` 正式登记为 `HYPE-5M-Micro-Scalp-V1.2`。指定 fee `0.001`/fill、双边各 `4 bps` 不利滑点后，V1.1 在 `1x/2x/3x` 下年化 `1.56x/2.38x/3.55x`、maxDD `-9.84%/-19.12%/-27.82%`；V1.2 为 `1.76x/2.98x/4.89x`、maxDD `-9.96%/-19.90%/-29.67%`。V1.2 默认 `1x`，`2x/3x` 只作压力测试。
- `specs/hype-5m-micro-scalp-v1-3-baseline-spec.md`、`ablations/hype-5m-micro-scalp-v1-3-full-parameter-ablation-2026-07-01.md` 与 `research-notes/hype-5m-micro-scalp-v1-3-baseline-backtest-2026-07-01.md`：按用户要求将 V1.2 不生效参数全部剔除，登记为 `HYPE-5M-Micro-Scalp-V1.3`。V1.3 仅保留 `18` 个有效字段；与 V1.2 在指定成本下逐笔等价。消融 `60` 组显示 `tp_bps=130`、`close_pos=0.70`、`require_body_dir=false` 等单参变体年化更高，但样本与分段稳健性仍不足。
- `research-notes/hype-5m-micro-scalp-v1-3-atr-dynamic-tp-2026-07-01.md`：在 V1.3 信号与固定 `sl_bps=400` 不变下，将固定 `tp_bps=110` 替换为信号 K ATR 动态止盈。测试 `atr_abs`/`atr_pct` 多种倍数后，没有任何动态 TP 变体超过固定 TP 基线（`1.76x` / maxDD `-9.96%`）；最接近的 `atr_pct×3.0` 为 `1.72x` 但 maxDD 加深到 `-22.18%`，FWD PF 降至 `1.31`。
- `research-notes/hype-5m-micro-scalp-v1-3-atr-dynamic-leverage-2026-07-01.md`：V1.3 信号与固定 TP/SL 不变，仅改杠杆层。固定 `3x` 年化 `4.89x`、maxDD `-29.7%`；ATR 动态 `1x-3x` 平均杠杆 `2.15x`、年化 `2.92x`、maxDD `-23.5%`，介于固定 `2x` 与 `3x` 之间。

## 当前决策

- `HYPE-5M-Micro-Scalp-search-2026-06-26`：原始严格形态，即 `3-5` 笔/天的高胜率 micro-profit scalping，为 no-go。
- `HYPE-5M-Micro-Scalp-relaxed-rounds-2026-06-26` 与 `HYPE-5M-Micro-Scalp-candidate-robustness-2026-06-26`：放宽频率并弱化 micro-profit 框架后，找到了 audit candidate。
- `HYPE-5M-Micro-Scalp-V1`：当前 baseline 版本，仅代表可复现 audit baseline，不代表 live-ready。全参数消融显示局部还有更优参数，但先不升级为 V1.1，避免在未审计逐笔路径、订单维护和重启恢复前继续追参。
- `HYPE-5M-Micro-Scalp-V1.1`：由 `V1S_rand_016782__N00596` 记录而来，是当前 audit observation baseline；它改善了收益并使 maxDD 略浅于当前数据 V1，但仍需逐笔路径图、同 K TP/SL 与 gap ordering、参数邻域二次收缩、walk-forward 固化、订单维护和 restart-state 审计，不是 live/paper-live/handoff。
- `HYPE-5M-Micro-Scalp-V1.2`：由 `V1.1_tune_grid_004895` 正式登记而来；相对 V1.1 调整 EMA HTF、ADX/Chop/RVOL/ATR 过滤及 TP/SL。指定成本下收益更高但 maxDD 略深，默认 `1x`，仍为 audit observation / not live-ready。
- `HYPE-5M-Micro-Scalp-V1.3`：V1.2 的精简 schema 登记版；剔除 dormant 与等效关闭字段，交易逻辑与 V1.2 逐笔等价。当前标准配置表只暴露 `18` 个有效参数；仍为 audit observation / not live-ready。
- V1.2/V1.3 尚未完成二次邻域、逐笔路径、walk-forward 或 live-executable 审计；`2x/3x` 仅作 aggressive research stress，不作为实盘仓位建议。
- 当前证据表明，在可用 HYPEUSDT `5m` 样本、该 executable model 和观测到的 Binance cost model 下，原始高频 micro-profit 形态不可行。
- 当前最佳 relaxed candidate 不是 live-ready；最多只能推进到逐笔 audit、order-maintenance audit、restart-state audit 和 live-spec drafting。
- 不要提升本次搜索中的高胜率行，除非同时明确说明其 PF 为负、年化倍数为负、且回撤很深。
