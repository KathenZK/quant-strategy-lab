# TRX-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`TRX-1H-Adaptive-Regime`
- Short id：`TRX-1H-AR`
- Market：Binance USD-M Futures `TRXUSDT` perpetual
- Timeframe：`1h`

## 当前状态

`TRX-1H-Adaptive-Regime-V1 + V2 + V3 registered / diagnostic only / NO-GO / not promoted / not live-ready`。

用户于 2026-07-05 明确要求把上一轮领先观察值登记为 `TRX-1H-Adaptive-Regime-V1`。用户于 2026-07-06 明确要求把干净参数版本登记为 `TRX-1H-Adaptive-Regime-V2`，并对 V2 做全参数消融；随后明确要求把 V2 消融引导微调观察值登记为 `TRX-1H-Adaptive-Regime-V3`。此前文档中的 `V1base` 是登记前临时命名；当前正式版本为 `V1`、`V2`、`V3`。`V2` 是 `V1` 的 clean-equivalent 参数版本，与 V1 逐交易路径完全一致；`V3` 是基于 V2 参数面微调后的新交易路径。

## V1 身份与冻结边界

- Source observation：`ENS__TRX_1H_AR_N131875__TRX_1H_AR_N129128`
- Frozen data：`2024-07-03T06:00:00Z -> 2026-07-03T05:00:00Z`，`17,520` 根闭合 `1h` K。
- Train：`2024-08-17T06:00:00Z -> 2025-09-07T08:24:00Z`。
- Validation：`2025-09-07T08:24:00Z -> 2026-04-03T06:00:00Z`。
- Reused holdout：`2026-04-03T06:00:00Z -> 2026-07-03T06:00:00Z`；已在初始研究中揭盲，后续不得称为 fresh OOS。
- Cost：fee `0.001/fill`、adverse slippage `4 bps/fill`、实际 Binance funding。

| Scope | Annual multiple | Return | Max DD | Win rate | Trades | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| train | `9.198x` | `+944.03%` | `-16.34%` | `90.77%` | `65` | diagnostic |
| validation | `1.792x` | `+39.40%` | `-19.84%` | `80.65%` | `31` | diagnostic |
| prefit | `5.189x` | `+1355.40%` | `-19.84%` | `87.50%` | `96` | annual `<10x` |
| reused holdout | `0.844x` | `-4.12%` | `-11.42%` | `75.00%` | `8` | loss / insufficient trades |
| full | `4.077x` | `+1295.38%` | `-19.84%` | `86.54%` | `104` | annual `<10x`; holdout failed |

## V1 双组件规则

### MACD flip

- `MACD(34,89,13)` histogram 零轴交叉，both sides。
- Filters：`ADX 12-28`、`RVOL>=1.5`、`ATR<=200 bps`、directional `ROC12>=-100 bps`、距 `EMA377<=1000 bps`、`12h` trend 同向、MACD turn。
- Exit/risk：fixed `TP=2 ATR / SL=4 ATR / max_hold=168h / cooldown=3h / entry_delay=1 / 4x`。

### Stochastic reversal

- `Stochastic(21)` K/D 交叉，阈值 `25/85`，long-only。
- Filters：`ADX<=30`、`RVOL>=1.0`、directional `ROC3>=-200 bps`、body 同向。
- Exit/risk：trailing `initial SL=5 ATR / activation=3 ATR / trail=1.25 ATR / max_hold=168h / cooldown=24h / entry_delay=1 / 3x`。

### Ensemble

- 两组件按冻结前 prefit score 排序处理冲突；单仓、不加仓。
- 闭合 K 产生信号，下一根 open 成交；保护 stop 立即有效；同 K 双触发 stop-first；gap 穿越 stop 按 open 成交。

## V2 Clean 参数版本

`TRX-1H-Adaptive-Regime-V2` 是 V1 全字段消融后的干净参数版本：

- `33` 个语义 dormant/neutral 字段从外部参数面移除并固定为 V1 值；
- `9` 个版本身份/订单契约字段硬编码；
- `36` 个 V2 对外参数字段保留，其中包括 component-level `entry_delay_bars` 与 Stochastic `side_mode`。

`trx_1h_ar_v2.py` 已以逐交易签名确认 V2 与完整 V1 路径完全一致。

V2 参数面：

