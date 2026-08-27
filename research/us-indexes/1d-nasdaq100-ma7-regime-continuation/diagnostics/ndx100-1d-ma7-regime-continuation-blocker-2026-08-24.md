# NDX100-1D-MA7-RC-P0 数据访问阻塞报告

日期：2026-08-24  
状态：`explore / diagnostic-only / not promoted / not live-ready`

## 结论

P0 研究合同、historical Nasdaq-100 point-in-time membership、Massive 接口、标识审计、事件统计、robustness、gap 诊断与 cross-market adapter 均已实现。用户提供的 legacy Polygon / Massive key 可以认证，ticker details、当前日线和 ticker events 检查通过；但 `2010-01-04` 历史日线 anchor 不可用，MU `2010-01-01–2026-08-21` 请求只返回最近 `499` 根（`2024-08-26–2026-08-21`）。因此 historical P0 仍被历史深度 entitlement 阻塞。

仓库中也没有既有 Massive/Polygon credential 环境变量引用、`.env` 接入或客户端依赖。新接口只使用 Python 标准库发出 REST 请求，避免为当前阻塞额外改变共享依赖；key 永不写入 URL 日志或产物。

这不是结构失败或 `NO-GO`；它是明确的 `BLOCKED_DATA_ACCESS`。不得从 Binance 结果、membership 本身或合成测试推断股票市场结论。

## 已完成的证据

- 成分重建：4,184 sessions、252 historical tickers、247 entity lineages；末端 current snapshot match，integrity finding `0`。
- 变更来源：研究期 200 条变更，补证后为 `142 primary_official / 58 secondary_cited / 0 uncited_secondary_index`；7 条 source augmentation 不改成分事件，3 条手工公司行动修正均有外部来源。
- 代码：Massive adjusted aggregate、interval details、ticker-events、FIGI reuse/rename audit、XNAS OHLCV audit、连续 session fail-closed、三类 regime、双向聚类、BH-FDR、robustness、gap、cross-market wide table。
- 验证：专用单测覆盖 config hash、成分公司行动、rolling percentile、股票特征/gap、same-symbol generation、对称事件收益、聚类/BH 和 wide table。

## 未执行与禁止声明

- 未确认 Massive 套餐是否允许 2010 起历史 aggregates、delisted ticker details 和 experimental ticker-events。
- 未生成 `events.parquet`、regime edges 或任何 Nasdaq-100 统计 CSV。
- 未生成四列市场/方向 cross-market 对照；Binance 单变量和三变量产物当前已存在，但必须等待股票端通过，不能单边填表。
- 不使用 Yahoo、Stooq、当前 QQQ holdings 或当前 Nasdaq-100 list 代替。

## 恢复方法

升级到覆盖 2010 年的 Massive 历史套餐后，把 key 只注入运行进程的 `MASSIVE_API_KEY`（兼容 legacy `POLYGON_API_KEY`，但优先前者），不要写入仓库。然后依次运行：

```bash
.venv/bin/python research/us-indexes/1d-nasdaq100-ma7-regime-continuation/scripts/research_ndx100_1d_ma7_regime_continuation.py --check-access
.venv/bin/python research/us-indexes/1d-nasdaq100-ma7-regime-continuation/scripts/research_ndx100_1d_ma7_regime_continuation.py --run
```

任何 entitlement、FIGI lineage、duplicate key、OHLCV 或 XNAS session blocker 都会停止统计，不会生成部分结果冒充完整 P0。

机器阻塞记录：[`../artifacts/ndx100_1d_ma7_rc_p0_data_access_blocker.json`](../artifacts/ndx100_1d_ma7_rc_p0_data_access_blocker.json)
