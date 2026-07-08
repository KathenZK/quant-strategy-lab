# HYPE-EMA-X-V17.1 全参数消融与精简口径

日期：2026-07-01

Main ledger：`hype-ema-x-core-ledger.md`

## 方法

- 脚本：`research_hype_v17_1_full_ablation.py`
- 基准：`HYPE-EMA-X-V17.1`（`hq_scale=1.1`，`lq_scale=1.0`）
- 数据切片：`<= 2026-06-01 03:00 UTC`，rolling 1Y
- 候选数：`145` 个单参数消融 + baseline
- Baseline 复现：收益 `+3861.48%`，回撤 `-19.44%`，
  `33` 笔，胜率 `+90.91%`

判定口径：

- **noop**：所有消融取值与 baseline 成交路径完全一致（收益/回撤/笔数/胜率相同）。
- **noop_band**：部分消融取值无效，说明官方点附近存在宽无效带。
- **inactive_harmful**：模块默认关闭；一旦打开明显伤害收益。
- **defensive_only**：只能守 baseline，调参不能改善且偏离会显著变差。
- **sizing_or_risk_knob**：主要改变风险预算，不是信号识别器。

## 结论摘要

V17.1 官方规则里写了大量参数，但 **146 项消融** 表明其中相当一部分在当前 HYPE 1Y 样本上 **从未改变实际成交**。
这不是说代码没算这些字段，而是说它们对 **33 笔成交路径** 没有边际贡献。

应保留的是：**方向/基础信号、HQ/LQ 分流、普通入场窗口、late re-entry、动态仓位、预警+EMA21 出场、swing96 结构退出**。
应从 live spec 删除或保持关闭的是：**OBV/CMF/hot-edge 卫星附加过滤、confirm_window 调参、
pullback/reentry/breakout 补单、segment/fallback 分段退出、以及样本内从未触发的 stop 距离调参**。

## 1. 可剔除（noop：对成交无影响）

| 参数 | 官方默认 | 消融结论 | 处理 |
| --- | --- | --- | --- |
| `lq_require_not_hot_edge` | `-` | 1/1 个取值与 baseline 完全相同 | 从规格删除 |
| `lq_require_obv` | `-` | 1/1 个取值与 baseline 完全相同 | 从规格删除 |
| `confirm_window` | `24` | 2/2 个取值与 baseline 完全相同 | 从规格删除 |

## 2. 宽无效带（官方值可保留，邻域调参无效）

| 参数 | 官方默认 | 无效带观察 | 处理 |
| --- | --- | --- | --- |
| `lq_max_score` | `6` | 1/2 个取值无效；return_range `11.4%` | 规格只写官方点 |
| `lq_max_dist_ema96` | `0.04` | 3/4 个取值无效；return_range `11.4%` | 规格只写官方点 |

## 3. 保持关闭的模块（打开会伤收益）

| 参数 | 默认 | 最差收益 | 处理 |
| --- | --- | --- | --- |
| `entry_max_move48` | `0.0` | `+2030.58%` | 不写进 live spec |
| `entry_min_rvol96` | `0.0` | `+2872.13%` | 不写进 live spec |
| `segment_exit_mode` | `none` | `+1557.18%` | 不写进 live spec |
| `pullback_buffer` | `0.0` | `+2730.05%` | 不写进 live spec |
| `fallback_adx` | `0.0` | `+499.21%` | 不写进 live spec |
| `require_pullback` | `false` | `+3237.11%` | 不写进 live spec |
| `reentry_mode` | `none` | `+902.31%` | 不写进 live spec |

## 4. 风险旋钮（有效，但属于仓位预算）

| 参数 | 最佳消融 | 收益增量 | 判断 |
| --- | --- | ---: | --- |
| `hq_scale` | 见 sensitivity | `+1954.9%` | V17.1 已用 |
| `hard_exit_mode` | 见 sensitivity | `+235.4%` | 不升格官方 |
| `lq_scale` | 见 sensitivity | `+343.0%` | 不升格官方 |
| `cooldown_bars` | 见 sensitivity | `+59.7%` | 不升格官方 |
| `late_dist_ema96` | 见 sensitivity | `+80.1%` | 不升格官方 |
| `hard_exit_bars` | 见 sensitivity | `+235.4%` | 不升格官方 |

## 5. 核心有效参数（必须保留）

| 模块 | 保留参数 |
| --- | --- |
| 方向/基础信号 | `ema_spread, ADX28, vol_surge192, h1 确认, atr_ratio<=1.8` |
| HQ 主信号 | `trend_score>=7` |
| LQ 卫星 | `trend_score 5-6, dir_dist_ema96<=4%, atr_ratio<=1.1` |
| 普通入场 | `regime_age<=128, dist_ema96<=8%, 下一根 open` |
| Late re-entry | `late_max_age=384, late_dist=7.5%, cooldown=12, min_prev_pnl=-3%, min_prev_mfe=3ATR` |
| 仓位 | `dynamic allocation max 3x; V17.1: HQ×1.1, LQ×1.0` |
| 预警出场 | `min_mfe=4ATR, warning either, capture>=35%, confirm EMA21` |
| 量能预警 | `no_mfi_div, exit_rvol=2.0, wick_min=0.55` |
| 振荡预警 | `1h RSI/KDJ/MACD, osc_min_score=2` |
| 结构退出 | `hard_exit_mode=swing96, hard_exit_bars=1` |

