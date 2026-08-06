# SOX-1D-MA7 V1 零调参迁移合同

## 身份

- 研究线：`SOX-1D-MA7-Separated-Trend-Transfer`
- 来源版本：[`HYPE-1D-MA7-Asymmetric-Body-Trend-V1`](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-v1-spec.md)
- 目标序列：Yahoo Finance `^SOX`，PHLX Semiconductor price index
- 周期：America/New_York 交易所 session 日线
- 状态：`explore / not promoted / not live-ready`
- 选择：SOX 历史零调参；不改 SMA、ATR、入场、退出、保护或冷却参数。

## 数据合同

- 来源：Yahoo Finance chart API，symbol `^SOX`、interval `1d`。
- 范围：`1994-05-04` 至 `2026-08-04`，`8,117` 个交易日。
- 字段：session date、UTC session-open timestamp、OHLC、volume、adjusted close。
- 主回测统一使用 raw OHLC；Yahoo adjusted close 与 close 的最大差异约 `4.84 bps`，不混用 adjusted close 与未调整 high/low。
- 交易日完整性按美国股票市场常规假日与已知全日特别休市检查。

## V1 参数

多头：下方 reclaim SMA7 后、`SMA7` 一日斜率至少 `0.02*ATR7`，次 session open 入场；收盘跌破 `SMA7-0.75*ATR7` 次开退出；`1.5*ATR7` trailing、最长 `90` 个 session、冷却 `2` 个 session、无首日 hard stop。

空头：上方下穿至 `SMA7-0.10*ATR7` 以下且两日 SMA7 下降至少 `0.02*ATR7`，次 session open 入场；收盘高于 `SMA7+0.25*ATR7` 或 SMA7 一日不再下降时次开退出；`1.5*ATR7` hard stop、`4.0*ATR7` trailing、最长 `20` 个 session、冷却 `5` 个 session。

多空信号同时满足时多头优先；日开先退出后入场；单仓、固定约 `1x`、非加仓。

## SOX 成交解释

- `^SOX` 不是可直接交易工具，用户没有指定 ETF/期货代理或交易成本。
- 主结果使用零手续费、零滑点、零借券费、零融资费；只能视为价格路径 diagnostic。
- 另给每次成交 `10 bps` 的示意摩擦敏感性，但不宣称它是 SOX 的可执行成本模型。
- Yahoo 全历史只有日线：session open 跳空穿越 stop 时按 open，session high/low 触发时按 stop；无法恢复 session 内 high/low 的先后顺序。
- phase test 无法由交易所 session 日线构造；缺失不能记为通过。

## 冻结审计

- 全历史：`1994-05-04` 至 `2026-08-04` terminal open。
- HYPE 日历重叠：首个可交易日 `2025-06-02` 至 `2026-07-30` terminal open。
- 消融：combined、long-only、short-only。
- 压力：每 fill `10 bps` 示意摩擦、信号额外延迟一个交易 session。
- 稳定性：最近 `1d/7d/1m/3m/6m/1y`、逐年窗口、滚动三年窗口。
- 所有切片只用于 audit，不用于选参数。
