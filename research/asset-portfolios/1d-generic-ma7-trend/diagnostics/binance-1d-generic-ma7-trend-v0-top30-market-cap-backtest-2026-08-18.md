# BIN-1D-GMA7T-v0：current market-cap Top30 通用迁移审计

日期：2026-08-18  
状态：`COMPLETED_DIAGNOSTIC / explore / not promoted / not live-ready`  
结论：**NO-GO for promotion；只保留为下一阶段研究候选。**

## 1. Executive verdict

冻结的 Generic v0 在最终 22 个可交易且历史充分的标的上，共产生 876 笔平仓交易：

- 单币净 Sharpe 中位数 `0.239`、均值 `0.135`；`12/22` Sharpe 为正，`12/22` PF > 1。
- 单币净总收益中位数 `+3.14%`，但分布极宽；22 币中 10 币为负。
- long 在 `11/22` 币上贡献为正，聚合 PF `1.171`；short 仅 `8/22` 为正，聚合 PF `0.966`。对称空头核心没有显示可靠正期望。
- 30 币冻结规则形成的 22 币 equal-risk 组合：净收益 `+22.84%`、CAGR `10.85%`、Sharpe `0.582`、MDD `-25.11%`；gross Sharpe `0.984`，说明成本侵蚀明显。
- HYPE 同一注册窗口内，原 V7.1 权威锚点为 `+711.04%`；Generic v0 为 `+93.69%`，只保留原收益的 `13.18%`。两者差额 `617.35pp`（原收益的 `86.82%`）与 HYPE-specific 完整规则集相关，但不是逐模块因果归因。
- 参数扰动总体不是单一尖峰，但 `1.2 ATR` protective stop 将组合 Sharpe 压至 `0.112`，说明风险退出距离仍有实质敏感性。

所以四个问题的回答是：

1. **存在可迁移的 generic trend core，但很弱且不均匀。**
2. **12/22 币保留正 Sharpe/PF>1 迹象；净成本压力下 8bps stress 只剩 10/22 正收益。**
3. **同一注册窗口的 86.82% 原始收益差额与专属化完整规则集相关；不能把它等同为某单一 arm 的贡献。**
4. **值得做新的前瞻研究，不值得 promotion，更不 live-ready。**

## 2. 治理：先冻结，再看结果

v0 的 [规格](../specs/binance-1d-generic-ma7-trend-v0-spec.md)、[配置](../configs/binance-1d-generic-ma7-trend-v0.json) 和 [genericization audit](binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md) 均在本轮 30 币结果之前落盘。配置 SHA-256：

`7ed73b21945a923c0ca42bd4beb5b4c6d6f0c8e9fc34f454c69429367d6a2c55`

本轮没有 per-asset grid、threshold、hold day、方向参数或结果后筛币。扰动只作稳定性报告，不会重写 v0，也不会选 `MA6` 或其他事后表现更好的参数。

## 3. Genericization audit

| 审查项 | 分类 | v0处理 | 证据结论 |
| --- | --- | --- | --- |
| SMA7 / price-body reclaim | A 通用趋势核心 | 对称保留 | 是价格重新占领趋势基准的通用结构 |
| ATR7 与 slope/ATR | A 通用趋势核心 | 对称保留 | 提供跨币波动归一化 |
| MA ± 0.75 ATR hysteresis | A 通用趋势核心 | 对称保留 | 降低 MA 边界反复切换 |
| long/short 不同 slope、entry buffer、trail、max-hold、cooldown | B HYPE/post-hoc | 全部改为对称 | 原始搜索在已揭示 HYPE 路径上选择；short 样本极少 |
| short RSI 20×2 | B HYPE/post-hoc | 删除 | 针对 HYPE 急跌/反弹路径的额外处置 |
| OAPP | B HYPE/post-hoc | 删除 | 957 个配置搜索；一次性 H 上的关键路径反而伤害后续 forced short |
| PEHC | B HYPE/post-hoc | 删除 | 490 arms；仅 6 个机会、5 次接受、1 次为负，样本不足以证明通用性 |
| forced reversal | B HYPE/post-hoc | 删除 | 与 HYPE 特定 exit/handoff 状态机绑定 |
| ATR hard/trailing protection | C 风险保护 | 对称保留为 1.5 ATR | 属于必要执行/风险层；扰动显示其仍敏感 |
| next-open、1h replay、费用/滑点/funding | C 执行层 | 保留 | 防止同 bar 偷看并维持已有记账口径 |

