# NDX100-1D-MA7-RC-Y1 Yahoo 历史成分覆盖审计

## 结论

历史退出成分已经纳入抓取和 point-in-time 映射，但 Yahoo 不能完整支持这项历史研究。`252` 个历史 membership ticker 均已请求；在末端 `100` 个成分之外的 `152` 个历史退出 ticker 中，`90` 个原代码有成分期直接价格，另有 `5` 个可通过冻结的同实体改名链获得至少部分覆盖。

完整 membership 共 `429,268` 个 member stock-days。直接命中 `341,151`，唯一实体 lineage fallback 补入 `7,311`，合计 `348,462`，覆盖率 `81.1759%`；仍缺 `80,806`（`18.8241%`）。这低于 Y1 在看结果前冻结的 `99.5%` 门槛，因此 `MA7 → regime → forward expectancy` 统计未运行，不能用这批部分样本更新 Y0 或跨市场结论。

状态：`BLOCKED_INCOMPLETE_YAHOO_HISTORY / diagnostic-only / not promoted / not live-ready`。

## 已完成范围

- 复用 P0 的 `2010-01-04–2026-08-21` point-in-time membership：`4,184` sessions、`252` tickers、`247` entities。
- 请求全部历史 ticker 与 QQQ 的 `2008-01-01–2026-08-21` Yahoo 日线；没有发生全局限流或整批拒绝。
- 取得 `199/252` 个股票 ticker 的某段可用序列；原始股票与 QQQ 合计 `752,428` 行。
- 对 membership ticker/date 先做原代码直接映射；仅当同一冻结 `entity_key` 当天恰有一个其他代码可用时才 fallback。
- 保存逐 member-day 映射、按 ticker/年份覆盖、fallback 明细、缺失明细、阻塞 JSON 和 hash manifest。

## 不能静默忽略的缺口

Yahoo 对 `53` 个历史 ticker 没有返回任何可用日线，包括 `ATVI`、`XLNX`、`CERN`、`CTXS`、`MXIM`、`ALXN`、`MYL`、`CELG`、`YHOO` 等。另有一些当前可请求的代码只对应新上市或复用后的证券，和旧 Nasdaq-100 membership 日期不重叠，例如 `BBBY`、`SPLS`、`DELL`；`EA`、`SNDK` 等则只覆盖极短的新序列或旧成分期的一小部分。

按缺失 member stock-days 最大的前十项为：`EA 3,667`、`ATVI 3,405`、`XLNX 3,055`、`CERN 3,012`、`CTXS 2,761`、`MXIM 2,681`、`ALXN 2,591`、`MYL 2,510`、`NLOK 2,510`、`CELG 2,489`。

这些缺口集中于被收购、退市、改名和代码复用证券，并非随机缺失。若直接在剩余 `81.18%` 上运行事件研究，会重新引入 survivorship/identifier bias，所以不能把“抓取没有整体被拒绝”解释成“历史数据已经完整”。

## 冻结裁决

- 保留已经补入的历史退出股票数据与可复现映射，不退回当前成分回填。
- 不生成 Y1 event、quintile、组合 regime、gap、robustness 或 Crypto 对照结果。
- Y0 结论保持不变：它仍是当前成分回填快速诊断，不是 point-in-time 证据。
- 要解除阻塞，需为缺失的 `80,806` member stock-days 接入可审计的历史/退市证券数据，并重新通过 `99.5%` 覆盖门槛；不得针对回测结果选择补数对象。

## 复现

```bash
.venv/bin/python research/us-indexes/1d-nasdaq100-ma7-regime-continuation/scripts/fetch_yahoo_historical_ndx100_daily.py
.venv/bin/python research/us-indexes/1d-nasdaq100-ma7-regime-continuation/scripts/audit_yahoo_historical_ndx100_coverage.py
.venv/bin/pytest -q tests/test_ndx100_1d_ma7_regime_continuation.py
```

冻结合同：[`../specs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-contract-2026-08-25.md`](../specs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-contract-2026-08-25.md)。机器摘要：`../artifacts/ndx100_1d_ma7_rc_y1_coverage_audit.json`。
