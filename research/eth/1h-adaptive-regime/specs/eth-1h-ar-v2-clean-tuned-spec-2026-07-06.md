# ETH-1H-Adaptive-Regime-V2 Clean Tuned Spec

## 版本身份

- 完整名称：`ETH-1H-Adaptive-Regime-V2`。
- 家族：`ETH-1H-Adaptive-Regime`（`ETH-1H-AR`）。
- 市场：Binance USD-M Futures `ETHUSDT` perpetual `1h`。
- 状态：`registered tuned observation / NO-GO / not promoted / not live-ready`。
- 版本来源：V1 全参数消融后 `29` 参数 clean interface 的 prefit-only 微调观察值；最近三个月 reused holdout 不参与参数选择。

V2 的登记只冻结可复现身份，不代表达到用户要求的 `10x / >=50% / DD<20% / 可实盘` 门槛。

## 数据、切分与成本

- 原始闭合 K：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，共 `17,520` 根。
- warmup 后 train：`2024-08-17T05:00:00Z` 至 `2025-09-07T07:24:00Z`。
- validation：`2025-09-07T07:24:00Z` 至 `2026-04-03T05:00:00Z`。
- prefit：`2024-08-17T05:00:00Z` 至 `2026-04-03T05:00:00Z`。
- reused holdout：`2026-04-03T05:00:00Z` 至 `2026-07-03T05:00:00Z`；已在 V1 阶段解锁，只能用于失败审计。
- fee：`0.001`/fill；slippage：`4 bps`/fill；计入 Binance 历史资金费；funding/carry 使用抓取的 Binance funding history。
- 数据质量：missing/duplicate/null/OHLCV violation/raw-normalized mismatch/未闭合 K 误收均为 `0`。

## 执行契约

- 闭合 `1h` K 生成信号，`K+1 open` 市价成交；单仓，不加仓。
- 入场后立即挂 ATR stop/TP；同 K 同时触发 stop 与 target 时按 stop-first。
- stop 跳空穿越按该 K open 成交；固定持仓超时按 open 平仓。
- 组件同时争抢仓位时，按各组件 prefit score 降序优先；持仓期间忽略重叠信号。

## 冻结 clean 参数

### BB breakout leg

```json
{
  "ema_htf": 89,
  "indicator_window": 32,
  "band_k": 2.0,
  "roc_window": 48,
  "min_adx": 28.0,
  "min_rvol": 2.5,
  "min_atr_bps": 50.0,
  "min_dir_roc_bps": -200.0,
  "max_dist_ema_bps": 10000.0,
  "max_aligned_funding_bps": 10000.0,
  "tp_atr": 3.0,
  "sl_atr": 4.0,
  "max_hold_bars": 48,
  "fixed_leverage": 2.0
}
```

### RSI reversal leg

```json
{
  "ema_htf": 377,
  "indicator_window": 14,
  "threshold_low": 10.0,
  "threshold_high": 65.0,
  "roc_window": 6,
  "min_adx": 16.0,
  "max_adx": 100.0,
  "min_atr_bps": 100.0,
  "min_dir_roc_bps": -10000.0,
  "max_dist_ema_bps": 1000.0,
  "tp_atr": 2.5,
  "sl_atr": 2.0,
  "max_hold_bars": 24,
  "cooldown_bars": 0,
  "fixed_leverage": 1.5
}
```

## 冻结指标

| Window | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `3.8425x` | - | `-15.02%` | `72.60%` | `73` |
| validation | `2.7855x` | - | `-10.56%` | `75.00%` | `32` |
| prefit | `3.4333x` | - | `-15.02%` | `73.33%` | `105` |
| reused holdout | `0.4323x` | `-18.86%` | `-18.93%` | `50.00%` | `10` |
| current full | `2.6071x` | - | `-18.93%` | `71.30%` | `115` |

V2 相对 V1 的 prefit 与 current full 年化更高、回撤更小，胜率仍在适中区间；但 reused holdout 收益为负，因此不能 promotion。

## 近期分片审计

以下分片锚定数据集结束时间 `2026-07-03T05:00:00Z`，不参与选参，只用于登记后审计。

| Slice | Annual multiple | Return | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1d` | `1.0000x` | `0.00%` | `0.00%` | `0.00%` | `0` |
| `7d` | `0.0007x` | `-12.88%` | `-12.97%` | `0.00%` | `2` |
| `1m` | `0.3923x` | `-7.40%` | `-12.97%` | `60.00%` | `5` |
| `3m` | `0.4323x` | `-18.86%` | `-18.93%` | `50.00%` | `10` |
| `6m` | `1.1874x` | `8.88%` | `-18.93%` | `65.22%` | `23` |
| `1y` | `1.9568x` | `95.59%` | `-18.93%` | `70.37%` | `54` |

## 稳健性与实盘边界

- K+2 延迟下 prefit `2.5862x / -19.55% / 67.96% / 103`，current full `2.2383x / -19.55% / 65.79% / 114`；reused holdout 年化仍低于 `1x`。
- 8 bps slippage 下 prefit `3.0156x / -15.57% / 71.70% / 106`，current full `2.3194x / -19.61% / 69.83% / 116`；reused holdout 仍为负。
- `66` 个 one-at-a-time / exposure 邻域中，`42` 个继续满足 prefit + K+2 改善，但 reused-holdout positive 为 `0`。
- 月度块 `23` 个，其中 `4` 个为负；bootstrap 10,000 次 annual 5/50/95 为 `1.72x / 2.62x / 3.90x`，原始 `10x / >=50% / DD<20%` 形状命中率为 `0%`。
- 当前没有 production runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。

## 复现与证据

```bash
uv run python research/eth/1h-adaptive-regime/scripts/audit_eth_1h_ar_v1_clean_tune.py
```

- 全参数消融：`../ablations/eth-1h-ar-v1-full-parameter-ablation-2026-07-03.md`。
- clean 参数微调：`../research-notes/eth-1h-ar-v1-clean-parameter-tune-2026-07-03.md`。
- 最终审计：`../research-notes/eth-1h-ar-v1-clean-tune-audit-2026-07-03.md`。

## 登记后消融与微调

- V2 全参数消融：`../ablations/eth-1h-ar-v2-full-parameter-ablation-2026-07-06.md`，覆盖 `29/29` 个 clean 参数槽；单字段 high-win gate 命中 `0`。
- V2 消融引导高胜率微调：`../research-notes/eth-1h-ar-v2-ablation-guided-tune-2026-07-06.md`，observation 后续登记为 `ETH-1H-Adaptive-Regime-V2.1`；current full 为 `3.0277x / -19.55% / 87.50% / 40`，但 reused holdout 为负且压力测试穿越 `20%` 回撤。
- V2.1 参数说明：`eth-1h-ar-v2-1-high-win-tuned-spec-2026-07-06.md`。V2.1 不修改本 V2 version spec，不构成 candidate、paper-live、dry-run、handoff 或 live。

## 登记结论

`ETH-1H-Adaptive-Regime-V2` 登记为 clean tuned diagnostic observation。它不是 candidate、paper-live、dry-run、handoff 或 live；下一步证据必须来自冻结 V2 参数后的新增 forward trades。
