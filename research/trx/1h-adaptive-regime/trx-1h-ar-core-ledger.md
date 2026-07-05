# TRX-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`TRX-1H-Adaptive-Regime`
- Short id：`TRX-1H-AR`
- Market：Binance USD-M Futures `TRXUSDT` perpetual
- Timeframe：`1h`

## 当前状态

`TRX-1H-Adaptive-Regime-V1 registered / diagnostic baseline / NO-GO / not promoted / not live-ready`。

用户于 2026-07-05 明确要求把上一轮领先观察值登记为 V1。此前文档中的 `V1base` 与 `V2 clean` 是登记前的临时命名：它们共享完全相同的交易行为，不构成两个版本。当前唯一登记版本为 `TRX-1H-Adaptive-Regime-V1`；删参结果属于 V1 的 clean-equivalent 配置面。

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

## V1 Clean-equivalent 参数面

全字段消融覆盖两个组件 `78/78` 个 `StrategyConfig` 槽位：

- `33` 个语义 dormant/neutral 字段从外部参数面移除并固定为 V1 值；
- `9` 个版本身份/订单契约字段硬编码；
- `36` 个真实决策字段保留，其中包括消融显示有价值的 component-level `entry_delay_bars`，以及 Stochastic `side_mode`。

`trx_1h_ar_v1_clean.py` 已以逐交易签名确认 clean 配置与完整 V1 路径完全一致。clean-equivalent 不是新版本。

## 版本表

| Version | Status | Metrics | Evidence | Live readiness |
| --- | --- | --- | --- | --- |
| `TRX-1H-Adaptive-Regime-V1` | registered diagnostic baseline / clean-equivalent surface / not promoted | full `4.077x annual / -19.84% DD / 86.54% win / 104 trades`; reused holdout `0.844x annual / -4.12% return / -11.42% DD / 75.00% win / 8 trades` | `canonical-specs/trx-1h-ar-v1-baseline-spec.md`; `artifacts/trx_1h_ar_v1_config_2026-07-05.json`; `artifacts/trx_1h_ar_v1_clean_config_2026-07-05.json` | `NO-GO / not live-ready` |

## Promotion 边界

登记不等于 promotion。V1 未达到 `>=10x` 年化目标，reused holdout 亏损，且仓库无 TRX production runner、重启恢复、交易所 reconciliation、缺 K fail-closed 与 kill switch。因此禁止标记为 candidate、paper-live、dry-run、handoff 或 live。
