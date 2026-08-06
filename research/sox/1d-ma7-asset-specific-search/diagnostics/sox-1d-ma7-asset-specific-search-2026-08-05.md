# SOX 日线 MA7 共享参数控制与分资产搜索诊断

## 结论

1. BTC/ETH 共享参数在 `^SOX` 全历史 combined 为 `-2.96%`、MDD `-77.49%`；`10 bps/fill` 后为 `-58.48%`，额外延迟一 session 后为 `-41.16%`。共享版本失败。
2. 固定 `SMA7/ATR7` 后，SOX 专属搜索找到了绝对正收益候选：development-selected combined 在未参与选择的 2021+ 后段为 `+111.06%`，全历史为 `+200.29%`。
3. 这不等于找到了可接受策略。该候选在 2010 年前为 `-79.36%`，全历史 MDD 为 `-93.47%`，而 buy-and-hold 为 `+9,725.06%`；全历史年化仅约 `3.47%`。
4. 结论是“能搜到正收益状态机”，不是“SOX MA7 已稳健有效”。不登记、不 promotion、不 live-ready。

## 数据与合同

- 数据：Yahoo Finance `^SOX` raw session OHLC，`1994-05-04` 至 `2026-08-04`，共 `8,117` 个 sessions，数据质量 blocker 为 `0`。
- `^SOX` 是不可直接交易的价格指数；主结果为零成本路径诊断，`10 bps/fill` 仅是示意摩擦。
- 收盘信号在下一 session open 执行；open gap 穿越 stop 按 open，日内 high/low 触发按 stop。
- 搜索固定 MA 长度 `7` 和 ATR 长度 `7`，每方向 seed `20260805` 抽样 `8,000` 个配置。
- 只用 `2010-01-04` 至 `2021-01-04` exclusive 选择参数。2010 年前是 backward audit；2021+ 是未参与本次选择、但已被研究者查看过的 holdout。
- 完整冻结条件见[搜索合同](../specs/sox-1d-ma7-asset-specific-search-contract-2026-08-05.md)。

## BTC/ETH 共享参数零调参结果

| Window | Base | MDD | `10 bps/fill` | 延迟一 session | Buy-and-hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2010 年前 backward | `-49.34%` | `-77.49%` | `-66.77%` | `-57.13%` | `+202.20%` |
| 2010–2020 development | `+78.77%` | `-40.01%` | `+35.00%` | `+40.12%` | `+675.23%` |
| 2021+ exposed holdout | `+5.47%` | `-48.02%` | `-9.10%` | `-1.89%` | `+319.38%` |
| Full | `-2.96%` | `-77.49%` | `-58.48%` | `-41.16%` | `+9,725.06%` |

共享 long 产生的收益被 short 持续侵蚀：全历史共享参数交易中 long 累计贡献约 `+192.31%` 初始权益，short 约 `-195.26%`。它在 2010 后尚可描述部分上升趋势，但无法覆盖完整 SOX 历史结构。

## SOX 专属 combined 参数

### 多头

- Entry mode：`pullback_reclaim`。
- 趋势：`SMA7[t]-SMA7[t-1] >= 0.05*ATR7[t]`。
- 确认：连续 `3` 个收盘都高于各自 `SMA7+0.10*ATR7`。
- Pullback：当前信号前 `3` 个 sessions 内至少一次收盘不高于 `SMA7+0.25*ATR7`；随后满足确认，下一 session open 做多。
- 退出：一次收盘低于 `SMA7-1.00*ATR7` 后次开退出；另有 `4.0*ATR7` trailing、最长 `20` sessions。
- 无 hard stop、无 slope exit；退出后冷却 `1` session。

### 空头

- Entry mode：`reclaim` 的空头方向，即前一 session 收盘仍在 `SMA7` 上方或附近，当前收盘跌到 `SMA7-0.10*ATR7` 以下。
- 趋势：`SMA7[t] <= SMA7[t-7]`；确认 `1` session，下一 session open 做空。
- 退出：连续 `3` 个收盘高于 `SMA7+0.10*ATR7`，或 `SMA7[t] >= SMA7[t-5]`，均在次开退出。
- 保护：`2.0*ATR7` hard stop、`1.5*ATR7` trailing、最长 `10` sessions、冷却 `1` session。

多空同日都满足时多头优先；单仓、约 `1x`、非加仓。

## SOX 专属 combined 结果

