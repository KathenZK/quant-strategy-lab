# HYPE-1H-Adaptive-Regime-V1 基线规格

## 身份与状态

- Full version：`HYPE-1H-Adaptive-Regime-V1`。
- 历史搜索 id：`ENS__HYPE_1H_AR_N026857__HYPE_1H_AR_N090440`。
- 状态：`diagnostic baseline / NO-GO / not live-ready / not promoted`。
- 登记原因：按用户要求，将本家族截至 2026-07-02 已冻结规则中 current-full 年化最高的可复现边界正式登记为 V1。

V1 是版本基线，不是 live、paper-live、dry-run、candidate 或 handoff。登记版本不会改变它未通过实盘压力审计的事实。

## 数据与回测口径

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，`1h`。
- 全量闭合 K：`2025-05-30 10:00 UTC` 至 `2026-07-02 02:00 UTC`，共 `9,545` 根。
- 数据质量：missing `0`、duplicate `0`、critical null `0`、OHLCV violation `0`、raw/normalized mismatch `0`。
- 闭合保护：直接以 UTC `close_time < Binance server time` 判断；normalized unclosed-at-cutoff 与 raw false-closed 均为硬 blocker。2026-07-02 修复毫秒 dtype 单位问题后，本版本及全部下游研究已全量重跑。
- 历史资金费：`2,385` 条，按 `entry_ts <= funding_ts < exit_ts` 逐笔计入。
- 指标 warmup 后计分起点：`2025-07-14 10:00 UTC`。
- Prefit 截止：`2026-04-13 03:39 UTC`；之后区间已经在历史研究中解锁，必须称为 `reused holdout`，不得再次称为 untouched OOS。
- 手续费：`0.001/fill`；滑点：`0.0004/fill`。

## 腿 A：DI-cross

信号为 `+DI14 - -DI14` 的零轴交叉。仅使用信号 K 闭合后可知的数据。

| 参数 | 值 |
| --- | ---: |
| `ema_htf` | `89` |
| `min_adx / max_adx` | `12 / 36` |
| `min_rvol` | `2.0` |
| `max_atr_bps` | `250` |
| `roc_window / min_dir_roc_bps` | `24 / -200` |
| `max_dist_ema_bps` | `750` |
| `htf_mode` | `h12` |
| `require_body_dir` | `true` |
| `max_aligned_funding_bps` | `8` |
| `tp_atr / sl_atr` | `1.5 / 4.0` |
| `max_hold_bars` | `18` |
| `fixed_leverage` | `3.0x` |

过滤含义：`12 <= ADX14 <= 36`、`RVOL48 >= 2`、`ATR14/close <= 250 bps`、方向化 `ROC24 >= -200 bps`、距 `EMA89 <= 750 bps`、方向与闭合 `12h` EMA regime、K 线实体和最后已知 funding 一致。

## 腿 B：Stoch-reversal

信号为 Stoch K/D 在超卖或超买区的反向交叉。

| 参数 | 值 |
| --- | ---: |
| `indicator_window` | `21` |
| `threshold_low / threshold_high` | `25 / 60` |
| `ema_htf` | `55` |
| `min_adx / min_rvol` | `12 / 1.0` |
| `min_atr_bps / max_atr_bps` | `200 / 400` |
| `max_dist_ema_bps` | `2500` |
| `macd_fast / slow / signal` | `8 / 21 / 5` |
| `require_macd_turn` | `true` |
| `sl_atr` | `4.0` |
| `trail_activation_atr / trail_atr` | `1.0 / 1.0` |
| `max_hold_bars / cooldown_bars` | `8 / 24` |
| `fixed_leverage` | `2.0x` |

## 可执行状态机

- 两条腿都允许 long/short；同一时间最多一个仓位，不加仓。
- 闭合信号 K 后在下一根 `1h` open 市价入场，即严格 K+1；禁止信号 K close 偷跑。
- DI 腿成交后立即放 `TP=1.5 ATR14`、`SL=4 ATR14`；Stoch 腿成交后立即放 `SL=4 ATR14`。
- Stoch trailing 只在持仓 K 完全闭合后更新，新 stop 从下一根 K 生效；禁止用同 K high 更新 stop 后再用同 K low 触发。
- stop gap 穿越按该 K open 加退出不利滑点；同 K stop/target 双触发按 stop-first。
- 同一入场时刻两腿冲突时 DI-cross 优先；被在途仓位覆盖的信号直接丢弃，不延后补入。
- 所有 ATR 距离使用信号 K 的 `ATR14` 冻结值。

完整公式与边界处理可交叉检查 `hype-1h-ar-boundary-reproduction-not-live-ready-2026-07-01.md`；V1 身份与本文件为准。

## 冻结结果

| Window | Annual multiple | Annual return | Max DD | Win rate | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `11.6665x` | `+1066.65%` | `-16.93%` | `79.25%` | `53` | `7.267` |
| Reused holdout | `5.1305x` | `+413.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| Current full | `9.6838x` | `+868.38%` | `-19.64%` | `78.26%` | `69` | `6.486` |

## Promotion 结论

`NO-GO`：current full 未达到 `10x`，reused holdout 远低于 `10x`；K+2 与加倍滑点会把回撤推过 `20%`。此外没有生产 runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 复现

```bash
uv run python research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py --refresh
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v1_full_ablation.py
```

关键证据：

- `artifacts/hype_1h_ar_v1_full_ablation_2026-07-02.json`
- `artifacts/hype_1h_ar_v1_full_ablation_rows_2026-07-02.csv`
- `artifacts/hype_1h_ar_v1_full_ablation_fields_2026-07-02.csv`
- `ablations/hype-1h-ar-v1-full-parameter-ablation-2026-07-02.md`
