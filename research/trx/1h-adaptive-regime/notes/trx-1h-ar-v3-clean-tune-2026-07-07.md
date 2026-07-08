# TRX-1H-Adaptive-Regime-V3 clean 参数面微调 - 2026-07-07

## 结论

本轮在 V3 clean 参数面（31 个可调槽，5 个 dormant 字段固定为 V3 值）上做随机邻域微调；选择过程只使用 train/validation/prefit，不读取 reused holdout 或近期分片。硬约束要求 prefit 年化、胜率、回撤同时严格优于 V3。

- 唯一候选评估数：`3420`（seed `20260707`，最多 `6000` 次抽样）。
- prefit 三指标同时严格优于 V3 的候选：`0`。
- 独立 seed（`99120707`）追加验证 `9111` 个唯一候选：三指标同时改善命中仍为 `0`。

在该 clean 参数面与本轮搜索域内，没有候选能在 prefit 上同时做到收益更高、胜率更高、回撤更小。结合 V3 全参数消融中 prefit 严格改善行为 `0`，V3 在此参数面上已是局部最优；本轮为 no-hit 诊断结论，V3 参数保持不变。

## 三目标边界证据

V3 prefit 基线为 `7.3305x annual / 94.05% win / -17.17% DD`。首轮 `3420` 个候选按单指标统计：

| 改善维度 | 候选数 |
| --- | ---: |
| annual 更高 | `114` |
| win 更高 | `145` |
| DD 更小 | `719` |
| annual + win 同时更高 | `1` |
| annual 更高 + DD 更小 | `1` |
| win 更高 + DD 更小 | `91` |
| 三者同时改善 | `0` |

最接近的两个两指标候选（作诊断，不选中）：

- `macd_flip.tp_atr=2.0; stoch_reversal.max_hold_bars=72; macd_flip.entry_delay_bars=1; stoch_reversal.threshold_high=85.0`：prefit `7.9013x / -17.17% DD` 但 win 降至 `91.01%`。
- `macd_flip.min_rvol=0.8; stoch_reversal.fixed_leverage=4.0`：prefit `7.5603x / 94.52% win` 但 DD 恶化至 `-18.56%`。

即收益与胜率/回撤在此参数面上形成明确 trade-off，无法三者同收。

## 研究边界

- 本轮为微调观察，不自动登记新版本；任何登记需用户明确指令。
- reused holdout 已揭盲，只能做冻结后审计，不能作为 fresh OOS。
- V3 家族当前仍为 `NO-GO / not promoted / not live-ready`。

## 机器证据

- `artifacts/trx_1h_ar_v3_clean_tune_2026-07-07.json`
- `artifacts/trx_1h_ar_v3_clean_tune_candidates_2026-07-07.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v3_clean_tune.py
```
