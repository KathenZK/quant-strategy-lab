# Binance 1D MA7 P2-E Hard-MDD 共享参数广搜裁决

## 结论

P2-E 对现有 `SMA7/ATR7` price-only 状态机作了预注册、固定 seed 的 BTC/ETH 共享参数广搜。每方向生成 `20,000` 个唯一配置，完成单边筛选与稳定性审计后，将固定 `60 long × 60 short = 3,600` 个组合全部回测。

原 engine 的日内极值保守口径与随后修复的真实 `1h` 顺序口径结论一致：

- 两资产均满足真实 ordered `MDD<=20%`：`0 / 3,600`；
- 两资产均满足 `>=20x` 且真实 ordered `MDD<=20%`：`0 / 3,600`；
- development candidate：`0`；
- researcher-exposed audit 与 prospective：均未读取。

因此关闭现有 price-only MA7 参数面，裁决为 `HARD-GATE-FAILED / explore / not promoted / not live-ready`。不得把排名次优登记为 V2，也不得更换 seed、追加同类阈值或用杠杆放大收益；下一轮必须另立 materially new mechanism 合同。

## 冻结范围

- 主合同：[P2-E hard-MDD 共享搜索合同](../specs/binance-1d-ma7-p2e-hard-mdd-shared-search-contract-2026-08-12.md)
- MDD 修复合同：[P2-E ordered 1h MDD 修复合同](../specs/binance-1d-ma7-p2e-ordered-1h-mdd-repair-contract-2026-08-12.md)
- Development：`2019-12-24 00:00 UTC` 至 `2025-08-07 00:00 UTC` exclusive
- 成本：`0.001/fill + 4 bps`，实际 funding；稳定性审计另含 `8 bps` 与 `+1d delay`
- 执行：closed daily signal、next-open、真实 `1h` stop path、约 `1x`
- 参数随机种子：`20260812`，每方向固定 `20,000` 个唯一配置

## 分阶段结果

| Stage | Long | Short | Pair / candidate |
| --- | ---: | ---: | ---: |
| 随机唯一配置 | `20,000` | `20,000` | — |
| Stage 1 retained | `300` | `300` | — |
| Stage 2 stability retained | `60` | `60` | — |
| Stage 3 fixed pairs | — | — | `3,600` |
| ordered MDD-safe | — | — | `0` |
| hard-target | — | — | `0` |

Stage 1/2 已包含两资产单边 full、calendar、rolling、`8 bps` 与 `+1d delay`。Stage 3 无 hard-target，故不存在可进入一次性 audit 的唯一冻结候选。

## 收益与回撤 frontier

### 收益优先组合

真实 ordered 口径下，两资产较低终值最高的 pair 为：

| Asset | Equity | Ordered 1h MDD | 原日内极值 MDD | Trades |
| --- | ---: | ---: | ---: | ---: |
| BTCUSDT | `7.617x` | `-38.38%` | `-38.37%` | `55` |
| ETHUSDT | `9.326x` | `-39.24%` | `-37.26%` | `60` |

该 pair 的两资产最差终值为 `7.617x`，距离 `20x` 仍大，最差真实回撤为 `-39.24%`。

### 回撤优先组合

全部 `3,600` pairs 中最好的两资产最差真实回撤为 `-25.47%`，仍未达到 `-20%` hard gate：

| Asset | Equity | Ordered 1h MDD | 原日内极值 MDD | Trades |
| --- | ---: | ---: | ---: | ---: |
| BTCUSDT | `2.899x` | `-25.47%` | `-25.47%` | `25` |
| ETHUSDT | `4.753x` | `-24.87%` | `-32.38%` | `27` |

BTC 单资产有 `81` 个 ordered MDD-safe pairs，最佳 MDD 为 `-15.18%`；ETH 单资产为 `0`，最佳仅 `-24.87%`。因此当前共享参数空间的主要硬瓶颈是 ETH 路径风险，而不是组合排序权重。

## Ordered 1h MDD 口径修复

原 engine 在无 stop 日统一按日内 `favorable extreme -> adverse extreme` 计算回撤，可能把同一天晚于 adverse 的 favorable 先计入 peak。修复轮不改变信号、成交、费用、funding、终值或候选集合，只按 direct `1h` 的 UTC 顺序重放每笔账户权益，并在小时内部继续使用保守的 `open -> favorable -> adverse -> close`。

重放完整覆盖 `3,600 × 2` 条资产路径；收益终值与 engine 对账通过。收益优先 pair 的最大逐笔连续性误差为 `1.52e-11`，终值误差为 `7.46e-14`。修复显著纠正了部分 ETH `2020-03-12` 的伪顺序峰谷，但没有产生任何 MDD-safe pair，因此不会改变 P2-E 的失败裁决。

## 失败归因与下一步边界

1. **不是样本量不足**：每方向 `20,000` 个唯一配置，并经 calendar/rolling/stress/delay 后固定组合；继续换 seed 属于结果驱动扩池。
2. **不是单纯 MDD 算法误杀**：真实 1h 顺序修复后最佳共享最差 MDD仍为 `-25.47%`，ETH 无任何单资产 `<=20%` pair。
3. **收益与风险同时缺口明显**：收益 frontier 仅 `7.62x/9.33x` 且回撤约 `39%`；风险 frontier 终值仅 `2.90x/4.75x`。
4. **静态阈值面已穷尽本轮授权**：P2-C/P2-D 的 episode stop、静态 MA7 退出失败，本轮完整参数面也失败；不能继续搜相同 entry buffer、confirm、stop ATR、trail、hold 或 cooldown。
5. **后续必须改变信息或状态结构**：可预注册研究 slow-regime / volatility-state / lifecycle lockout 等独立机制，但必须保持 closed-bar/next-open、1x 风险口径和双资产共享参数；先做因果诊断，再开有限机制臂，不能从失败 frontier 直接救参。

## 机器证据

- [P2-E 主 JSON](../artifacts/binance_1d_ma7_p2e_hard_mdd_shared_search_2026-08-12.json) — SHA256 `861563b01442596a3c5a7bcc25ec713697f699eb768783f5482a9cc0617c87d4`
- [Stage 3 pairs](../artifacts/binance_1d_ma7_p2e_hard_mdd_shared_search_2026-08-12_pairs.csv) — SHA256 `84cbf49e025570a0b5a41ee530f5a423849f36da5fe732525ad2912f36a9ddfe`
- [Development 稳定性指标](../artifacts/binance_1d_ma7_p2e_hard_mdd_shared_search_2026-08-12_audit_metrics.csv) — SHA256 `94a8de4fb38cd353ffc5c584274a24ef233436149fdce99e88086293d1fb906c`
- [Ordered 1h MDD 主 JSON](../artifacts/binance_1d_ma7_p2e_ordered_1h_mdd_2026-08-12.json) — SHA256 `cea2b7e7bd824a447708585ebdbd6bbda24721c485703be91f85e1d0814f923c`
- [Ordered 1h MDD 全量 pairs](../artifacts/binance_1d_ma7_p2e_ordered_1h_mdd_2026-08-12_pairs.csv) — SHA256 `ec0e2bef9e0a20c286fb9b232f53502251010d0c5486c5b7503457b07ca6193a`
- [搜索脚本](../scripts/search_binance_1d_ma7_p2e_hard_mdd_shared.py)
- [Ordered MDD 修复脚本](../scripts/audit_binance_1d_ma7_p2e_ordered_1h_mdd.py)
