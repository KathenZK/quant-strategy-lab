# BIN-MTF-PTC Goal 最终研究报告

## 结论

**HARD-GATE-FAILED / no registered candidate / not promoted / not live-ready。**

本轮证明了两件不同的事：

1. 趋势延续不是完全不可度量。ETH 的 24h onset meter 在 24h/72h/168h 标签上均有稳定排序增量；BTC/HYPE 的证据较弱或不稳定。
2. “能排序一部分延续概率”不等于“能做出高收益策略”。在真实回调等待、next-open、独立 lot stop、手续费、滑点、funding、逐 15m 盯市、3x 杠杆和风险不变量下，BTC 只有一个低收益、高集中度的 Pareto frontier；ETH/HYPE 不合格。动态加仓、半回吐减仓和限价回踩均未形成跨资产稳定优势。

目标 `annual equity multiple >=20x` 未实现。最高合规风险档位约为 BTC 2x scaling，revealed diagnostic validation 年化仅 `1.134x`，bar 内 MDD `-17.05%`；3x scaling 的 bar 内 MDD `-23.03%`，已超过 `20%` 硬约束。收益缺口来自机制 alpha 不够，不是仓位没有放大。

因为没有资产同时通过稳定、成本、集中度和收益门禁，本轮没有资格揭示 historical locked evaluation，也没有合格资产可装配组合。保持锁定集未运行是本轮治理成功的一部分，不是缺少结果。

## 1. 数据与时序

统一 closed cutoff 为 `2026-08-03 11:45 UTC`：

| 资产 | 15m rows | 起点 | 缺口 | 重复 | OHLC 违规 | raw/normalized mismatch |
|---|---:|---|---:|---:|---:|---:|
| BTC | 241,993 | 2019-09-08 17:45 UTC | 0 | 0 | 0 | 0 |
| ETH | 234,353 | 2019-11-27 07:45 UTC | 0 | 0 | 0 | 0 |
| HYPE | 41,286 | 2025-05-30 10:30 UTC | 0 | 0 | 0 | 0 |

数据审计 blocker 为 `0`。1h bar 由四根完整 15m bar 聚合，索引移动到最早可见 close 时点；所有信号使用 closed bar，成交使用后续可执行 15m open。失败 pullback plan 直到真实 24h 到期前保持 pending，不能预知“未来不会成交”后提前尝试下一信号。

证据：[数据切分审计](../artifacts/binance_mtf_ptc_data_split_audit_2026-08-03.json) · [数据合同](../specs/binance-mtf-ptc-data-split-contract-2026-08-03.md)

## 2. 延续性度量是否成立

Meter 使用过去价格路径的幅度、速度与形状：scaled move、efficiency、jump concentration、path R²、acceleration、ATR expansion、directional RSI。RSI 只作为路径位置测量，不决定多空。标签为未来 `24h/72h/168h` 内先到 `+1R` 还是 `-0.5R`；同 bar 两边同时触及按失败，不完整路径不进入已知标签。

### 2.1 24h onset validation

| 资产 | 24h label AUC | 72h label AUC | 168h label AUC | 主要判断 |
|---|---:|---:|---:|---|
| BTC | 0.536 | 约 0.517 | 约 0.515 | 弱，主要集中在短方向/短 horizon |
| ETH | 0.594 | 0.576 | 0.575 | 三个 horizon 均有稳定排序；quintile 基本单调 |
| HYPE | 0.554 | 0.543 | 0.540 | 排序略正，但 Brier skill 为负、年份漂移明显 |

ETH long/short 与 2024/2025 子组均保留增量，efficiency 是最大单一贡献；HYPE 过度依赖 jump concentration。结论是：**ETH 延续性排名初步成立，HYPE 只可探索，BTC 不足以单独授权仓位。**

证据：[meter metrics](../artifacts/binance_mtf_ptc_continuation_meter_v0_metrics_2026-08-03.csv) · [subgroups](../artifacts/binance_mtf_ptc_continuation_meter_v0_subgroups_audit_2026-08-03.csv) · [ablations](../artifacts/binance_mtf_ptc_continuation_meter_v0_ablations_audit_2026-08-03.csv)

## 3. 回调入场是否比确认后立即进入更好

冻结 anchor 为：1h 回调至少 `0.5 ATR(24)`、最多回吐 impulse leg 50%、两根 15m 不再创新极值、15m close 突破前 4 根顺势极值且处于顺势半区、下一 15m open 成交。

