# HYPE-1H-Adaptive-Regime-V3 基线规格

## 身份与状态

- Full version：`HYPE-1H-Adaptive-Regime-V3`。
- 来源：V2 全参数消融后的组合复测 lead `di_roc_off__stoch_th55`。
- 状态：`diagnostic baseline / NO-GO / not live-ready / not promoted`。
- 登记原因：按用户要求，将 V2 消融引导组合复测中 base K+1 current full 表现最强的组合登记为 V3，便于后续独立消融、时间片复核和 forward 观察。

V3 不是 live、paper-live、dry-run、candidate 或 handoff。登记版本不会改变它未通过 K+2、8 bps 滑点压力和 live-executable 审计的事实。

## 数据与回测口径

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，`1h`。
- 全量闭合 K：`2025-05-30 10:00 UTC` 至 `2026-07-02 02:00 UTC`，共 `9,545` 根。
- 数据质量：missing `0`、duplicate `0`、critical null `0`、OHLCV violation `0`、raw/normalized mismatch `0`、normalized unclosed `0`。
- 历史资金费：`2,385` 条，按逐笔持仓区间计入。
- 指标 warmup 后计分起点：`2025-07-14 10:00 UTC`。
- Prefit 截止：`2026-04-13 03:39 UTC`；之后区间已经在历史研究中解锁，必须称为 `reused holdout`，不得再次称为 untouched OOS。
- 手续费：`0.001/fill`；滑点：`0.0004/fill`。

## DI-cross 配置

```text
ema_htf=89
min_adx=12.0
max_adx=36.0
min_rvol=2.0
max_atr_bps=250.0
roc_window=24
min_dir_roc_bps=-10000.0
max_dist_ema_bps=750.0
htf_mode=h12
require_body_dir=true
max_aligned_funding_bps=8.0
tp_atr=1.5
sl_atr=4.0
max_hold_bars=18
fixed_leverage=3.0
```

相对 V2，V3 只改变 `min_dir_roc_bps`：从 `-200.0` 放宽到 `-10000.0`，等价于关闭 DI 腿方向化 ROC 下限过滤。其余 DI-cross 状态机与 V2 一致。

## Stoch-reversal 配置

```text
indicator_window=21
threshold_low=25.0
threshold_high=55.0
ema_htf=55
min_adx=12.0
min_rvol=1.0
min_atr_bps=200.0
max_atr_bps=400.0
max_dist_ema_bps=2500.0
macd_fast=8
macd_slow=21
macd_signal=5
require_macd_turn=true
sl_atr=4.0
trail_activation_atr=1.0
trail_atr=1.0
max_hold_bars=8
cooldown_bars=24
fixed_leverage=2.0
```

相对 V2，V3 只改变 `threshold_high`：从 `60.0` 收紧到 `55.0`，使 Stoch 做空反转触发区更早进入候选。其余 Stoch-reversal 状态机与 V2 一致。

## 硬编码 live 语义

- `side=both`。
- `entry_delay_bars=1`：闭合 K 信号，下一根 `1h` open 入场。
- DI：固定 ATR bracket；Stoch：闭合 K 更新的 ATR trailing。
- 固定权益名义 sizing。
- 单仓；同刻冲突 DI-cross 优先。
- stop gap-open、stop-first、逐 fill 成本和逐笔 funding 与 V2 完全相同。

## 冻结结果

| Window | Annual multiple | Annual return | Max DD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `17.4864x` | `+1648.64%` | `-16.93%` | `80.70%` | `57` | `8.288` |
| Reused holdout | `9.0300x` | `+803.00%` | `-19.11%` | `76.47%` | `17` | `5.521` |
| Current full | `15.0530x` | `+1405.30%` | `-19.11%` | `79.73%` | `74` | `7.549` |

## 最近窗口

| Window | Trades | Win rate | Total return | Max DD | Annual multiple |
| --- | ---: | ---: | ---: | ---: | ---: |
| 最近 7 天 | `1` | `100.00%` | `+3.91%` | `-0.56%` | `7.3908x` |
| 最近 30 天 | `8` | `87.50%` | `+43.70%` | `-16.37%` | `82.6096x` |
| 最近 90 天 | `18` | `72.22%` | `+60.83%` | `-19.11%` | `6.8789x` |
| 最近 180 天 | `36` | `72.22%` | `+200.15%` | `-19.11%` | `9.3027x` |
| 最近 365 天 | `74` | `79.73%` | `+1271.47%` | `-19.11%` | `15.0530x` |

## 全参数消融结论

V3 全参数消融覆盖 clean 配置接口 `34` 个字段槽：DI-cross `15` 个，Stoch-reversal `19` 个；输出 `98` 行，coverage missing fields 为 `0`。

- Current full 同时提高年化、降低回撤且胜率 `>=50%`：`9` 行。
- 完整 current full + reused holdout target-like 通过：`5` 行。

这些行仍只作参数敏感性诊断；尚未通过 K+2、8 bps、真实 stop-market 滑点、生产 runner 和新增 forward trades，因此不提升为 live/paper-live/dry-run/candidate/handoff。

## 复现

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_ablation_combo_retest.py
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v3_full_ablation.py
```

关键证据：

- `notes/hype-1h-ar-v2-ablation-combo-retest-2026-07-06.md`
- `ablations/hype-1h-ar-v3-full-parameter-ablation-2026-07-06.md`
- `artifacts/hype_1h_ar_v3_full_ablation_2026-07-06.json`
