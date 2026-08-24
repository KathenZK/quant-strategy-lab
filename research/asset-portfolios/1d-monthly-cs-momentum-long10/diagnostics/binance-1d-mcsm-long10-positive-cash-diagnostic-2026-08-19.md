# BIN-1D-MCSM-L10 正收益限定与现金缺口诊断（2026-08-19）

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 窗口：`2020-03-01`–`2026-06-30` UTC，76次月度换仓
- 规则：Top10中仅买上月形成收益严格 `>0` 的名字，每个仍为10%；空缺持现金，Top10全非正则整月空仓
- 成本：手续费 `0.001/边` + 不利滑点 `0.0004/边`；逐日资金费；现金收益为0
- 契约：[binance-1d-mcsm-long10-positive-cash-diagnostic-contract-2026-08-19.md](../specs/binance-1d-mcsm-long10-positive-cash-diagnostic-contract-2026-08-19.md)

## 先回答：有没有 Top10 全负的月份

有，但全样本只有 **1个月：`2020-04-01` 换仓**。这次信号来自2020年3月全球风险资产暴跌：

- 全上市 Top10 的上月形成收益范围为 `-23.97%` 至 `-32.80%`；
- ADV Top10 的范围为 `-24.23%` 至 `-38.98%`；
- 正收益限定版因此在4月整月持有现金，但仍承担3月旧仓在4月1日退出的极小成本。

这个月也展示了绝对动量门槛的典型代价：原始全上市 Top10 在2020年4月反弹 `+28.66%`，空仓版约 `-0.02%`，完全错过V形反弹。

## 正收益数量分布

| 正收益名字数 | 全上市月份 | ADV月份 | 现金比例 |
| ---: | ---: | ---: | ---: |
| 0 | 1 | 1 | 100% |
| 2 | 1 | 1 | 80% |
| 3 | 2 | 2 | 70% |
| 4 | 1 | 3 | 60% |
| 5 | 2 | 1 | 50% |
| 7 | 2 | 2 | 30% |
| 8 | 1 | 2 | 20% |
| 9 | 3 | 3 | 10% |
| 10 | **63** | **61** | 0% |

全上市只有13/76个月会改变仓位，ADV为15/76个月；平均正收益名字数分别为 `9.22/9.11`。全上市最后一次触发是 `2023-01`，ADV另在 `2024-05` 触发一次。此后直到样本末，Top10全部为正，所以最近切片与原策略完全相同。

## 核心结果

| 宇宙 / 配置 | 净收益 | CAGR | 年化波动 | Sharpe | 最大回撤 | 月胜率 | 年化换手 | 平均 gross |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 全上市 baseline | +2402.97% | 66.31% | 100.95% | 1.009 | -93.79% | 46.05% | 20.29x | 100.00% |
| 全上市 positive-cash | **+3629.90%** | **77.13%** | 95.99% | **1.070** | -91.43% | 47.37% | 19.13x | 92.28% |
| 全上市 target20 | +217.36% | 20.01% | 22.39% | 0.926 | -42.33% | 57.89% | 4.58x | 22.12% |
| 全上市 positive-cash target20 | **+245.39%** | **21.63%** | 23.50% | **0.950** | **-41.61%** | 59.21% | 4.72x | 22.54% |
| ADV baseline | +2104.80% | 63.01% | 101.56% | 0.991 | -92.99% | 44.74% | 20.07x | 100.00% |
| ADV positive-cash | **+3088.09%** | **72.79%** | 95.07% | **1.045** | -90.25% | 46.05% | 18.87x | 91.08% |
| ADV target20 | +219.58% | 20.15% | 22.37% | **0.932** | **-39.12%** | 55.26% | 4.51x | 21.98% |
| ADV positive-cash target20 | +218.78% | 20.10% | 23.44% | 0.898 | -40.56% | 56.58% | 4.70x | 22.56% |

未缩放版本在两个宇宙都改善了终值、Sharpe和MDD，但 MDD 仍为 `-90%` 左右，依旧不可接受。与当前更有意义的 target20 对照时，结果不一致：