关键来源见 [audit](binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md)。V7.1 本身只清理 dormant/schema 字段，并未把 V7 变成通用策略；因此本任务没有把 V7.1 直接批量搬运后称为 generic。

## 4. 冻结的 Generic v0

- `SMA7`、简单 `ATR7`。
- long：前一日 close ≤ SMA，当前 close > SMA，且一日 SMA slope/ATR ≥ `0.02`。
- short：完全镜像。
- closed daily signal，下一 UTC 日 open 成交。
- close 穿越 `SMA ± 0.75 ATR` 后下一日 open 退出。
- 初始 hard stop `1.5 ATR`；按已完成日线最有利 close 更新 `1.5 ATR` trailing stop。
- stop 用真实 `1h` intrabar replay；小时开盘已越过 stop 时按 open gap fill，否则按 stop fill。
- 1x、单仓、不加仓；无 OAPP、short RSI、PEHC、forced reversal、max-hold、cooldown、slope exit。
- net：`10 bps/fill + 4 bps/fill slippage + actual funding`；另报 gross 与 `8 bps/fill` stress。

## 5. Universe 快照与筛选

市值来源：CoinGecko `/coins/markets`，`market_cap_desc`；抓取时间 `2026-08-18T13:56:45.534701Z`。原始响应 SHA-256：`7887b615a47b81fdb1b959f07f0cc1df2da784fc47320c67f3be8ab862c45ba8`。完整快照见 [market_cap_snapshot.json](../artifacts/binance_1d_gma7t_v0_2026-08-18_market_cap_snapshot.json)。

先按市值顺序排除 fiat/stable、收益型美元锚、黄金锚、wrapped/staked duplicate、tokenized fund/credit，再取 30 个独立经济暴露。因此第 30 个合格市值标的是原榜第 44 位 TAO：

`BTC, ETH, BNB, XRP, SOL, TRX, HYPE, DOGE, RAIN, LEO, ZEC, XMR, LINK, ADA, WBT, XLM, BCH, GRAM, CC, LTC, HBAR, AVAX, SUI, SHIB, CRO, NEAR, OKB, UNI, WLFI, TAO`。

与运行时 Binance `TRADING` USDT perpetual 相交并要求至少 365 根闭合日线后：

- 最终 22：`1000SHIBUSDT, ADAUSDT, AVAXUSDT, BCHUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, HBARUSDT, HYPEUSDT, LINKUSDT, LTCUSDT, NEARUSDT, SOLUSDT, SUIUSDT, TAOUSDT, TRXUSDT, UNIUSDT, XLMUSDT, XMRUSDT, XRPUSDT, ZECUSDT`。
- 无 Binance USDT perp：`RAIN, LEO, WBT, CRO, OKB`。
- 历史不足：`GRAM` 47 日、`CC` 291 日、`WLFI` 360 日。
- 不用榜外币补足 30；最终不足 30 是冻结交集规则的结果。

这是 **current-top30 retrospective backtest**，不是历史动态市值成分回测，仍有 survivorship bias。完整逐项决定见 [universe.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_universe.csv)。

## 6. 数据与执行审计

- Binance USD-M perpetual；最多 730 个闭合 UTC 日，HYPE 因上市历史只有 445 日。
- 每个标的同时抓 `1d`、`1h` 和 funding events；日/小时 continuity、duplicate、OHLC、close-time 均须 PASS。
- 最终 22 币全部通过；逐币原始序列 SHA-256 见 [data_quality.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_data_quality.csv)。
- funding mark 沿用已有便携研究引擎，以事件小时 close 近似；这是已披露的精度限制。
- 首轮并发抓取曾触发 Binance 临时限流；正式结果使用逐币质量门与任务缓存恢复为冻结 22 币，网络错误没有变成 universe 排除规则。

