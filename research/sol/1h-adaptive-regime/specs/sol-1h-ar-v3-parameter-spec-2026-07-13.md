# SOL-1H-Adaptive-Regime-V3 参数规格 - 2026-07-13

## 版本身份

- Version：`SOL-1H-Adaptive-Regime-V3`
- Previous observation：`V2-SM-OBS`
- Status：`registered / not promoted / not live-ready`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Mechanism：`Donchian core + VWAP arm-confirm-expire satellite`
- Evidence：`diagnostics/sol-1h-ar-v2-vwap-state-machine-2026-07-10.md`

## 结论

V3 按用户要求登记此前的 `V2-SM-OBS`。该版本通过延迟 VWAP 入场确认修复 V2 最近三个月的连续 short-revert 失效，但 reused holdout 只有 `3` 笔且已揭盲，因此登记不等于 promotion。

- prefit：annual `2.3129x`，DD `-19.05%`，win `79.57%`，trades `93`，PF `3.625`。
- full：annual `2.0977x`，return `301.24%`，DD `-19.05%`，win `79.17%`，trades `96`，PF `3.570`。
- reused holdout：annual `1.1089x`，return `+2.61%`，DD `-4.55%`，win `66.67%`，trades `3`，PF `2.223`。
- last `1y`：annual `1.7439x`，return `74.33%`，DD `-17.89%`，win `79.07%`，trades `43`，PF `2.976`。

## 数据、成本与执行

