# BTC/ETH 日线 MA7 分资产参数搜索与共享参数诊断

## Reclaim 的准确含义

`reclaim` 不是“价格一直在 MA7 上方就持续开仓”，而是一个离散的失而复得事件：

- long reclaim：`t-1` 收盘不高于入场带，`t` 收盘重新越过 MA7 入场带，并满足 MA7 正斜率；在 `t+1` open 做多；
- short reclaim：`t-1` 收盘不低于空头入场带，`t` 收盘重新跌破该带，并满足 MA7 负斜率；在 `t+1` open 做空。

搜索仍固定 `SMA7/ATR7`，但允许 regime、reclaim、pullback-reclaim、breakout 等 MA7 状态触发模式，并搜索其确认、持有和退出参数。

## 结论

参数搜索可以在 BTC、ETH 全历史上得到非常高的数字，但真正重要的是未参与选择的时间后段：

| Selection / target | Development `550d` | Exposed holdout `179d` | Full `729d` | Full MDD | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC asset-specific → BTC | `+125.11%` | `+0.06%` | `+125.24%` | `-19.67%` | `33` |
| ETH asset-specific → ETH | `+364.32%` | `-8.82%` | `+421.94%` | `-28.71%` | `26` |
| Shared → BTC | `+111.30%` | `+0.49%` | `+112.34%` | `-17.96%` | `28` |
| Shared → ETH | `+140.80%` | `+27.14%` | `+161.46%` | `-29.29%` | `24` |

因此：

1. BTC/ETH 都能在固定 MA7 下搜索到高历史收益；
2. 单资产最高收益主要集中在 development，BTC 后段近乎归零、ETH 后段转负，显示明显 selection fit；
3. 共享参数的后段表现优于单资产最高收益，但 ETH 的 `12h` 相位从 `+161.46%` 翻为 `-10.58%`；
4. 本次不能产生 registered version 或 promotion；共享参数只比单资产赢家更值得原样 prospective 观察。

## 搜索合同与证据角色

- 数据：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual accepted `1h`，聚合 UTC `1d`；
- 全窗口：`2024-07-31` 至 `2026-07-30 UTC` terminal open，共 `729d`；
- development：前 `550d`，截止 `2026-02-01` exclusive；
- researcher-exposed holdout：后 `179d`，不参与本次选择，但此前已被迁移报告查看，不是 clean OOS；
- 每方向固定 seed 抽样 `20,000` 个唯一配置；每资产每方向保留 `120` 个稳健候选，前 `20 × 20` 配对；
- 共享候选以 BTC/ETH development 最差侧的 stage-1、子窗口、`8 bps` 和额外延迟分数选择；
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、真实 event-time funding；压力 `8 bps/fill`；
- 所有选参只读取 development；没有按 holdout 或 phase 结果二次挑选。

完整合同见[搜索合同](../specs/binance-btc-eth-1d-ma7-search-contract-2026-08-05.md)。

## 分资产参数结构

### BTC asset-specific

- Long：`reclaim`；5 日 MA 斜率，`0.25 ATR` 入场带；退出确认 2 日、`1 ATR` 迟滞；无 hard stop / trailing / max-hold。
- Short：`pullback_reclaim`；5 日斜率、`0.10 ATR` 阈值；7 日回调结构；`5 ATR` hard stop、最长 10 日、冷却 2 日。
- 与 HYPE V1 相比，BTC 更依赖慢斜率、宽迟滞和较少的 trailing 干预。

### ETH asset-specific

- Long：`reclaim`；5 日斜率、`0.02 ATR` 阈值；`0.75 ATR` 退出迟滞；`3 ATR` hard stop、最长 20 日、冷却 3 日。
- Short：`reclaim`；2 日斜率、`0.05 ATR` 阈值、`0.25 ATR` 入场带；2 日退出确认、`1 ATR` 迟滞；`5 ATR` hard stop、`3 ATR` trailing、最长 20 日。
- ETH 需要比 HYPE 更宽的保护和更长的持有上限，但这些参数在时间后段没有保留收益。

### BTC/ETH shared

- Long 与 BTC asset-specific long 相同：慢 5 日斜率、`0.25 ATR` reclaim、2 日确认和 `1 ATR` 迟滞。
- Short：5 日斜率的 `pullback_reclaim`，`0.1 ATR` 入场带，`1.5 ATR` hard stop、`5 ATR` trailing、最长 10 日、冷却 2 日。

共享参数说明 MA7 核心可以形成共同开发解，但不等于已证明跨资产稳定。

## 单资产候选详细结果

