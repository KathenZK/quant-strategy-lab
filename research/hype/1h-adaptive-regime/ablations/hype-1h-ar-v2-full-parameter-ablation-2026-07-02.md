# HYPE-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-02

## 结论

本轮以 `HYPE-1H-Adaptive-Regime-V2` clean baseline 为基线，只覆盖 V2 clean 配置接口中的 `34` 个字段槽：DI-cross `15` 个，Stoch-reversal `19` 个。

共输出 `98` 行（含 baseline 与两条 leg_removed 诊断行），coverage missing fields 为 `0`。

单字段消融中，prefit 同时提高年化、降低回撤且胜率 `>=50%` 的行数为 `1`；current full 同时提高年化、降低回撤且胜率 `>=50%` 的行数为 `13`；完整 current full + reused holdout target-like 通过行数为 `0`。这些结果仍只作诊断，不构成新版本登记。

## V2 当前数据复现

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prefit | `11.6665x` | `526.17%` | `-16.93%` | `79.25%` | `53` | `7.267` |
| Reused holdout | `5.1305x` | `43.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| Current full | `9.6838x` | `795.75%` | `-19.64%` | `78.26%` | `69` | `6.486` |

## 字段覆盖

| Component | Field | Baseline | Variant rows | Prefit improve | Current improve | Target-like pass |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `di_cross` | `ema_htf` | `89` | `2` | `0` | `0` | `0` |
| `di_cross` | `fixed_leverage` | `3.0` | `3` | `0` | `1` | `0` |
| `di_cross` | `htf_mode` | `h12` | `3` | `0` | `0` | `0` |
| `di_cross` | `max_adx` | `36.0` | `3` | `0` | `0` | `0` |
| `di_cross` | `max_aligned_funding_bps` | `8.0` | `2` | `0` | `0` | `0` |
| `di_cross` | `max_atr_bps` | `250.0` | `3` | `0` | `0` | `0` |
| `di_cross` | `max_dist_ema_bps` | `750.0` | `3` | `0` | `0` | `0` |
| `di_cross` | `max_hold_bars` | `18` | `3` | `0` | `0` | `0` |
| `di_cross` | `min_adx` | `12.0` | `2` | `0` | `0` | `0` |
| `di_cross` | `min_dir_roc_bps` | `-200.0` | `2` | `0` | `1` | `0` |
| `di_cross` | `min_rvol` | `2.0` | `3` | `0` | `0` | `0` |
| `di_cross` | `require_body_dir` | `True` | `1` | `0` | `0` | `0` |
| `di_cross` | `roc_window` | `24` | `2` | `1` | `1` | `0` |
| `di_cross` | `sl_atr` | `4.0` | `2` | `0` | `0` | `0` |
| `di_cross` | `tp_atr` | `1.5` | `2` | `0` | `0` | `0` |
| `stoch_reversal` | `cooldown_bars` | `24` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `ema_htf` | `55` | `3` | `0` | `1` | `0` |
| `stoch_reversal` | `fixed_leverage` | `2.0` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `indicator_window` | `21` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `macd_fast` | `8` | `3` | `0` | `1` | `0` |
| `stoch_reversal` | `macd_signal` | `5` | `2` | `0` | `0` | `0` |
| `stoch_reversal` | `macd_slow` | `21` | `3` | `0` | `3` | `0` |
| `stoch_reversal` | `max_atr_bps` | `400.0` | `4` | `0` | `1` | `0` |
| `stoch_reversal` | `max_dist_ema_bps` | `2500.0` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `max_hold_bars` | `8` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `min_adx` | `12.0` | `3` | `0` | `2` | `0` |
| `stoch_reversal` | `min_atr_bps` | `200.0` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `min_rvol` | `1.0` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `require_macd_turn` | `True` | `1` | `0` | `0` | `0` |
| `stoch_reversal` | `sl_atr` | `4.0` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `threshold_high` | `60.0` | `4` | `0` | `1` | `0` |
| `stoch_reversal` | `threshold_low` | `25.0` | `4` | `0` | `0` | `0` |
| `stoch_reversal` | `trail_activation_atr` | `1.0` | `3` | `0` | `0` | `0` |
| `stoch_reversal` | `trail_atr` | `1.0` | `3` | `0` | `1` | `0` |

## Top current full 单字段改善诊断

| Label | Current annual | Current DD | Current win | Current trades | Reused holdout annual | Reused holdout DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `di_cross__min_dir_roc_bps__m10000p0` | `12.9357x` | `-19.11%` | `79.45%` | `73` | `7.0433x` | `-19.11%` |
| `di_cross__roc_window__12` | `12.2096x` | `-19.11%` | `80.28%` | `71` | `7.0433x` | `-19.11%` |
| `di_cross__fixed_leverage__3p5` | `11.9754x` | `-19.64%` | `78.26%` | `69` | `6.3352x` | `-19.64%` |
| `stoch_reversal__threshold_high__55p0` | `11.2688x` | `-19.64%` | `78.57%` | `70` | `6.5776x` | `-19.64%` |
| `stoch_reversal__macd_fast__12` | `10.5675x` | `-19.64%` | `77.61%` | `67` | `5.1305x` | `-19.64%` |
| `stoch_reversal__macd_slow__55` | `10.5675x` | `-19.64%` | `77.61%` | `67` | `5.1305x` | `-19.64%` |
| `stoch_reversal__macd_slow__89` | `10.5675x` | `-19.64%` | `77.61%` | `67` | `5.1305x` | `-19.64%` |
| `stoch_reversal__max_atr_bps__600p0` | `10.4561x` | `-19.64%` | `78.57%` | `70` | `5.1305x` | `-19.64%` |
| `stoch_reversal__min_adx__0p0` | `10.4064x` | `-19.64%` | `78.26%` | `69` | `5.1305x` | `-19.64%` |
| `stoch_reversal__min_adx__8p0` | `10.4064x` | `-19.64%` | `78.26%` | `69` | `5.1305x` | `-19.64%` |

## Promotion 边界

- 本轮是 V2 clean base 的 one-at-a-time 参数敏感性诊断，不使用 reused holdout 重新选参。
- `target-like pass` 只代表 current full 与 reused holdout 在基础硬门槛形状上通过；它仍未包含 K+2、8 bps、真实 stop-market 滑点、生产 runner 和新增 forward trades。
- Reused holdout 已在本家族多轮研究中解锁，不能重新包装为 untouched OOS。
- 除非后续完成冻结参数后的 forward trades 与 live-executable 审计，否则不创建 V2.1/V3，不提升为 candidate、paper-live、dry-run、handoff 或 live。

## 机器证据

- JSON：`artifacts/hype_1h_ar_v2_full_ablation_2026-07-02.json`
- 行级 CSV：`artifacts/hype_1h_ar_v2_full_ablation_rows_2026-07-02.csv`
- 字段级 CSV：`artifacts/hype_1h_ar_v2_full_ablation_fields_2026-07-02.csv`
- 窗口 CSV：`artifacts/hype_1h_ar_v2_full_ablation_windows_2026-07-02.csv`

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_full_ablation.py
```