24h onset 中，配对回调成交相对 candidate close 的中位“改善”实际为 BTC `-0.156%`、ETH `-0.136%`、HYPE `-0.892%`；负数代表成交更差。4h/12h earlier onset 仍普遍降低 success rate。原因不是“回调思想错误”，而是当前 restart 确认在许多路径中重新把订单带回局部高点/低点，同时结构 stop 很紧，成本后大量交易集中在约 `-1R`。

随后在 development-inner 对每资产冻结 60 个组合，选出唯一参数再进入 validation。Probe-only 在可信逐 15m 盯市与真实 quantity 后：

| 资产 | Return | 15m MDD | bar 内 MDD | PF | 胜率 | 判断 |
|---|---:|---:|---:|---:|---:|---|
| BTC | +4.07% | -9.40% | -9.41% | 1.25 | 10.98% | 正偏但低效 |
| ETH | +5.79% | -11.72% | -11.75% | 1.37 | 8.11% | 正偏但高度集中 |
| HYPE | -0.61% | -5.11% | -5.17% | 0.93 | 6.45% | 失败 |

ETH 前三笔赢家贡献约 `84%` 毛利润，HYPE 只有两笔赢家。该阶段不满足稳定门禁。

## 4. 动态加减仓是否能吃完整趋势

Campaign V0 实现了真实 Probe/Add-1/Add-2/Add-3 lot：每层独立结构 stop，每层请求 `0.25%` risk，MFE `0.5R/1R/2R` 只授予资格，之后仍须新 continuation candidate + pullback + restart；每级最多两次尝试；总 projected operational stop risk `<=0.9%`、hard `<=1%`、effective leverage `<=3x`；funding 后 LIFO risk trim；24h 未 +1R 退出；336h timeout；无固定 TP。

默认规则在 +2R 后回吐 peak MFE 50% 时卸新增层。结果：

| 资产 | Full default | Probe-only | No half-reduce | 8bps no-half stress |
|---|---:|---:|---:|---:|
| BTC | -1.51% | +6.51% | +13.35% | +10.60% |
| ETH | -1.72% | +0.63% | +0.31% | -1.18% |
| HYPE | -1.02% | -1.10% | -2.35% | -3.71% |

默认半回吐减仓损害 BTC 长尾；取消后 BTC 改善，但 2024 盈利、2025 上半年略负，且最大赢家超过策略最终净利润。ETH/HYPE 无可迁移优势。

## 5. 日/周方向先验与限价回踩

为补上用户人工流程中的“日/周先判断方向”，V1 只在 development expanding folds 搜索纯价格先验：过去 168h、672h 与二者一致性；同时比较 0/1/3 layers 和 half-reduce on/off，共 20 个预声明组合。

BTC 胜出：`weekly_monthly_consensus + 3 layers + no half-reduce`：

- development 2021/2022/2023 三折全正，合并 `+12.70%`；8bps stress `+10.21%`；
- revealed diagnostic validation base `+11.30%`、annual multiple `1.074x`、MDD `-7.23%`、bar 内 `-9.58%`、PF `1.87`；
- stress `+9.33%`、annual multiple `1.061x`；
- validation top-1/top-3 gross-profit concentration `72.6% / 96.0%`。

ETH 胜出仍是 `none + probe-only`，validation stress `-0.31%`；HYPE development 只有单折，validation base/stress `-1.10%/-2.56%`。

V2 比较 restart market 与 25%/50% 回踩、1h/4h 限价。BTC 仍选择 market；ETH `limit50_4h` 在 development 看似 `+27.37%`，到 validation 直接 `-10.03%`，是明确过拟合；HYPE 不改善。

## 6. 风险缩放与 20x 可行性

只对 BTC frontier 做机械缩放：

| 成本 | 档位 | Dev annual multiple | Dev worst MDD | Validation annual multiple | Validation MDD | Validation bar 内 MDD | Max leverage |
|---|---|---:|---:|---:|---:|---:|---:|
| base | 1x | 1.041x | -6.99% | 1.074x | -7.23% | -9.58% | 0.73x |
| base | 2x | 1.076x | -13.09% | 1.134x | -12.86% | -17.05% | 1.44x |
| base | 3x | 1.106x | -18.52% | 1.182x | -17.37% | **-23.03%** | 2.15x |
| stress | 2x | 1.061x | -12.83% | 1.109x | -12.35% | -16.38% | 1.34x |
| stress | 3x | 1.084x | -18.19% | 1.145x | -16.76% | **-22.23%** | 2.00x |

