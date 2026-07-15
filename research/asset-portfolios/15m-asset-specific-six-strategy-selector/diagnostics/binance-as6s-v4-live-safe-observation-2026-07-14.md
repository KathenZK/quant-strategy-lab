# 六币单币优先 V4 无未来仲裁观察（2026-07-14）

## 结论

V3 在账户候选 strength 完全相同时使用 `exit_ts` 作为次级排序。`exit_ts` 只有交易结束后才知道，因此即使历史样本中没有真正触发该分支，这段规则也不满足可实盘要求。V3 的收益结论没有因此失真，但其 live-executable gate 必须判为 `FAIL`。

V4 不修改任何单腿、参数、暴露、strength、账户缩放或抢占门槛，只把候选顺序冻结为：

```text
strength descending
-> sleeve_id ascending
-> symbol ascending
-> side descending
```

并在执行契约中禁止入场仲裁读取：

- `exit_ts`
- `exit_reason`
- `net_return_1x`
- `mae_return_1x`

## 影响审计

[未来信息 tie-break 审计](../artifacts/binance_as6s_v3_future_tiebreak_audit_2026-07-14.json)重建了 15 条腿、三种执行情景和两条账户路线。

| 情景 | 同时入场组 | 最高 strength 平分组 | 删除 `exit_ts` 后逐笔账变化 |
| --- | ---: | ---: | --- |
| base | 46 | 0 | 无 |
| 8 bps | 46 | 0 | 无 |
| K+2 | 37 | 0 | 无 |

六条路线账的交易顺序、sleeve、entry、exit、side 和 exit reason 全部逐笔一致。因此 V4 的历史指标与 V3 完全相同，不需要重新挑腿或重新优化参数。

## V4 当前指标

| 路径 | 全区间笔数 | 笔/日 | 胜率 | 总收益 | 年化权益倍数 | 最大回撤 | 最近三个月收益 / 胜率 / 回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| nonpreemptive | 548 | 0.750 | 85.40% | +3387.63% | 5.91x | -12.86% | +72.47% / 84.81% / -7.47% |
| strong-breakout-preemptive | 557 | 0.763 | 85.46% | +2005.46% | 4.59x | -8.27% | +57.08% / 84.81% / -6.17% |

全六币均可交易后的频率仍分别为 `0.954` 与 `0.966` 笔/日。8 bps 和 K+2 压力门槛均保持通过。

## OOS 边界

V4 修复只依据静态代码审计和 `<2026-07-14T09:00Z` 的冻结历史交易账，没有读取任何该时点后的行情、收益或部分 OOS 指标。由于历史逐笔账不变，未来最终 OOS 继续沿用：

```text
[2026-07-14T09:00Z, 2026-10-14T09:00Z)
```

未来窗口必须结束后一次性揭示；不得提前查看部分结果。

## 冻结与复现

- V4 candidate：[账户 artifact](../artifacts/binance_as6s_asset_first_v4_live_safe_candidate_2026-07-14.json)
- V4 基准逐笔账：[交易 CSV](../artifacts/binance_as6s_asset_first_v4_live_safe_candidate_trades_2026-07-14.csv)
- 无未来账户路由：[as6s_live_safe_router.py](../scripts/as6s_live_safe_router.py)
- V4 冻结清单：[未来 OOS freeze](../artifacts/binance_as6s_v4_live_safe_future_oos_freeze_2026-07-14.json)
- 冻结校验：[verify_binance_as6s_v4_live_safe_freeze.py](../scripts/verify_binance_as6s_v4_live_safe_freeze.py)
- 一次性揭示：[reveal_binance_as6s_v4_live_safe_future_oos.py](../scripts/reveal_binance_as6s_v4_live_safe_future_oos.py)
- 实盘执行契约：[V4 execution contract](../artifacts/binance_as6s_v4_live_safe_execution_contract_2026-07-14.json)

## 状态

V4 为 `frozen observation / not registered / not promoted / not live-ready`。它解决了账户仲裁中的未来字段问题，但 runner 逐笔 parity、交易所 mark-price 保护差异、抢占双币连续成交和完整未来 OOS 仍是 promotion blocker。