## 7. 单币结果

`MDD` 为真实 1h 顺序回放口径。完整 gross/net/stress 和附加字段见 [per_asset_metrics.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_per_asset_metrics.csv)。

| Symbol | Gross ret | Net ret | CAGR | Sharpe | Sortino | MDD | Calmar | PF | Trades | Win | Avg hold d |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1000SHIB | 119.44% | 91.61% | 38.49% | 0.900 | 1.099 | -47.94% | 0.843 | 1.677 | 33 | 51.5% | 11.27 |
| ADA | 97.19% | 74.04% | 31.97% | 0.768 | 0.858 | -51.43% | 0.652 | 1.236 | 35 | 28.6% | 8.22 |
| AVAX | 23.19% | 3.70% | 1.84% | 0.327 | 0.432 | -53.77% | 0.036 | 1.014 | 46 | 37.0% | 7.93 |
| BCH | -64.77% | -70.32% | -45.57% | -1.045 | -1.151 | -73.71% | -0.625 | 0.461 | 48 | 27.1% | 7.25 |
| BNB | -36.04% | -43.78% | -25.05% | -0.668 | -0.632 | -61.03% | -0.415 | 0.609 | 40 | 32.5% | 8.25 |
| BTC | 17.57% | 2.58% | 1.28% | 0.194 | 0.218 | -41.22% | 0.033 | 1.024 | 43 | 41.9% | 7.99 |
| DOGE | 25.49% | 9.55% | 4.67% | 0.346 | 0.387 | -51.22% | 0.095 | 1.054 | 39 | 41.0% | 8.92 |
| ETH | 23.64% | 5.07% | 2.51% | 0.283 | 0.361 | -53.66% | 0.048 | 1.022 | 47 | 34.0% | 7.94 |
| HBAR | -66.33% | -70.67% | -45.89% | -0.921 | -1.025 | -75.10% | -0.616 | 0.459 | 44 | 20.5% | 7.32 |
| HYPE | 121.09% | 107.82% | 82.46% | 1.267 | 1.692 | -30.52% | 3.047 | 2.209 | 22 | 59.1% | 9.34 |
| LINK | -19.67% | -29.10% | -15.82% | -0.001 | -0.001 | -62.85% | -0.260 | 0.839 | 36 | 36.1% | 8.00 |
| LTC | -40.78% | -49.64% | -29.07% | -0.457 | -0.510 | -74.52% | -0.399 | 0.694 | 48 | 33.3% | 7.83 |
| NEAR | 114.99% | 90.23% | 37.98% | 0.844 | 1.094 | -38.95% | 1.049 | 1.326 | 35 | 45.7% | 8.66 |
| SOL | 20.46% | 5.29% | 2.61% | 0.293 | 0.320 | -56.41% | 0.050 | 1.033 | 40 | 40.0% | 8.97 |
| SUI | -42.91% | -49.63% | -29.06% | -0.336 | -0.376 | -75.01% | -0.392 | 0.640 | 40 | 30.0% | 8.19 |
| TAO | 220.48% | 187.18% | 69.59% | 1.108 | 1.286 | -64.57% | 1.135 | 1.591 | 36 | 36.1% | 10.62 |
| TRX | 10.62% | -10.03% | -5.15% | -0.062 | -0.066 | -36.61% | -0.151 | 0.862 | 43 | 41.9% | 9.47 |
| UNI | 129.44% | 102.70% | 42.44% | 0.843 | 1.167 | -45.22% | 0.956 | 1.474 | 37 | 43.2% | 9.64 |
| XLM | -10.70% | -21.71% | -11.54% | -0.118 | -0.113 | -39.02% | -0.312 | 0.770 | 35 | 42.9% | 8.46 |
| XMR | -51.17% | -58.68% | -35.76% | -0.707 | -0.851 | -69.35% | -0.519 | 0.574 | 45 | 24.4% | 8.17 |
| XRP | -44.62% | -51.76% | -30.58% | -0.519 | -0.487 | -67.50% | -0.466 | 0.555 | 45 | 33.3% | 7.80 |
| ZEC | 65.37% | 47.47% | 21.47% | 0.631 | 0.735 | -62.11% | 0.360 | 1.132 | 39 | 35.9% | 6.98 |

