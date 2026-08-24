# Binance 1D MA7 BTC/ETH Shared V1 全参数消融

## 结论

在严格 development-only 的 `2019-12-24` 至 `2025-08-07` 窗口内，共运行 `121` 个 long/short 单参数 OAT 变体；`18` 个变体在 BTC、ETH 上均与 V1 逐笔等价，`0` 个变体同时达到两资产 `>=20x` 且 MDD 不超过 `20%`。

最强的单参数线索不是微调 stop/cooldown，而是改变 long entry lifecycle：把 long 从单日 `reclaim` 改为 `pullback_reclaim` 后，BTC/ETH development 终值提高到 `6.3164x / 6.0161x`，但 MDD 仍为 `-52.80% / -56.76%`；改为持续 `regime` 结果近似。该线索说明 V1 的 long reclaim 过度稀疏、错过趋势延续，但“放宽入场”同时释放大量低质量交易，尚未形成风险合格策略。

本轮没有读取 researcher-exposed audit，也没有选择或冻结下一版本。V1 继续为 `registered / not promoted / not live-ready`；P2 继续进入预注册的 entry/exit lifecycle 机制臂，重点解决放宽 long entry 后的跨 regime 回撤，而不是围绕最优单点继续调参。

## 冻结范围

- 合同：[P2 共享参数演进合同](../specs/binance-1d-ma7-shared-evolution-p2-contract-2026-08-12.md)
- Baseline：[V1 长历史零调参审计](../diagnostics/binance-1d-ma7-shared-v1-long-history-2026-08-12.md)
- 仅消费 development：`2019-12-24 00:00 UTC` 至 `2025-08-07 00:00 UTC` exclusive
- 每次只改变 long 或 short 的一个字段，其余字段与另一条腿保持 V1
- 使用基准成本、实际 funding、closed-bar/next-open 和真实 `1h` stop path
- 排名只用于 development 因果诊断；未运行 audit/OOS，不产生候选晋升结论

## Baseline

| Asset | Equity | MDD | Trades | PF |
| --- | ---: | ---: | ---: | ---: |
| BTC | `1.2235x` | `-60.41%` | 81 | `1.096` |
| ETH | `2.2988x` | `-65.67%` | 80 | `1.413` |

## 主要 OAT 结果

| Variant | BTC equity / MDD | ETH equity / MDD | 最差侧终值 | 裁决 |
| --- | ---: | ---: | ---: | --- |
| long `entry_mode=pullback_reclaim` | `6.3164x / -52.80%` | `6.0161x / -56.76%` | `6.0161x` | 收益显著改善，回撤硬失败 |
| long `entry_mode=regime` | `6.1604x / -53.97%` | `6.0161x / -56.76%` | `6.0161x` | 与上项近似；持续同侧暴露过强 |
| long `entry_mode=breakout` | `4.9969x / -51.71%` | `5.2240x / -65.90%` | `4.9969x` | ETH 尾部风险更差 |
| long `entry_buffer=0.0 ATR` | `3.1462x / -50.44%` | `3.0801x / -60.09%` | `3.0801x` | 放宽入场有正贡献，风险未修复 |
| long `entry_buffer=0.1 ATR` | `2.8102x / -53.46%` | `3.2350x / -58.26%` | `2.8102x` | 同上 |
| short `slope_lookback=7` | `2.2125x / -50.73%` | `2.0216x / -62.92%` | `2.0216x` | short 过滤改善有限 |
| short `cooldown=5d` | `1.4806x / -53.31%` | `2.9415x / -59.18%` | `1.4806x` | 不能跨资产解决尾部风险 |

## Entry lifecycle 归因

long `pullback_reclaim` 将 long 交易数从 baseline 的 BTC/ETH `40/40` 提高到 `76/76`；combined 总交易数为 `117/116`。收益提高来自允许趋势中持续 pullback 后重新入场，不是 stop 或 leverage 变化。

但退出原因显示新增 long 多数仍由 `ma7_slope_exit` 平仓：BTC/ETH 分别 `65/63` 次；combined 胜率仅 `37.61% / 42.24%`。因此下一轮不能简单把 `pullback_reclaim` 当 champion，而应把它作为冻结的 entry-lifecycle probe，与独立风险/退出臂做单项组合：

1. 限制持续 regime 中的重复 long 暴露；
2. 区分趋势正常回撤和结构性破坏，避免单一 slope exit 统治路径；
3. 对新增 long 的 MAE/MFE、持有期和亏损簇做 episode attribution；
4. 风险保护必须在 BTC、ETH 两侧同时降低 MDD，不能只牺牲弱侧换平均收益。

## Dormant / path-equal 结果

`18` 个变体在两资产 development 内逐笔等价：

- long `pullback_lookback=2/3/5/7`：当前 long 为 `reclaim`，字段不参与判定；
- long `breakout_lookback=2/3/5/10/14`：当前 long 非 `breakout`；
- short `breakout_lookback=2/3/5/7/14`：当前 short 非 `breakout`；
- long `max_hold=60/90d`：历史持仓在这些阈值前已由其它退出结束；
- short `trail=0/6 ATR`：在当前 development 路径上与冻结 `5 ATR` 逐笔等价，说明该 trail 在当前 stop/max-hold/MA7 组合中没有边际行为。

前三组可在后续 clean candidate 规格中按 entry mode 删除 schema-only 字段。long max-hold 与 short trail 只能标为 development-path dormant；在机制改变后必须重新消融，不能永久断言无效。

## 失败归因与下一步

本轮拒绝两类错误路线：

- 继续微调 short stop/cooldown：单参数最佳仍有约 `-59%` 至 `-63%` 最差侧 MDD；
- 直接采用 long `pullback_reclaim`：虽然两资产终值约 `6x`，但 MDD 仍超过 `50%`，且交易扩张近一倍。

下一步按 P2-C 建立一个冻结的 `long pullback lifecycle + risk/exit attribution` 机制臂。先对新增 long episode 做 MAE/MFE 和亏损簇归因，再测试少量机制级保护，不执行组合广搜；若没有机制能把两资产 MDD 大幅压低且保留跨资产收益，则关闭该 entry-lifecycle 方向。

## 裁决

- 全 active-parameter OAT 完整性：`PASS`
- audit/OOS 隔离：`PASS`（未读取）
- 两资产 `>=20x`：`0/121`
- 两资产 `MDD<=20%`：`0/121`
- P2-B 总裁决：`HARD-TARGET-FAILED / explore / not promoted / not live-ready`

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_shared_v1_full_parameter_ablation_2026-08-12.json) — SHA256 `4409a1e3781758c6f06989006bbeeaf193d18242c26f50a171bf169b1c430e51`
- [逐资产指标](../artifacts/binance_1d_ma7_shared_v1_full_parameter_ablation_2026-08-12_metrics.csv) — SHA256 `bacc92689754aec3f947b1e0b719f947cdb9d4e7c3d6a923cd6f3f2ed39ac7c6`
- [变体排名](../artifacts/binance_1d_ma7_shared_v1_full_parameter_ablation_2026-08-12_ranking.csv) — SHA256 `14107ca115ad1676409ca27eb5e6d309f1b8c142e3b71f4916c4b4a90e81be6d`
- [复现脚本](../scripts/audit_binance_1d_ma7_shared_v1_full_parameter_ablation.py)

