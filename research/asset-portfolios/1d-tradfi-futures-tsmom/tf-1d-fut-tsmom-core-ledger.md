# TF-1D-FUT-TSMOM Core Ledger

## Family Identity

- Full name：`TradFi-1D-Multi-Asset-Futures-TSMOM`
- Alias：`TF-1D-FUT-TSMOM`
- 防串线：独立于黄金单标的、Binance TSMOM 与传统资产 EWMAC 代理研究
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`

## Current Observation

| Observation | Status | Contract | Decision |
| --- | --- | --- | --- |
| `P0-2026-08-18` | completed / diagnostic-only | [P0 契约](specs/tf-1d-fut-tsmom-p0-contract-2026-08-18.md) | 24 市场固定池完成；12M 显著强于 1M/3M/Composite，但数据未达期货晋级标准 |
| `Proxy-Validation-2026-08-18` | completed / secondary diagnostic | [长期代理报告](diagnostics/tf-1d-fut-tsmom-proxy-validation-2026-08-18.md) | 30 个 ETF/FX 代理约 13.57 年；12M 结论延续，但不得冒充期货证据 |
| `Paper-Exact-P1-2026-08-19` | completed / diagnostic-only | [论文原式报告](diagnostics/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19.md) | 作者原论文期强、2010年后明显衰减；本地原式主要以更高gross换取绝对收益，不晋级 |

## Fixed Boundary

- 四大类各 `25%` raw risk budget，类内等权。
- `1M/3M/12M` 与等权 Composite 四个固定分支；Long-only risk parity 是基准。
- 单市场与组合层均用 `60-day COM EWMA`；组合目标年化波动 `10%`。
- 月末确定下一月目标，单边 `0/2 bps`；不单列供应商未披露的 roll cost。
- Paper-Exact P1 是单独观察：`12M × 40%/sigma × 全市场等权`，不使用类别权重、组合
  波动目标或 gross cap；不得与 P0 风险受控结果混写。

## Evidence

- [决策日志](decision-log.md)
- [24 市场期货 P0 报告](diagnostics/tf-1d-fut-tsmom-p0-2026-08-18.md)
- [长期代理验证报告](diagnostics/tf-1d-fut-tsmom-proxy-validation-2026-08-18.md)
- [固定规则研究结论](diagnostics/tf-1d-fut-tsmom-research-conclusion-2026-08-18.md)
- [MOP 2012 论文原式复刻](diagnostics/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19.md)
- [Artifacts](artifacts/README.md)
- [Scripts](scripts/README.md)

## Result Snapshot

按 `2 bps/边`：

| 表面 | 分支 | CAGR | Sharpe | MDD | 净总收益 | 年换手 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 24 连续代码，2022-01–2026-07 | `12M` | 5.14% | 0.618 | -14.30% | 25.73% | 11.960x |
| 24 连续代码，2022-01–2026-07 | `Composite` | 2.25% | 0.286 | -19.18% | 10.70% | 22.853x |
| 24 连续代码，2022-01–2026-07 | `Long-only RP` | 0.96% | 0.145 | -22.57% | 4.46% | 2.484x |
| 30 代理，2013-01–2026-07 | `12M` | 4.75% | 0.666 | -16.56% | 87.75% | 9.285x |
| 30 代理，2013-01–2026-07 | `Composite` | 3.82% | 0.506 | -14.45% | 66.29% | 24.476x |
| 30 代理，2013-01–2026-07 | `Long-only RP` | 4.09% | 0.504 | -20.96% | 72.29% | 2.357x |

## Decision

- 固定规则中只有 `12M` 在两个表面都形成一致的正收益和更高 Sharpe；`1M` 为负，`3M`
  较弱，等权 Composite 因引入短周期而降低质量并显著增加换手。
- 组合的主要经济价值是危机/通胀冲击期的方向切换与跨类别分散，不是长期绝对收益碾压：
  代理表面 Composite 的 Sharpe 与 Long-only RP 基本相同，CAGR 还略低。
- 不登记版本、不晋级实盘。下一步若继续，应先取得官方结算价、逐合约映射、实际换月日与
  roll/slippage 账本，再对原样 `12M` 做独立复核；不得在已揭示历史上重新调权重或删市场。
- 优先升级源为 [CME Group Continuous Price Series](https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html)
  的 Active/Front 官方结算序列与 next roll date；取得授权后可通过
  [DataMine API](https://www.cmegroup.com/datamine/datamine-api.html) 固化原始文件、文件 ID 和哈希。
- Paper-Exact P1 不改变上述裁决：作者原始1985–2009因子强，但AQR更新序列2010年后衰减；
  当代本地公式的高绝对收益伴随约4–5倍平均gross和更差回撤，不能据此恢复晋级。
