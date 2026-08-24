# HYPE-1D-MA7-ABT V6 全参数消融（post-reveal diagnostic）

- 日期：2026-08-11
- 角色：`diagnostic-only / post-reveal / not promoted / not live-ready`
- 标的：Binance USD-M `HYPEUSDT` perpetual
- 决策周期：UTC `1d`；真实风险回放：`1h`
- 成本：手续费 `0.001/fill`，基准不利滑点 `4 bps/fill`；压力组 `8 bps/fill`；默认计入真实 Binance funding。
- 证据：[机器证据](../artifacts/hype_1d_ma7_abt_v6_full_parameter_ablation_2026-08-11.json)及[SHA256](../artifacts/hype_1d_ma7_abt_v6_full_parameter_ablation_2026-08-11.json.sha256)，脚本：[全参数消融脚本](../scripts/audit_hype_1d_ma7_abt_v6_full_parameter_ablation.py)。

## 范围

本轮不是重新搜索V7，而是围绕已登记 V6 做 one-at-a-time active-parameter ablation 与每个参数的单参数邻域扫描，共 `224` 个候选。覆盖：

- V4继承层：`entry_mode`、`slope_lookback/slope_min_atr`、`confirm_days`、`entry_buffer_atr`、`pullback_lookback/touch`、`breakout_lookback`、退出确认/迟滞、`slope_exit_lookback`、保护止损、max hold、cooldown；
- V5 OAPP层：long MFE fraction exit 的冻结网格 `activation/giveback/confirm_days` 与 off，short `RSI6` 止盈阈值、天数与 off；
- V6 PEHC层：冻结网格 `expiry_days`、`slope_threshold`、`chase_cap_atr`、`execution`、`enabled/entry_enabled`。

每个候选均跑全窗、`8 bps`、funding-off、额外 `1d` lag、`8×54d` cold-flat block 与最近 `1d/7d/1m/3m/6m/1y` 切片。所有结果均为已揭示历史上的诊断，不构成登记或promotion证据。

## 基准

Exact V6 control：

| 指标 | 数值 |
| --- | ---: |
| 全窗收益 | `+617.09%` |
| 真实`1h` MDD | `-18.40%` |
| 交易数 | 19 |
| Profit factor | 12.88 |
| `long_trail_exit` | 8 |
| `short_rsi_exit` | 3 |
| `protective_stop` | 3 |
| `handoff_accept` | 5 |

## 全窗双优线索

本轮只有三个经济上不同的单参数邻域候选在全窗收益高于V6且MDD不劣，并通过 `8 bps`、`1d lag` 与 `8/8` block 正收益的机器筛选：

| 候选 | 改动 | 全窗收益 | 真实`1h` MDD | 交易数 | 机制变化 |
| --- | --- | ---: | ---: | ---: | --- |
| `n_short_cooldown_days_3` | short cooldown `5d -> 3d` | `+711.04%` | `-18.40%` | 20 | 多1笔交易，8bps `+698.75%`，1日lag `+267.61%` |
| `short_cooldown_8` / `n_short_cooldown_days_10` | short cooldown `5d -> 8/10d` | `+672.81%` | `-18.40%` | 17 | 少2笔交易，`handoff_accept 5 -> 4`，`protective_stop 3 -> 2` |
| `short_rsi_threshold_25` | short RSI6止盈阈值 `20 -> 25` | `+621.22%` | `-18.40%` | 19 | `short_rsi_exit 3 -> 4`，只多`+4.13pp` |

扫描完成时，这些只能视为前瞻观察线索：

- `short_cooldown_days_3` 是本轮邻域全扫的最高收益点，但它与 `8/10d` 同时出现，说明 short cooldown 对少数已暴露episode非常敏感；扫描当时不能根据同一历史直接选 `3d` 写入V6。
- `short_cooldown_8/10` 的主窗增收较大，但本质是少做两笔已暴露历史中的低质量机会；这类 cooldown 拉长也可能是样本路径选择。
- `short_rsi_threshold_25` 只多 `+4.13pp`，MDD完全相同，边际太小，不足以在已揭示历史上直接改版。

## 风险型线索

有些候选能降低或保持MDD，但明显牺牲收益，不适合作为V7，只能说明风险来源：

| 候选 | 全窗收益 | MDD | 解释 |
| --- | ---: | ---: | --- |
| `oapp_long_confirm_1` | `+438.96%` | `-16.42%` | 更快确认long利润回吐，回撤降低约`1.97pp`，但收益少`178.13pp` |
| `n_short_slope_exit_lookback_5` | `+531.50%` | `-17.77%` | short slope exit 更慢可降回撤约`0.63pp`，但收益少`85.60pp` |
| `natural_short_entry_removed` | `+389.76%` | `-18.40%` | 关闭自然short保留handoff/forced shorts，说明自然short贡献不稳定，但收益少`227.33pp` |
| `pehc_chase_cap_075` | `+591.59%` | `-18.40%` | 给handoff加`0.75ATR`追价上限，收益少`25.50pp`，说明无限追价不是当前主风险 |
| `short_hard_stop_removed` | `+602.24%` | `-18.40%` | short hard stop历史上不是收益来源，但关闭后收益仍少`14.85pp` |

## 不能随便动的核心模块

消融显示 V6 的主要收益仍依赖少数高选择性入场和long路径，不是靠某个小参数可线性优化：

- 自然入场 `reclaim` 不能删：`short_reclaim_removed_regime` 为 `-16.85%/-68.36%`，`both_reclaims_removed_regime` 为 `-9.32%/-69.16%`。
- 入场 slope 不能大幅放开：`all_slopes_removed` 为 `-30.96%/-67.33%`，`long_entry_slope_removed` 仅 `+8.51%/-68.63%`。
- short entry buffer 不能降到0：`short_entry_buffer_removed` 只有 `+212.19%/-30.71%`。
- long trailing 参数不能收紧到 `1.0ATR`：`long_trailing_stop_100` 只有 `+98.35%/-37.62%`。
- V6 PEHC 不能简单加 slope 门：`pehc_slope_000/002` 均降至 `+595.30%/-21.57%`。
- 关闭 PEHC 回到V5为 `+509.32%/-21.57%`；关闭 OAPP+PEHC 回到近似V4为 `+398.84%/-25.09%`，说明V5/V6叠加层在历史上仍有实际贡献。

## 裁决

`diagnostic-only / post-reveal / not promoted / not live-ready`。

本轮确实找到三个历史双优线索：`short_cooldown_days_3`、`short_cooldown_days_8/10` 和 `short_rsi_threshold_25`。但它们都来自已揭示432日，同一substrate已反复调参。扫描完成时的治理建议是只把 short cooldown 与 short RSI6 阈值列为前瞻observer假设；随后用户明确要求将 `short_cooldown_days_3` 登记为V7，版本身份见 [V7规格](../specs/hype-1d-ma7-abt-v7-spec.md)，但该登记仍不等于promotion，仍需 `2026-08-11` 之后至少90日clean prospective与足够新增short/PEHC事件再判断。
