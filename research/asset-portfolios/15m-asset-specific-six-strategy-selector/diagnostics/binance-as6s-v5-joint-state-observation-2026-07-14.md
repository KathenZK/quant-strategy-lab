# 六币单币优先 V5 联合状态观察（2026-07-14）

## 结论

V5 保留 V4 的 15 条资产专属腿、全部参数、单腿暴露、strength 公式、账户缩放和抢占门槛，只修正候选状态语义：

```text
市场信号出现
-> 进入账户仲裁
-> 未获账户仓位：立即丢弃，不排队，不修改任何 sleeve 状态
-> 获得账户仓位：由全局账户创建唯一持仓
-> 真实退出后：才写入该 sleeve 的显式 cooldown
```

因此 V5 才符合“空仓时竞争、持仓时不抢占或仅允许冻结规则下的强突破抢占”的真实联合状态机。V4 因预先应用 `frontier15m / cleanrsi15m` 假想持仓而被否决；证据见[联合状态审计](../artifacts/binance_as6s_v4_joint_state_audit_2026-07-14.json)。

## 历史影响

| 路径 | V4 笔数 | V5 笔数 | V5 胜率 | V5 总收益 | 年化权益倍数 | 最大回撤 | 最近三个月收益 / 胜率 / 回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| nonpreemptive | 548 | 553 | 85.17% | +3280.13% | 5.82x | -12.86% | +69.19% / 83.95% / -7.89% |
| strong-breakout-preemptive | 557 | 564 | 85.11% | +1963.97% | 4.54x | -8.27% | +54.62% / 83.95% / -6.51% |

全六币均可交易后的频率分别为 `0.966` 与 `0.983` 笔/日，仍接近目标 `1` 笔/日。

## 压力情景

| 路径 | 情景 | 全区间笔数 | 胜率 | 总收益 | 年化权益倍数 | 最大回撤 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| nonpreemptive | 8 bps | 548 | 85.04% | +2338.91% | 4.94x | -13.28% |
| nonpreemptive | K+2 | 565 | 81.77% | +1368.07% | 3.83x | -19.30% |
| strong-breakout-preemptive | 8 bps | 560 | 84.82% | +1467.69% | 3.96x | -8.69% |
| strong-breakout-preemptive | K+2 | 581 | 81.58% | +1026.06% | 3.36x | -17.17% |

两条路线在基础、8 bps 与 K+2 下均保持账户胜率不低于 `80%`、总收益为正且最大回撤小于 `20%`。这些仍是已揭示历史诊断，不替代未来 OOS。

## OOS 边界

V5 只读取 `<2026-07-14T09:00Z` 的原冻结历史数据，推导过程没有读取后续行情或部分收益。未来最终 OOS 继续锁定为：

```text
[2026-07-14T09:00Z, 2026-10-14T09:00Z)
```

窗口结束前不得检查部分结果；结束后一次性揭示。V5 当前为 `frozen observation / not registered / not promoted / not live-ready`，不能用历史修复替代最终未来 OOS。

## 复现入口

- 联合状态审计：[audit_binance_as6s_v4_joint_state.py](../scripts/audit_binance_as6s_v4_joint_state.py)
- V5 candidate：[binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json](../artifacts/binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json)
- V5 逐笔账：[binance_as6s_asset_first_v5_joint_state_candidate_trades_2026-07-14.csv](../artifacts/binance_as6s_asset_first_v5_joint_state_candidate_trades_2026-07-14.csv)
- 无未来账户路由：[as6s_live_safe_router.py](../scripts/as6s_live_safe_router.py)
- V5 冻结清单：[binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json](../artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json)
- V5 执行契约：[binance_as6s_v5_joint_state_execution_contract_2026-07-14.json](../artifacts/binance_as6s_v5_joint_state_execution_contract_2026-07-14.json)
- 历史逐笔重建门禁：[test_as6s_v5_reveal_parity.py](../../../../tests/test_as6s_v5_reveal_parity.py)

## 当前 blocker

- `quant-runner` joint Driver 尚未完成逐笔 parity；
- 交易所 mark-price 保护和强突破抢占的先平后开流程尚未通过 dry-run；
- 完整未来三个月 OOS 尚未到揭示时点。
