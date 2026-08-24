# Artifacts

本目录保留沪深 300 日 K与 `HYPE-1D-MA7-ABT-V7.1` 四年零调参迁移的可复现证据。

## 数据证据

- [东方财富原始响应](csi300_eastmoney_1d_raw_2026-08-17.json)及其 [SHA256](csi300_eastmoney_1d_raw_2026-08-17.json.sha256)：`secid=1.000300 / klt=101 / fqt=0`，含 warmup。
- [东方财富解析日 K](csi300_eastmoney_1d_2026-08-17.csv)：`2022-04-19` 至 `2026-08-17`，1,051 个 session。
- [Yahoo 交叉核验原始响应](csi300_yahoo_1d_crosscheck_2026-08-17.json)及其 [SHA256](csi300_yahoo_1d_crosscheck_2026-08-17.json.sha256)：只用于来源差异检查，不参与回测。

## 回测证据

- [机器结果](csi300_1d_hype_ma7_v7_1_transfer_2026-08-17.json)及其 [SHA256](csi300_1d_hype_ma7_v7_1_transfer_2026-08-17.json.sha256)：full、成本、延迟、单腿、买持、近期切片、年度切片与数据质量。
- [逐笔交易](csi300_1d_hype_ma7_v7_1_trades_2026-08-17.csv)：零成本主路径 56 笔闭合交易。
- [日路径](csi300_1d_hype_ma7_v7_1_path_2026-08-17.csv)：969 个研究 session 的 OHLC、指标、仓位、事件与 close equity。

本轮未登记版本，且用户未要求图表，因此不生成交互式 HTML。