成本结论：gross 正收益 `13/22`、net `12/22`、8bps stress `10/22`；gross/net 中位收益分别 `19.01%` 与 `3.14%`，中位拖累 `15.08pp`。这不是“成本后仍广泛稳健”的截面。

## 8. Long / short 分拆

| Side | Trades | Win rate | Aggregate PF | 正贡献资产 | 负贡献资产 | 中位资产 PnL contribution | 聚合 contribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Long | 429 | 33.33% | 1.171 | 11 | 11 | +0.25% | +337.54% |
| Short | 447 | 38.93% | 0.966 | 8 | 14 | -10.49% | -65.62% |

详细逐币分拆见 [long_short.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_long_short.csv)。对称化没有证明 short 是通用 alpha；下一阶段若研究市场结构不对称，必须作为新机制预注册，不能拿本轮 short 结果回头改 v0。

## 9. Equal-risk / volatility-scaled 组合

组合使用所有冻结合格币，不做盈利币筛选：20 日 EWM volatility（halflife 20）、inverse-vol equal-risk、20% 年化目标、3x gross cap，权重只使用 T-1 信息。

| Portfolio view | Total return | CAGR | Sharpe | Sortino | MDD | Calmar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gross sleeves | 45.97% | 20.85% | 0.984 | 1.430 | -22.69% | 0.919 |
| Net before weight-drift rebalance cost | 26.83% | 12.64% | 0.656 | — | -24.93% | — |
| Final net | 22.84% | 10.85% | 0.582 | 0.834 | -25.11% | 0.432 |

LOAO 只作依赖性检查：22 个 leave-one-asset-out 组合全部保持正收益，Sharpe 范围约 `0.467–0.747`；去掉 HYPE 后仍为 `+18.86% / Sharpe 0.505 / MDD -26.29%`。这表明组合不是只靠 HYPE，但不得用 LOAO 事后挑选子集。完整日序列与 LOAO 见 [portfolio_daily.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_portfolio_daily.csv) 和 [portfolio_loao.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_portfolio_loao.csv)。

## 10. HYPE 对照 A/B/C

| Control | Window | Net return | Sharpe | 1h MDD | PF | Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A. 原注册 V7.1 / HYPE | 2025-05-31 至 2026-08-06，432d | 711.04% | 注册账未以相同字段冻结 | -18.40% | 17.51 | 20 |
| B. Generic v0 / HYPE | 同一 432d | 93.69% | 1.194 | -30.52% | 2.051 | 21 |
| C. Generic v0 / current Top30 intersection | 最终 22 币，最长 730d | 中位 3.14% | 中位 0.239 | 单币中位不作组合 MDD | 12/22 > 1 | 876 |

同窗 B 只保留 A 的 `13.18%` 回报；差额 `617.35pp / 86.82%`。这支持“+711% 大部分不是简单 generic MA7 core”的结论，但不支持把差额全部归因给某一个 HYPE arm，因为 A→B 同时改变了多空非对称、OAPP、RSI、PEHC、cooldown/max-hold、forced reversal 与 trail 状态机。

仓库便携 V7.1 引擎在当前 445 日公共 API 窗口另得到 `+273.46%`，仅作同窗 portability supplement；它不能替代原注册 `+711.04%` 权威锚点。机器字段见 [summary.json](../artifacts/binance_1d_gma7t_v0_2026-08-18_summary.json)。

## 11. 时间切片

