# Binance HYPEUSDT 永续 1h 数据质量 - 2026-07-02

## 结论

`PASS`。截至 Binance server time `2026-07-02 03:40:55.224 UTC`，可用于研究的最后一根闭合 `1h` K 为 `2026-07-02 02:00 UTC`。

| Check | Result |
| --- | ---: |
| Raw rows / closed raw rows | `9,546 / 9,545` |
| Closed normalized rows | `9,545` |
| Expected rows | `9,545` |
| First / last | `2025-05-30 10:00 UTC` / `2026-07-02 02:00 UTC` |
| Missing | `0` |
| Raw duplicate / normalized duplicate | `0 / 0` |
| Critical nulls | `0` |
| OHLCV violations | `0` |
| Normalized bars not closed at server cutoff | `0` |
| Raw rows incorrectly flagged closed at/after cutoff | `0` |
| Raw/normalized field mismatches | `0` |
| Zero-volume bars | `0` |
| Raw / normalized partitions | `399 / 399` |
| Funding rows | `2,385` |
| Funding max gap | `8h` |
| Blockers | `0` |

合约快照：`TRADING` perpetual，tick `0.001`、quantity step `0.01`、market min qty `0.01`、min notional `5 USDT`、percent-price band `0.85x-1.15x`。

## 闭合 K 防未来函数修复

本轮最终验收发现旧实现用 `datetime.astype("int64") // 1_000_000` 与毫秒 cutoff 比较。Pandas 对 `datetime64[ms]` 保留毫秒整数单位时，这会再次错误缩放，可能把运行中的小时 K 标成 closed。修复后直接比较 UTC datetime，不再依赖底层整数单位；无 `--refresh` 读取已有 raw 分区时也会按当次 Binance server time 重新计算 `is_closed` 并重新归一化。

新增两项 data-quality blocker：`normalized_bar_not_closed_at_cutoff` 与 `raw_closed_flag_at_or_after_cutoff`。专门回归测试覆盖 `02:57` 时 `01:00` K 已闭合、`02:00` K 未闭合的毫秒 dtype 场景。修复后重新抓取并重跑 V1、V2、消融、前沿压力和 `640,000` 组扩大搜索；最终策略指标未因末根临时价格改变。

复现：

```bash
uv run python research/hype/1h-adaptive-regime/scripts/fetch_hype_binance_1h.py --refresh
```

机器证据：`artifacts/hype_binance_1h_data_quality.json`。任何 missing、duplicate、关键空值、OHLCV 违规、raw/normalized mismatch、非闭合 K 或未知来源都必须 fail closed。
