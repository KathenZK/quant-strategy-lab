# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1 完整复现规格 - 2026-07-07

## 给同事 / AI 的使用说明

这份文件是 `Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1` 的完整复现规格。目标是：同事把本文件交给他的 AI 后，可以在本仓库内复现同一条 V1 交易路径、同一组近期分片指标和同一个 `NO-GO` 判断。

最短复现命令：

```bash
uv run python research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_single_position_backtest.py
```

复现脚本会输出并落盘：

- 汇总 JSON：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_2026-07-07.json`
- 小时权益曲线：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_equity_2026-07-07.csv`
- 中选交易：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_trades_2026-07-07.csv`

## 版本身份

- Full version：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble-V1`
- Short id：`BIN-1H-AR-MAE-V1`
- Family：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`
- Market：Binance USD-M Futures perpetual
- Symbols：`TRXUSDT`、`SOLUSDT`、`HYPEUSDT`、`ETHUSDT`、`BTCUSDT`、`BNBUSDT`
- Timeframe：`1h`
- Status：`registered diagnostic single-position version / NO-GO / not promoted / not live-ready`

`V1` 是一个账户级组合策略：六个已登记的单资产 `1h adaptive-regime` 策略同时生成候选交易，但全账户同一时间只允许一笔持仓。它不是实盘候选，也不是 paper-live / dry-run / handoff 版本。

## 复现环境与数据边界

- 仓库根目录：`/Users/ZK/OpenCode/quant-strategy-lab`
- Python 入口：使用 `uv run python ...`
- 组合脚本：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_mae_single_position_backtest.py`
- 成分 loader 脚本：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py`
- 组合窗口：`2024-08-17T06:00:00Z -> 2026-07-02T03:00:00Z`
- HYPE sleeve 起点：`2025-07-14T10:00:00Z`，此前 HYPE 不参与候选交易。
- 费用：`0.001` fee/fill
- 滑点：`0.0004` adverse slippage/fill，即 `4 bps`
- Funding：每个 sleeve 逐笔计入 Binance 历史 funding。
- 数据质量：各成分家族 loader 自带数据质量校验；任一成分数据质量漂移或主账指标漂移，组合脚本应直接失败。

## 成分版本清单

V1 固定使用以下成分版本，不随未来单资产版本升级自动变化：

| Asset | Symbol | 成分版本 | 机制 | 成分主账 current-full 校验 |
| --- | --- | --- | --- | --- |
| TRX | `TRXUSDT` | `TRX-1H-Adaptive-Regime-V3` | `macd_flip + stoch_reversal` | `5.686x / -17.17% DD / 92.47% win / 93 trades` |
| SOL | `SOLUSDT` | `SOL-1H-Adaptive-Regime-V2` | `donchian_break + vwap_revert` | `2.07x / -17.41% DD / 93.91% win / 115 trades` |
| HYPE | `HYPEUSDT` | `HYPE-1H-Adaptive-Regime-V4` | `di_cross + stoch_reversal` | `22.8128x / -19.11% DD / 81.08% win / 74 trades` |
| ETH | `ETHUSDT` | `ETH-1H-Adaptive-Regime-V3` | `bb_break + rsi_reversal` | `3.3084x / -15.70% DD / 95.65% win / 46 trades` |
| BTC | `BTCUSDT` | `BTC-1H-Adaptive-Regime-V4` | `keltner_break + cci_reversal` | `5.27x / -17.47% DD / 86.49% win / 74 trades` |
| BNB | `BNBUSDT` | `BNB-1H-Adaptive-Regime-V3` | `ema_pullback + wick_reject` | `2.94x / -18.24% DD / 88.33% win / 120 trades` |

## 账户级组合规则

候选交易生成：

1. 每个 asset sleeve 先独立运行其家族冻结策略，得到各自已合并后的单资产交易路径。
2. 只保留 `sleeve["start"] <= trade.entry_ts < sleeve["end"]` 的交易。
3. 组合候选池为六个 sleeve 的交易并集；本次候选交易数应为 `522`。

账户级单仓选择：

1. 将候选交易按以下 key 排序：

```python
(
    trade.entry_ts,
    -TIE_PRIORITY[asset],
    trade.exit_ts,
)
```

2. `TIE_PRIORITY` 固定如下：

```json
{
  "HYPE": 22.8128,
  "TRX": 5.686,
  "BTC": 5.27,
  "ETH": 3.3084,
  "BNB": 2.94,
  "SOL": 2.07
}
```

3. 从排序后的候选池顺序扫描：
   - 如果当前没有持仓，选中该交易。
   - 选中交易后，设置 `blocked_until = trade.exit_ts`。
   - 若后续候选交易 `entry_ts <= blocked_until`，直接跳过。
   - 只有当 `entry_ts > blocked_until` 时，才允许开下一笔。
4. 新信号不会抢仓，不会提前平当前持仓。
5. 中选交易占用全账户权益，并按原 sleeve 冻结的 `fixed_leverage` / `exposure` 执行。
6. 阻塞只移除候选交易，不改变中选交易的 entry、exit、价格、费用、滑点或 funding。

选择统计应为：

```json
{
  "candidate_trades": 522,
  "selected_trades": 371,
  "skipped_blocked": 151,
  "same_hour_entry_ties": 22,
  "per_asset_candidates": {
    "TRX": 93,
    "SOL": 115,
    "HYPE": 74,
    "ETH": 46,
    "BTC": 74,
    "BNB": 120
  },
  "per_asset_selected": {
    "TRX": 70,
    "SOL": 78,
    "HYPE": 54,
    "ETH": 33,
    "BTC": 51,
    "BNB": 85
  },
  "avg_exposure": 2.5954177897574127,
  "max_exposure": 5.0,
  "median_hold_hours": 7.0,
  "in_position_hours_pct": 0.3555718028392128
}
```

重要近似：本 V1 复现脚本没有在跨资产阻塞后重新逐 K 重演各 sleeve 的 cooldown / 内部状态机。它是“先生成每个 sleeve 的冻结交易路径，再做账户级阻塞筛选”。因此它是 diagnostic backtest，不是可直接实盘的联合状态机。

## 权益曲线构造

中选交易按全账户权益复利：

```python
equity = 1.0
for asset, trade in selected:
    # 持仓中用 bar close 做 mark-to-market
    mark_return = close_i / trade.entry_price - 1.0
    equity_mark = equity * (1.0 + trade.exposure * trade.side * mark_return)

    # 出场时用 sleeve 冻结交易的 equity_ret 对齐，equity_ret 已包含费用、滑点和 funding
    equity *= 1.0 + trade.equity_ret