## 6. 防守型参数（不能删，但也不应为了提收益去改）

| 参数 | 官方默认 | return_range | 说明 |
| --- | --- | ---: | --- |
| `confirm_mode` | `ema21` | `3235.3%` | 偏离 baseline 明显变差 |
| `hq_min_score` | `7` | `2386.4%` | 偏离 baseline 明显变差 |
| `entry_max_dist_ema96` | `0.08` | `2365.9%` | 偏离 baseline 明显变差 |
| `segment_min_mfe_atr` | `-` | `1886.7%` | 偏离 baseline 明显变差 |
| `warning_exit_min_capture` | `0.35` | `1584.6%` | 偏离 baseline 明显变差 |
| `warning_source` | `either` | `1551.5%` | 偏离 baseline 明显变差 |
| `min_mfe_atr` | `4.0` | `1317.8%` | 偏离 baseline 明显变差 |
| `stop_atr` | `8.0` | `1304.7%` | 偏离 baseline 明显变差 |
| `exit_rvol` | `2.0` | `1259.0%` | 偏离 baseline 明显变差 |
| `min_prev_mfe_atr` | `3.0` | `1156.1%` | 偏离 baseline 明显变差 |
| `entry_max_regime_age` | `128` | `1129.6%` | 偏离 baseline 明显变差 |
| `volume_warning_mode` | `no_mfi_div` | `1038.6%` | 偏离 baseline 明显变差 |
| `osc_min_score` | `2` | `1028.8%` | 偏离 baseline 明显变差 |
| `wick_min` | `0.55` | `868.4%` | 偏离 baseline 明显变差 |
| `segment_exit_min_capture` | `-` | `840.2%` | 偏离 baseline 明显变差 |
| `late_max_age` | `384` | `753.7%` | 偏离 baseline 明显变差 |
| `trail_atr` | `-` | `407.6%` | 偏离 baseline 明显变差 |
| `segment_adx` | `-` | `330.2%` | 偏离 baseline 明显变差 |
| `fallback_bars` | `-` | `140.3%` | 偏离 baseline 明显变差 |
| `segment_bars` | `-` | `137.7%` | 偏离 baseline 明显变差 |
| `hq_enabled` | `true` | `0.0%` | 偏离 baseline 明显变差 |

## 7. 精简后官方口径（建议写法）

下面是把无效项剔除后的最小集合；已正式登记为 **`HYPE-EMA-X-V18`**。
完整规格见 `specs/hype-ema-x-v18-baseline-spec.md`。

### 信号

- 基础：`atr18` EMA regime 信号（多/空阈值见主台账）。
- HQ：`trend_score >= 7`。
- LQ：`trend_score` 5–6 且 `dir_dist_ema96 <= 4%` 且 `atr_ratio96_672 <= 1.1`。
- **删除**：`lq_require_obv`、`lq_require_cmf`、`lq_require_not_hot_edge`。

### 入场

- 普通：`regime_age <= 128`，`dir_dist_ema96 <= 8%`，收盘确认、下一根 open。
- Late：`late_max_age=384`，`late_dist_ema96=7.5%`，`cooldown=12`，`min_prev_pnl=-3%`，`min_prev_mfe_atr=3`。
- **删除**：`require_pullback`、`reentry_mode`、`entry_min_rvol96`、`entry_max_move48`。

### 仓位

- `allocation = min(3, target_atr / atr_pct672)`；HQ `×1.1`，LQ `×1.0`。

### 出场

- 硬止损：`stop_atr=8`（保留规则，但当前 1Y 样本 0 笔触发；不宜为了调参删规则）。
- 结构：`swing96`，破位后下一根 open。
- 利润保护：`min_mfe_atr=4`，`warning_source=either`，`warning_exit_min_capture=35%`，`confirm_mode=ema21`。
- 量能：`no_mfi_div`，`exit_rvol=2.0`，`wick_min=0.55`。
- 振荡：`osc_min_score=2`（1h）。
- **删除/保持关闭**：`fallback_adx`、`segment_exit_*`、`confirm_window` 调参、`hard_exit_bars>1` 试验项。

## 8. 重要限制

1. **noop 不等于逻辑无用**：例如 `stop_atr` 在 8–12 之间结果相同，是因为样本内没有 stop_loss；实盘仍必须保留止损规则。
2. **LQ 只有 4 笔**：`lq_max_atr_ratio`、`lq_scale` 等卫星参数对总收益敏感，但证据薄，不宜借消融结果继续加复杂卫星过滤。
3. **`hq_scale` 是最强收益旋钮**：继续放大 HQ 会越过 20% 回撤边界；V17.1 的 1.1 已是风险预算上限附近。
4. **不建议为增样本去放宽 HQ 过滤**：那会退回 V16 路线，不是 V17.1 精简。

## 产物

- 全量消融：`artifacts/hype_v17_1_full_ablation_ranking.csv`
- 敏感性：`artifacts/hype_v17_1_full_ablation_sensitivity.csv`
- 剔除表：`artifacts/hype_v17_1_parameter_prune_audit.csv`
- 本报告：`diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md`
- V18 干净规格：`specs/hype-ema-x-v18-baseline-spec.md`
