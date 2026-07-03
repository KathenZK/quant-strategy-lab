# TRX-1H-Adaptive-Regime 两年广搜与 locked OOS 结论 - 2026-07-03

## 结论先行

没有找到同时满足以下三项硬门槛且通过最近三个月样本外验证的 `TRXUSDT 1h` 策略：

- 年化权益倍率 `>=10.0x`（年化收益 `>=900%`）；
- 胜率 `>=50%`；
- 最大回撤严格小于 `20%`。

本轮原始搜索结论为 `NO-GO / not promoted / not live-ready`。后续主账将领先观察值登记为 `V1base`，并把全参数消融后的干净参数面登记为 `V2`；这两个版本都只是 diagnostic baseline，不是可以诚实交付实盘的版本。全样本看起来很高的观察值在 locked OOS 亏损，不能用全样本叙事掩盖。

## 数据与冻结边界

- Binance USD-M Futures `TRXUSDT` perpetual `1h`。
- 精确闭合 K：`17,520` 根，UTC `2024-07-03T06:00:00Z -> 2026-07-03T05:00:00Z`。
- warmup/raw start：`2024-07-03T06:00:00Z`；有效 train start：`2024-08-17T06:00:00Z`。
- train：至 `2025-09-07T08:24:00Z`。
- validation：至 `2026-04-03T06:00:00Z`。
- locked OOS：`2026-04-03T06:00:00Z -> 2026-07-03T06:00:00Z`，右开。
- missing、duplicate、critical null、OHLC violation、raw/normalized mismatch 均为 `0`；资金费 `2,190` 条。

参数生成、评分、保留、邻域 seed 和 ensemble 优先级只使用 train + validation。OOS 只在 finalists 冻结后揭盲一次，且没有用于重排最终观察值。

## 可执行回测口径

- `K` 完整闭合后计算信号，`K+1 open` 市价成交；单仓、不加仓。
- 入场后立即具备 ATR stop/TP；同 K stop 与 target 双触发时 stop-first。
- open 跳过 stop 时按首个可成交 open 退出，再施加不利滑点。
- trailing 只在完整 K 闭合后更新，从下一根 K 生效。
- Binance fee `0.001/fill`，adverse slippage `4 bps/fill`，逐笔计入实际历史资金费。
- fixed/risk sizing 均参与搜索，最大观察杠杆 `5x`；最终领先 ensemble 的组件为 `4x` 与 `3x`。

## 搜索规模

| Phase | Generated | Tradable evaluated | Prefit eligible | Prefit hard-shape | Locked target |
| --- | ---: | ---: | ---: | ---: | ---: |
| broad curated + random | `300,768` | `109,143` | `22,298` | `0` | `0/500` |
| prefit-only neighborhood | `180,000` | `169,299` | `126,780` | `0` | `0/500` |
| persistent regime optimistic boundary | `12,936` | `11,308` | `11,308` | `0` | `0/300` |

指标与机制覆盖 EMA/MACD、RSI、Stochastic、CCI、Williams %R、ADX/DI、ATR、Bollinger、Keltner、Donchian、rolling VWAP、RVOL、动量、wick/body、squeeze、`4h/12h/1d` 闭合 regime、资金费过滤、long/short/both、fixed/risk sizing、fixed bracket/trailing，以及持续趋势/均值回归持仓状态。

## 领先观察值，不是 candidate

选择 id：`ENS__TRX_1H_AR_N131875__TRX_1H_AR_N129128`，由 prefit score 冻结。

| Window | Annual multiple | Total return | Max DD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `9.198x` | `+944.03%` | `-16.34%` | `90.77%` | `65` | `6.793` |
| validation | `1.792x` | `+39.40%` | `-19.84%` | `80.65%` | `31` | `2.089` |
| prefit | `5.189x` | `+1355.40%` | `-19.84%` | `87.50%` | `96` | `4.758` |
| locked OOS | `0.844x` | `-4.12%` | `-11.42%` | `75.00%` | `8` | `0.771` |
| full | `4.077x` | `+1295.38%` | `-19.84%` | `86.54%` | `104` | `4.090` |

它在 prefit 和 full 的年化权益倍率都低于 `10x`；OOS 不仅未达到 `10x`，而且区间实际亏损 `4.12%`，只有 `8` 笔，低于冻结 gate 的 `12` 笔最低证据量。高胜率不能弥补负 OOS 收益和收益目标失败。

### 两个组件