```

窗口指标使用权益曲线重定基：

- `total_return = final_equity - 1`
- `annual_multiple = final_equity ** (365.25 / days)`
- `max_dd = min(equity / equity.cummax() - 1)`

逐笔胜率和 PF 使用中选交易的 `trade.equity_ret`。

## 成分参数总表

以下参数是 V1 复现所需的冻结参数。若同事使用本仓库脚本复现，优先调用脚本；若独立实现，需要按本节参数和各家族执行契约重建信号。

### TRX-1H-Adaptive-Regime-V3

来源：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_trx`
- 成分脚本：`research/trx/1h-adaptive-regime/scripts/trx_1h_ar_v3_clean.py`
- 成分版本：`TRX-1H-Adaptive-Regime-V3`

MACD flip leg：

```json
{
  "ema_htf": 89,
  "roc_window": 6,
  "macd_fast": 34,
  "macd_slow": 89,
  "macd_signal": 13,
  "min_adx": 20.0,
  "max_adx": 24.0,
  "min_rvol": 0.0,
  "max_atr_bps": 150.0,
  "min_dir_roc_bps": -100.0,
  "max_dist_ema_bps": 10000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "tp_atr": 2.0,
  "sl_atr": 5.0,
  "max_hold_bars": 120,
  "cooldown_bars": 3,
  "entry_delay_bars": 1,
  "fixed_leverage": 5.0
}
```

Stochastic reversal leg：

