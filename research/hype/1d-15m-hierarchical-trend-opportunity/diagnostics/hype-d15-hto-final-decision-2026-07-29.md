# HYPE-D15-HTO 最终研究决策

## 结论

本轮没有找到同时满足“年化权益倍数 `>=10x`、净胜率 `>=50%`、最大回撤 `<20%`”的 HYPE 日线方向 + `15m` 择时策略。最终状态为 `registered / not promoted / not live-ready`，不创建 live spec，不交接 `quant-runner`。

## 冻结流程

- 数据：40,770 根 Binance `HYPEUSDT` 永续已收盘 `15m`，`2025-05-30 10:30 UTC` 至 `2026-07-29 02:45 UTC`；缺口、重复、关键空值、OHLCV 异常与 raw/normalized mismatch 均为 0。
- 日线：424 个完整 UTC 日；首尾不完整日排除。
- locked OOS：`[2026-04-29 03:00 UTC, 2026-07-29 03:00 UTC)`，8,736 根；搜索阶段未读取。
- 原始搜索：30,000 组全局随机 + 20,000 组机制前沿邻域，共 50,000 组，冻结 V1。
- 消融：34 个参数槽位 + 10 个组件；V2 删除 path-equal/dormant 自由度，并与 V1 逐笔等价。
- clean 调优：40,000 组风险参数 + 80,000 组联合参数，共 120,000 组，冻结 V3。
- 总计评估 170,000 个不重复配置；开发段三项硬门槛同时命中数为 0，OOS 前最后 60 日单段命中 44 组，但没有任何一组同时通过开发段与内部验证段。

## 冻结指标

| 版本 / 区间 | 年化倍数 | 净收益 | 胜率 | MDD | 交易数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 prefit | `1.488x` | `+43.75%` | `62.07%` | `18.85%` | 58 |
| V3 prefit | `1.838x` | `+74.40%` | `60.00%` | `20.98%` | 50 |
| V3 locked OOS | `0.242x` | `-29.76%` | `29.41%` | `36.75%` | 17 |
| V3 全冻结样本连续回放 | `1.191x` | `+22.50%` | `52.24%` | `36.75%` | 67 |

同期 OOS 1x 买入持有净收益为 `+35.69%`，策略超额为 `-65.45` 个百分点。OOS 零手续费、零滑点仍为 `-20.72%`，说明失败不是成本单独造成。

## 稳健性门禁

- `8 bps/fill`：prefit 年化 `1.649x`，MDD `21.81%`。
- K+2：prefit 年化 `1.564x`，MDD `20.62%`；K+3 MDD `32.34%`。
- 交易 bootstrap 10,000 次：MDD 95 分位 `30.58%`，亏损概率 `3.42%`。
- 1,000 个局部参数邻域：prefit 目标命中率 `0%`，prefit 正收益占比 `25.3%`，中位 MDD `35.36%`。
- 真实 1m 相位：+5 分钟 MDD `41.00%`；+10 分钟净亏损 `8.81%`，相位门禁失败。
- OOS：17 笔、胜率 `29.41%`、MDD `36.75%`，三项硬门槛全部失败。

## 实盘边界

研究内核使用闭合日线、闭合 `15m`、next-open、stop-first、gap-at-open、实际资金费和最高 `2.5x`，不存在已知前视或陈旧 stop fill。但“可在回测中按实盘时序计算”不等于“已可实盘”：本版本既未通过绩效与稳健性门禁，也没有 runner 的保护单生命周期、拒单恢复、重启恢复、断流 fail-closed、kill switch、指标/信号 parity 和线上逐笔对账证据。

若未来重开，必须采用 materially new mechanism，并从 `2026-07-29 03:00 UTC` 之后启动全新的 outcome-blind prospective OOS；不得在已揭示的最近三个月上调参。

## 证据

- [数据冻结](../artifacts/hype_d15_hto_dataset_freeze_2026-07-29.json)
- [V1 搜索](../artifacts/hype_d15_hto_v1_search_2026-07-29.json)
- [V1 全消融](../ablations/hype-d15-hto-v1-full-ablation-2026-07-29.md)
- [V3 调优](../artifacts/hype_d15_hto_v3_tune_2026-07-29.json)
- [V3 prefit 稳健性](hype-d15-hto-v3-prefit-robustness-2026-07-29.md)
- [V3 locked OOS](hype-d15-hto-v3-locked-oos-final-2026-07-29.md)
- [V3 冻结规格](../specs/hype-d15-hto-v3-spec.md)

