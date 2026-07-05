# ETH-1H-Adaptive-Regime-V1 Canonical Baseline Spec

## 版本身份

- 完整名称：`ETH-1H-Adaptive-Regime-V1`。
- 家族：`ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）。
- 市场：Binance USD-M Futures `ETHUSDT` perpetual `1h`。
- 状态：`registered diagnostic baseline / NO-GO / not promoted / not live-ready`。
- 版本来源：首轮 `600,768` 组配置的 prefit 冻结冠军；不是根据最近三个月 OOS 反向选择。

V1 的登记只冻结可复现身份，不代表达到用户要求的 `10x / >=50% / DD<20% / 可实盘` 门槛。

## 数据与切分

- 原始闭合 K：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，共 `17,520` 根。
- warmup 后 train：`2024-08-17T05:00:00Z` 至 `2025-09-07T07:24:00Z`。
- validation：`2025-09-07T07:24:00Z` 至 `2026-04-03T05:00:00Z`。
- prefit：`2024-08-17T05:00:00Z` 至 `2026-04-03T05:00:00Z`。
- locked OOS：`2026-04-03T05:00:00Z` 至 `2026-07-03T05:00:00Z`。
- 数据质量：missing/duplicate/null/OHLCV violation/raw-normalized mismatch/未闭合 K 误收均为 `0`。

## 执行契约

- 闭合 `1h` K 生成信号，`K+1 open` 市价成交；单仓，不加仓。
- 入场后立即挂 ATR stop/TP；同 K 同时触发 stop 与 target 时按 stop-first。
- stop 跳空穿越按该 K open 成交；固定持仓超时按 open 平仓。
- 组件同时争抢仓位时，按各组件 prefit score 降序优先；持仓期间忽略重叠信号。
- fee：`0.001`/fill；slippage：`4 bps`/fill；计入 Binance 历史资金费。

## 冻结组件

### BB breakout leg

```json
{
  "style": "bb_break",
  "side_mode": "long",
  "ema_fast": 13,
  "ema_slow": 34,
  "ema_htf": 89,
  "indicator_window": 72,
  "threshold_low": 40.0,
  "threshold_high": 85.0,
  "band_k": 2.0,
  "pullback_atr": 0.25,
  "roc_window": 12,
  "roc_threshold_bps": 50.0,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "min_adx": 16.0,
  "max_adx": 100.0,
  "min_rvol": 2.0,
  "min_atr_bps": 75.0,
  "max_atr_bps": 250.0,
  "min_dir_roc_bps": -200.0,
  "max_dist_ema_bps": 750.0,
  "htf_mode": "none",
  "require_macd_turn": false,
  "require_body_dir": false,
  "max_aligned_funding_bps": 2.0,
  "exit_kind": "fixed",
  "tp_atr": 3.0,
  "sl_atr": 2.5,
  "trail_activation_atr": 0.75,
  "trail_atr": 0.75,
  "max_hold_bars": 18,
  "cooldown_bars": 0,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 2.5,
  "risk_fraction": 0.015,
  "max_leverage": 3.0
}
```

### RSI reversal leg

```json
{
  "style": "rsi_reversal",
  "side_mode": "both",
  "ema_fast": 55,
  "ema_slow": 233,
  "ema_htf": 89,
  "indicator_window": 21,
  "threshold_low": 15.0,
  "threshold_high": 60.0,
  "band_k": 1.5,
  "pullback_atr": 0.0,
  "roc_window": 3,
  "roc_threshold_bps": 100.0,
  "macd_fast": 21,
  "macd_slow": 55,
  "macd_signal": 9,
  "min_adx": 0.0,
  "max_adx": 45.0,
  "min_rvol": 0.0,
  "min_atr_bps": 100.0,
  "max_atr_bps": 600.0,
  "min_dir_roc_bps": 50.0,
  "max_dist_ema_bps": 750.0,
  "htf_mode": "none",
  "require_macd_turn": false,
  "require_body_dir": true,
  "max_aligned_funding_bps": 2.0,
  "exit_kind": "fixed",
  "tp_atr": 3.0,
  "sl_atr": 2.0,
  "trail_activation_atr": 0.75,
  "trail_atr": 2.0,
  "max_hold_bars": 12,
  "cooldown_bars": 6,
  "entry_delay_bars": 1,
  "sizing_kind": "fixed",
  "fixed_leverage": 1.0,
  "risk_fraction": 0.03,
  "max_leverage": 4.0
}
```

## 冻结指标

| Window | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `2.8190x` | `199.08%` | `-16.29%` | `72.46%` | `69` |
| validation | `2.7959x` | `79.54%` | `-11.43%` | `69.70%` | `33` |
| prefit | `2.8109x` | `436.97%` | `-16.29%` | `71.57%` | `102` |
| locked OOS | `0.5196x` | `-15.05%` | `-20.87%` | `14.29%` | `7` |
| current full | `2.2462x` | `356.15%` | `-20.87%` | `67.89%` | `109` |

## 复现与边界

```bash
uv run python research/eth/1h-adaptive-regime/scripts/eth_1h_ar_v1.py
```

配置证据：`research/eth/1h-adaptive-regime/artifacts/eth_1h_ar_v1_config_2026-07-03.json`。V1 的 locked OOS 年化、胜率和回撤均失败，因此不得称为 candidate、paper-live、dry-run、handoff 或 live。

## 登记后消融与微调边界

- 全参数消融：`78/78` 字段槽；clean interface 保留 `33` 个 active 参数并与本 spec 逐笔完全等价。
- clean tuned observation 虽改善 prefit 与 current full 的收益/回撤，但 reused holdout 收益仍为负。
- 该 observation 不修改本 canonical spec，不登记为 V1.1/V2；详见 `../ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md` 与 `../research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md`。
