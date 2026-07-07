# BTC-1H-Adaptive-Regime-V3 参数必要性审计 - 2026-07-07

## 结论

基于 2026-07-06 V3 全参数消融的路径等价证据，对 V3 clean surface 的 `27` 个 active 槽位逐项做中和验证：把候选参数替换为“移除等价”的中性值，并要求替换后与 V3 逐笔交易签名完全一致（贪心累积验证）。

结果：`7` 个槽位在 V3 冻结值下从不生效，可以安全移除；`roc_window` 在方向 ROC 过滤移除后完全失效（probe 验证 `True`），一并从最小表面剔除。最小等价表面共 `19` 个必要参数（Keltner `8` 个、CCI `11` 个），逐笔路径与 V3 完全等价，指标不变。

## 移除明细

| Leg | Parameter | V3 value | 中和值 | 累积路径等价 | 决定 | 原因 |
| --- | --- | ---: | ---: | --- | --- | --- |
| `keltner` | `max_atr_bps` | `200.0` | `10000.0` | `True` | 移除 | 波动率上限；消融显示放宽到 250/300/10000 路径不变，从不拒绝信号 |
| `keltner` | `min_dir_roc_bps` | `-200.0` | `-10000.0` | `True` | 移除 | 方向 ROC 下限；放宽到 -10000 路径不变，过滤器从不生效 |
| `keltner` | `max_aligned_funding_bps` | `4.0` | `10000.0` | `True` | 移除 | 顺方向资金费上限；收紧到 2.0 或放宽到 10000 路径均不变 |
| `keltner` | `max_hold_bars` | `240` | `100000` | `True` | 移除 | 最长持仓；168/216 路径不变，没有交易持仓到 240 根上限 |
| `keltner` | `cooldown_bars` | `0` | `0` | `True` | 移除 | 冷却期；V3 冻结值即 0（关闭状态），槽位本身无效 |
| `cci` | `max_atr_bps` | `600.0` | `10000.0` | `True` | 移除 | 波动率上限；收紧到 300 路径都不变，从不拒绝信号 |
| `cci` | `cooldown_bars` | `0` | `0` | `True` | 移除 | 冷却期；V3 冻结值即 0（关闭状态），槽位本身无效 |
| `keltner` | `roc_window` | `24` | 依附移除 | `True` | 移除 | 方向 ROC 过滤（min_dir_roc_bps）移除后该窗口不再被读取 |

## 必要参数（最小等价表面）

### Keltner breakout leg（8 个）

| Parameter | V3 value |
| --- | ---: |
| `indicator_window` | `20` |
| `band_k` | `2.0` |
| `min_adx` | `40.0` |
| `min_rvol` | `1.25` |
| `htf_mode` | `h4` |
| `tp_atr` | `1.5` |
| `sl_atr` | `5.0` |
| `fixed_leverage` | `2.4` |

### CCI reversal leg（11 个）

| Parameter | V3 value |
| --- | ---: |
| `ema_htf` | `377` |
| `indicator_window` | `20` |
| `threshold_high` | `125.0` |
| `max_adx` | `40.0` |
| `min_rvol` | `1.25` |
| `min_atr_bps` | `75.0` |
| `max_dist_ema_bps` | `750.0` |
| `tp_atr` | `5.5` |
| `sl_atr` | `1.5` |
| `max_hold_bars` | `72` |
| `fixed_leverage` | `3.5` |

## 边界

- “非必要”只针对 V3 当前冻结值：这些过滤器在历史两年数据上从不触发，不代表它们在其他参数组合下也永远无效。
- 移除验证使用逐笔交易签名完全一致，指标与 V3 逐字节相同，不构成新版本。
- 该审计不改变 `diagnostic observation / not live-ready`。

## 机器证据

- `artifacts/btc_1h_ar_v3_param_necessity_2026-07-07.json`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v3_param_necessity.py
```
