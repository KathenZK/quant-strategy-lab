# TRX-1H-Adaptive-Regime 近期适配搜索 - 2026-07-03

## 结论

本轮近期适配搜索没有找到可 promotion 版本。

- 数据：Binance USD-M Futures `TRXUSDT` perpetual `1h`，`17520` 根；missing/duplicate/critical null/OHLC violation 均为 `0`。
- 搜索：生成 unique configs `80800`，可评估/保留 `42905/600`，ensemble `1225`，recent hard hits `0`。
- 近期 hard gate：`1y annual>=10x / DD<20% / win>=50% / trades>=24`，且 `6m/3m` 正收益、DD<20%、win>=50%，`1m` 非负且至少 2 笔。

## 最佳近期观察值

- id：`ENS_REC__TRX_1H_AR_REC_N011284__TRX_1H_AR_REC_N031489`；kind/style：`ensemble` / `momentum_break+wick_reject`。
- recent hard pass：`False`；score：`17.723`。

| Window | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `1.000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `1.496x` / `3.37%` / `-1.40%` / `100.00%` / `2` |
| `last_3m` | `2.251x` / `22.40%` / `-4.14%` / `100.00%` / `9` |
| `last_6m` | `2.735x` / `64.65%` / `-4.14%` / `100.00%` / `17` |
| `last_1y` | `2.227x` / `122.58%` / `-10.67%` / `79.49%` / `39` |
| `full` | `2.813x` / `595.71%` / `-18.35%` / `69.32%` / `88` |

## 标准分片

| Slice | UTC Start | Annual / Return / DD / Win / Trades |
| --- | --- | --- |
| `last_1d` | `2026-07-02 06:00:00+00:00` | `1.000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `2026-06-26 06:00:00+00:00` | `1.000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `2026-06-03 06:00:00+00:00` | `1.496x` / `3.37%` / `-1.40%` / `100.00%` / `2` |
| `last_3m` | `2026-04-03 06:00:00+00:00` | `2.251x` / `22.40%` / `-4.14%` / `100.00%` / `9` |
| `last_6m` | `2026-01-03 06:00:00+00:00` | `2.735x` / `64.65%` / `-4.14%` / `100.00%` / `17` |
| `last_1y` | `2025-07-03 06:00:00+00:00` | `2.227x` / `122.58%` / `-10.67%` / `79.49%` / `39` |

## 曝光缩放边界

| Fixed leverage | 1y annual / return / DD / win / trades | Full annual / return / DD / trades | Pass |
| ---: | --- | --- | --- |
| `2.5x` | `2.227x` / `122.58%` / `-10.67%` / `79.49%` / `39` | `2.813x` / `595.71%` / `-18.35%` / `88` | `False` |
| `3.0x` | `2.598x` / `159.66%` / `-12.73%` / `79.49%` / `39` | `3.408x` / `896.78%` / `-21.81%` / `88` | `False` |
| `3.5x` | `3.026x` / `202.33%` / `-14.77%` / `79.49%` / `39` | `4.108x` / `1315.48%` / `-25.20%` / `88` | `False` |
| `4.0x` | `3.517x` / `251.36%` / `-16.79%` / `79.49%` / `39` | `4.930x` / `1892.66%` / `-28.52%` / `88` | `False` |
| `4.5x` | `4.080x` / `307.57%` / `-18.78%` / `79.49%` / `39` | `5.890x` / `2681.36%` / `-31.76%` / `88` | `False` |
| `5.0x` | `4.724x` / `371.90%` / `-20.74%` / `79.49%` / `39` | `7.005x` / `3749.92%` / `-34.93%` / `88` | `False` |

## 执行可行性复核

- 逐笔重放违规：`0`；merged 违规：`0`。
- stop gap/open 按 open 成交：`0` 次。
- target gap 以 target 价记账：`0` 次。
- 该搜索直接使用已解锁近期行情做适配排序，不能声称是新鲜 OOS；若要 promotion，必须冻结参数后等待新增 forward trades。

## 机器证据

- `artifacts/trx_1h_ar_recent_adaptation_search_2026-07-03.json`
- `artifacts/trx_1h_ar_recent_adaptation_ranking_2026-07-03.csv`
- `artifacts/trx_1h_ar_recent_adaptation_slices_2026-07-03.csv`
- `artifacts/trx_1h_ar_recent_adaptation_top_trades_2026-07-03.csv`
- `artifacts/trx_1h_ar_recent_adaptation_trade_audit_2026-07-03.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_recent_adaptation_search.py
```