- 冻结研究帧：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z`，`17520` 根闭合 `1h` K。
- 费用：`0.001` fee/fill。
- 滑点：`4 bps` adverse slippage/fill。
- Funding：逐笔计入真实 Binance funding。
- 信号只使用闭合 K；入场在下一根 open。
- 固定 bracket 入场即生效；同 K 双触发 stop-first；跳空穿越 stop 按 open 成交。
- 单仓、不加仓；双腿重叠时使用 prefit score 优先级。

## Ensemble

- Donchian leg：`DON_SM_L3_TP1_SL4_H72`
- VWAP leg：`VWAP_SM_W3_roc6_macd_L1_TP1.5_SL1.5_H12`
- 合并：按 entry index 排序，重叠持仓只保留 prefit score 更高的交易。

## Donchian Core

- `style = donchian_break`
- `side_mode = both`
- `indicator_window = 24`
- `ema_fast / ema_slow / ema_htf = 144 / 233 / 377`
- `roc_window / min_dir_roc_bps = 24 / 100`
- `MACD = 34 / 89 / 13`
- `min_adx / max_adx = 36 / 100`
- `min_rvol = 1.0`
- `min_atr_bps / max_atr_bps = 100 / 10000`
- `max_dist_ema_bps = 750`
- `require_macd_turn = true`
- `max_aligned_funding_bps = 2`
- `exit_kind = fixed`
- `tp_atr / sl_atr = 1.0 / 4.0`
- `max_hold_bars = 72`
- `cooldown_bars = 0`
- `entry_delay_bars = 1`
- `sizing_kind = fixed`
- `fixed_leverage = 3.0`

## VWAP Satellite State Machine

### Arm

- 原始事件：`vwap_dev_atr48` 从上向下穿越 `+1.25 ATR`，方向仅 short。
- arm 时应用 V2 原过滤：`h12` bearish、bearish body、ATR、funding、distance 等。
- `indicator_window = 48`
- `ema_fast / ema_slow / ema_htf = 34 / 55 / 89`
- `htf_mode = h12`
- `require_body_dir = true`
- `max_aligned_funding_bps = 1`

### Confirm / Expire

- confirm window：`3` 根完整 `1h` K。
- confirm 条件：`roc6 <= 0` 且 MACD `8/21/5` histogram <= 0。
- confirm K 再次检查慢周期、body、funding 和 volatility 过滤。
- 窗口内无 confirm 则事件过期，不交易。
- confirm 后下一根 open 入场。

### Exit / Sizing

- `exit_kind = fixed`
- `tp_atr / sl_atr = 1.5 / 1.5`
- `max_hold_bars = 12`
- `cooldown_bars = 3`
- `entry_delay_bars = 1`
- `sizing_kind = fixed`
- `fixed_leverage = 1.0`

## Promotion 边界

- reused holdout 已在 V1/V2 研究中揭盲，不是 fresh OOS。
- reused holdout 只有 `3` 笔，不能证明状态机稳定。
- full DD `-19.05%` 已接近 `<20%` 边界。
- 当前没有生产 runner、订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch 与真实 stop-market 滑点证据。
- V3 禁止标记为 dry-run/live；必须等待新增 fresh forward trades 和完整 live-executable audit。

## 复现

- 脚本：`scripts/research_sol_1h_ar_v2_vwap_state_machine.py`
- 报告：`diagnostics/sol-1h-ar-v2-vwap-state-machine-2026-07-10.md`
- 摘要：`artifacts/sol_1h_ar_v2_vwap_state_machine_2026-07-10.json`
- 交易：`artifacts/sol_1h_ar_v2_vwap_state_machine_selected_trades_2026-07-10.csv`

# SOL-1H-Adaptive-Regime-V3 参数规格 - 2026-07-13

## 版本身份

- Version：`SOL-1H-Adaptive-Regime-V3`
- Status：`registered observation / not promoted / not live-ready`
- Market：Binance USD-M Futures `SOLUSDT` perpetual
- Timeframe：`1h`
- Mechanism：`Donchian core + VWAP arm-confirm-expire satellite`
- Source observation：`V2-SM-OBS`
- Frozen candidate：`ENS__DON_SM_L3_TP1_SL4_H72__VWAP_SM_W3_roc6_macd_L1_TP1.5_SL1.5_H12`
- Evidence：`diagnostics/sol-1h-ar-v2-vwap-state-machine-2026-07-10.md`

## 登记结论

V3 是用户明确要求登记的研究观察版本。它不是 promotion：

- prefit：annual `2.3129x`，DD `-19.05%`，win `79.57%`，trades `93`；
- full：annual `2.0977x`，DD `-19.05%`，win `79.17%`，trades `96`；
- reused holdout：annual `1.1089x`，return `+2.61%`，DD `-4.55%`，win `66.67%`，trades `3`；
- last `1y`：annual `1.7439x`，return `74.33%`，DD `-17.89%`，win `79.07%`，trades `43`。

最近三个月已在 V1/V2 研究阶段揭盲，且只有 `3` 笔，因此 V3 只能固定版本身份，不能进入 dry-run/live。

## 数据与执行

- 冻结数据：`2024-07-03T05:00:00Z` 至 `2026-07-03T04:00:00Z` 的 `17520` 根闭合 `1h` K。
- 选择只使用 train/validation/prefit；reused holdout 不参与排序。
- fee `0.001`/fill；slippage `4 bps`/fill；逐笔计真实 Binance funding。
- 闭合 K 信号，下一根 open 成交。
- 入场即有保护 stop；同 K 双触发 stop-first；gap 穿越按 open；单仓不加仓。

## Donchian Core

- Signal source：`donchian_break`
- `side_mode=both`
- `indicator_window=24`
- `ema_fast/slow/htf=144/233/377`
- `macd=34/89/13`
- `min_adx=36`
- `min_rvol=1.0`
- `min_atr_bps=100`
- `min_dir_roc_bps=100`
- `max_dist_ema_bps=750`
- `require_macd_turn=true`
- `max_aligned_funding_bps=2`
- `exit_kind=fixed`
- `tp_atr=1.0`
- `sl_atr=4.0`
- `max_hold_bars=72`
- `cooldown_bars=0`
- `entry_delay_bars=1`
- `sizing_kind=fixed`
- `fixed_leverage=3.0`

## VWAP Satellite Arm-Confirm-Expire

### Arm

- 原始事件：`vwap_dev_atr48` 从上向下穿越 `+1.25 ATR`，方向仅 short。
- arm K 仍需满足 V2 原始过滤：
  - `h12` bearish；
  - bearish body；
  - `min_atr_bps=125`；
  - 与 EMA89 距离不超过 `1000 bps`；
  - aligned funding 不超过 `1 bp`。

### Confirm / Expire

- confirm window：arm 后最多 `3` 根完整 `1h` K。
- confirm 从 arm 后下一根 K 开始。
- short confirm：
  - `roc6_bps <= 0`；
  - MACD `8/21/5` histogram `<= 0`。
- confirm K 再次检查慢周期、body、funding 与 volatility filters。
- 窗口内无 confirm 则事件 expire，不交易。
- confirm K 闭合后，下一根 open 市价入场。

### Exit / Sizing

- `exit_kind=fixed`
- `tp_atr=1.5`
- `sl_atr=1.5`
- `max_hold_bars=12`
- `cooldown_bars=3`
- `entry_delay_bars=1`
- `sizing_kind=fixed`
- `fixed_leverage=1.0`

## Ensemble

- 两腿交易按 entry index 排序。
- 同时触发时使用各腿 prefit score 作为优先级。
- 持仓区间重叠时只保留优先级更高的交易。
- 单账户、单仓、不加仓。

## Promotion 边界

- V3 未达到原硬目标 `10x / 80% / <20% DD`。
- reused holdout 只有 `3` 笔，且已揭盲。
- 当前没有 fresh-forward 交易证据、production runner、订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。
- V3 禁止标记为 dry-run、handoff 或 live。

## 机器证据

- `artifacts/sol_1h_ar_v2_vwap_state_machine_2026-07-10.json`
- `artifacts/sol_1h_ar_v2_vwap_state_machine_candidates_2026-07-10.csv`
- `artifacts/sol_1h_ar_v2_vwap_state_machine_selected_trades_2026-07-10.csv`
- `scripts/research_sol_1h_ar_v2_vwap_state_machine.py`

