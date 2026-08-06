# MU Polygon 15m Regular-Session 接受审计（2026-08-06）

## 结论

Polygon `MU` 15m 数据通过 `exchange-calendars 4.13.2` 的 `XNAS` regular-session
日历、闭合状态、raw/normalized 对齐和 round-trip 审计，已作为
NASDAQ / equity / MU / 15m 的 canonical normalized 数据接受。该结论只改变数据
接受状态，不登记或晋升任何策略版本。

机器审计见
[`mu-polygon-15m-acceptance-2026-08-06.json`](../artifacts/mu-polygon-15m-acceptance-2026-08-06.json)，
复现脚本见
[`accept_mu_polygon_ohlcv.py`](../scripts/accept_mu_polygon_ohlcv.py)。

## 来源与转换

- source dataset：`polygon-mu-15m-adjusted-2025-06-17-2026-06-17`；
- raw 保持 `raw_unaccepted` 和原生 extended-hours 快照，不回写代理字段；
- 以 `XNAS` regular session 过滤，保留 Polygon 原生 `vwap`；
- 原生 `transactions` 逐行无损映射为 `trade_count`；
- `quote_volume` 通过显式 `OHLCVDerivationPolicy` 按
  `close × volume` 生成，保留 `derivation_provenance` 与
  `derived_quote_volume_proxy` 标记；
- `session`、session open/close、`bar_close_ts`、`is_closed`、
  session/closure provenance 一并写入 normalized。

## 实际审计结果

| 项目 | 结果 |
| --- | ---: |
| raw 文件 / 行数 | 270 / 15,951 |
| XNAS regular-session 行数 | 6,490 |
| 过滤的非 regular 行数 | 9,461 |
| sessions | 251 |
| 正常 / 提前收市 sessions | 248 / 3 |
| regular UTC 范围 | 2025-06-17 13:30 → 2026-06-16 19:45 |
| 缺 K / session 外行 | 0 / 0 |
| closure mismatch / open rows | 0 / 0 |
| raw/normalized 缺失键 | 0 / 0 |
| OHLCV、quote volume、trade count、vwap、闭合状态差异 | 全部 0 |
| normalized 日分区 / 行数 | 251 / 6,490 |

normalized 通过同一 trusted loader round-trip 重读；写入采用同文件系统 staging
目录审计完成后一次性目录替换，缺口或对齐失败发生在 commit 前，不会留下
canonical 分区。

## Yahoo 隔离

Yahoo 15m 与 1d 数据继续只存在于 raw，状态保持 `raw_unaccepted`。其缺失
`trade_count` 的问题没有用 `0` 或代理值填充，schema 未放宽，也没有写入
normalized。Polygon 的接受结论不得外推到 Yahoo。

## 使用边界

读取该 equity 数据必须在
`DuckDBWarehouse.load_trusted_ohlcv()` 中显式使用 `xnas_regular` policy。
本次接受允许它作为后续研究输入，但不替任何策略完成超额基线、OOS、稳健性、
执行可行性或 promotion 门禁。
