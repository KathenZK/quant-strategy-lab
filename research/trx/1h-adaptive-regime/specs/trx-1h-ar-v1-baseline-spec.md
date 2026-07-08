# TRX-1H-Adaptive-Regime-V1 基线规格

## 版本身份

- Version：`TRX-1H-Adaptive-Regime-V1`
- Registered：2026-07-05
- Status：`registered baseline / NO-GO / not promoted / not live-ready`
- Source observation：`ENS__TRX_1H_AR_N131875__TRX_1H_AR_N129128`
- Canonical implementation：`scripts/trx_1h_ar_v1.py`
- Clean-equivalent implementation：`scripts/trx_1h_ar_v1_clean.py`

## 市场、数据和成本

- Binance USD-M Futures `TRXUSDT` perpetual `1h`。
- 冻结闭合 K：`17,520` 根，UTC `2024-07-03T06:00:00Z -> 2026-07-03T05:00:00Z`。
- fee `0.001` of filled notional per fill；adverse slippage `0.0004` per fill；逐笔历史 funding。
- 单仓、不加仓；权益按交易顺序复利。

## 因果订单时序

1. 只在 `1h` K 完整闭合后计算信号与 filters。
2. 信号在下一根 `K+1 open` 以市价成交；V1 两组件 `entry_delay_bars=1`。
3. 入场成交后立即放置 reduce-only stop-market；fixed leg 同时放置 reduce-only take-profit-market。
4. 同一 K 同时触发 stop 和 target 时按 stop-first。
5. open 跳过 stop 时，以首个可成交 open 加 adverse slippage 退出。
6. trailing 只使用已闭合 K 的 high/low 更新，并从下一根 K 生效。
7. timeout 在到期 K 的 open 退出；cooldown 期间不接受新入场。

## Component A：MACD flip

```text
style=macd_flip
side_mode=both
MACD=(34,89,13)
ema_htf=377
roc_window=12
min_adx=12
max_adx=28
min_rvol=1.5
max_atr_bps=200
min_dir_roc_bps=-100
max_dist_ema_bps=1000
htf_mode=h12
require_macd_turn=true
exit_kind=fixed
tp_atr=2
sl_atr=4
max_hold_bars=168
cooldown_bars=3
entry_delay_bars=1
sizing_kind=fixed
fixed_leverage=4
```

## Component B：Stochastic reversal

```text
style=stoch_reversal
side_mode=long
ema_htf=55
indicator_window=21
threshold_low=25
threshold_high=85
roc_window=3
max_adx=30
min_rvol=1
min_dir_roc_bps=-200
require_body_dir=true
exit_kind=trailing
sl_atr=5
trail_activation_atr=3
trail_atr=1.25
max_hold_bars=168
cooldown_bars=24
entry_delay_bars=1
sizing_kind=fixed
fixed_leverage=3
```

## Ensemble 冲突

- 组件各自生成完整交易路径。
- 按组件在 train/validation/prefit 上的冻结 score 作为优先级合并；较高优先级在同一入场时刻先占用单仓。
- 持仓期间的其他信号被忽略，直到退出后再次允许新交易。
- reused holdout 不参与组件优先级、参数或版本身份选择。

## Clean-equivalent

原始表示为两腿各 `39` 个字段，共 `78` 个槽。全字段消融后：

- 删除/硬编码语义 dormant 或 neutral 槽 `33` 个；
- 硬编码版本身份与订单契约槽 `9` 个；
- 保留真实决策槽 `36` 个。

clean 表面必须通过 `trade_signature` 与本规格逐笔相等；这只是 V1 的最小接口，不是 V2。

## 冻结指标

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `9.198x` | `+944.03%` | `-16.34%` | `90.77%` | `65` | `6.793` |
| validation | `1.792x` | `+39.40%` | `-19.84%` | `80.65%` | `31` | `2.089` |
| prefit | `5.189x` | `+1355.40%` | `-19.84%` | `87.50%` | `96` | `4.758` |
| reused holdout | `0.844x` | `-4.12%` | `-11.42%` | `75.00%` | `8` | `0.771` |
| full | `4.077x` | `+1295.38%` | `-19.84%` | `86.54%` | `104` | `4.090` |

## Live-readiness

V1 未通过收益与 reused-holdout gate，且没有生产 runner。登记仅冻结研究身份；不得用于 paper-live、dry-run、handoff 或 live。
