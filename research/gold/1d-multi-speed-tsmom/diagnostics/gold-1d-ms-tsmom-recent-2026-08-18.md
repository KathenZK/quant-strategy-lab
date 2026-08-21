# 黄金多速度 TSMOM 2022–2026 近期扩展（2026-08-18）

- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 独立近期窗口：`2021-12-01` → `2026-07-31`，约 `4.66` 年
- 数据：Yahoo Chart API `GC=F` raw quote OHLC；未使用 adjusted close
- 预热：2020-01 起；2021-11 月末信号从下一交易日开始作用于扩展窗口
- 成本：0 bps 对照 + 2 bps 单边目标仓位换手；Buy&Hold 仅首次建仓收费

## 结论

Composite 含成本总收益 `43.08%`、CAGR `7.99%`、Sharpe `0.866`、最大回撤 `-12.54%`。
同期 Buy&Hold 总收益 `127.23%`、CAGR `19.25%`、Sharpe `1.028`、最大回撤 `-25.06%`。

## 含 2 bps 成本结果

| 分支 | CAGR | 年化收益 | 年化波动 | Sharpe | Sortino | 最大回撤 | Calmar | 日胜率 | 正收益月 | 年换手 | 毛收益 | 净收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1M` | 5.29% | 5.77% | 10.90% | 0.529 | 0.730 | -16.79% | 0.315 | 51.54% | 62.50% | 6.24 | 27.94% | 27.19% |
| `3M` | 11.57% | 11.57% | 10.88% | 1.063 | 1.498 | -9.69% | 1.194 | 54.18% | 62.50% | 3.12 | 67.11% | 66.62% |
| `12M` | 6.70% | 7.09% | 10.90% | 0.651 | 0.903 | -25.56% | 0.262 | 52.82% | 57.14% | 2.52 | 35.61% | 35.29% |
| `Composite` | 7.99% | 8.15% | 9.41% | 0.866 | 1.202 | -12.54% | 0.637 | 52.39% | 57.14% | 3.80 | 43.59% | 43.08% |
| `Buy&Hold` | 19.25% | 19.46% | 18.93% | 1.028 | 1.430 | -25.06% | 0.768 | 54.69% | 58.93% | 0.21 | 127.27% | 127.23% |

## 解释边界

该段使用另一供应商的独立序列，不与 1985–2021 Stooq 路径硬拼。Yahoo 未披露连续合约换月映射，且 quote close 未获官方结算价逐日核验，因此仍为 `raw_unaccepted`。本结果用于观察近年形态，不能把两个供应商的分段收益直接连乘成一条正式全历史净值。

## 证据与复现

- 数据审计：[../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-data-audit.json](../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-data-audit.json)
- 完整 0/2 bps 指标：[../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-metrics.csv](../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-metrics.csv)
- 日路径：[../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-daily-paths.csv](../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-daily-paths.csv)
- 交互图：[../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-interactive.html](../artifacts/gold-1d-ms-tsmom-recent-extension-2026-08-18-interactive.html)

```bash
.venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/fetch_gold_gc_yahoo_recent.py --run-date 2026-08-18
.venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/research_gold_1d_multi_speed_tsmom_recent.py --run-date 2026-08-18 --allow-untrusted
.venv/bin/python research/gold/1d-multi-speed-tsmom/scripts/render_gold_1d_multi_speed_tsmom.py --run-date 2026-08-18 --artifact-kind recent-extension
```
