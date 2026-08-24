# MOP 2012 TSMOM 论文原式复刻（2026-08-19）

- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 原式：`12M sign × 40% / sigma`，所有有效市场等权，持有下月
- 明确取消：类别25%、组合层10%目标、portfolio scalar、3x gross cap
- 作者序列为 monthly excess returns；本地连续期货和代理不与其拼接

## 一句话结论

作者原论文文件在 1985–2009 的 CAGR 为 `17.60%`、Sharpe `1.385`；AQR 更新序列在 2010–2026-05 降至 CAGR `4.50%`、Sharpe `0.402`。论文效应仍为正，但论文后明显衰减。
同一公式在24个当前期货代码上的2 bps结果为 CAGR `7.27%`、Sharpe `0.553`；30代理长期表面为 CAGR `8.16%`、Sharpe `0.591`。

## 作者/AQR diversified factor

| 序列 | CAGR | 年化算术收益 | 波动 | Sharpe | MDD | 总收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 作者原论文文件 1985–2009 | 17.60% | 17.08% | 12.33% | 1.385 | -15.23% | 5660.79% |
| AQR 更新口径重建 1985–2009 | 17.39% | 16.84% | 11.93% | 1.411 | -15.15% | 5402.77% |
| AQR 论文后 2010–2026-05 | 4.50% | 5.25% | 13.06% | 0.402 | -27.91% | 105.92% |
| AQR 更新全期 1985–2026-05 | 12.10% | 12.25% | 12.49% | 0.981 | -27.91% | 11231.34% |

## 四资产类别：原论文窗口 vs 论文后

| 类别 | 原论文 CAGR | 原论文 Sharpe | 论文后 CAGR | 论文后 Sharpe |
| --- | ---: | ---: | ---: | ---: |
| Equity indices | 21.24% | 0.827 | -1.24% | 0.089 |
| Currencies | 12.99% | 0.743 | 1.84% | 0.190 |
| Fixed income | 19.22% | 0.743 | 9.46% | 0.454 |
| Commodities | 14.44% | 1.063 | 1.65% | 0.182 |

## 本地论文公式（2 bps/边）

| 表面 | 分支 | CAGR | 波动 | Sharpe | MDD | 净总收益 | 年换手 | 平均gross | 峰值gross |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `24_yahoo_continuous_futures` | `MOP 12M TSMOM` | 7.27% | 15.28% | 0.553 | -28.93% | 37.83% | 18.274 | 4.062 | 5.625 |
| `24_yahoo_continuous_futures` | `Always-long control` | 2.05% | 20.44% | 0.205 | -38.85% | 9.75% | 3.421 | 4.063 | 5.625 |
| `30_etf_fx_proxies` | `MOP 12M TSMOM` | 8.16% | 15.94% | 0.591 | -32.21% | 190.18% | 16.712 | 4.716 | 7.733 |
| `30_etf_fx_proxies` | `Always-long control` | 7.06% | 20.74% | 0.446 | -48.67% | 152.53% | 4.275 | 4.716 | 7.733 |

## 为什么论文式看起来更赚钱

| 表面 | 构造 | CAGR | 波动 | Sharpe | MDD | 平均gross | 峰值gross |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `24_yahoo_continuous_futures` | P0 受控12M | 5.14% | 8.73% | 0.618 | -14.30% | 2.595 | 3.000 |
| `24_yahoo_continuous_futures` | 论文原式 | 7.27% | 15.28% | 0.553 | -28.93% | 4.062 | 5.625 |
| `30_etf_fx_proxies` | P0 受控12M | 4.75% | 7.39% | 0.666 | -16.56% | 2.839 | 3.000 |
| `30_etf_fx_proxies` | 论文原式 | 8.16% | 15.94% | 0.591 | -32.21% | 4.716 | 7.733 |

论文原式提高了绝对收益，但同时取消3倍帽并把平均gross推到约4–5倍；两个本地表面的 Sharpe 都低于对应的P0受控12M，MDD约扩大一倍。因此收益提升主要来自更高风险预算，不是更强的当代预测能力。

## 重要审计发现

AQR 更新文件会重建全部历史。更新口径与作者原始文件在共同300个月的 diversified 月收益相关性为 `0.974`，平均绝对月差为 `0.50%`。因此论文原始结论以 original workbook 为准，更新文件只用于论文后稳定性。

本地24市场缺少论文的58市场广度及逐合约/远期 excess-return 构造；Yahoo 连续代码也没有官方 roll mapping。30代理包含ETF费用、分红与商品基金roll结构。两套本地结果只能回答公式在可得表面的表现，不能称为相同数据复刻。

## 证据

- [冻结契约](../specs/tf-1d-fut-tsmom-paper-exact-p1-contract-2026-08-19.md)
- [作者/AQR 指标](../artifacts/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19-published-factor-metrics.csv)
- [本地同式指标](../artifacts/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19-local-metrics.csv)
- [配置与审计摘要](../artifacts/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19-summary.json)
- [SHA256 清单](../artifacts/tf-1d-fut-tsmom-paper-exact-p1-2026-08-19-checksums.sha256)