```json
{
  "side_mode": "both",
  "ema_htf": 233,
  "indicator_window": 21,
  "threshold_low": 25.0,
  "threshold_high": 90.0,
  "roc_window": 3,
  "max_adx": 24.0,
  "min_rvol": 1.0,
  "min_dir_roc_bps": -300.0,
  "require_body_dir": true,
  "sl_atr": 6.0,
  "trail_activation_atr": 3.0,
  "trail_atr": 2.0,
  "max_hold_bars": 120,
  "cooldown_bars": 6,
  "entry_delay_bars": 2,
  "fixed_leverage": 3.5
}
```

### SOL-1H-Adaptive-Regime-V2

来源：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_sol`
- 成分版本：`SOL-1H-Adaptive-Regime-V2`
- Ensemble 优先级：使用高胜率搜索覆写后的 `engine.prefit_score(train, validation, prefit)` 动态计算。

Donchian break leg：

```json
{
  "name": "SOL_1H_AR_HW_R132002",
  "style": "donchian_break",
  "side_mode": "both",
  "ema_fast": 144,
  "ema_slow": 233,
  "ema_htf": 377,
  "indicator_window": 24,
  "threshold_low": 25.0,
  "threshold_high": 75.0,
  "band_k": 1.5,
  "pullback_atr": 0.25,
  "roc_window": 24,
  "roc_threshold_bps": 50.0,
  "macd_fast": 34,
  "macd_slow": 89,
  "macd_signal": 13,
  "min_adx": 36.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 100.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": 100.0,
  "max_dist_ema_bps": 750.0,
  "htf_mode": "none",
  "require_macd_turn": true,
  "require_body_dir": false,
  "max_aligned_funding_bps": 2.0,
  "exit_kind": "fixed",
  "tp_atr": 0.75,
  "sl_atr": 4.0,
  "trail_activation_atr": 0.75,
  "trail_atr": 0.5,
  "max_hold_bars": 120,
  "cooldown_bars": 0,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 3.0,
  "risk_fraction": 0.01,
  "max_leverage": 2.5
}
```

VWAP revert leg：

```json
{
  "name": "SOL_1H_AR_HW_R243705",
  "style": "vwap_revert",
  "side_mode": "short",
  "ema_fast": 34,
  "ema_slow": 55,
  "ema_htf": 89,
  "indicator_window": 48,
  "threshold_low": 30.0,
  "threshold_high": 70.0,
  "band_k": 1.25,
  "pullback_atr": 0.25,
  "roc_window": 72,
  "roc_threshold_bps": 50.0,
  "macd_fast": 8,
  "macd_slow": 21,
  "macd_signal": 5,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 0.0,
  "min_atr_bps": 125.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 1000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": true,
  "max_aligned_funding_bps": 1.0,
  "exit_kind": "fixed",
  "tp_atr": 0.75,
  "sl_atr": 3.0,
  "trail_activation_atr": 1.0,
  "trail_atr": 1.25,
  "max_hold_bars": 18,
  "cooldown_bars": 3,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 1.5,
  "risk_fraction": 0.01,
  "max_leverage": 1.5
}
```

### HYPE-1H-Adaptive-Regime-V4

来源：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_hype`
- 成分版本：`HYPE-1H-Adaptive-Regime-V4`
- 单资产内部 merge：`DI` 优先级 `1.0`，`Stoch` 优先级 `0.0`；同一时段冲突时 DI 优先。

DI engine config：

