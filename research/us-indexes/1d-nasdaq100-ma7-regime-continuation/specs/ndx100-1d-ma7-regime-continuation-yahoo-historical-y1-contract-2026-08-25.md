# NDX100-1D-MA7-RC-Y1 Yahoo 历史成分诊断合同

## 身份

- Observation：`NDX100-1D-MA7-RC-Y1`。
- Universe：复用 P0 已冻结的 historical point-in-time Nasdaq-100 membership，包含 `252` 个历史 ticker、`247` 个 entity，不做当前成分回填。
- Provider：Yahoo Finance chart endpoint；这是独立诊断，不覆盖 Massive P0。
- 状态：`explore / diagnostic-only / Yahoo-identifier-risk / not promoted / not live-ready`。

## 数据与映射

- 拉取 `2008-01-01–2026-08-21` 的 split-only 日线，为 2010 年起的 RV252 提供 warm-up。
- 主价格由 raw OHLC 和 Yahoo split events 重建，分红不进入 forward return。
- 每个历史 membership ticker 都先直接请求；退市 ticker 返回的原历史保留。
- 若 membership ticker 某日无价格，只允许使用同一冻结 `entity_key` 的其他 lineage ticker 在该日的唯一可用序列，并逐行记录 source ticker；不允许跨 entity 猜测或按结果选择。
- 同一 ticker 被不同 entity 复用时，以冻结 membership date/entity 映射分代；连续 feature 不跨 Yahoo 内部缺口。
- 任何缺失 member stock-day 均保持缺失；总体覆盖低于 `99.5%` 时不允许生成结论。

## 研究冻结

MA7 trigger、Slope/ER/RV、quintile、1/3/5/10/20/40-session forward return、gap 和 MA5/7/10 robustness 全部继承 P0，禁止调参。结果必须同时报告 Yahoo 请求失败、无数据 ticker、lineage fallback、member stock-day 覆盖和 temporal stability。

机器配置：[`../configs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1.json`](../configs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1.json)。
