# 美股指数日线 MA7 共享参数零调参迁移合同

## 研究问题

把 BTC/ETH 日线 MA7 搜索中冻结的共享多空参数原样迁移到：

- Yahoo `^GSPC`：S&P 500 price index；
- Yahoo `^IXIC`：Nasdaq Composite price index。

不使用任何美股指数结果调整参数。

## 参数与执行

- 指标：session 日线 `SMA7/ATR7`。
- Long：BTC/ETH 共享 `reclaim` 参数。
- Short：BTC/ETH 共享 `pullback_reclaim` 参数。
- 完整配置固定于[来源机器摘要](../../../asset-portfolios/1d-ma7-asset-specific-search/artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)。
- 收盘信号下一 regular session open 执行；单仓、约 `1x`、非加仓。
- open gap 穿越 stop 时按 open；session high/low 触发时按 stop。
- 两个指数只有日线，无法恢复 session 内 high/low 先后顺序。

## 数据

- Yahoo Finance chart API，America/New_York regular-session 日线。
- 共同研究起点固定为 `1994-05-04`，结束于 `2026-08-04` terminal session。
- 检查时间戳、重复、关键空值、OHLC、交易日完整性和 close/adjusted-close 差异。
- 原始响应与标准化 CSV 分别保留在本家族 `artifacts/`。

## 成本与工具边界

- `^GSPC` 和 `^IXIC` 都是不可直接交易的价格指数。
- 主结果为零手续费、零滑点、零借券、零融资且不含分红的路径诊断。
- 另给每 fill `10 bps` 示意摩擦与额外延迟一 session。
- 结果不得静默解释为 SPY、QQQ、期货或其他代理的可执行收益。

## 固定审计

- `1994-05-04` 至 2010 年前；
- 2010–2020；
- 2021+；
- full；
- combined、long-only、short-only；
- 逐年、滚动三年、最近 `1d/7d/1m/3m/6m/1y`。

全部窗口只用于零调参 audit，不参与选择；本测试不产生版本登记或 promotion。
