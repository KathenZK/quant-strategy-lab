# MU-HYPE-XFER 实验 V14 最新数据有效性诊断（2026-07-20）

## 结论

MU-HYPE-XFER 实验 V14 在完整历史样本上仍有较高累计收益，但最新自然前向段未确认策略继续有效：

- 严格执行口径 ALL：`+198.53%`，MDD `-29.46%`，20 笔，胜率 `75.00%`。
- 原研究截止点后的自然前向段（2026-06-17 06:00 UTC 至 2026-07-20 07:00 UTC）：`-4.83%`，MDD `-18.16%`，仅 2 笔。
- 最近 1 个月：`-18.16%`，只有 1 笔止损；最近 1 天和 7 天均无交易。
- 前向段虽然好于同期买入持有的 `-19.82% / -35.28%`，但绝对收益为负且样本太少，不能据此确认 OOS 有效性。

因此维持 `explore / not promoted / not live-ready`。V14 当前只能解释为“历史趋势样本强、回撤期相对防守，但新增数据尚未形成正向有效性证据”。

## 策略身份

- 市场：Binance USD-M Futures `TRADIFI_PERPETUAL`
- 标的：`MUUSDT`
- 周期：`15m`
- 方向：long-only
- 入场时段：全部 Binance 15m K 线
- 仓位：固定 `3x`
- 止盈 / 止损：`TP10ATR / SL9ATR`
- warmup：1,600 根 15m K 线
- 状态：`explore / not promoted / not live-ready`

V14 仍是实验编号，并未完成正式版本登记。本报告只审计冻结参数的最新表现，不构成 promotion review。

身份警告：历史名称“V6 long-only”不是完整 HYPE V6 状态机。实际入场来自冻结内核中 `v6_variant.entry=v2_regime`，退出使用 `ema_spread > 0` 趋势状态加 TP10/SL9，没有接入 `v6_variant` 的 ADX exit；仓位也是固定 3x，而非 dynamic sizing。本文保留 V14 历史别名以便复现，但不得据此声称已复现完整 V6。

## 数据补齐与质量

数据已从原来的 2026-06-17 补齐至 2026-07-20 07:00 UTC：

- K 线范围：2026-04-07 13:30 UTC 至 2026-07-20 07:00 UTC
- closed 15m bars：9,959
- 缺失 K 线：0
- 重复时间戳：0
- raw / normalized OHLCV、quote volume、trade count 不一致：0
- critical null：0
- 非法 OHLC：0
- 未闭合 K 线：0
- funding：316 个原始事件，映射到 315 根 15m K；其中 1 根 K 内有 2 个真实 funding 事件，回测按费率求和
- 零成交量 K 线：1；VWAP 按显式 provenance 使用 close 填充

刷新时发现并删除了一个遗留的粗分区文件。该文件把 2026-04-07 至 2026-06-18 的数据错误存放在 `date=2026-04-01` 下，并与日分区重复；修复后 consumer view 为 105 个日分区、9,959 行、无重复、无分区日期错位。

数据质量结构化证据见 [`mu_binance_15m_data_quality_latest.json`](../artifacts/mu_binance_15m_data_quality_latest.json)。

## 严格执行口径

本次没有把旧 V14 引擎直接当作有效性证据，而是使用以下可执行性更保守的口径：

- 15m 收盘确认信号，下一根 15m open 入场。
- 1h / 4h 特征只使用前一根已完成高周期 K；三个前缀重算检查点均无未来数据差异。
- 指标退出在收盘决定，下一根 open 按市价滑点退出。
- 同一根 15m K 同时触发 TP/SL 时按止损先发生。
- 跳空穿越止损时按下一可见 open 加不利滑点成交，不使用陈旧止损价。
- Binance 每次成交手续费 `0.001`，每次成交不利滑点 `4 bps`。
- 持仓跨 funding 事件时应用 Binance 实际 funding；同一 15m K 内多个事件全部计入。
- 一根 K 内退出后不立即重新武装，保持原 V14 状态机的下一根再判断规则。
- 权益若变为非正或非有限值立即 fail closed，不用缺失的强平模型继续虚构收益。

本次实际交易路径没有出现同 K TP/SL 冲突或跳空止损，但引擎已按保守规则处理这些情况。

