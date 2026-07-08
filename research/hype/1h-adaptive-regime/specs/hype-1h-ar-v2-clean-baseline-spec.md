# HYPE-1H-Adaptive-Regime-V2 干净等价基线规格

## 身份与状态

- Full version：`HYPE-1H-Adaptive-Regime-V2`。
- 来源：`HYPE-1H-Adaptive-Regime-V1` 全字段 one-at-a-time 消融。
- 状态：`clean equivalent diagnostic baseline / NO-GO / not live-ready / not promoted`。

V2 的目的不是制造更好看的指标，而是删除 V1 中对当前机制无效、结构上休眠或不应成为可调参数的字段。V2 与 V1 的 DI 逐笔路径、Stoch 逐笔路径、组合逐笔路径和资金曲线完全一致。

## 消融覆盖与清理结果

- `StrategyConfig` 除 `name` 外共 `38` 字段，两条腿共 `76` 个字段槽。
- 运行 `123` 行（含 baseline）全字段消融；两腿 missing coverage 均为 `0`。
- 分类：structural dormant `24`、disabled/fixed switch `16`、active mechanism field `36`。
- 从可调配置接口删除 `40` 个字段槽；保留两腿共 `34` 个数值/布尔 active 参数，`style` 作为机制身份硬编码。

### DI-cross 删除的 22 个字段

- 结构休眠：`band_k`、`ema_fast`、`ema_slow`、`indicator_window`、`macd_fast`、`macd_slow`、`macd_signal`、`max_leverage`、`pullback_atr`、`require_macd_turn`、`risk_fraction`、`roc_threshold_bps`、`threshold_low`、`threshold_high`、`trail_activation_atr`、`trail_atr`。
- 固定状态机/禁用边界：`cooldown_bars`、`entry_delay_bars`、`exit_kind`、`min_atr_bps`、`side_mode`、`sizing_kind`。

### Stoch-reversal 删除的 18 个字段

- 结构休眠：`band_k`、`ema_fast`、`ema_slow`、`max_leverage`、`pullback_atr`、`risk_fraction`、`roc_threshold_bps`、`tp_atr`。
- 固定状态机/禁用边界：`entry_delay_bars`、`exit_kind`、`htf_mode`、`max_adx`、`max_aligned_funding_bps`、`min_dir_roc_bps`、`require_body_dir`、`roc_window`、`side_mode`、`sizing_kind`。

“固定状态机”不等于删除行为。例如 `entry_delay_bars=1`、双向、固定权益名义仓位、DI fixed bracket、Stoch trailing 仍然存在，只是不允许搜索脚本把这些 live 语义当作普通参数随意切换。

## V2 唯一配置接口

### `DICleanConfig`

```text
ema_htf=89
min_adx=12.0
max_adx=36.0
min_rvol=2.0
max_atr_bps=250.0
roc_window=24
min_dir_roc_bps=-200.0
max_dist_ema_bps=750.0
htf_mode=h12
require_body_dir=true
max_aligned_funding_bps=8.0
tp_atr=1.5
sl_atr=4.0
max_hold_bars=18
fixed_leverage=3.0
```

### `StochCleanConfig`

```text
indicator_window=21
threshold_low=25.0
threshold_high=60.0
ema_htf=55
min_adx=12.0
min_rvol=1.0
min_atr_bps=200.0
max_atr_bps=400.0
max_dist_ema_bps=2500.0
macd_fast=8
macd_slow=21
macd_signal=5
require_macd_turn=true
sl_atr=4.0
trail_activation_atr=1.0
trail_atr=1.0
max_hold_bars=8
cooldown_bars=24
fixed_leverage=2.0
```

### 硬编码 live 语义

- `side=both`。
- `entry_delay_bars=1`，即闭合 K 信号、下一根 open 入场。
- DI：固定 ATR bracket；Stoch：闭合 K 更新的 ATR trailing。
- 固定权益名义 sizing。
- 单仓；同刻冲突 DI-cross 优先。
- stop gap-open、stop-first、逐 fill 成本和逐笔 funding 与 V1 完全相同。

## 等价验收

| Check | Result |
| --- | ---: |
| DI component trade signature | `PASS / exact equal` |
| Stoch component trade signature | `PASS / exact equal` |
| Merged trade signature | `PASS / exact equal` |
| Current-full trades | `69 = 69` |
| Current-full annual multiple | `9.683753100839603x = 9.683753100839603x` |
| Current-full max DD | `-19.642595770825744% = -19.642595770825744%` |

V2 的窗口指标与 V1 相同：prefit `11.6665x / -16.93% / 79.25%`，reused holdout `5.1305x / -19.64% / 75.00%`，current full `9.6838x / -19.64% / 78.26%`。

## V2 微调结论

- 第一轮：DI `30,000`、Stoch `30,000`、组合 `19,600`。仅按 prefit 冻结的第一名在后段出现 `-36.57%` 回撤，拒绝。
- 基础 current full + reused holdout 三项硬门槛共有 `6` 组，但要求 base K+1、K+2、8 bps/fill 都完整达到硬门槛后为 `0` 组。
- 将 K+2 与 8 bps 直接放入 prefit 选参后，扩大到 DI `800`、Stoch `800`、组合 `640,000`，prefit 三场景稳健命中 `7,613`；预先评分第一名冻结后 current full 为 `13.6490x / -32.69% / 81.25%`，仍因回撤失败。
- 稳健榜前 `1,000` 组事后审计中，同时满足基础硬门槛、K+2/8 bps 不破 `20%`、且比 V2 高收益低回撤的数量为 `0`。

因此本轮不存在可以诚实登记为更优版本的微调结果。V2 保持干净等价基线；所有高年化 tune 只保留为 rejected diagnostic，不创建 V2.1/V3，不提升 promotion 状态。

## 复现

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_clean_tune.py
uv run python research/hype/1h-adaptive-regime/scripts/audit_hype_1h_ar_v2_tune_frontier.py
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_live_robust_tune.py --pool-size 800
```

实现真值位于 `research_hype_1h_ar_v2_clean_tune.py` 的两个 clean dataclass 和 `di_to_base` / `stoch_to_base` 显式映射；不得从已删除的 V1 dormant 字段反推 V2 行为。
