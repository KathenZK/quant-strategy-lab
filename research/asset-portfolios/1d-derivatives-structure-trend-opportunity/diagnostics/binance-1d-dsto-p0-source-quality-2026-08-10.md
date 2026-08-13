# BIN-1D-DSTO P0 官方 Metrics 源质量诊断

## 结论

原 P0 为 `HARD-GATE-FAILED`，不得按原 [P0/P1 合同](../specs/binance-1d-dsto-p0-p1-contract-2026-08-10.md)运行 full-field P1。

Binance Vision 在 `[2021-12-01, 2025-05-31) UTC` 为五个资产完整列出了 `6,385` 个日包；所有下载文件均通过 S3 ETag/MD5、ZIP CRC 和 SHA256 身份检查。但 ZIP 内容不满足合同要求的完整 `5m` 网格和全字段有限正值，问题来自官方源内容，不是下载损坏。

## 质量结果

| Asset | 缺失 5m 网格点 | 含缺行日 | 含非法值日 | 非法 timestamp 行 | 重复 timestamp |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC | 282 | 34 | 348 | 165 | 2 |
| ETH | 254 | 34 | 347 | 139 | 2 |
| BNB | 285 | 34 | 349 | 163 | 2 |
| SOL | 275 | 36 | 348 | 142 | 3 |
| TRX | 145 | 9 | 350 | 0 | 0 |

字段缺失并非零星噪声：

- `count_toptrader_long_short_ratio`：每资产约 `92,173–92,177` 个非法值；
- `sum_toptrader_long_short_ratio`：每资产约 `92,167–92,168` 个非法值；
- `sum_taker_long_short_vol_ratio`：每资产约 `37,250–37,273` 个非法值；
- `count_long_short_ratio`：每资产约 `5,775–5,777` 个非法值；
- OI/OI value 缺陷较少，但仍存在缺点、重复或错位 timestamp。

典型反例：

- BTC `2021-12-04` 只有 `285/288` 行，缺 `05:00/05:25/05:30 UTC`；
- BTC `2021-12-30 14:35–23:55 UTC` 的 top-account ratio 连续为空；
- BTC `2024-04-04` 出现 `+1s` timestamp 和跨到次日 `00:00` 的行。

## 处置

1. 未做 nearest、round、forward-fill、backfill 或插值。
2. gapful 拼接被标为 unaccepted cache，存放在 `data/cache/binance_1d_dsto_p0_unaccepted/`；已删除此前误写入 `data/features/` 的同内容文件。
3. Binance Vision S3 不存在 `monthly/metrics` 官方归档，无法用同源月包修复日包。
4. 原合同要求六字段全历史和 30 日窗口 `100%` 完整，因此结果必须 fail closed；不得通过降低完整率直接继续。
5. 在不读取收益/label 的情况下另行冻结 [P0R OI + Funding 合同](../specs/binance-1d-dsto-p0r-oi-funding-contract-2026-08-10.md)：只接受精确、唯一、有限正值的 OI 端点，缺陷 anchor 直接删除，并以已审计 funding 补充独立信息。

## 证据

- [P0 data quality JSON](../artifacts/p0_data_2026-08-10/p0_data_quality.json)
- [P0 source manifest](../artifacts/p0_data_2026-08-10/p0_source_manifest.json)
- [P0 manifest](../artifacts/p0_data_2026-08-10/manifest.json)
- [同步与质量审计脚本](../scripts/sync_binance_vision_dsto_metrics.py)