## 最新分片结果

所有窗口均锚定数据结束时间 2026-07-20 07:00 UTC；这些分片只用于审计，没有参与参数选择。

| 窗口 | 收益 | MDD | 交易 | 胜率 | 买入持有收益 | 说明 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1D | 0.00% | 0.00% | 0 | - | +1.15% | 无信号 |
| 7D | 0.00% | 0.00% | 0 | - | -6.82% | 无信号 |
| 1M | -18.16% | -18.16% | 1 | 0.00% | -25.80% | 1 笔止损 |
| 3M | +198.53% | -29.46% | 20 | 75.00% | +77.80% | 实际仅覆盖约 87 天，不是完整 3M |
| 6M | 不可用 | - | - | - | - | MUUSDT 上线历史不足 |
| 1Y | 不可用 | - | - | - | - | MUUSDT 上线历史不足 |
| ALL | +198.53% | -29.46% | 20 | 75.00% | +77.80% | 2026-04-24 warmup 后开始 |

ALL 交易结构为 15 次止盈、5 次止损，Sharpe `4.56`。由于只有 20 笔交易，且大部分收益来自早期强趋势段，该 Sharpe 不应按稳定长期水平外推。

## 原选择段与新增前向段

| 区间 | V14 收益 | V14 MDD | 交易 | 买入持有收益 | 买入持有 MDD |
| --- | ---: | ---: | ---: | ---: | ---: |
| 原选择段：2026-04-24 05:30 → 2026-06-17 05:45 UTC | +213.68% | -29.46% | 18 | +121.13% | -22.95% |
| 新增自然前向段：2026-06-17 06:00 → 2026-07-20 07:00 UTC | -4.83% | -18.16% | 2 | -19.82% | -35.28% |

旧台账的 V14 `+238.08% / -29.23%` 可以在原选择段用 legacy 引擎复现。改用当前手续费、实际 funding 和严格成交口径后，同一选择段降为 `+213.68% / -29.46%`。在最新完整数据上，legacy 为 `+222.06%`，严格口径为 `+198.53%`；legacy 结果不再作为有效性主证据。

## 有效性判断

支持项：

- 数据质量门禁通过，未发现缺口、重复、未闭合 K 或 raw / normalized 不一致。
- EMA、ATR、1h、4h 和最终信号的前缀重算未发现 lookahead。
- ALL 严格结果仍显著高于同期买入持有累计收益。
- 新增回撤期相对买入持有少亏约 15 个百分点。

不支持项：

- 新增自然前向段绝对收益为负。
- 前向段只有 2 笔，最近 1 个月只有 1 笔，统计信息量不足。
- 完整 Binance 历史不足 6 个月，无法提供完整 6M / 1Y 分片。
- 尚未完成独立 OOS/CPCV、Monte Carlo、压力测试、相位敏感性和 runner parity。
- 固定 3x 的历史 MDD 已接近 `-30%`，不适合作为当前 shadow 或 dry-run 默认候选。
- “V6”只是历史标签，当前 V14 没有完整 V6 dynamic sizing / ADX exit parity。
- 尚无维持保证金和真实强平价格模型；当前路径未触发非正权益不代表 3x 已通过强平压力测试。

下一决策门应等待更多冻结参数的自然前向交易，或使用不参与本轮参数选择的独立数据完成正式 promotion review；在此之前不登记、不交接 runner、不进入 dry-run。

## 复现入口

- 数据刷新与质量检查：[`refresh_and_audit_mu_binance_15m.py`](../scripts/refresh_and_audit_mu_binance_15m.py)
- V14 严格审计：[`audit_mu_v14_latest.py`](../scripts/audit_mu_v14_latest.py)
- 结构化摘要：[`mu_v14_latest_strict_audit.json`](../artifacts/mu_v14_latest_strict_audit.json)
- 交易明细：[`mu_v14_latest_strict_trades.csv`](../artifacts/mu_v14_latest_strict_trades.csv)
- 权益曲线：[`mu_v14_latest_strict_equity.csv`](../artifacts/mu_v14_latest_strict_equity.csv)
- 家族实验台账：[`mu-hype-xfer-session-aware-ledger.md`](../mu-hype-xfer-session-aware-ledger.md)
