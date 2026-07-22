# MU-15M-Donchian-Trend-Breakout 冻结搜索诊断（2026-07-20）

## 结论

本轮没有找到可以通过 final audit 的 MUUSDT 15m Donchian 趋势策略。

18 组 train/validation 封闭搜索只有 `dtb-5e79abef48cf` 通过开发门槛；冻结后一次性揭示 `2026-06-25 → 2026-07-20`，结果为 `-4.13% / -4.93% MDD`，仅 2 笔且全部亏损。虽然同期 1x buy-and-hold 为 `-30.31% / -35.87% MDD`，候选明显少亏，但绝对收益为负、交易数不足，不能把“相对防守”解释为有效趋势策略。

最终裁决：`sample_insufficient / final gate failed`。家族维持 `explore / not promoted / not live-ready`；不登记版本、不扩搜、不交接 runner。

## 数据与冻结协议

- 市场：Binance USD-M `MUUSDT` `TRADIFI_PERPETUAL`
- 周期：closed `15m`
- 数据：2026-04-07 13:30 UTC 至 2026-07-20 07:00 UTC，共 9,959 根
- 数据质量：缺失、重复、critical null、非法 OHLC、未闭合 K 均为 0
- Train：2026-04-12 00:00 → 2026-06-01 00:00 UTC
- Gap：2026-06-01 00:00 → 2026-06-05 00:00 UTC
- Validation：2026-06-05 00:00 → 2026-06-25 00:00 UTC
- Final audit：2026-06-25 00:00 → 2026-07-20 07:15 UTC

`search` 只加载到 2026-06-25 之前的 7,530 根 K；搜索产物在揭示前写入参数、数据 fingerprint、代码 SHA256 与 payload SHA256。Final audit 只运行一次，揭示后未回调参数。

这仍是一次 retrospective holdout，不是从今天以后积累的 prospective 证据。

## 搜索空间

机制固定为 long-only：

1. 可选 `EMA96 > EMA384` 且 `EMA384` 16 根斜率为正；
2. 收盘突破前序 Donchian 高点；
3. 下一根 open 以 1x 入场；
4. entry-bar 即启用 ATR 初始止损；
5. 每根 K 收盘后用已完成 high / ATR 更新 trailing stop；
6. 跌破半周期 Donchian 低点或 EMA regime 失效时，下一根 open 退出。

唯一搜索维度：

- Entry Donchian：`48 / 96 / 192`
- Exit Donchian：对应 `24 / 48 / 96`
- Stop：`3 / 4 / 5 ATR`
- EMA regime：`off / on`

总计严格 18 组；没有 ADX、量能、TP、session、杠杆或揭示后的邻域扩搜。

## 成本与执行

- 每次成交手续费 `0.001`
- 每次成交不利滑点 `4 bps`
- Binance funding 逐事件计入；同一 15m K 多事件求和
- 收盘信号下一根 open 执行
- gap stop 使用更差 open
- stop 与 channel exit 同 K 冲突时 stop 优先
- 退出当根不立即重新武装
- 权益非正或非有限时 fail closed
- 开发门槛另外要求 fee / slippage 双倍压力下 train、validation 都为正

三个前缀重算检查点对 EMA、ATR 与 Donchian 特征的 mismatch 为 0。

## 开发搜索

唯一通过候选为 `dtb-5e79abef48cf`：

- Entry / exit：Donchian `192 / 96`
- Stop：`3 ATR`
- EMA regime：开启
- 仓位：固定 `1x`
- 邻域 train/validation 同正比例：`2 / 3`

| 区间 | 收益 | MDD | 交易 | 胜率 | PF | 双倍成本收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | +19.42% | -10.28% | 40 | 45.00% | 2.02 | +6.89% |
| Validation | +3.76% | -2.99% | 10 | 80.00% | 3.78 | +0.89% |

Validation 的 10 笔中 80% 胜率与较高 PF 没有在 final audit 延续，说明短窗口开发结果仍容易受局部路径影响。

## 一次性 Final Audit

| 指标 | 冻结候选 | 1x buy-and-hold | 固定 Turtle 基线 |
| --- | ---: | ---: | ---: |
| 收益 | -4.13% | -30.31% | -14.97% |
| MDD | -4.93% | -35.87% | -15.68% |
| 交易 | 2 | - | 14 |
| 胜率 | 0.00% | - | 14.29% |
| PF | 0.00 | - | 0.14 |
| 双倍成本收益 | -4.67% | - | - |

候选只暴露 2.68% 的 final bars，因 EMA + Donchian192 过滤而较少参与下跌；这解释了其显著少亏，但不能证明存在正收益趋势 alpha。固定 Turtle 交易更多但亏损更深，也没有支持放宽 EMA regime。

## 最新分片

所有分片锚定 2026-07-20 07:15 UTC，独立从 flat 开始，只作审计：

| 窗口 | 收益 | MDD | 交易 | 1x buy-and-hold | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| 1D | 0.00% | 0.00% | 0 | +1.14% | 无信号 |
| 7D | -1.95% | -1.95% | 1 | -7.39% | 绝对亏损 |
| 1M | -2.65% | -6.09% | 5 | -26.35% | 相对防守，绝对亏损 |
| 3M | +2.12% | -11.88% | 55 | +73.84% | 严重落后买入持有 |
| 6M | 不可用 | - | - | - | 上线历史不足 |
| 1Y | 不可用 | - | - | - | 上线历史不足 |
| ALL | +9.51% | -11.88% | 59 | +90.15% | 正收益但无超额收益 |

ALL 中有 56 次普通 stop 和 3 次 gap stop，暴露率仅 7.35%。累计结果为正但比同期 buy-and-hold 少约 80.64 个百分点，无法支持“已找到稳健趋势策略”。

## 与 MU-HYPE-XFER V14 对照

- V14 严格 ALL：`+198.53% / -29.46%`，但依赖固定 3x 和早期强趋势段。
- V14 原截止点后的前向段：`-4.83% / -18.16%`，2 笔。
- 本轮 Donchian final audit：`-4.13% / -4.93%`，2 笔。

两种不同趋势机制在新增后段都没有给出正绝对收益。Donchian 候选主要改善了回撤和暴露，不足以推翻“当前 Binance MU 短历史尚未支持稳健趋势策略”的结论。

## 决策

- 不登记 `dtb-5e79abef48cf` 为版本。
- 不把 `sample_insufficient` 写成通过；final gate 实际未通过。
- 不围绕该候选增加过滤器或扩大参数网格。
- 只有积累新的 prospective Binance 数据后，才允许用冻结候选做观察；揭示过的 2026-06-25 至 2026-07-20 不得再次充当 OOS。

## 复现入口

- 搜索 / 揭示脚本：[`research_mu_15m_dtb.py`](../scripts/research_mu_15m_dtb.py)
- 冻结搜索：[`mu_15m_dtb_search_freeze_2026-07-20.json`](../artifacts/mu_15m_dtb_search_freeze_2026-07-20.json)
- 18 组试验清单：[`mu_15m_dtb_search_trials_2026-07-20.csv`](../artifacts/mu_15m_dtb_search_trials_2026-07-20.csv)
- Final audit：[`mu_15m_dtb_final_audit_2026-07-20.json`](../artifacts/mu_15m_dtb_final_audit_2026-07-20.json)
- 交易明细：[`mu_15m_dtb_final_trades_2026-07-20.csv`](../artifacts/mu_15m_dtb_final_trades_2026-07-20.csv)
- 权益曲线：[`mu_15m_dtb_final_equity_2026-07-20.csv`](../artifacts/mu_15m_dtb_final_equity_2026-07-20.csv)
