# HYPE-15M-TB-MII-ENS Core Ledger

Family：`HYPE-15M-Trend-Breakout-Multi-Indicator-Ensemble`

Alias：`HYPE-15M-TB-MII-ENS`

Created：2026-07-07

## 边界

本台账只覆盖 `HYPE-EMA-Trend-Breakout-V35` 与 `HYPE-15M-Multi-Indicator-Intraday-V1.3` 的组合研究。裸版本号不具有策略身份；母版本定义以各自家族主账为准。

## 当前状态

- 当前状态：`first combination diagnostic / not registered as version / NO-GO / not live-ready`。
- 尚无登记版本；首次组合回测只用于回答"结合起来会怎样"，不是 promotion。
- 两个母版本各自为 `NO-GO / not live-ready`，组合继承全部 blocker（V35：盘口级 stop 证据、闪崩尾部风险；V1.3：资金费、runner、重启恢复、kill switch），并新增单账户杠杆叠加与 preempt 换仓时序风险。

## 数据与成本口径

- Exchange：Binance；Market：USD-M perpetual；Symbol：`HYPE/USDT:USDT`；Timeframe：`15m`。
- 数据：标准 raw/normalized 数据湖，`2025-05-30T10:30:00Z` 到 `2026-06-26T04:00:00Z`；质量 gate 全通过。
- V35 腿成本：`0.00085`/fill（家族 canonical 覆盖），计入 Binance funding。
- V1.3 腿成本：fee `0.001`/fill + slippage `4 bps`/fill（round-trip `0.28%`），funding 未计。
- 组合评估窗口从 V35 warmup（1600 根 15m）后开始：`2025-06-16T02:30:00Z` 起。

## 组合结构台账

| 结构 | 说明 | K+1 全样本 | 最大回撤 | Sharpe | 结论 |
| --- | --- | ---: | ---: | ---: | --- |
| `leg_v35_only` | V35 单独（对照） | `+7604.96%` | `-23.46%` | `4.78` | 收益主力腿 |
| `leg_mii_v13_k1` | V1.3 单独（对照，组合窗口） | `+496.37%` | `-21.54%` | `3.07` | 频率补充腿 |
| `portfolio_5050_rebal` | 双子账户 50/50 逐 K 再平衡 | `+2498.88%` | `-13.96%` | `5.99` | 回撤/Sharpe 最优，收益让渡大 |
| `portfolio_3070_rebal` | 30% V35 / 70% V1.3 | `+1410.68%` | `-11.85%` | `5.50` | 全表最浅回撤 |
| `single_v35_priority` | 单账户，V35 优先 + preempt | `+34987.81%` | `-28.01%` | `5.59` | 收益最高；回撤叠加、K+2 压力 `-33.59%` |
| `single_no_preempt` | 单账户，V1.3 持仓时放弃 V35 | `+23691.23%` | `-30.30%` | `5.23` | 劣于 preempt，不建议 |

两腿日收益相关系数 `-0.087`（组合窗口，K+1）。

## 证据入口

- 首次组合回测：`notes/hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md`
- 复现脚本：`scripts/research_hype_15m_tb_mii_ensemble_backtest.py`
- 保留产物：`artifacts/hype_15m_tb_mii_ensemble_backtest_2026-07-07.json` 及配套 equity/trades CSV
- Decision log：`decision-log.md`

## 已知风险

- 同样本组合，无 untouched OOS；权重与仲裁规则未做稳健性搜索。
- 单账户组合的超额收益来自资金利用率（V35 空档被 V1.3 复利），不是新 alpha；回撤同样叠加。
- 成本口径两腿不统一；V1.3 腿 funding 未计。
- 单账户全时段带 `2.5x-3x` 暴露，Binance 闪崩插针尾部风险大于 V35 单独。
- V1.3 近期信号枯竭时组合退化为纯 V35。

## 下一步（若继续）

- 统一成本口径并给 V1.3 腿补 funding 回放。
- 对仲裁规则做邻域测试（如 V1.3 持仓中允许 V35 只在反向信号时 preempt）。
- 滚动窗口与随机切片复核组合回撤叠加的频率。
- 若要任何 promotion 讨论，先完成两个母家族各自的 live-executable 审计。
