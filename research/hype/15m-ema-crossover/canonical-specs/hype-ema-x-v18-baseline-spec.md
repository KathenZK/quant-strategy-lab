# HYPE-EMA-X-V18 基线规格

Family id：`HYPE-EMA-X`

版本：`HYPE-EMA-X-V18`

源版本：`HYPE-EMA-X-V17.1`（`hq_scale=1.1`，`lq_scale=1.0`）

状态：`research candidate / not live-ready`

## 一句话定义

`HYPE-EMA-X-V18` 不是新的信号搜索版本，而是 **V17.1 经 146 项单参数消融后的干净参数规格**。交易逻辑与 V17.1 相同，只删除对当前 HYPE 1Y 样本 **无成交影响** 或 **默认关闭且打开伤收益** 的参数项，便于 live spec、runner 和交接文档维护。

## 版本身份

- 2026-07-01：`research_hype_v17_1_full_ablation.py` 完成 V17.1 全参数消融；`research_hype_v17_1_parameter_prune_audit.py` 给出剔除结论。
- V18 继承 V17.1 的 HQ/LQ 信号、late re-entry、状态机退出和 `HQ×1.1` 仓位。
- 证据：`diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md`；`artifacts/hype_v17_1_full_ablation*`。
- 版本登记只固定参数与执行口径，不表示 live、paper-live、dry-run、handoff 或实盘批准。

## 台账指标（与 V17.1 相同）

数据切片：`<= 2026-06-01 03:00 UTC`，rolling 1Y。

| 指标 | 数值 |
| --- | ---: |
| 1Y 收益 | +3861.48% |
| 最大回撤 | -19.44% |
| 胜率 | 90.91% |
| 交易数 | 33 |
| Late 交易 | 7 |
| stop_loss | 0 |

## 数据与执行成本

| 参数 | 值 |
| --- | --- |
| symbol | HYPEUSDT perpetual |
| timeframe | 15m |
| slippage | 0.0005 |
| trade_cost | 0.00085 |
| 信号时序 | 第 `t` 根收盘确认 → 第 `t+1` 根 open 成交 |
| 1h 指标 | resample 后 `shift(1)` 对齐 15m |
| entry_atr | 入场前一根 `atr_pct672` |

## 信号

### 方向与基础过滤（`atr18`）

**多头**：`ema_spread > 0`；`ADX28 >= 28`；`vol_surge192 >= 0.25`；`h1_adx21 > 18`；`h1_pdi21 > h1_mdi21`；`atr_ratio96_672 <= 1.8`

**空头**：`ema_spread < 0`；`ADX28 >= 36`；`vol_surge192 >= 0.50`；`h1_ema_spread < 0`；`atr_ratio96_672 <= 1.8`

### HQ 主信号

- `trend_score >= 7`（10 项趋势质量至少过 7 项，定义同 V15）

### LQ 卫星信号

- `trend_score` 在 5–6
- `dir_dist_ema96 <= 0.04`
- `atr_ratio96_672 <= 1.1`

### V18 明确删除（消融 noop 或从未生效）

- `lq_require_obv`
- `lq_require_cmf`
- `lq_require_not_hot_edge`

## 入场

### 普通入场

| 参数 | 值 |
| --- | ---: |
| entry_max_regime_age | 128 |
| entry_max_dist_ema96 | 0.08 |

### Late re-entry

| 参数 | 值 |
| --- | ---: |
| late_max_age | 384 |
| late_dist_ema96 | 0.075 |
| cooldown_bars | 12 |
| min_prev_pnl | -0.03 |
| min_prev_mfe_atr | 3.0 |

附加条件：同方向、同 EMA regime、上一笔非 `stop_loss`、当前仍有 HQ/LQ 信号。

### V18 不写入规格的模块（保持关闭）

- `require_pullback` / `pullback_buffer`
- `reentry_mode`（breakout 补单）
- `entry_min_rvol96`
- `entry_max_move48`

## 仓位

| 参数 | 值 |
| --- | ---: |
| max_allocation | 3.0 |
| long_target_atr_pct | 0.016 |
| short_target_atr_pct | 0.014 |
| allocation | `min(3.0, target_atr_pct / atr_pct672)` |
| hq_scale | **1.1** |
| lq_scale | **1.0** |

## 出场

### 硬止损

| 参数 | 值 |
| --- | ---: |
| stop_atr | 8.0 |

多头：`entry × (1 - 8 × entry_atr)`；空头：`entry × (1 + 8 × entry_atr)`。盘中 high/low 触发。

> 当前 1Y 样本 0 笔 `stop_loss`，但规则必须保留；`stop_atr` 8–12 在样本内等价。

### 结构破坏

| 参数 | 值 |
| --- | ---: |
| hard_exit_mode | swing96 |
| hard_exit_bars | 1 |

收盘破位 → 下一根 open 出场。

### 利润后预警确认（主退出路径）

| 参数 | 值 |
| --- | ---: |
| min_mfe_atr | 4.0 |
| warning_source | either |
| warning_exit_min_capture | 0.35 |
| confirm_mode | ema21 |
| volume_warning_mode | no_mfi_div |
| exit_rvol | 2.0 |
| wick_min | 0.55 |
| osc_min_score | 2 |
| osc_tf | 1h |

### V18 不写入规格的退出模块

- `fallback_adx` / `fallback_bars`
- `segment_exit_mode` 及关联参数
- `confirm_window` 调参
- `take_profit` / `max_hold_bars`（保持关闭）

## 相对 V17.1 的变化摘要

| 维度 | V17.1 | V18 |
| --- | --- | --- |
| 信号/成交逻辑 | 完整研究口径 | **相同** |
| 参数表 | 含 noop 与关闭模块 | **只保留有效参数** |
| 文档用途 | 搜索与消融 | live spec / handoff 最小集合 |
| 收益/回撤 | +3861.48% / -19.44% | **相同** |

## 复现

- 回测引擎：`scripts/research_hype_v13_late_reentry.py` + `scripts/research_hype_v17_hybrid_ablation.py`
- V17.1 消融：`scripts/research_hype_v17_1_full_ablation.py`
- 参数剔除审计：`scripts/research_hype_v17_1_parameter_prune_audit.py`
- 严格执行审计：`scripts/research_hype_ema_x_v17_1_strict_live_audit.py`

## 相关文档

- 主台账：`../hype-ema-x-core-ledger.md`
- 剔除证据：`../diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md`
- 严格执行审计：`../diagnostics/hype-ema-x-v17-1-strict-live-audit-2026-07-01.md`
- V17 合体消融：`../ablations/hype-ema-x-v17-hybrid-ablation.md`
