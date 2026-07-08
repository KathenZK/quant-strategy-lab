# HYPE-EMA-TB-V40 可复现参数说明（观察候选）

日期：2026-07-08

本文档登记 `HYPE-EMA-Trend-Breakout-V40`。V40 = V39 主仓 + V37 标准 early-long 小仓卫星。V40 当前是观察候选，不是 live-ready 版本。

## 版本身份

```text
V39 = V35 + long_vol_min 0.35
          + short_target_atr_pct 0.022
          + 移除冗余空头 1h EMA 确认
          + 保留 max_hold_bars=384 timeout 兜底

V40 = V39 主仓 + V37 标准 early-long 卫星
```

不要把本文档与 `HYPE-Candle-Count-Reversal` 的同名版本号混用。本文档只对应 Binance HYPEUSDT 永续 `15m` 的 `HYPE-EMA-TB` 趋势突破族。

## 数据与成本口径

| 项目 | 值 |
| --- | --- |
| 市场 | Binance USD-M 永续 |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-08 05:30 UTC` |
| 数据质量 | 38765 根已闭合 K 线，缺口 0、重复 0、OHLCV 关键空值 0 |
| Funding | Binance funding，对齐持仓区间 |
| 成本 | `0.00085`/fill，表示手续费与 4 bps adverse slippage 合并口径，主仓与卫星各自开平各一次 |

## 组合执行口径

```yaml
portfolio:
  main_leg: V39
  satellite_leg: V37 标准 early-long
  overlap_allowed: true
  compounding: per-bar main return + satellite return, then compound
  signal_bar: K0 15m close
  entry_execution: K2 open
```

主仓与卫星可以重叠持仓。回测组合权益用逐根主仓收益和卫星收益相加后复利；上线前必须审计组合持仓、订单冲突、保证金和重启恢复。

## 主仓：V39

```yaml
main_leg:
  entry:
    long:
      ema_spread_min: 0.0
      adx_min: 28
      volume_surge_min: 0.35
      h1_adx21_gt: 18
      h1_plus_di_gt_h1_minus_di: true
    short:
      ema_spread_max: 0.0
      adx_min: 36
      volume_surge_min: 0.50
      one_hour_ema_confirm: removed
  sizing:
    long_target_atr_pct: 0.020
    short_target_atr_pct: 0.022
    max_allocation: 3.0
  exits:
    take_profit_atr: 5.0
    hard_stop_atr: 7.0
    adx_exit: 22
    delayed_bars: 3
    disable_after_mfe_atr: 1.5
    max_hold_bars: 384
```

## 卫星：V37 Canonical Early-Long

卫星只做多，专门处理主仓 ADX28 尚未确认、但 ADX14 已强势启动的上涨早期。

```yaml
satellite_leg:
  direction: long_only
  entry:
    ema_spread_min: 0.0
    volume_surge_min: 0.25
    h1_adx21_gt: 18
    h1_plus_di_gt_h1_minus_di: true
    adx28_lt: 28
    adx14_min: 35
    adx14_rising: true
    plus_di14_gt_minus_di14: true
  sizing:
    target_atr_pct: 0.008
    max_allocation: 1.0
  exits:
    take_profit_atr: 4.0
    hard_stop_atr: 5.0
    weak_exit: adx14 < 22
    weak_exit_execution: next_bar_open
```

卫星量能门槛保留 V37 canonical 的 `volume_surge >= 0.25`，不跟随 V39 主仓上调到 `0.35`。测试显示 `sat_v035` 结果略差；尝试补回 V39 量能缺口的 `sat_gap` 被否决。

## 回测摘要

| 版本 | full收益 | full maxDD | Sharpe | 开单量 | 胜率 | 3m收益 | 6m收益 | 1y收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V39 | +9969.45% | -23.46% | 4.81 | 107 | 79.44% | +217.53% | +1802.57% | +11342.95% |
| V37 复现（V35+卫星） | +10316.90% | -24.76% | 4.85 | 150 | 72.67% | +257.27% | +2017.23% | +11407.69% |
| V40 | +12322.33% | -24.76% | 4.91 | 149 | 73.15% | +259.76% | +2058.51% | +13621.22% |

## 分片开单量

按 `entry_ts` 落入窗口统计：

| 窗口 | 收益 | maxDD | 开单量 | 主腿 | 卫星 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1d | +0.00% | +0.00% | 0 | 0 | 0 |
| 7d | +9.94% | -14.60% | 3 | 3 | 0 |
| 1m | +23.17% | -24.76% | 11 | 7 | 4 |
| 3m | +259.76% | -24.76% | 49 | 35 | 14 |
| 6m | +2058.51% | -24.76% | 90 | 68 | 22 |
| 1y | +13621.22% | -24.76% | 145 | 104 | 41 |
| full | +12322.33% | -24.76% | 149 | 107 | 42 |

## 当前状态

- 状态：观察候选。
- 决策：按用户指定登记为 `HYPE-EMA-TB-V40`。
- live-readiness：未通过，不得标记为 live、paper-live、dry-run 或 handoff。
- 上线前 blocker：Hyperliquid/OKX 跨所同窗迁移检查、walk-forward 验证、主仓+卫星组合持仓审计、订单冲突审计、TP/SL reduce-only 挂单审计、重启恢复审计、缺失数据处理审计。

## 证据

- 研究报告：`../notes/hype-ema-tb-v39-v37-satellite-2026-07-08.md`
- 复现脚本：`../scripts/research_hype_ema_tb_v39_v37_satellite.py`
- 汇总 JSON：`../artifacts/hype_ema_tb_v39_v37_satellite_2026-07-08.json`
- 逐笔 CSV：`../artifacts/hype_ema_tb_v39_v37_satellite_trades_2026-07-08.csv`
- 权益曲线 CSV：`../artifacts/hype_ema_tb_v39_v37_satellite_equity_2026-07-08.csv`