| Window | Base | MDD | Trades | `10 bps/fill` | 延迟一 session | Buy-and-hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2010 年前 backward | `-79.36%` | `-93.47%` | `226` | `-86.88%` | `-65.77%` | `+202.20%` |
| 2010–2020 development | `+584.29%` | `-28.31%` | `146` | `+411.38%` | `+594.10%` | `+675.23%` |
| 2021+ exposed holdout | `+111.06%` | `-32.21%` | `75` | `+81.67%` | `+83.81%` | `+319.38%` |
| Full | `+200.29%` | `-93.47%` | `447` | `+22.79%` | `+339.55%` | `+9,725.06%` |

Full 的 Sharpe 为 `0.261`、profit factor 为 `1.177`、年化因子为 `1.0347`。447 笔中 long `299` 笔，累计约 `+216.60%` 初始权益；short `148` 笔，累计约 `-16.31%`。正收益仍主要来自多头。

## Long-only 对照

Development-selected long-only 使用更明确的深 pullback 后恢复：两日 SMA7 上升至少 `0.05*ATR7`，过去 7 sessions 曾收在 `SMA7-0.25*ATR7` 以下，当前收回 `SMA7+0.25*ATR7` 以上；退出为连续 3 收盘低于 `SMA7-0.50*ATR7`、`4.0*ATR7` hard stop、`5.0*ATR7` trailing 或最长 30 sessions。

| Window | Base | MDD | `10 bps/fill` | 延迟一 session |
| --- | ---: | ---: | ---: | ---: |
| 2010 年前 backward | `-28.85%` | `-88.82%` | `-47.29%` | `-69.00%` |
| Development | `+431.57%` | `-27.39%` | `+336.08%` | `+393.88%` |
| 2021+ exposed holdout | `+62.12%` | `-41.25%` | `+45.52%` | `+103.44%` |
| Full | `+482.33%` | `-88.82%` | `+217.68%` | `+199.44%` |

Long-only 的全历史绝对收益高于 combined，但同样具有不可接受的早期回撤和严重 timing sensitivity；仍远逊于 buy-and-hold。

## 稳定性

- Combined：33 个逐年窗口中 `22` 个为正；30 个滚动三年窗口中 `20` 个为正，中位 `+28.67%`，最差 `-82.34%`。
- Long-only：33 年中 `19` 年为正；30 个滚动三年中 `18` 个为正，最差 `-49.57%`。
- Short-only：全历史 `-43.25%`，MDD `-68.73%`；30 个滚动三年窗口仅 `12` 个为正。
- Combined 最近 `1m/3m/6m/1y` 分别为 `+5.50%/+14.88%/+1.31%/+11.07%`；这些切片只用于 audit。
- 交易所 session 日线没有可平移的 12h/phase 数据；phase gate 缺失，不能记作通过。

## 判定

搜索回答了“能否找到正收益”：能，尤其在 2010 年后的样本中。

但作为策略判定仍失败：

1. backward regime 几乎摧毁权益；
2. full MDD 达 `-93.47%`；
3. 所有候选都大幅跑输 buy-and-hold；
4. short 没有独立长期 edge；
5. 指数不可交易，缺少真实 instrument、成本、借券与日内执行合同；
6. 没有 clean prospective OOS。

因此保留为 `explore / not promoted / not live-ready`，不登记版本。

## 证据

- [机器摘要](../artifacts/sox_1d_ma7_asset_specific_search_summary_2026-08-05.json)
- [候选前沿](../artifacts/sox_1d_ma7_asset_specific_search_frontier_2026-08-05.csv)
- [配对排名](../artifacts/sox_1d_ma7_asset_specific_search_pairs_2026-08-05.csv)
- [窗口指标](../artifacts/sox_1d_ma7_asset_specific_search_metrics_2026-08-05.csv)
- [逐年窗口](../artifacts/sox_1d_ma7_asset_specific_search_calendar_years_2026-08-05.csv)
- [滚动三年](../artifacts/sox_1d_ma7_asset_specific_search_rolling_3y_2026-08-05.csv)
- [近期切片](../artifacts/sox_1d_ma7_asset_specific_search_recent_2026-08-05.csv)
- [完整交易](../artifacts/sox_1d_ma7_asset_specific_search_trades_2026-08-05.csv)
- [复现脚本](../scripts/search_sox_1d_ma7_asset_specific.py)