- `macd_flip`：`ema_htf`、`roc_window`、`macd_fast`、`macd_slow`、`macd_signal`、`min_adx`、`max_adx`、`min_rvol`、`max_atr_bps`、`min_dir_roc_bps`、`max_dist_ema_bps`、`htf_mode`、`require_macd_turn`、`tp_atr`、`sl_atr`、`max_hold_bars`、`cooldown_bars`、`entry_delay_bars`、`fixed_leverage`。
- `stoch_reversal`：`side_mode`、`ema_htf`、`indicator_window`、`threshold_low`、`threshold_high`、`roc_window`、`max_adx`、`min_rvol`、`min_dir_roc_bps`、`require_body_dir`、`sl_atr`、`trail_activation_atr`、`trail_atr`、`max_hold_bars`、`cooldown_bars`、`entry_delay_bars`、`fixed_leverage`。

## V2 全参数消融

2026-07-06 对 V2 对外暴露的 `36/36` 个 clean 参数槽完成 one-at-a-time 全参数消融，行数 `211`（含 baseline），coverage missing `0`，prefit 严格改善 `8` 行。严格改善行只作为诊断，不使用 reused holdout 或近期分片选参。

V2 严格近期分片：

| Slice | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: |
| `last_1d` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `last_7d` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `last_1m` | `-10.12%` | `-11.42%` | `50.00%` | `4` |
| `last_3m` | `-4.12%` | `-11.42%` | `75.00%` | `8` |
| `last_6m` | `+12.80%` | `-11.42%` | `77.78%` | `18` |
| `last_1y` | `+45.18%` | `-19.84%` | `80.00%` | `50` |

V2 逐笔执行重放覆盖 warmup 后 merged `107` 笔交易（full 指标窗口 `104` 笔）和组件交易；违规计数 `0`，merged 违规 `0`。stop gap 按 open 成交 `22` 次，有利 target gap 以 target 价保守记账 `0` 次。

## V3 消融引导微调版本

2026-07-06 根据 V2 全参数消融与 clean-surface pair pool 做一次微调，选择过程只使用 train/validation/prefit，不读取 reused holdout 或近期分片。硬约束为 train/validation/prefit `win>=80%`、DD `<20%`、train/validation 正收益、prefit annual 高于 V2。pair pool `500` 行，满足硬约束 `41` 行；选中观察值原 id 为 `TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06`，现按用户指令正式登记为 `TRX-1H-Adaptive-Regime-V3`。

| Window | V2 annual / return / DD / win / trades | Tune annual / return / DD / win / trades |
| --- | --- | --- |
| `train` | `9.198x / +944.03% / -16.34% / 90.77% / 65` | `8.156x / +819.38% / -17.17% / 90.91% / 55` |
| `validation` | `1.792x / +39.40% / -19.84% / 80.65% / 31` | `6.013x / +177.62% / -11.17% / 100.00% / 29` |
| `prefit` | `5.189x / +1355.40% / -19.84% / 87.50% / 96` | `7.330x / +2452.42% / -17.17% / 94.05% / 84` |
| `reused holdout` | `0.844x / -4.12% / -11.42% / 75.00% / 8` | `1.083x / +2.02% / -15.23% / 77.78% / 9` |
| `current full` | `4.077x / +1295.38% / -19.84% / 86.54% / 104` | `5.686x / +2503.89% / -17.17% / 92.47% / 93` |

近期分片方面，微调观察值最近 `1m +3.52% / -1.56% DD / 100% win / 2 trades`，`3m +2.02% / -15.23% DD / 77.78% win / 9 trades`，`6m +80.29% / -15.23% DD / 91.30% win / 23 trades`，`1y +191.14% / -15.71% DD / 91.84% win / 49 trades`。

执行复核：逐笔重放违规 `0`，merged 违规 `0`；stop gap/open 按 open 成交 `10` 次，target gap 以 target 价记账 `0` 次。V3 满足本次提出的 current full 收益更高、win `>=80%`、DD `<20%` 目标，但 reused holdout 胜率仅 `77.78%`，且无新增 forward trades 与 production runner，因此 V3 只是 diagnostic registered version，不 promotion。

## V3 全参数消融与 clean 参数面

