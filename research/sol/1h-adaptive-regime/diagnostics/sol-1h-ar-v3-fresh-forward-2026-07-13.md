# SOL-1H-Adaptive-Regime-V3 Fresh Forward 审计 - 2026-07-13

## 结论

`2026-07-03T05:00:00Z` 至 `2026-07-13T07:00:00Z` 没有产生 V3 交易。该窗口不能验证、也不能否定 V3；版本状态保持 `registered / not promoted / not live-ready`。

- fresh forward：trades `0`，return `0.00%`，DD `0.00%`。
- 更新后 current full：annual `2.0753x`，DD `-19.05%`，win `79.17%`，trades `96`。
- 数据为 2026-07-13 刷新的最近两年闭合 SOLUSDT perpetual 1h 帧，质量 blocker `0`。

## 标准近期分片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_1m` | `1.7878x` | `4.89%` | `-2.43%` | `100.00%` | `2` | `inf` |
| `last_3m` | `1.1089x` | `2.61%` | `-4.55%` | `66.67%` | `3` | `2.223` |
| `last_6m` | `1.1498x` | `7.20%` | `-17.29%` | `75.00%` | `16` | `1.433` |
| `last_1y` | `1.7439x` | `74.33%` | `-17.89%` | `79.07%` | `43` | `2.976` |

## 边界

- 零交易不是通过 forward gate。
- 至少等待足够新增交易后再判断 V3；不得因本窗口净值不变而 promotion。

## 机器证据

- `artifacts/sol_1h_ar_v3_fresh_forward_2026-07-13.json`

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/audit_sol_1h_ar_v3_fresh_forward.py
```