- `TRX_1H_AR_N131875`：`MACD(34,89,13)` flip，both sides，`ADX 12-28`、`RVOL>=1.5`、`ATR<=200 bps`、directional ROC12 `>=-100 bps`、距 EMA377 `<=1000 bps`、`12h` trend 同向、MACD turn；fixed `TP=2 ATR / SL=4 ATR / hold<=168h / cooldown=3h / 4x`。
- `TRX_1H_AR_N129128`：Stochastic(21) reversal，long-only，阈值 `25/85`，`ADX<=30`、`RVOL>=1.0`、ROC3 `>=-200 bps`、body 同向；trailing `initial SL=5 ATR / activation=3 ATR / trail=1.25 ATR / hold<=168h / cooldown=24h / 3x`。
- 冲突时使用 prefit score 冻结优先级；完整字段以 refine JSON 的 `retained_configs` 为准。

## 稳健性与实盘压力

| Scenario | Full annual | Full DD | OOS return | OOS annual | OOS DD | Pass |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline K+1 / 4 bps | `4.077x` | `-19.84%` | `-4.12%` | `0.844x` | `-11.42%` | `False` |
| K+2 delay / 4 bps | `2.504x` | `-34.46%` | `-5.44%` | `0.799x` | `-11.05%` | `False` |
| K+1 / 8 bps | `2.456x` | `-24.74%` | `-20.06%` | `0.407x` | `-24.62%` | `False` |
| K+2 / 8 bps | `2.208x` | `-34.84%` | `-6.70%` | `0.757x` | `-11.55%` | `False` |
| fee 15 bps / slippage 8 bps | `2.044x` | `-31.19%` | `-22.34%` | `0.363x` | `-25.75%` | `False` |

另有 `392` 个 causal persistent states、`0.5x-10x` side/leverage 组合的乐观上界审计。该审计故意不计 intrabar adverse excursion，也不要求保护单，仍为 `0` hard-gate 命中；最佳 prefit-selected 仅 `1.032x annual`，OOS `0.925x annual`。

## 为什么不能实盘

1. 收益硬门槛在 prefit、full、OOS 均失败。
2. 最近三个月 OOS 为实际亏损，且只有 `8` 笔，不足以证明 `75%` 胜率稳定。
3. K+2 或较高滑点会突破 `20%` 回撤边界。
4. 研究状态机虽可描述为真实订单时序，但仓库没有 TRX production runner、exchange reconciliation、保护单监控和 kill switch。

因此本轮不登记可 promotion 的 `V1`，不生成 canonical live spec，不进入 paper-live/dry-run/handoff。后续登记的 `V1base` 与 `V2` 只用于失败边界和删参复现。

## 复现命令

```bash
uv run python research/trx/1h-adaptive-regime/scripts/fetch_trx_binance_1h.py
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_adaptive_regime_search.py --random-configs 300000 --prefit-keep 800 --holdout-keep 300 --workers 8
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_adaptive_regime_refine.py --neighbors 180000 --prefit-keep 800 --holdout-keep 300 --workers 8
uv run python research/trx/1h-adaptive-regime/scripts/audit_trx_1h_persistent_regime_boundary.py
uv run python research/trx/1h-adaptive-regime/scripts/audit_trx_1h_live_feasibility.py
```

`fetch` 会刷新运行时最近两年数据；要逐字段复现本报告，应使用本轮精确 Parquet、quality JSON、funding CSV 和 contract snapshot，而不是未来刷新后的窗口。

## 证据

- `diagnostics/trx-binance-1h-data-quality-2026-07-03.md`
- `diagnostics/trx-1h-adaptive-regime-search-2026-07-03.md`
- `diagnostics/trx-1h-adaptive-regime-refine-2026-07-03.md`
- `diagnostics/trx-1h-persistent-regime-boundary-2026-07-03.md`
- `live-specs/trx-1h-ar-live-feasibility-2026-07-03.md`
- `ablations/trx-1h-ar-v1base-full-parameter-ablation-2026-07-03.md`
- `artifacts/trx_1h_adaptive_regime_search_2026-07-03.json`
- `artifacts/trx_1h_adaptive_regime_refine_2026-07-03.json`
- `artifacts/trx_1h_persistent_regime_boundary_2026-07-03.json`
- `artifacts/trx_1h_live_feasibility_2026-07-03.json`
- `artifacts/trx_1h_ar_v1base_full_ablation_2026-07-03.json`