2x 是最高合规档位；3x 违反 bar 内 20% MDD。以 2x validation base 的年化增长计算，达到 20x 仍需约 `23.8x` 当前对数增长；stress 需要约 `28.9x`。这是 alpha 缺口，不可能由合规仓位解决。

证据：[risk scaling](../artifacts/binance_mtf_ptc_risk_scaling_v1_aggregate_2026-08-03.csv)

## 7. 理论问题还是落地问题

### 理论中成立的部分

- 趋势路径的幅度、效率、跳跃集中、加速度和波动扩张对未来延续有条件排序能力，ETH 最明确。
- 趋势收益具有正偏：多数试单小亏，少数 campaign 贡献大盈利。
- 高周期 7d/28d 共识能改善 BTC 的候选方向。

### 理论中没有成立的部分

- 延续性排名强度不足以覆盖真实 entry/exit 成本并产生高 CAGR。
- 一个资产上“看起来趋势明显”不代表该资产能提供稳定可交易的 continuation edge；HYPE 明确反例。
- 动态加仓不是自动放大利润：若延续分数、回调结构和退出不够稳，它会同时放大费用、止损和尾部依赖。

### 首轮落地中被修正的问题

- 平仓点 MDD 改为逐 15m liquidation MDD + bar 内不利极值；
- 计划风险复利改为真实 quantity、3x cap 和实际 stop risk；
- 同 bar stop 优先级、funding settlement、退出同 bar 禁止重入；
- 失败 pullback plan 不能在 candidate 当下预知失败；
- 限价盘中成交不使用可能发生在成交前的 MFE high/low。

修正后 BTC frontier 仍为正，说明不是所有结果都由虚假状态机制造；但收益仍远低于目标，说明核心瓶颈已经从“执行偏差”转为“机制优势不足”。

## 8. 最终门禁矩阵

| 门禁 | BTC | ETH | HYPE |
|---|---|---|---|
| 数据质量 | PASS | PASS | PASS |
| continuation meter 稳定 | WEAK | PASS | EXPLORATORY/poor calibration |
| development rolling | PASS for frontier | PASS but weak | insufficient history |
| base diagnostic validation | PASS but low | marginal | FAIL |
| stress diagnostic validation | PASS but low | FAIL | FAIL |
| tail concentration | FAIL | FAIL | FAIL |
| 20x / MDD<=20% | FAIL | FAIL | FAIL |
| locked evaluation eligibility | **NO** | **NO** | **NO** |
| portfolio eligibility | **NO** | **NO** | **NO** |

## 9. 状态与后续边界

- 不登记版本；不启动 prospective；不写 live/dry-run 实现；不揭示 locked historical evaluation。
- 当前家族保持 `explore / not promoted / not live-ready`，本轮决定为 `HARD-GATE-FAILED`。
- 若继续，必须是 materially new mechanism，而不是继续调 q、ATR、restart 或只删掉失败年份/方向。更有信息量的后继方向是扩大真正低相关资产生态、使用事件/持仓/流动性状态作为延续条件，或把趋势 campaign 作为低权重 sleeve，而不是要求单个 HYPE/BTC 规则承担 20x 目标。
- “完美趋势策略做不出来”不是可证明命题；本轮能证明的是：**这组纯价格 continuation + pullback/restart + pyramiding 机制，在 BTC/ETH/HYPE 与当前成本/风险约束下做不到目标。**

## 10. 复现

```bash
cd /Users/ZK/OpenCode/quant-strategy-lab
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/audit_binance_mtf_ptc_data.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/research_continuation_meter_v0.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/audit_continuation_meter_v0.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/search_probe_entry_v0.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/research_campaign_engine_v0.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/search_regime_campaign_v1.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/search_limit_retest_v2.py
.venv/bin/python research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/audit_risk_scaling_v1.py
.venv/bin/pytest -q tests/test_binance_mtf_ptc_continuation.py tests/test_binance_mtf_ptc_probe_execution.py tests/test_binance_mtf_ptc_campaign_engine.py
```

测试结果：`9 passed`。

交互证据：[Campaign Goal Evidence HTML](../artifacts/binance_mtf_ptc_goal_evidence_2026-08-03.html)。
