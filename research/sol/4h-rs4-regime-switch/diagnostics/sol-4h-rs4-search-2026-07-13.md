# SOL-4H-RS4-Regime-Switch 首轮搜索 - 2026-07-13

## 结论

没有 prefit spec 命中 `10x / 80% / <20% DD`；本轮状态为 `explore / not promoted / not live-ready`。

- specs `401`；base-gate pass `0`；prefit hard pass `0`。
- 机制：压缩 regime 的 MACD 双向 v10 leg，与扩张/高 ER regime 的 Donchian melt leg 互斥路由。

## 数据与执行

- SOLUSDT perpetual `4h`：`4379` 根完整 K，UTC `2024-07-13T08:00:00+00:00` 至 `2026-07-13T00:00:00+00:00`。
- 4h violations：`{'missing_4h_bars': 0, 'duplicate_4h_bars': 0, 'row_count_not_4': 0, 'high_lt_open_close': 0, 'low_gt_open_close': 0, 'nonpositive_ohlc': 0}`。
- fee `0.001`/fill，slippage `4 bps`/fill，逐 bar 计真实 funding。
- 闭合 4h K 决策，下一根 4h open 生效。
- blocker：当前 RS4 是 open-to-open position return 模型，没有交易所驻留的 intrabar protection stop；任何正收益也只能 diagnostic。

## Prefit-only 选中观察

- id：`SOL_4H_RS4_R0343`；score `0.042`。
- train：annual `1.0762x`，DD `-26.08%`，win `43.38%`，trades `136`。
- validation：annual `1.4846x`，DD `-26.58%`，win `52.17%`，trades `69`。
- prefit：annual `1.2045x`，DD `-26.58%`，win `46.34%`，trades `205`。
- reused holdout：annual `0.3496x`，return `-23.04%`，DD `-34.13%`，win `34.69%`，trades `49`。
- fresh forward：return `2.24%`，DD `-4.98%`，trades `3`。
- current full：annual `1.0312x`，DD `-47.97%`，win `43.97%`，trades `257`。

## 标准近期分片（锚定数据集末端，仅审计）

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `last_1d` | `0.0294x` | `-0.96%` | `-1.66%` | `0.00%` | `0` | `0.000` |
| `last_7d` | `0.9710x` | `-0.06%` | `-4.98%` | `0.00%` | `2` | `0.000` |
| `last_1m` | `2.6955x` | `8.49%` | `-7.77%` | `57.14%` | `14` | `1.787` |
| `last_3m` | `0.6978x` | `-8.58%` | `-22.34%` | `39.13%` | `46` | `1.070` |
| `last_6m` | `0.4218x` | `-34.95%` | `-47.97%` | `35.90%` | `78` | `0.734` |
| `last_1y` | `0.9102x` | `-8.97%` | `-47.97%` | `46.58%` | `146` | `1.088` |

## 延迟与成本压力

| Scenario | Prefit ann | Prefit DD | Holdout ann | Fresh return | Full ann | Full DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1_cost1` | `1.2045x` | `-26.58%` | `0.3496x` | `2.24%` | `1.0312x` | `-47.97%` |
| `delay_k2_cost1` | `1.2659x` | `-35.57%` | `0.5257x` | `3.46%` | `1.1430x` | `-48.99%` |
| `base_k1_cost2` | `0.8396x` | `-38.15%` | `0.2024x` | `1.24%` | `0.7013x` | `-59.21%` |

## 研究边界

- 本 family 与 HYPE-RS4、SOL-1H-AR 独立，不继承版本号。
- reused holdout 不参与选择；fresh forward 仅约 10 天。
- 缺少 intrabar protection stop 是 live-executable blocker。
- 首轮不登记版本，不进入 dry-run/live。

## 机器证据

- `artifacts/sol_4h_rs4_search_2026-07-13.json`
- `artifacts/sol_4h_rs4_search_ranking_2026-07-13.csv`
- `artifacts/sol_4h_rs4_search_slices_2026-07-13.csv`
- `artifacts/sol_4h_rs4_search_selected_trades_2026-07-13.csv`
- `artifacts/sol_4h_rs4_input_2026-07-13.parquet`
- `artifacts/sol_4h_rs4_data_quality_2026-07-13.json`

复现：

```bash
uv run python research/sol/4h-rs4-regime-switch/scripts/research_sol_4h_rs4_search.py
```
