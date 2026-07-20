---
schema_version: "1.0"
spec_role: lab_handoff
family_id: FAMILY-ID
main_status: live spec
spec_status: draft
strategy_id: FAMILY-ID-V1
runner_kind: runner_kind
peer_spec: crates/quant-runner/src/runner/strategies/runner_kind/FAMILY-ID-V1-SPEC.md
manifest_instance_ids: []
approval_level_max: none
overlays:
  - handoff
---

# <Family Full Name> <Version> Lab Live Spec

> 状态：`live spec`。本规格描述 runner 实现合同；它不单独授权实例启用。

## 身份与边界

- Family / version：
- Exchange / market / symbol / timeframe：
- Runner module：

> Joint SPEC 不得使用并行的 `strategy_ids` / `runner_kinds` 列表。删除标量
> `strategy_id`、`runner_kind`、`peer_spec`，改用下面的一一映射：
>
> ```yaml
> implementations:
>   - strategy_id: FAMILY-ID-V1-A
>     runner_kind: runner_kind_a
>     peer_spec: crates/quant-runner/src/runner/strategies/runner_kind_a/FAMILY-ID-V1-A-SPEC.md
>   - strategy_id: FAMILY-ID-V1-B
>     runner_kind: runner_kind_b
>     peer_spec: crates/quant-runner/src/runner/strategies/runner_kind_b/FAMILY-ID-V1-B-SPEC.md
> ```

## 完整参数表

<!-- 使用 quant-runner 的准确配置字段名与字面值。 -->

## 数据与 warmup

<!-- 来源、schema、closed-bar-only、质量门禁、最小 warmup。 -->

## 执行与恢复合同

<!-- entry/exit/order/cancel/restart/missing-bar/kill-switch。 -->

## 成本与资金

<!-- fee、slippage、funding；资金边界可链接 operations/decision log。 -->

## Runner TOML

```toml
# 完整可解析示例
```

## 验证与未决缺口

- Smoke：
- Offline parity JSON artifact：
- Online open/close reconciliation：
- Remaining blockers：

## 双向链接

- Core ledger：
- Research evidence：
- Runner SPEC：
