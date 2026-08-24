# HYPE-1D-MA7-ABT-V7 全参数清理消融

## 结论

在 V7 基线上重新运行224个全参数消融/邻域候选后，确认 V7.1 可以登记为 **功能等价参数面精简版本**：移除当前 `reclaim` / `off` 模式下的 dormant/schema-only 字段，不改变 V7 交易路径。

本轮不把 `short_rsi_threshold_25` 作为 V7.1。它是 post-reveal 行为改变候选，`+715.71%/-18.40%`，只比 V7 多 `+4.67pp`，不属于“移除没用参数”。

## 基线

| Version | 全窗收益 | 真实1h MDD | 交易数 | 状态 |
| --- | ---: | ---: | ---: | --- |
| `exact_v7` | `+711.04%` | `-18.40%` | 20 | `registered / not promoted / not live-ready` |
| `V7.1 cleanup` | `+711.04%` | `-18.40%` | 20 | 与 V7 功能等价 |

## Top 结果

| Candidate | Group | 全窗收益 | 真实1h MDD | 交易数 | 裁决 |
| --- | --- | ---: | ---: | ---: | --- |
| `short_rsi_threshold_25` | `oapp_short_rsi` | `+715.71%` | `-18.40%` | 20 | `DIAGNOSTIC_CANDIDATE` |
| `n_short_rsi_threshold_25` | `neighborhood_oapp_short_rsi` | `+715.71%` | `-18.40%` | 20 | `DIAGNOSTIC_CANDIDATE` |
| `exact_v7` | `baseline` | `+711.04%` | `-18.40%` | 20 | `CONTROL` |

解释：`short_rsi_threshold_25` 是行为参数变更，不是无效字段删除。它曾在组合搜索中也表现为小幅 post-reveal 候选，但不能作为 V7.1 的精简依据。

## 可移除字段

V7.1 从规格中移除以下字段：

- `long_config.pullback_lookback`
- `long_config.pullback_touch_atr`
- `long_config.breakout_lookback`
- `short_config.pullback_lookback`
- `short_config.pullback_touch_atr`
- `short_config.breakout_lookback`
- `oapp_config.entry.lookback`
- `oapp_config.entry.scope`
- `oapp_config.entry.threshold`
- `oapp_config.short_exit.activation_atr`
- `oapp_config.short_exit.giveback`
- `oapp_config.short_exit.confirm_days`
- `pehc_config.allowed_origin_indices`
- `pehc_config.blocked_origin_indices`

理由：

- long/short `entry_mode="reclaim"`，pullback/breakout 专用字段不参与当前 entry 判断。
- OAPP `entry.kind="off"`，其内部 lookback/scope/threshold 不参与判断。
- OAPP `short_exit.mode="off"`，其内部 activation/giveback/confirm 不参与判断。
- PEHC origin allow/block 列表为空，当前 V7 没有使用 origin allow/block 约束。

## 保留字段

以下字段虽然部分历史样本中未触发，仍保留：

- `short_config.hard_stop_atr`
- `long_config.trail_atr`
- `short_config.trail_atr`
- `short_config.max_hold_days`
- `cooldown_days`
- entry/exit buffer、slope gate、PEHC `enabled/entry_enabled/expiry/execution`

理由：它们是未来行为或风险保护的一部分，不能仅因当前历史未触发就删除。

## 分组摘要

- `entry_event`：移除 `reclaim` 机制会显著破坏收益，最佳仅 `+106.08%`。
- `neighborhood_oapp_short_rsi`：`threshold=25` 小幅双优，但属于行为变化。
- `neighborhood_pehc`：无双优，PEHC 当前配置保持。
- `neighborhood_long_config` / `neighborhood_short_config`：多个 dormant 字段变化与 V7 完全等价，但风险保护字段不因等价样本而删除。

## 裁决

登记 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`：

- 主状态：`registered / not promoted / not live-ready`
- 角色：V7 功能等价参数面精简版本
- 不改变交易逻辑，不 promotion，不生成 HTML，不创建 live spec，不授权 runner。

## 证据

- [V7.1合同](../specs/hype-1d-ma7-abt-v7-1-parameter-cleanup-contract-2026-08-11.md)
- [V7.1规格](../specs/hype-1d-ma7-abt-v7-1-spec.md)
- [机器证据](../artifacts/hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation.py)