- 全上市：净收益增加 `28.03` 个百分点，CAGR提高 `1.62` 个百分点，MDD改善 `0.72` 个百分点；
- ADV：净收益略降 `0.80` 个百分点，Sharpe从 `0.932` 降至 `0.898`，MDD恶化 `1.44` 个百分点；最长水下期由 `834` 天扩大至 `1383` 天。

因此不能把它认定为稳健改进。它对少数历史危机月份的权重调整有效，但对宇宙定义敏感，而且样本只有13–15个实际触发月。

## 发生了什么

绝对动量门槛同时做了两件相反的事：

1. 避开部分延续下跌。例如全上市 `2020-03` 从原始 `-32.35%` 缓和到 `-6.11%`，`2021-06` 从 `-23.06%` 缓和到 `-14.94%`。
2. 错过崩跌后的反弹。最明显的是 `2020-04`：原始组合 `+28.66%`，现金版约为0。

全期改善主要是这些少数月份路径复利的结果，不是每个月都产生的新alpha。2024–2026H1全上市版本完全没有触发，近期收益也完全没有变化。

## 分年结果

| 年 | 全上市 baseline | 全上市 positive-cash | 全上市 target20 | 全上市 positive-cash target20 |
| --- | ---: | ---: | ---: | ---: |
| 2020（3–12月） | +104.84% | +96.29% | +27.49% | +31.41% |
| 2021 | +1095.45% | +1247.78% | +68.68% | +75.91% |
| 2022 | -85.10% | -79.56% | -32.28% | -31.53% |
| 2023 | +69.05% | +70.06% | +26.67% | +26.84% |
| 2024 | -9.69% | -9.69% | +10.89% | +10.89% |
| 2025 | -8.78% | -8.78% | +13.32% | +13.32% |
| 2026 H1 | +392.41% | +392.41% | +36.92% | +36.92% |

## PnL attribution

| 配置 | Price PnL | Funding | Fees | Slippage | 复利净收益 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 全上市 positive-cash | +5.5861 | +1.0941 | -0.1212 | -0.0485 | +3629.90% |
| 全上市 positive-cash target20 | +1.2409 | +0.2156 | -0.0299 | -0.0120 | +245.39% |
| ADV positive-cash | +5.2529 | +1.2129 | -0.1196 | -0.0478 | +3088.09% |
| ADV positive-cash target20 | +1.1346 | +0.2407 | -0.0298 | -0.0119 | +218.78% |

## 裁决

- “Top10全负则空仓”确实会触发，但76个月只有1次；它不是主要风险控制来源。
- “只买正收益名字、其余现金”在未缩放版本表现更好，但仍无法解决约90% MDD。
- 叠加target20后只有全上市小幅改善，ADV反向变差，缺乏跨宇宙稳健性。
- 不继续搜索门槛，不登记、不晋升；当前仍以原 Top10 target20 作为较简单的风险缩放观察对照。

## 证据与复现

- 汇总：[binance-1d-mcsm-long10-positive-cash-2026-08-19-summary.json](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-summary.json)
- 全指标：[binance-1d-mcsm-long10-positive-cash-2026-08-19-metrics.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-metrics.csv)
- 正收益月份：[binance-1d-mcsm-long10-positive-cash-2026-08-19-positive-months.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-positive-months.csv)
- Attribution：[binance-1d-mcsm-long10-positive-cash-2026-08-19-attribution.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-attribution.csv)
- 持仓：[binance-1d-mcsm-long10-positive-cash-2026-08-19-holdings.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-holdings.csv)
- 日路径：[binance-1d-mcsm-long10-positive-cash-2026-08-19-daily-paths.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-daily-paths.csv)
- 分年：[binance-1d-mcsm-long10-positive-cash-2026-08-19-yearly.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-yearly.csv)
- 最近切片：[binance-1d-mcsm-long10-positive-cash-2026-08-19-recent-slices.csv](../artifacts/binance-1d-mcsm-long10-positive-cash-2026-08-19-recent-slices.csv)
- 脚本：[research_binance_1d_mcsm_long10_positive_cash.py](../scripts/research_binance_1d_mcsm_long10_positive_cash.py)

```bash
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_positive_cash.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_positive_cash.py --run-date 2026-08-19 --force
```