```json
{
  "name": "HYPE_1H_AR_V4_DI",
  "style": "di_cross",
  "side_mode": "both",
  "ema_fast": 8,
  "ema_slow": 55,
  "ema_htf": 89,
  "indicator_window": 20,
  "threshold_low": 20.0,
  "threshold_high": 80.0,
  "band_k": 0.5,
  "pullback_atr": 0.0,
  "roc_window": 24,
  "roc_threshold_bps": 25.0,
  "macd_fast": 8,
  "macd_slow": 21,
  "macd_signal": 5,
  "min_adx": 10.0,
  "max_adx": 100.0,
  "min_rvol": 2.0,
  "min_atr_bps": 0.0,
  "max_atr_bps": 250.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 10000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "fixed",
  "tp_atr": 1.5,
  "sl_atr": 4.5,
  "trail_activation_atr": 1.0,
  "trail_atr": 1.0,
  "max_hold_bars": 18,
  "cooldown_bars": 0,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 3.0,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

Stoch engine config：

```json
{
  "name": "HYPE_1H_AR_V4_STOCH",
  "style": "stoch_reversal",
  "side_mode": "both",
  "ema_fast": 8,
  "ema_slow": 55,
  "ema_htf": 55,
  "indicator_window": 21,
  "threshold_low": 25.0,
  "threshold_high": 55.0,
  "band_k": 0.5,
  "pullback_atr": 0.0,
  "roc_window": 12,
  "roc_threshold_bps": 25.0,
  "macd_fast": 8,
  "macd_slow": 55,
  "macd_signal": 5,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 200.0,
  "max_atr_bps": 500.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 10000.0,
  "htf_mode": "none",
  "require_macd_turn": true,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "trailing",
  "tp_atr": 1.0,
  "sl_atr": 4.0,
  "trail_activation_atr": 1.0,
  "trail_atr": 1.0,
  "max_hold_bars": 8,
  "cooldown_bars": 36,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.0,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

### ETH-1H-Adaptive-Regime-V3

来源：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_eth`
- 成分脚本：`research/eth/1h-adaptive-regime/scripts/eth_1h_ar_v2_1_clean.py`
- 成分版本：`ETH-1H-Adaptive-Regime-V3`

BB break clean config（含硬编码字段）：

```json
{
  "ema_htf": 55,
  "indicator_window": 72,
  "band_k": 2.5,
  "roc_window": 24,
  "min_adx": 16.0,
  "min_rvol": 3.5,
  "min_atr_bps": 75.0,
  "min_dir_roc_bps": 200.0,
  "max_dist_ema_bps": 750.0,
  "max_aligned_funding_bps": 8.0,
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "max_hold_bars": 72,
  "fixed_leverage": 1.5
}
```

RSI reversal clean config：

```json
{
  "ema_htf": 233,
  "indicator_window": 7,
  "threshold_low": 5.0,
  "threshold_high": 75.0,
  "roc_window": 6,
  "min_adx": 20.0,
  "max_adx": 45.0,
  "min_atr_bps": 125.0,
  "min_dir_roc_bps": -300.0,
  "max_dist_ema_bps": 750.0,
  "tp_atr": 2.0,
  "sl_atr": 3.0,
  "max_hold_bars": 48,
  "cooldown_bars": 24,
  "fixed_leverage": 2.5
}
```

### BTC-1H-Adaptive-Regime-V4

来源：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_btc`
- 成分脚本：`research/btc/1h-adaptive-regime/scripts/btc_1h_ar_v4.py`
- 成分版本：`BTC-1H-Adaptive-Regime-V4`

Keltner engine config（含中和值固定字段）：

```json
{
  "indicator_window": 20,
  "band_k": 2.0,
  "roc_window": 24,
  "min_adx": 40.0,
  "min_rvol": 1.25,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "htf_mode": "h4",
  "max_aligned_funding_bps": 10000.0,
  "tp_atr": 1.5,
  "sl_atr": 5.0,
  "max_hold_bars": 100000,
  "cooldown_bars": 0,
  "fixed_leverage": 2.4
}
```

CCI engine config（含中和值固定字段）：

```json
{
  "ema_htf": 377,
  "indicator_window": 20,
  "threshold_high": 125.0,
  "max_adx": 40.0,
  "min_rvol": 1.25,
  "min_atr_bps": 75.0,
  "max_atr_bps": 10000.0,
  "max_dist_ema_bps": 750.0,
  "tp_atr": 5.5,
  "sl_atr": 1.5,
  "max_hold_bars": 72,
  "cooldown_bars": 0,
  "fixed_leverage": 3.5
}
```

### BNB-1H-Adaptive-Regime-V3

来源：

- Loader：`research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py::load_bnb`
- 成分参数源：`research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v2_micro_tune_2026-07-07.json`
- 成分版本：`BNB-1H-Adaptive-Regime-V3`
- 单资产内部 merge priorities：`[2.445774012147314, 1.6307399812929821]`

EMA pullback leg：

```json
{
  "name": "BNB_1H_AR_V2_EMA_PULLBACK_T00405",
  "style": "ema_pullback",
  "side_mode": "both",
  "ema_fast": 55,
  "ema_slow": 144,
  "ema_htf": 377,
  "indicator_window": 14,
  "threshold_low": 0.0,
  "threshold_high": 100.0,
  "band_k": 0.0,
  "pullback_atr": -0.25,
  "roc_window": 12,
  "roc_threshold_bps": 0.0,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "min_adx": 0.0,
  "max_adx": 100.0,
  "min_rvol": 1.0,
  "min_atr_bps": 50.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 300.0,
  "htf_mode": "none",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "trailing",
  "tp_atr": 3.0,
  "sl_atr": 5.0,
  "trail_activation_atr": 2.0,
  "trail_atr": 1.5,
  "max_hold_bars": 240,
  "cooldown_bars": 12,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.5,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

Wick reject leg：

```json
{
  "name": "BNB_1H_AR_V2_WICK_REJECT_T01080",
  "style": "wick_reject",
  "side_mode": "both",
  "ema_fast": 21,
  "ema_slow": 144,
  "ema_htf": 55,
  "indicator_window": 14,
  "threshold_low": 0.4,
  "threshold_high": 0.75,
  "band_k": 0.5,
  "pullback_atr": 0.0,
  "roc_window": 12,
  "roc_threshold_bps": 0.0,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "min_adx": 28.0,
  "max_adx": 100.0,
  "min_rvol": 2.0,
  "min_atr_bps": 0.0,
  "max_atr_bps": 10000.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 100000.0,
  "htf_mode": "h12",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 10000.0,
  "exit_kind": "fixed",
  "tp_atr": 1.0,
  "sl_atr": 5.0,
  "trail_activation_atr": 100000.0,
  "trail_atr": 100000.0,
  "max_hold_bars": 48,
  "cooldown_bars": 24,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 1.0,
  "risk_fraction": 0.01,
  "max_leverage": 1.0
}
```

## 期望复现结果

完整复现后，`artifacts/binance_1h_ar_mae_single_position_2026-07-07.json` 中关键字段应匹配：

```json
{
  "selection": {
    "candidate_trades": 522,
    "selected_trades": 371,
    "skipped_blocked": 151,
    "same_hour_entry_ties": 22
  },
  "portfolio_windows": {
    "full": {
      "total_return": 39997.48077136025,
      "annual_multiple": 287.0119873095173,
      "max_dd": -0.21432509786924225,
      "trades": 371,
      "win_rate": 0.9029649595687331,
      "profit_factor": 6.86244478871941
    },
    "reused_holdout": {
      "total_return": 0.6531227010452689,
      "annual_multiple": 7.668775716212575,
      "max_dd": -0.1978707715933925,
      "trades": 42,
      "win_rate": 0.7857142857142857,
      "profit_factor": 2.3099514371238765
    },
    "last_7d": {
      "total_return": 0.004589559404015953,
      "max_dd": -0.15919886664826977,
      "trades": 3
    },
    "last_1m": {
      "total_return": 0.5818212790113322,
      "max_dd": -0.15919886664826965,
      "trades": 19
    },
    "last_3m": {
      "total_return": 0.6601388609659042,
      "max_dd": -0.1978707715933926,
      "trades": 42
    },
    "last_6m": {
      "total_return": 10.893542680444234,
      "max_dd": -0.21432509786924214,
      "trades": 101
    },
    "last_1y": {
      "total_return": 133.15394114272962,
      "max_dd": -0.21432509786924225,
      "trades": 212
    }
  }
}
```

## 结论与验证注意事项

验证有效性时必须同时验证收益和失败边界：

1. V1 能复现高全期收益，但 full、`last_6m`、`last_1y` 最大回撤均为 `-21.43%`，穿破 `<20%` 硬门槛。
2. reused holdout 为正，但最大回撤 `-19.79%` 几乎贴线，且不是 fresh OOS。
3. V1 是冻结 sleeve 交易路径上的账户级阻塞筛选，不是完整联合状态机；promotion 前必须逐 K 重演跨资产阻塞后的 cooldown / 状态机。
4. 成分策略全部仍是 diagnostic NO-GO；组合登记不改变任何成分家族的 live-readiness。

因此，正确复现的最终判断应是：`registered diagnostic / NO-GO / not promoted / not live-ready`。
