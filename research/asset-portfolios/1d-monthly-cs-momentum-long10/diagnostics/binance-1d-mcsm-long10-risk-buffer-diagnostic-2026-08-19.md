# BIN-1D-MCSM-L10 20% 波动目标与 10/20 缓冲诊断（2026-08-19）

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 市场与窗口：Binance USD-M USDT 永续，`2020-03-01`–`2026-06-30` UTC，76 次月度换仓
- 成本：手续费 `0.001/边` + 不利滑点 `0.0004/边`；逐日计入实际资金费
- 冻结改动：Top10 → 20% 组合目标波动 → gross 上限 100% → 10/20 持仓缓冲
- 契约：[binance-1d-mcsm-long10-risk-buffer-diagnostic-contract-2026-08-19.md](../specs/binance-1d-mcsm-long10-risk-buffer-diagnostic-contract-2026-08-19.md)

## 结论

固定 20% 组合目标波动是实质性改善：全上市版本最大回撤从 `-93.79%` 降至 `-42.33%`，年化波动从 `100.95%` 降至 `22.39%`，同时保留 `+217.36%` 净收益和 `20.01%` CAGR。ADV 版本 MDD 进一步为 `-39.12%`，净收益 `+219.58%`。

代价同样明确：原始 Top10 的 `+2402.97%` 主要来自承担极高风险；缩放后平均 gross 只有约 `22%`，CAGR 从 `66.31%` 回落到 `20.01%`，Sharpe 也从 `1.009` 小幅降到 `0.926`。风险缩放没有创造 alpha，只是把已有风险收益压到更可承受的尺度。

10/20 缓冲没有进一步改善组合。全上市缓冲版年化换手从 `4.58x` 降至 `4.17x`，但净收益降至 `+199.18%`、Sharpe 降至 `0.885`，MDD反而微增至 `-42.55%`。因此本轮判断为：**保留20%风险缩放作为有价值观察；不把10/20缓冲认定为改善。**

## 核心结果

| 宇宙 / 配置 | 净收益 | CAGR | 年化波动 | Sharpe | 最大回撤 | 月胜率 | 年化换手 | 平均 gross |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 全上市 Top10 baseline | +2402.97% | 66.31% | 100.95% | 1.009 | -93.79% | 46.05% | 20.29x | 100.00% |
| 全上市 Top10 target20 | **+217.36%** | **20.01%** | 22.39% | **0.926** | **-42.33%** | 57.89% | 4.58x | 22.12% |
| 全上市 buffer10/20 target20 | +199.18% | 18.90% | 22.38% | 0.885 | -42.55% | 52.63% | **4.17x** | 22.12% |
| ADV Top10 baseline | +2104.80% | 63.01% | 101.56% | 0.991 | -92.99% | 44.74% | 20.07x | 100.00% |
| ADV Top10 target20 | **+219.58%** | **20.15%** | 22.37% | **0.932** | **-39.12%** | 55.26% | 4.51x | 21.98% |
| ADV buffer10/20 target20 | +193.62% | 18.55% | 22.40% | 0.871 | -40.00% | 51.32% | **4.06x** | 21.93% |

目标是 20% 而实现波动约 22.4%，原因是风险系数只在月初更新并整月冻结，无法提前消除月内跳空和波动突增；成本与资金费也进入净收益波动。风险系数从未超过 1，实际全上市 target20 月度系数范围为 `12.41%–36.59%`，中位数 `21.47%`，满足无杠杆约束。

## 缓冲实际做了什么

全上市原始 Top10 相邻月平均重合 `1.56` 个名字；10/20 缓冲提高到 `2.37` 个，ADV 从 `1.65` 提高到 `2.53` 个。它确实增加了持仓连续性，但没有达到低换手策略：全上市样本中没有一个月能把全部十个名字原样保留。

缩放后全上市年化换手的边际变化为：

| 配置 | 年化换手 | Fees 算术和 | Slippage 算术和 |
| --- | ---: | ---: | ---: |
| target20 | 4.58x | -0.0290 | -0.0116 |
| buffer10/20 target20 | 4.17x | -0.0264 | -0.0106 |

