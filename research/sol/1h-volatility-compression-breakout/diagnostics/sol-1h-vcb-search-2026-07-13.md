# SOL-1H-Volatility-Compression-Breakout 首轮搜索 - 2026-07-13

## 结论

没有 prefit candidate 命中 `10x / 80% / <20% DD`，本轮结论为 `explore / not promoted / not live-ready`。

- entry configs `3000`；generated `14848`；eligible `1579`；prefit hard pass `0`；retained `1000`。
- 机制：多 K 波动压缩 arm、冻结区间、有限窗口方向突破确认、下一根 open 入场、ATR fixed/trailing exit、fixed/risk sizing。

## 数据质量

- Binance USD-M Futures `SOLUSDT` perpetual `1h`：`17520` 根闭合 K。
- UTC：`2024-07-13T07:00:00+00:00` 至 `2026-07-13T06:00:00+00:00`。
- missing `0`，duplicate `0`，blocker `0`。
- fee `0.001`/fill，slippage `4 bps`/fill，逐笔计入真实 Binance funding。

## 防泄漏切分

- train：`2024-08-27T07:00:00+00:00` 至 `2025-09-10T20:06:00+00:00`。
- validation：`2025-09-10T20:06:00+00:00` 至 `2026-04-03T05:00:00+00:00`。
- reused holdout：`2026-04-03T05:00:00+00:00` 至 `2026-07-03T05:00:00+00:00`；已被旧 SOL 家族研究揭盲，只审计。
- fresh forward：`2026-07-03T05:00:00+00:00` 至 `2026-07-13T07:00:00+00:00`；约 10 天，仅观察，不足以 promotion。

## Prefit-only 选中观察

- id：`SOL_1H_VCB_R002346`；score `2.397`；signals `45`；compression events `8625`。
- train：annual `1.4956x`，DD `-16.69%`，win `36.36%`，trades `22`。
- validation：annual `1.5899x`，DD `-13.76%`，win `40.00%`，trades `15`。
- prefit：annual `1.5279x`，DD `-16.69%`，win `37.84%`，trades `37`。
- reused holdout：annual `0.8870x`，return `-2.94%`，DD `-8.87%`，win `16.67%`，trades `6`。
- fresh forward：return `0.00%`，DD `0.00%`，win `0.00%`，trades `0`。
- current full：annual `1.4126x`，DD `-16.69%`，win `34.88%`，trades `43`。
- prefit payoff `3.868`，avg win `9.26%`，avg loss `-2.39%`，max trade loss `-3.82%`。

## 标准近期分片（锚定数据集末端，仅审计）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` | `0.000` |
| `last_1m` | `0.5350x` | `-5.01%` | `-7.23%` | `0.00%` | `2` | `0.000` |
| `last_3m` | `0.9553x` | `-1.13%` | `-8.87%` | `20.00%` | `5` | `0.902` |
| `last_6m` | `1.4948x` | `22.18%` | `-8.87%` | `45.45%` | `11` | `2.693` |
| `last_1y` | `1.6558x` | `65.52%` | `-14.93%` | `38.46%` | `26` | `2.494` |

## 延迟与成本

| Scenario | Prefit ann | Prefit DD | Holdout ann | Fresh return | Full ann | Full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1_4bps` | `1.5279x` | `-16.69%` | `0.8870x` | `0.00%` | `1.4126x` | `-16.69%` |
| `delay_k2_4bps` | `1.1291x` | `-20.00%` | `0.6277x` | `0.00%` | `1.0425x` | `-27.65%` |
| `base_k1_8bps` | `1.5074x` | `-17.05%` | `0.8739x` | `0.00%` | `1.3937x` | `-17.05%` |

## 研究边界

- 本 family 与 SOL-1H-Adaptive-Regime 独立，不继承其 V1/V2 版本号。
- reused holdout 不参与选择；fresh forward 仅约 10 天，样本不足。
- 首轮搜索只能形成 explore 结论，不登记版本，不进入 dry-run/live。

## 机器证据

- `artifacts/sol_1h_vcb_search_2026-07-13.json`
- `artifacts/sol_1h_vcb_search_ranking_2026-07-13.csv`
- `artifacts/sol_1h_vcb_search_slices_2026-07-13.csv`
- `artifacts/sol_1h_vcb_search_selected_trades_2026-07-13.csv`

复现：

```bash
uv run python research/sol/1h-volatility-compression-breakout/scripts/research_sol_1h_vcb_search.py
```
