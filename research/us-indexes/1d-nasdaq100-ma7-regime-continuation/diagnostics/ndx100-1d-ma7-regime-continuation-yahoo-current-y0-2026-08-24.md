# Nasdaq-100 当前成分 Yahoo 日线 Y0 诊断

## 结论

Yahoo 当前成分诊断已完整运行，但**没有支持“ER 越高，MA7 突破后延续性越强”的跨市场稳定结构**：

- 当前 terminal snapshot 实际包含 `102` 条证券；连同 QQQ 共拉取 `103` 个 ticker、`405,060` 行日线，所有请求成功；
- `MA7` 共有 `77,066` 个事件，其中 long `38,555`、short `38,511`；
- long 在 `1/3/5/10/20/40D` 的无条件方向收益均值为 `+0.16%/+0.37%/+0.61%/+1.56%/+3.16%/+6.15%`；
- short 同期为 `-0.19%/-0.42%/-0.85%/-1.51%/-3.18%/-6.31%`，说明当前幸存科技股样本中的长期向上漂移压过了向下 MA7 cross；
- ER、Slope、RV 的 quintile 关系没有形成跨方向、跨 horizon、跨市场一致的平滑延续结构；pre-2020 / post-2020 三变量 surface 相关性也接近零；
- 因此 Y0 只证明 Yahoo 当前成分方案可以快速产生大样本诊断，不能替代 historical point-in-time P0，也不能据此判断历史 Nasdaq-100。

状态保持 `explore / diagnostic-only / survivorship-biased / not promoted / not live-ready`。

## 数据审计

| 项目 | 结果 |
| --- | ---: |
| Terminal snapshot | `2026-08-21` |
| 当前证券数 | `102` |
| 请求数（含 QQQ） | `103` |
| 成功 / 失败 | `103 / 0` |
| 日线行数 | `405,060` |
| 全局范围 | `2008-01-02` 至 `2026-08-21` |
| 有效 feature sessions | `355,863` |
| 重复 ticker-session | `0` |
| 非法 OHLCV | `0` |
| 非 XNAS session | `0` |
| 内部缺失 session | MNST `2026-08-10` 共 `1` 条 |

MNST 缺口在 feature engine 中产生新的连续 block，rolling feature 和 forward return 不跨缺口。`28` 条当前证券的 Yahoo 历史晚于 `2010-01-01` 开始，主要是后上市、分拆或新 ticker；这些证券只在有完整 warm-up 后进入事件样本。

主价格由 Yahoo raw OHLC 和 split events 重建 split-only 序列；含分红的 `Adj Close` 只保留作诊断，不参与主收益。缓存是 task-local untrusted evidence，不进入 canonical accepted 数据湖。

## 无条件 MA7 事件

| Direction | 1D | 3D | 5D | 10D | 20D | 40D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long | `+0.16%` | `+0.37%` | `+0.61%` | `+1.56%` | `+3.16%` | `+6.15%` |
| Short | `-0.19%` | `-0.42%` | `-0.85%` | `-1.51%` | `-3.18%` | `-6.31%` |

20D long 胜率为 `57.84%`，short 胜率只有 `41.89%`。这不是对称突破延续，而更接近 current-survivor universe 的正向市场漂移。

## 单变量结构

20D raw return 均值：

| Direction / variable | Q1 | Q2 | Q3 | Q4 | Q5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Long ER20 | `3.63%` | `3.12%` | `2.73%` | `3.05%` | `3.21%` |
| Short ER20 | `-3.86%` | `-3.20%` | `-2.55%` | `-3.16%` | `-3.05%` |
| Long Slope | `3.94%` | `3.87%` | `3.32%` | `2.00%` | `2.58%` |
| Short Slope | `-3.91%` | `-3.46%` | `-3.34%` | `-2.16%` | `-3.03%` |
| Long RV percentile | `2.33%` | `2.23%` | `2.39%` | `3.58%` | `5.02%` |
| Short RV percentile | `-2.33%` | `-2.29%` | `-2.66%` | `-3.38%` | `-5.17%` |

ER20 没有预期的单调提升。RV 的 raw-return 振幅随波动分位上升，但 long/short 同时沿市场上涨方向扩大，更像波动与正 drift 的结合；ATR-normalized 后关系明显变弱。Slope 对 long 甚至整体反向，不能解释为高斜率提升突破延续。

## 稳健性和 gap

- raw-return 三变量 surface 的 pre-2020 / post-2020 Spearman：long 各 horizon 为 `0.03–0.20`，short 为 `-0.14–0.09`，时间稳定性弱；
- MA5/7/10 surface 相关性约 `0.54–0.83`，说明相邻 MA 会产生相似事件结构，但没有修复时间不稳定或跨市场方向不一致；
- 去掉绝对 gap `>=1%` 后，20D long ER quintile 均值变为 `2.19%/2.21%/2.13%/2.79%/2.15%`，仍无单调结构；
- 大量三变量 cell 因样本巨大和市场 drift 达到显著，但显著性不能替代 smoothness、temporal stability 或 cross-market agreement。

## 与 Binance P0 对照

20D raw-return 的 Slope 极端分位：

| Market / direction | Q1 | Q5 | 方向 |
| --- | ---: | ---: | --- |
| Crypto long | `-4.07%` | `+0.82%` | 高 Slope 改善 |
| Yahoo-current NDX long | `+3.94%` | `+2.58%` | 高 Slope 反而减弱 |
| Crypto short | `+3.87%` | `-1.11%` | 高 Slope 恶化 |
| Yahoo-current NDX short | `-3.91%` | `-3.03%` | 全部分位受正 drift 压制 |

因此当前成分 Yahoo 股票端与 Crypto 端没有形成方向一致、稳定、可解释的 regime → MA7 continuation 关系。

## 边界与决定

1. Y0 使用今天仍在指数中的公司回填历史，明确存在 survivorship bias、listing-age bias 和 ticker-history 风险。
2. 结果不得写回 historical P0，不解除 Massive 历史权限和 point-in-time identifier audit 的 blocker。
3. 不因 Y0 结果调整 ER/Slope/RV 阈值、MA 周期或 gap 阈值。
4. 记录为可复现的快速诊断；不登记策略版本、不 promotion。

## 证据

- [Y0 合同](../specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-contract-2026-08-24.md)
- [价格审计](../artifacts/ndx100_1d_ma7_rc_y0_yahoo_price_audit.json)
- [研究摘要](../artifacts/ndx100_1d_ma7_rc_y0_summary.json)
- [单变量统计](../artifacts/ndx100_1d_ma7_rc_y0_single_variable_stats.csv)
- [三变量统计](../artifacts/ndx100_1d_ma7_rc_y0_three_way_stats.csv)
- [gap 诊断](../artifacts/ndx100_1d_ma7_rc_y0_gap_diagnostic.csv)
- [跨市场宽表](../artifacts/ndx100_1d_ma7_rc_y0_cross_market_single_variable_wide.csv)
- [下载脚本](../scripts/fetch_yahoo_current_ndx100_daily.py)
- [研究脚本](../scripts/research_ndx100_current_yahoo_1d_ma7_regime_continuation.py)