成本节省约不足净值的 `0.4` 个算术百分点，而缓冲保留的排名 11–20 标的削弱了价格腿：Price PnL 算术和从 `+1.1313` 降至 `+1.0688`。因此缓冲带来的交易节省不足以抵消信号稀释。

## 分年结果

| 年 | 全上市 baseline | 全上市 target20 | 全上市 buffer target20 | ADV target20 |
| --- | ---: | ---: | ---: | ---: |
| 2020（3–12月） | +104.84% | +27.49% | +22.14% | +24.08% |
| 2021 | +1095.45% | +68.68% | +69.59% | +67.14% |
| 2022 | -85.10% | **-32.28%** | -32.62% | **-31.70%** |
| 2023 | +69.05% | +26.67% | +33.03% | +32.59% |
| 2024 | -9.69% | +10.89% | +8.26% | +10.80% |
| 2025 | -8.78% | +13.32% | +8.64% | +13.32% |
| 2026 H1 | +392.41% | +36.92% | +37.01% | +35.53% |

风险缩放大幅缓和了2022年，但 `-32%` 单年亏损仍然不轻。全上市 target20 的最大回撤从 `2021-11-25` 开始，于 `2023-08-31` 触底，并到 `2025-09-27` 才恢复；最长水下约 `1401` 天。绝对 MDD改善不等于路径已经稳定。

## 最近切片

切片锚定数据末日 `2026-06-30`，只作审计，不参与规则选择。

| 切片 | 全上市 target20 | 全上市 buffer target20 |
| --- | ---: | ---: |
| 1d | -0.51% | -0.57% |
| 7d | +0.17% | -0.05% |
| 1m | +8.23% | +7.99% |
| 3m | +25.84% | +25.84% |
| 6m | +36.10% | +36.19% |
| 1y | +69.86% | +68.98% |

样本尾端仍是强势区间，不能用最近一年再次上涨证明未来稳定性。

## PnL attribution

下表是每日收益贡献算术和；净收益是每日 Total 复利结果。

| 配置 | Price PnL | Funding | Fees | Slippage | 复利净收益 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 全上市 target20 | +1.1313 | +0.2231 | -0.0290 | -0.0116 | +217.36% |
| 全上市 buffer target20 | +1.0688 | +0.2229 | -0.0264 | -0.0106 | +199.18% |
| ADV target20 | +1.1097 | +0.2509 | -0.0286 | -0.0114 | +219.58% |
| ADV buffer target20 | +1.0154 | +0.2568 | -0.0257 | -0.0103 | +193.62% |

## 方法限制与裁决

- 20%目标使用 trailing 90 日未缩放组合价格波动，至少60日；共享引擎采用额外一日保守滞后，最后纳入收益截至换仓前第二个UTC日。
- 月度固定风险系数不是连续波动控制，实际波动不会精确等于20%。
- 线性回测不模拟逐合约保证金、强平、盘口容量和月初拥挤冲击；固定4 bps仍可能低估极端月份成交成本。
- 所有历史已经揭示；不能把 target20 的改善称为 clean OOS，也不能据此继续搜索15%、18%、22%、25%目标。
- 结果维持 `explore / diagnostic-only / not promoted / not live-ready`，不登记版本。

## 证据与复现

- 汇总：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-summary.json](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-summary.json)
- 全指标：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-metrics.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-metrics.csv)
- Attribution：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-attribution.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-attribution.csv)
- 持仓：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-holdings.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-holdings.csv)
- 月度风险系数：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-monthly-scales.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-monthly-scales.csv)
- 日路径：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-daily-paths.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-daily-paths.csv)
- 分年：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-yearly.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-yearly.csv)
- 最近切片：[binance-1d-mcsm-long10-risk-buffer-2026-08-19-recent-slices.csv](../artifacts/binance-1d-mcsm-long10-risk-buffer-2026-08-19-recent-slices.csv)
- 脚本：[research_binance_1d_mcsm_long10_risk_buffer.py](../scripts/research_binance_1d_mcsm_long10_risk_buffer.py)

```bash
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_risk_buffer.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_risk_buffer.py --run-date 2026-08-19 --force
```
