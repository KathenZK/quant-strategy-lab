# BIN-1D-MCSM-L10 月度 Top10 Long-only 全历史诊断（2026-08-18）

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 市场：Binance USD-M USDT 永续；完整点时全市场月档 `2020-01`–`2026-06`
- 评估：`2020-03-01`–`2026-06-30` UTC，76 次月度换仓
- 规则：月初开盘等权做多上一个完整日历月涨幅最高的 10 个合资格合约，总 gross 100%，不做空
- 成本：手续费 `0.001/边` + 不利滑点 `0.0004/边`；逐日计入实际资金费
- 契约：[binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md](../specs/binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md)

## 结论

只做多 Top10 后，横截面强势延续终于表现出明显的历史收益优势：全上市版本净收益 `+2402.97%`、CAGR `66.31%`、Sharpe `1.009`；`ADV≥1000万` 版本净收益 `+2104.80%`、CAGR `63.01%`、Sharpe `0.991`。两者都显著高于 Top3、全市场等权和同期 BTC/ETH buy-and-hold。

但它仍不是可直接交易的策略。全上市与 ADV 版本最大回撤分别为 `-93.79%/-92.99%`，2022 年分别亏 `-85.10%/-85.93%`。净值在 `2021-11-25` 达到历史高点，随后到 `2025-08-02` 发生最大回撤；截至样本末仍分别低于旧高 `26.82%/20.44%`，没有完全恢复。

因此本轮证明的是：

> Binance 永续上“1M 相对最强的十个合约”历史上存在可观的 long-only 延续收益，但原始 100% gross、无风险缩放版本的路径风险不可接受。

它纠正了此前“整个横截面都没有优势”的过度结论，但不能纠正为“已经稳定可交易”。

## 全区间结果

BTC/ETH 价格基准不计资金费和交易成本，用于复现原诊断基准；永续基准与 Top10 使用相同的资金费和进出成本。

| 配置 | 净收益 | CAGR | 年化波动 | Sharpe | 最大回撤 | 月胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 全上市 Top10 long-only | **+2402.97%** | **66.31%** | 100.95% | **1.009** | -93.79% | 46.05% |
| ADV≥1000万 Top10 long-only | **+2104.80%** | **63.01%** | 101.56% | **0.991** | -92.99% | 44.74% |
| 全上市 Top3 long-only control | -87.87% | -28.34% | 139.00% | 0.434 | -99.42% | 44.74% |
| ADV≥1000万 Top3 long-only control | -86.72% | -27.31% | 138.45% | 0.441 | -99.23% | 44.74% |
| 全市场合资格合约月度等权 | +28.87% | 4.09% | 84.70% | 0.488 | -89.81% | 42.11% |
| BTC 价格 buy-and-hold | +586.42% | 35.57% | 61.23% | 0.810 | -76.67% | 55.26% |
| ETH 价格 buy-and-hold | +620.82% | 36.62% | 81.83% | 0.798 | -79.35% | 51.32% |
| BTC 永续 long-only | +236.02% | 21.10% | 61.25% | 0.625 | -78.93% | 52.63% |
| ETH 永续 long-only | +213.00% | 19.75% | 81.72% | 0.637 | -79.98% | 48.68% |

Top10 相对 Top3 的改善不是来自更高月胜率，而是来自把单币极端波动分散到 10 个名字，并保留少数非常强的趋势月份。月胜率仍低于 50%，收益分布高度右偏。

## PnL attribution

下表为每日收益贡献的算术和；最后一列是每日 Total 复利后的账户净收益。

| 配置 | Price PnL | Funding | Fees | Slippage | Total 算术和 | 复利净收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 全上市 Top10 | +5.5612 | +1.0764 | -0.1286 | -0.0514 | +6.4576 | +2402.97% |
| ADV≥1000万 Top10 | +5.3562 | +1.1989 | -0.1272 | -0.0509 | +6.3770 | +2104.80% |

价格腿本身为正，资金费也贡献正 carry；这与多空版本的 short 腿毁损不同。年化换手约 `20.29x/20.07x`，资金费覆盖 `99.27%/99.47%`。

## 分年稳定性

| 年 | 全上市 Top10 | ADV≥1000万 Top10 | BTC 价格 | ETH 价格 |
| --- | ---: | ---: | ---: | ---: |
| 2020（3–12月） | +104.84% | +74.16% | +239.10% | +238.15% |
| 2021 | **+1095.45%** | **+1039.14%** | +59.61% | +398.65% |
| 2022 | **-85.10%** | **-85.93%** | -64.21% | -67.46% |
| 2023 | +69.05% | +103.10% | +155.87% | +90.94% |
| 2024 | -9.69% | -10.16% | +121.08% | +46.09% |
| 2025 | -8.78% | -8.78% | -6.35% | -10.97% |
| 2026 H1 | **+392.41%** | **+374.40%** | -33.11% | -47.10% |

优势并不稳定地逐年出现。2021 和 2026H1 贡献了大部分终值，2022 的单年亏损足以让实际账户接近失去继续运行的能力。2024–2025 连续两年为负，不能把全期 CAGR 当成平滑收益能力。

## 回撤与月度尾部