| Slice | 横截面中位收益 | 正收益占比 | 组合收益 | 组合 Sharpe |
| --- | ---: | ---: | ---: | ---: |
| 2024（部分年） | +7.43% | 71.43% | +11.49% | 1.256 |
| 2025 | -23.99% | 31.82% | -7.66% | -0.298 |
| 2026 YTD | +7.98% | 54.55% | +22.15% | 1.606 |
| 最近 1 年 | -12.38% | 31.82% | -0.73% | 0.062 |
| 2026Q3 至快照 | -7.15% | 22.73% | -6.14% | -4.652 |

2025 和最近一年明显失效，说明全窗正数不是跨时段稳定。完整逐币年/季度、recent slices 及聚合见 [period_slices.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_period_slices.csv) 与 [universe_period_summary.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_universe_period_summary.csv)。本策略没有训练或重选步骤，因此没有把 walk-forward 当作伪优化器；时间切片负责检查漂移，LOAO 负责检查资产依赖。

## 12. Parameter perturbation：稳定性，不选优

| Variant | Median Sharpe | Sharpe>0 | Portfolio Sharpe | Portfolio MDD |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 0.239 | 54.55% | 0.582 | -25.11% |
| MA 6 | 0.225 | 68.18% | 0.701 | -12.61% |
| MA 8 | 0.360 | 63.64% | 0.518 | -19.67% |
| ATR 6 | 0.129 | 54.55% | 0.467 | -25.65% |
| ATR 8 | 0.137 | 54.55% | 0.328 | -26.17% |
| slope 0.016 | 0.152 | 63.64% | 0.574 | -25.24% |
| slope 0.024 | 0.199 | 59.09% | 0.553 | -25.03% |
| exit 0.60 ATR | 0.210 | 63.64% | 0.608 | -25.05% |
| exit 0.90 ATR | 0.206 | 54.55% | 0.525 | -25.36% |
| stop 1.20 ATR | 0.018 | 50.00% | 0.112 | -25.42% |
| stop 1.80 ATR | 0.234 | 59.09% | 0.635 | -23.34% |

裁决标签：`PLATEAU_LIKE_WITH_PROTECTIVE_STOP_SENSITIVITY`。MA/slope/exit 邻域多数保持同号，但 stop 距离不是平坦高原。完整数据见 [perturbations.csv](../artifacts/binance_1d_gma7t_v0_2026-08-18_perturbations.csv)。

## 13. 可视化与可复现产物

- [交互式横截面分布与完整交易路径](../artifacts/binance_1d_gma7t_v0_2026-08-18_interactive_trade_paths.html)：22 币 Sharpe 分布、逐币 candle/SMA7、入出场连线、equity、完整交易表。
- [机器总结 JSON](../artifacts/binance_1d_gma7t_v0_2026-08-18_summary.json)；SHA-256 sidecar 同目录。
- [运行脚本](../scripts/research_binance_1d_generic_ma7_trend_v0.py) 与 [冻结配置](../configs/binance-1d-generic-ma7-trend-v0.json)。

复现命令：

```bash
uv run python research/asset-portfolios/1d-generic-ma7-trend/scripts/research_binance_1d_generic_ma7_trend_v0.py --run --workers 1 --force
uv run pytest -q tests/test_binance_1d_generic_ma7_trend_v0.py
```

## 14. 最终研究裁决与后继约束

`BIN-1D-GMA7T-V0` 保持 `explore / not promoted / not live-ready`。

下一阶段若继续，只允许新建预注册分支并取得新鲜数据，优先级是：

1. point-in-time historical market-cap universe 或固定上市可得集，降低 current-constituent survivorship；
2. 新鲜 prospective window，不再使用本轮币种/季度结果选参数；
3. 将 “long 可迁移、short 弱” 作为新假设，而不是直接删除亏损 short；
4. 在统一合同下验证更严格成本、portfolio turnover 与 funding mark 精度；
5. promotion 前至少要求多时段稳定、成本后多数资产正期望、组合 Sharpe/MDD 达标且 protective-stop 邻域不脆弱。

原 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1` 身份、参数、注册结果和结论均未修改。
