# HYPE-1D-MA7-ABT-V1 前瞻观察 #1（2026-08-06）

- 协议：[前瞻观察协议](../specs/hype-1d-ma7-abt-v1-prospective-observation-protocol-2026-08-06.md)（先冻结协议、后跑策略）。
- 市场：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`（`1h` 聚合）；费用 `0.001/fill`、基准滑点 `4 bps`（压力 `8 bps`）、事件级实际 funding。
- 观察窗：`2026-07-30 00:00` → `2026-08-06 00:00 UTC`（7 个完整日）；本窗即最近分片，仅作审计，不用于任何选择。

## 结论

- **观察窗净收益 `-1.69%`（压力 `8 bps` 为 `-1.72%`）**；同窗买入持有毛收益 `+5.63%`。
- 窗口起点继承一笔冻结前的空头（`2026-07-17` 入场 `60.721`），`2026-08-05` open `55.059` 以 `ma7_hysteresis_exit` 平仓，整笔 `+9.25%`；但该笔在观察窗内的部分为逆势亏损。
- 无新开仓信号；窗内结算 42 个 funding 事件；无数据洞、无执行异常。
- 累计观察台账（自协议起）：`7` 天 / `1` 笔平仓 / `-1.69%`。距离协议判定样本（`>=90` 天且 `>=5` 笔）尚远，不触发任何状态变化。

## 锚点复算校验

把小时与 funding 数据截断回冻结湖终点（`ts <= 2026-07-30 04:00 UTC`）后全期复算，与登记冻结值逐位一致（`equity_multiple 3.931956090669248`、MDD `-26.44335969228703%`、13 笔），校验通过；本报告有效。

## 数据补充

- [同步脚本](../scripts/sync_hype_1h_funding_prospective.py)经 fapi 抓取新增 `171` 根 `1h` K 线（至 `2026-08-06 07:00 UTC`）与 `43` 个 funding 事件，共享内核审计零 blocker：[sync 证据](../artifacts/hype_1h_prospective_sync_2026-08-06.json)。
- 全期重放参考（432 日，仅锚点/累计对照用）：base `+286.99%`、MDD `-26.44%`、13 笔；压力 `8 bps` `+283.11%`。

## 证据

- [观察脚手架](../scripts/observe_hype_1d_ma7_abt_v1_prospective.py)
- [机器摘要](../artifacts/hype_1d_v1_prospective_obs_2026-08-06_summary.json) · [窗内路径](../artifacts/hype_1d_v1_prospective_obs_2026-08-06_path.csv) · [窗内成交](../artifacts/hype_1d_v1_prospective_obs_2026-08-06_trades.csv)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
