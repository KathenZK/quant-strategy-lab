# SOL-1H-Pullback-Bracket 首轮搜索 - 2026-07-13

## 结论

没有 prefit candidate 命中 `10x / 80% / <20% DD`；本轮状态为 `explore / not promoted / not live-ready`。

- generated `1500`；evaluated `1376`；eligible `45`；prefit hard pass `0`。
- 机制：EMA 趋势持续 → 回踩 arm → 恢复并突破前 K 确认 → 下一根 open + 即时 ATR bracket。

## Prefit-only 选中观察

- id：`SOL_1H_PB_R01145`；signals `64`；events `1061`；score `1.487`。
- train：annual `1.1396x`，DD `-6.43%`，win `37.93%`，trades `29`。
- validation：annual `1.1918x`，DD `-4.92%`，win `38.89%`，trades `18`。
- prefit：annual `1.1576x`，DD `-9.56%`，win `38.30%`，trades `47`。
- reused holdout：annual `1.1236x`，return `2.95%`，DD `-1.79%`，trades `3`。
- fresh forward：return `-2.01%`，DD `-2.05%`，trades `2`。
- full：annual `1.1382x`，DD `-9.56%`，win `36.54%`，trades `52`。
- prefit payoff `2.542`，avg win `3.88%`，avg loss `-1.53%`。

## 标准近期分片（仅审计）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `0.3475x` | `-2.01%` | `-2.05%` | `0.00%` | `2` | `0.000` |
| `last_1m` | `1.2167x` | `1.62%` | `-2.05%` | `33.33%` | `3` | `1.838` |
| `last_3m` | `1.0358x` | `0.88%` | `-2.05%` | `20.00%` | `5` | `1.348` |
| `last_6m` | `1.2497x` | `11.75%` | `-4.30%` | `36.36%` | `11` | `2.587` |
| `last_1y` | `1.0686x` | `6.85%` | `-8.71%` | `30.77%` | `26` | `1.317` |

## 延迟与成本压力

| Scenario | Prefit ann | Prefit DD | Holdout ann | Fresh return | Full ann | Full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1_4bps` | `1.1576x` | `-9.56%` | `1.1236x` | `-2.01%` | `1.1382x` | `-9.56%` |
| `delay_k2_4bps` | `1.0249x` | `-13.83%` | `1.1194x` | `-2.01%` | `1.0255x` | `-13.83%` |
| `base_k1_8bps` | `1.1434x` | `-9.82%` | `1.1147x` | `-2.09%` | `1.1246x` | `-9.82%` |

## 研究边界

- reused holdout 不参与选择；fresh forward 仅约 10 天。
- 首轮不登记版本，不进入 dry-run/live。

## 机器证据

- `artifacts/sol_1h_pullback_bracket_search_2026-07-13.json`
- `artifacts/sol_1h_pullback_bracket_ranking_2026-07-13.csv`
- `artifacts/sol_1h_pullback_bracket_slices_2026-07-13.csv`
- `artifacts/sol_1h_pullback_bracket_selected_trades_2026-07-13.csv`

复现：

```bash
uv run python research/sol/1h-pullback-bracket/scripts/research_sol_1h_pullback_bracket_search.py
```
