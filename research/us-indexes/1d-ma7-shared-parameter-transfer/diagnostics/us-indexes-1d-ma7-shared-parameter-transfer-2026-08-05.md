# 标普与纳指日线 MA7 BTC/ETH 共享参数迁移诊断

## 结论

BTC/ETH 共享 `SMA7/ATR7` 参数零调参迁移到美股价格指数后：

- S&P 500 combined 全历史 `+18.77%`、MDD `-41.43%`，约 32 年年化仅 `0.53%`；
- Nasdaq Composite combined 全历史 `+91.43%`、MDD `-52.06%`，年化约 `2.03%`；
- 每 fill 加示意 `10 bps` 后，两者分别变为 `-48.26%/-12.38%`；
- 同期 price-index buy-and-hold 分别为 `+1,584.31%/+3,428.37%`；
- 两个指数的 long-only 都为正，short-only 都长期亏损。

Nasdaq 明显比 S&P 500 更适合这组参数，但两者均未形成可接受的长期绝对、成本后或超额收益。保持 `explore / not promoted / not live-ready`，不登记。

## 数据与合同

- Yahoo `^GSPC` 和 `^IXIC` raw session OHLC，各 `8,117` 行，`1994-05-04` 至 `2026-08-04`。
- 两份数据的时间戳、重复、关键空值、OHLC 和交易日检查 blocker 均为 `0`；adjusted close 与 close 最大差异为 `0 bps`。
- 两者都是不可直接交易的 price index；主结果为零手续费、零滑点、零借券、零融资且不含分红的路径诊断。
- 参数完全来自 BTC/ETH 共享选择，没有使用美股指数历史调参。
- 收盘信号下一 session open 执行；只有日 OHLC，无法恢复 session 内 high/low 先后。
- 完整冻结条件见[迁移合同](../specs/us-indexes-1d-ma7-shared-parameter-transfer-contract-2026-08-05.md)。

## 全历史

| Index / variant | 净收益 | 年化因子 | MDD | Sharpe | PF | Trades | Exposure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| S&P combined | `+18.77%` | `1.0053` | `-41.43%` | `0.10` | `1.04` | `415` | `43.64%` |
| S&P + `10 bps/fill` | `-48.26%` | — | `-61.27%` | — | — | `415` | — |
| S&P + 1 session lag | `+0.65%` | — | `-45.51%` | — | — | `410` | — |
| S&P long-only | `+59.86%` | `1.0147` | `-34.83%` | `0.24` | `1.28` | `178` | `27.56%` |
| S&P short-only | `-34.30%` | `0.9871` | `-47.38%` | `-0.09` | `0.85` | `249` | `17.52%` |
| S&P buy-and-hold | `+1,584.31%` | `1.0915` | — | — | — | — | — |
| Nasdaq combined | `+91.43%` | `1.0203` | `-52.06%` | `0.21` | `1.12` | `390` | `43.75%` |
| Nasdaq + `10 bps/fill` | `-12.38%` | — | `-69.24%` | — | — | `390` | — |
| Nasdaq + 1 session lag | `+19.79%` | — | `-69.53%` | — | — | `386` | — |
| Nasdaq long-only | `+255.55%` | `1.0401` | `-32.66%` | `0.46` | `1.76` | `158` | `26.75%` |
| Nasdaq short-only | `-41.22%` | `0.9837` | `-59.36%` | `-0.07` | `0.87` | `244` | `19.12%` |
| Nasdaq buy-and-hold | `+3,428.37%` | `1.1168` | — | — | — | — | — |

虽然主结果假设零成本，390–415 笔交易仍使较小的长期 edge 对摩擦高度敏感。额外延迟一 session 后 S&P 几乎归零、Nasdaq 收益下降约四分之三，也显示入场时序依赖。

## 分年代 combined

| Window | S&P base | S&P `10 bps` | Nasdaq base | Nasdaq `10 bps` |
| --- | ---: | ---: | ---: | ---: |
| 2010 年前 | `-9.84%` | `-41.16%` | `+38.54%` | `-5.12%` |
| 2010–2020 | `+33.82%` | `+2.95%` | `+15.99%` | `-11.70%` |
| 2021+ | `-2.96%` | `-16.15%` | `+16.65%` | `+2.01%` |
| Full | `+18.77%` | `-48.26%` | `+91.43%` | `-12.38%` |

S&P 的正收益主要集中在 2010–2020，前后两个大段都为负。Nasdaq 三段 base 都为正，但除 2021+ 外，示意摩擦后不再为正。

## 多空贡献

- S&P combined：long 166 笔累计约 `+64.70%` 初始权益，short 249 笔约 `-45.92%`。
- Nasdaq combined：long 146 笔约 `+170.82%`，short 244 笔约 `-79.39%`。
- 两个指数的 short-only full 分别为 `-34.30%/-41.22%`。

因此 shared combined 的核心问题与 SOX 相似：long 能识别部分上升趋势，但 short 没有足够 edge，并显著稀释 long。

## 长期与近期稳定性

| Index / variant | 正收益年度 | 年度中位 | 正收益滚动三年 | 三年中位 | 最差三年 |
| --- | ---: | ---: | ---: | ---: | ---: |
| S&P combined | `16/33` | `-0.85%` | `14/30` | `-0.66%` | `-24.59%` |
| S&P long-only | `18/33` | `+1.07%` | `20/30` | `+4.01%` | `-21.13%` |
| Nasdaq combined | `19/33` | `+2.70%` | `20/30` | `+8.35%` | `-28.96%` |
| Nasdaq long-only | `19/33` | `+0.56%` | `20/30` | `+9.68%` | `-15.08%` |

最近一年 combined 为 S&P `-11.89%`、Nasdaq `-7.25%`；最近 `1m/3m/6m` 也均为负。近期切片只用于 audit。

## 判定

1. Nasdaq 的零成本表现优于 S&P，但年化 `2.03%` 与 MDD `-52.06%` 不匹配。
2. 两个指数都大幅跑输 price-index buy-and-hold；即使 buy-and-hold 不含分红，这一差距仍非常大。
3. `10 bps/fill` 后两者全历史均亏损。
4. short leg 在两个指数都没有长期 edge。
5. 数据是指数而非可交易工具，无法支持实盘结论。

BTC/ETH 共享参数不是可跨加密货币与美股指数通用的 MA7 参数。Nasdaq 只说明较强趋势资产能保留部分 long edge，不构成 registration 或 promotion。

## 证据

- [机器摘要](../artifacts/us_indexes_1d_ma7_shared_parameter_transfer_summary_2026-08-05.json)
- [窗口指标](../artifacts/us_indexes_1d_ma7_shared_parameter_transfer_metrics_2026-08-05.csv)
- [逐年窗口](../artifacts/us_indexes_1d_ma7_shared_parameter_transfer_calendar_years_2026-08-05.csv)
- [滚动三年](../artifacts/us_indexes_1d_ma7_shared_parameter_transfer_rolling_3y_2026-08-05.csv)
- [近期切片](../artifacts/us_indexes_1d_ma7_shared_parameter_transfer_recent_2026-08-05.csv)
- [完整交易](../artifacts/us_indexes_1d_ma7_shared_parameter_transfer_trades_2026-08-05.csv)
- [复现脚本](../scripts/audit_us_indexes_1d_ma7_shared_params.py)
