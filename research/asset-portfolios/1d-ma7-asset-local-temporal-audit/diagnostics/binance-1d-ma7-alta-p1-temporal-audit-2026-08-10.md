# BIN-1D-MA7-ALTA P1 未见时间窗诊断

## 结论

- 状态：`DEVELOPMENT_HARD_GATE_FAILED / explore / not promoted / not live-ready`
- Test：`2025-05-31` 至 `2026-08-01`，21 资产 `1,341` 个未见 maturity events。
- `take_all` gate：`False`；asset-local model gate：`False`。
- HYPE requests/files/rows/features/train/evaluation：全部为 `0`。

## 主结果

| Policy | Selected | Mean | PF | Compound | MDD | 正资产 | Bootstrap P(mean>0) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `take_all` | 1341 | -0.120718% | 0.829 | -83.82% | -91.10% | 8/21 | 0.16% |
| `local_q80_ridge1000` | 276 | -0.310739% | 0.619 | -59.34% | -61.08% | 5/21 | 0.00% |

Local policy 相对 `take_all` 的 common-test `P(Δutility>0)` 为
`91.96%`，mean delta
`0.056763%/event`。

`take_all` 的 asset×90d bootstrap 95% 区间为
`[-0.1985%, -0.0403%]/event`；
local policy 区间为
`[-0.4770%, -0.1426%]/event`。
Local 相对增量为正只说明减少交易后少亏；自身经济性与 bootstrap 失败时不能解释成
可交易 alpha。表中 compound/MDD 是事件顺序审计，不是并发组合资本曲线。

## Gate

`take_all`：

```json
{
  "p0_capacity": true,
  "sample_and_direction_capacity": true,
  "main_economics": false,
  "positive_assets": false,
  "positive_compound_assets": false,
  "cluster_bootstrap": false,
  "stress_variants": false,
  "hype_lock": true
}
```

Asset-local：

```json
{
  "take_all_gate": false,
  "sample_capacity": true,
  "main_economics": false,
  "positive_assets": false,
  "cluster_bootstrap": false,
  "increment_over_take_all": true,
  "stress_variants": false,
  "hype_lock": true
}
```

## Lag1 口径

- `take_all` common-event lag1-main：
  `-0.260421%/event`。
- local common-event lag1-main：
  `-0.154386%/event`。
- 缺失 lag 的事件单独保留；portfolio comparison 以未执行 lag=`0` 报告，不用
  executable-only 正值过门。

## 终止口径

若 `take_all` 失败，按冻结合同关闭同一 maturity event 定义上的
selector/threshold/model 在已揭示数据上的继续搜索；local policy 只能作为失败对照。
该门证明无条件 substrate edge 为负，不单独证明所有未来独立信息 selector 都无效。
即使两者通过，也不自动读取或解锁 HYPE。

## 证据

- [合同](../specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md)
- [P0 data quality](../artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json)
- [P0 event capacity](../artifacts/p0_events_2026-08-10/p0_capacity.json)
- [P1 summary](../artifacts/p1_temporal_audit_2026-08-10/p1_summary.json)
- [P1 report](../artifacts/p1_temporal_audit_2026-08-10/p1_report.json)
- [P1 manifest](../artifacts/p1_temporal_audit_2026-08-10/manifest.json)