2026-07-07 对 V3 对外暴露的 `36/36` 个参数槽完成 one-at-a-time 全参数消融，行数 `215`（含 baseline），coverage missing `0`，prefit 严格改善行 `0`（V3 在单字段方向上已是局部最优）。V3 逐笔执行重放违规 `0`，merged 违规 `0`。

按 merged 交易路径识别出 `5` 个 dormant（无作用）字段并固定为 V3 值，从可调参数面移除：

- `macd_flip`：`ema_htf`、`max_atr_bps`、`max_hold_bars`、`require_macd_turn`。
- `stoch_reversal`：`ema_htf`。

V3 clean 参数面保留 `31` 个可调槽（MACD `15`、Stochastic `16`），`trx_1h_ar_v3_clean.py` 已确认 clean 面与 V3 逐交易路径完全一致。

## V3 clean 参数面微调（no-hit）

2026-07-07 在 V3 clean 参数面上做随机邻域微调（1-5 字段变更），选择只使用 train/validation/prefit，硬约束要求 prefit 年化、胜率、回撤同时严格优于 V3（`7.3305x / 94.05% / -17.17%`）。首轮 seed `20260707` 评估 `3,420` 个唯一候选，独立 seed `99120707` 追加验证 `9,111` 个，三指标同时改善命中均为 `0`。

单指标改善候选存在（annual `114`、win `145`、DD `719`），但 annual+win 仅 `1`、annual+DD 仅 `1`、三者同收 `0`——收益与胜率/回撤在此参数面上形成明确 trade-off。结论：V3 参数保持不变，本轮为 no-hit 诊断，未产生新版本。

## 版本表

| Version | Status | Metrics | Evidence | Live readiness |
| --- | --- | --- | --- | --- |
| `TRX-1H-Adaptive-Regime-V1` | registered baseline / not promoted | full `4.077x annual / -19.84% DD / 86.54% win / 104 trades`; reused holdout `0.844x annual / -4.12% return / -11.42% DD / 75.00% win / 8 trades` | `specs/trx-1h-ar-v1-baseline-spec.md`; `artifacts/trx_1h_ar_v1_config_2026-07-05.json` | `NO-GO / not live-ready` |
| `TRX-1H-Adaptive-Regime-V2` | registered clean parameter version / V1 trade-path equivalent / not promoted | same trade path as V1; V2 full parameter ablation coverage `36/36`; one-at-a-time rows `211`; prefit strict improve `8`; recent slices `1m -10.12%`, `3m -4.12%`, `6m +12.80%`, `1y +45.18%`; execution replay violations `0` | `artifacts/trx_1h_ar_v2_config_2026-07-06.json`; `ablations/trx-1h-ar-v2-full-parameter-ablation-2026-07-06.md`; `artifacts/trx_1h_ar_v2_full_ablation_2026-07-06.json` | `NO-GO / not live-ready` |
| `TRX-1H-Adaptive-Regime-V3` | registered V2 ablation-guided tuned diagnostic version / full ablation complete / clean-surface tune no-hit / not promoted | current full `5.686x annual / +2503.89% return / -17.17% DD / 92.47% win / 93 trades`; reused holdout `1.083x annual / +2.02% return / -15.23% DD / 77.78% win / 9 trades`; V3 full ablation coverage `36/36`, rows `215`, prefit strict improve `0`; clean surface `31` tunable + `5` dormant fixed; clean tune `12,531` unique candidates, triple-improve hits `0`; execution replay violations `0` | `specs/trx-1h-ar-v3-parameter-spec-2026-07-06.md`; `artifacts/trx_1h_ar_v3_config_2026-07-06.json`; `ablations/trx-1h-ar-v3-full-parameter-ablation-2026-07-07.md`; `artifacts/trx_1h_ar_v3_clean_config_2026-07-07.json`; `research-notes/trx-1h-ar-v3-clean-tune-2026-07-07.md` | `NO-GO / not live-ready` |

## Promotion 边界

登记不等于 promotion。V3 的 current full 收益、胜率和回撤优于 V2，但 reused holdout 胜率仅 `77.78%`，且 reused holdout 已揭盲，不是 fresh OOS；仓库也无 TRX production runner、重启恢复、交易所 reconciliation、缺 K fail-closed 与 kill switch。因此 V1/V2/V3 均禁止标记为 candidate、paper-live、dry-run、handoff 或 live。
