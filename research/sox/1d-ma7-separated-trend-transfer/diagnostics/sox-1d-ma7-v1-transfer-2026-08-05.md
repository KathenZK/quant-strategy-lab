# HYPE MA7 V1 迁移至 SOX 全历史诊断

## 结论

`HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 原参数在 Yahoo `^SOX` 上的长期 direct transfer **失败**：

- `1994-05-04` 至 `2026-08-04` 零成本组合收益 `-36.29%`，MDD `-76.58%`，PF `0.94`，365 笔；
- 每 fill 加示意 `10 bps` 后为 `-69.36%`；额外延迟一个交易 session 后为 `-53.33%`；
- 同期 SOX price-index buy-and-hold 为 `+9,725.06%`，年化因子约 `1.153`；策略年化因子只有 `0.986`；
- 33 个逐年窗口中只有 17 个为正，30 个滚动三年窗口中只有 13 个为正，中位收益 `-4.92%`；
- 最近 `1y/6m/3m` 组合收益为 `-2.53% / -4.29% / -3.21%`。

与 HYPE 日历重叠的 `423d` 区间组合为 `+5.98%`，但同期 buy-and-hold 为 `+132.77%`，且额外延迟一个 session 后转为 `-4.85%`，不能视为迁移成功。

## 身份与限制

- 来源版本：[HYPE V1 规格](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-v1-spec.md)。
- SOX 合同：[零调参迁移合同](../specs/sox-1d-ma7-v1-transfer-contract-2026-08-05.md)。
- `^SOX` 是价格指数，不是可直接交易标的；它不等于 SOXX ETF、期货或期权。
- 用户未指定执行代理与成本，主结果没有猜测手续费、滑点、借券费或融资费。
- Yahoo 全历史只提供 session 日线；stop 用 open gap 和日 high/low 触发，无法恢复 session 内 high/low 的先后。
- Sharpe 按 `252` 个交易 session 年化；收益年化按实际日历天数。

## 数据质量

Yahoo chart API 返回 `8,117` 行，范围 `1994-05-04` 至 `2026-08-04`：

- symbol `^SOX`，long name `PHLX Semiconductor`，instrument type `INDEX`；
- session date / timestamp 重复 `0`；
- OHLC、volume、adjusted close 空值 `0`，非法 OHLC `0`；
- 按美国股票市场常规假日与已知特别全日休市检查，缺失/意外 session 均为 `0`；
- `7,958` 行 volume 为零，符合指数而非交易工具的属性，且策略不使用 volume；
- adjusted close 与 close 有 `4,692` 行细小差异，最大约 `4.84 bps`；为保持 OHLC 内部一致，回测统一使用 raw OHLC。

原始响应 SHA256 为 `402440c9129f65f828074089386d52c06d0c76ada67528af7a1ac96a0d5a5e4e`。

## 全历史结果

| 变体 | 净收益 | 年化因子 | MDD | Sharpe | PF | 交易数 | 暴露 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `-36.29%` | `0.986` | `-76.58%` | `0.00` | `0.94` | `365` | `25.43%` |
| Combined + `10 bps/fill` | `-69.36%` | `0.964` | `-86.79%` | `-0.13` | `0.86` | `365` | `25.43%` |
| Combined + 1 session lag | `-53.33%` | `0.977` | `-84.12%` | `-0.06` | `0.89` | `381` | `24.72%` |
| Long-only | `+230.87%` | `1.038` | `-50.38%` | `0.31` | `1.21` | `296` | `23.74%` |
| Short-only | `-60.35%` | `0.972` | `-65.73%` | `-0.18` | `0.62` | `161` | `8.54%` |
| Buy-and-hold | `+9,725.06%` | `1.153` | — | — | — | — | `100%` |

Long-only 虽有正绝对收益，但 32 年只实现约 `3.8%` 年化、MDD 超过 `50%`，远逊于指数约 `15.3%` 年化；它不构成有效超额策略。Short-only 是组合长期失败的主要来源之一。

## HYPE 日历重叠窗口

窗口从周末后的首个 session `2025-06-02` 到 `2026-07-30` terminal open：

| 变体 | 净收益 | MDD | PF | 交易数 |
| --- | ---: | ---: | ---: | ---: |
| Combined | `+5.98%` | `-15.66%` | `1.40` | `13` |
| Combined + `10 bps/fill` | `+3.27%` | `-16.58%` | `1.20` | `13` |
| Combined + 1 session lag | `-4.85%` | `-18.75%` | `0.78` | `16` |
| Long-only | `+6.65%` | `-10.27%` | `1.76` | `7` |
| Short-only | `+3.15%` | `-11.64%` | `1.30` | `8` |
| Buy-and-hold | `+132.77%` | — | — | — |

这一小段的正收益既缺少超额，也对一个 session 的执行偏移翻负。

## 近期切片

| 方向 | `1d` | `7d` | `1m` | `3m` | `6m` | `1y` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined | `-6.19%` | `-5.42%` | `+0.95%` | `-3.21%` | `-4.29%` | `-2.53%` |
| Long-only | `0.00%` | `0.00%` | `0.00%` | `0.00%` | `-0.58%` | `-5.34%` |
| Short-only | `-6.19%` | `-5.42%` | `+0.95%` | `-3.21%` | `-4.95%` | `+1.67%` |

切片以 `2026-08-04` terminal open 锚定，只用于 audit。

## 长期稳定性

- 逐年：33 个窗口，正收益 17 个、负收益 16 个；2026 YTD 为 `-9.28%`。
- 滚动三年：30 个窗口，正收益 13 个、负收益 17 个。
- 滚动三年中位收益 `-4.92%`，最差 `-37.26%`。
- 长期亏损发生在零执行成本假设下，因此补充真实成本不会修复结果。

## 未完成门禁

- `^SOX` 不可直接交易，缺少明确交易代理与真实成本/借券合同；
- 只有日线，session 内路径顺序与 phase/bar-alignment gate 不完整；
- V1 多头首持仓日仍无固定 hard stop；
- 没有 SOX clean prospective OOS、可执行工具 parity、runner 实现或线上对账。

## 决策

1. 保留 HYPE V1 的已登记身份，但 SOX 结果增加一项跨市场泛化失败证据。
2. 不把 SOX 迁移线登记为版本，不晋升，不根据 SOX 历史调参。
3. 如需研究可交易的美国半导体暴露，应另建 SOXX 或指定期货/期权家族，明确 adjusted data、交易时段、费用、spread、借券/融资和 stop 成交模型；不得继承本指数诊断的 live-readiness。

## 证据

- [机器摘要](../artifacts/sox_1d_ma7_v1_transfer_summary_2026-08-05.json)
- [Yahoo 原始响应](../artifacts/sox_yahoo_chart_1d_raw_2026-08-05.json)
- [标准化日线](../artifacts/sox_yahoo_1d_normalized_2026-08-05.csv)
- [指标表](../artifacts/sox_1d_ma7_v1_transfer_metrics_2026-08-05.csv)
- [近期切片](../artifacts/sox_1d_ma7_v1_transfer_recent_2026-08-05.csv)
- [逐年窗口](../artifacts/sox_1d_ma7_v1_transfer_calendar_years_2026-08-05.csv)
- [滚动三年](../artifacts/sox_1d_ma7_v1_transfer_rolling_3y_2026-08-05.csv)
- [完整交易](../artifacts/sox_1d_ma7_v1_transfer_trades_2026-08-05.csv)
- [组合路径](../artifacts/sox_1d_ma7_v1_transfer_path_2026-08-05.csv)
- [复现脚本](../scripts/research_sox_1d_ma7_v1_transfer.py)
