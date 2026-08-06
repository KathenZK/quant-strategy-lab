# SOX 日线 MA20 零调参替换合同

## 研究问题

把已冻结的 SOX development-selected combined、long-only、short-only 参数中的信号均线从 `SMA7` 替换为 `SMA20`，观察较慢均线是否改善完整历史和跨年代稳定性。

## 冻结边界

- 唯一变化：`SMA7[t] = mean(close[t-6:t])` 改为 `SMA20[t] = mean(close[t-19:t])`。
- `ATR7` 保持不变；所有 entry mode、MA 斜率 ATR 阈值、确认 session、entry/exit buffer、hard/trailing stop、max-hold、cooldown 和多头优先级均保持不变。
- 不用 MA20 结果重新选择参数，不搜索 MA20 专属配置。
- 来源参数与时间角色固定于 [SOX MA7 搜索合同](sox-1d-ma7-asset-specific-search-contract-2026-08-05.md)。

## 数据与执行

- Yahoo Finance `^SOX` raw session OHLC，America/New_York session `1d`。
- 收盘信号下一 session open 执行；open gap 穿越 stop 按 open，日 high/low 触发按 stop。
- 主结果零成本；另审计每 fill `10 bps` 示意摩擦和额外延迟一 session。
- `^SOX` 不可直接交易，结果只属于价格指数路径诊断。

## 审计

- Backward：2010 年前；
- Development：`2010-01-04` 至 `2021-01-04` exclusive；
- Researcher-exposed holdout：2021+；
- Full、逐年、滚动三年与最近 `1d/7d/1m/3m/6m/1y`。

本测试不产生版本登记或 promotion。