| Target | Full base | `8 bps` | +1 day lag | Long-only | Short-only | Buy & hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | `+125.24%` | `+119.43%` | `+116.42%` | `+63.07%` | `+38.12%` | `-17.38%` |
| ETH | `+421.94%` | `+411.53%` | `+235.30%` | `+95.90%` | `+79.38%` | `-51.15%` |

这些 full stress 数字仍包含 development，且 stress / delay 已进入 development 选择目标，不能当独立稳健性证明。

Holdout：

| Target | Base | `8 bps` | +1 day lag | Trades |
| --- | ---: | ---: | ---: | ---: |
| BTC asset-specific | `+0.06%` | `-0.58%` | `+7.80%` | `8` |
| ETH asset-specific | `-8.82%` | `-9.40%` | `-14.63%` | `8` |

BTC 的优势在 holdout 消失；ETH 在三种执行假设下都亏损。ETH full 比 development 与 flat-start holdout 的简单复合更高，部分原因是 full 路径保留了跨越切分点的既有持仓；不能用 full 覆盖 holdout 失败。

## 共享参数结果

| Target | Full base | Full MDD | `8 bps` | +1 day lag | Holdout base | Holdout `8 bps` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | `+112.34%` | `-17.96%` | `+107.67%` | `+155.15%` | `+0.49%` | `-0.07%` |
| ETH | `+161.46%` | `-29.29%` | `+156.55%` | `+182.32%` | `+27.14%` | `+26.54%` |

共享参数在 ETH holdout 保留正收益，但 BTC 仍近乎持平；holdout 分别只有 `7 / 6` 笔，且历史已揭示。

## 日界相位

| Selection / target | `0h` | `12h` | 判断 |
| --- | ---: | ---: | --- |
| BTC asset-specific → BTC | `+125.24%` | `+50.23%` | 保持正收益，但只保留约 40% |
| ETH asset-specific → ETH | `+421.94%` | `+19.74%` | 只保留约 4.7%，失败 |
| Shared → BTC | `+112.34%` | `+69.29%` | 两相位为正 |
| Shared → ETH | `+161.46%` | `-10.58%` | 符号翻转，失败 |

ETH 是当前共同 blocker。MA7 的视觉状态并未消失，但信号与成交日对 UTC 日界高度敏感。

## 滚动窗口与近期

滚动 `180d`、每 `60d` 前进：

- BTC asset-specific → BTC：`10/10` 为正，中位 `+28.23%`、最低 `+5.25%`；
- ETH asset-specific → ETH：`10/10` 为正，中位 `+49.82%`、最低 `+14.73%`；
- Shared → BTC：`10/10` 为正，中位 `+25.37%`、最低 `+5.82%`；
- Shared → ETH：`7/10` 为正，中位 `+19.65%`、最低 `-16.08%`。

这些窗口高度重叠，并且大部分属于 development；不能替代 holdout。

最近 `1y`：

- BTC asset-specific → BTC：`+34.01%`；
- ETH asset-specific → ETH：`+47.86%`；
- Shared → BTC/ETH：`+39.40% / +9.56%`。

最近 `7d` 四条目标 route 均为负，近期切片只用于 audit。

## 与原 HYPE 迁移失败的关系

原 HYPE 参数直迁失败不代表 MA7 在 BTC/ETH 上无用，而是说明：

- HYPE 的快 reclaim、短斜率、特定 trailing/退出组合不适合 BTC/ETH；
- BTC/ETH development 更偏好 5 日斜率、宽退出迟滞和不同的保护层；
- 但是单资产搜索后的 holdout 衰减说明“为每个资产重新调参”很容易再次制造 HYPE 式的历史赢家；
- 共享参数比单资产最高收益更可信一些，但 ETH 相位翻负，仍不能称为通用策略。

## 决策

1. 记录单资产 full 历史上限：BTC `+125.24%`，ETH `+421.94%`。
2. 以 holdout 为主要诊断：BTC `+0.06%`，ETH `-8.82%`，单资产路线不登记。
3. 共享参数保留为优先 prospective observation，但不按当前 ETH phase 结果继续修改。
4. 不把本次搜索结果回写 HYPE V1 或零调参迁移家族，不推进 runner。

## 证据

- [机器摘要](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_summary_2026-08-05.json)
- [单边候选前沿](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_frontier_2026-08-05.csv)
- [组合候选](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_pairs_2026-08-05.csv)
- [窗口、成本与延迟指标](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_metrics_2026-08-05.csv)
- [相位审计](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_phase_2026-08-05.csv)
- [滚动 180 日](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_rolling_180d_2026-08-05.csv)
- [近期切片](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_recent_2026-08-05.csv)
- [逐笔交易](../artifacts/binance_btc_eth_1d_ma7_asset_specific_search_trades_2026-08-05.csv)
- [复现脚本](../scripts/search_binance_btc_eth_1d_ma7_asset_specific.py)