- 全上市历史高点：`2021-11-25`，权益 `34.20x`；最大回撤谷底：`2025-08-02`，MDD `-93.79%`；期末权益 `25.03x`，仍未回到旧高。
- ADV 历史高点：`2021-11-25`，权益 `27.71x`；最大回撤谷底同为 `2025-08-02`，MDD `-92.99%`；期末权益 `22.05x`。
- 全上市最佳月：`2021-03 +140.22%`；最差月：`2022-04 -47.32%`。
- 最近一年：全上市 `+798.94%`、ADV `+766.05%`，但两者期间最大回撤仍为 `-54.52%`。

最近一年与 2026H1 的暴涨说明样本尾端再次进入强山寨趋势期，也是全期结果对尾段敏感的直接证据。

## 币池变化与可执行性

- `2020-03` 全上市只有 11 个合资格合约，Top10 几乎等于全市场；首月持仓为 `LINK,ETH,XRP,XLM,BTC,TRX,ADA,LTC,EOS,BCH`。
- 到 `2026-06` 全上市合资格数为 640，ADV 版本为 183；两者 Top10 均为 `LAB,PORTAL,UB,HOME,H,ALLO,VVV,BEAT,COLLECT,MU`。
- 后期 Top10 主要是高波动山寨和新热点。即使 ADV≥1000 万，固定 4 bps 滑点仍可能低估月初集中换仓冲击。
- 单日最差收益约 `-41.85%/-42.55%`。本回测没有逐合约强平，但总 gross 仅 100%，不存在原多空 200% gross 的结构性额外杠杆。

## 为什么这次能看到横截面优势

1. 去掉 short 后，不再承受 loser 反弹和 short squeeze 的无限上行损失。
2. 从 Top3 扩到 Top10，单个妖币的权重从 `33.3%` 降至 `10%`。
3. 1M 强者延续的少数大月份得以保留，而亏损月份的单名冲击被分散。
4. Funding 对 long Top10 在本样本中是正贡献，不再与价格腿方向相抵。

但“横截面排序有历史 edge”与“策略稳定”仍是两件事。`100%` 年化波动和 `93%` 回撤说明必须另行解决组合风险，不能用高终值掩盖路径破产问题。

## 股票永续是否纳入（2026-08-19 更正）

此前这里把“外部现货美股全市场”和“Binance 原生股票永续”混为一谈，结论不准确。这个回测不按资产类别排除 Binance USD-M 合约，因此 Binance 上市的股票/TradFi 永续在形成期数据足够后会与加密永续一起排序。实际持仓已经证明这一点：`MU` 在 `2026-06-01` 的 1M 信号为 `+95.52%`、全市场排名第 10，被全上市与 ADV Top10 同时买入并持有至 `2026-06-30`。

`SNDK` 与 `SKHYNIX` 没有持有，不是因为它们是股票，而是样本结束前没有足够形成期：`SNDK` 的本地数据始于 `2026-05-01`，缺少 `2026-04-30` 端点；`SKHYNIX` 始于 `2026-06-12`，连 `2026-06-01` 换仓日都尚未上市。完整审计见[宽度诊断](binance-1d-mcsm-long-breadth-diagnostic-2026-08-19.md)。

只有在另行加入 Binance 之外的现货美股全市场时，才至少需要：

- 每月可交易的 NYSE/Nasdaq 点时股票清单，包含退市股票；
- 拆股、分红、并购与退市收益的调整口径；
- 美股交易日历、月初成交时点和单独的股票手续费/滑点；
- 先决定加密 24/7 与美股交易时段如何对齐，以及是否允许两类资产直接争夺同一个 Top10 名额。

在这些条件满足前，只能确认 Binance 合约池 Long10（其中可含 Binance 原生股票永续），不能声称已经验证独立的现货美股全市场横截面策略。

## 证据与复现

- 汇总：[binance-1d-mcsm-long10-diagnostic-2026-08-18-summary.json](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-summary.json)
- 全指标：[binance-1d-mcsm-long10-diagnostic-2026-08-18-metrics.csv](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-metrics.csv)
- Attribution：[binance-1d-mcsm-long10-diagnostic-2026-08-18-attribution.csv](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-attribution.csv)
- 换仓：[binance-1d-mcsm-long10-diagnostic-2026-08-18-holdings.csv](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-holdings.csv)
- 日路径：[binance-1d-mcsm-long10-diagnostic-2026-08-18-daily-paths.csv](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-daily-paths.csv)
- 分年：[binance-1d-mcsm-long10-diagnostic-2026-08-18-yearly.csv](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-yearly.csv)
- 最近切片：[binance-1d-mcsm-long10-diagnostic-2026-08-18-recent-slices.csv](../artifacts/binance-1d-mcsm-long10-diagnostic-2026-08-18-recent-slices.csv)
- 脚本：[research_binance_1d_mcsm_long10.py](../scripts/research_binance_1d_mcsm_long10.py)

```bash
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10.py --run-date 2026-08-18 --force
```

## 状态

`explore / diagnostic-only / not promoted / not live-ready`。本轮不登记版本；Top10 的高收益是已揭示历史，不得直接作为 clean OOS 候选。
