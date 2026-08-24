# BTC 日线青泽临界点趋势参数搜索与锁定验证

## 结论

原始 SMA60 基线的主要问题在 development 段：520 天仅 `+0.32%`、MDD `-13.38%`，其中第二折 `-3.07%`；参数搜索把 development 提升到 `+21.94%`，但预先冻结的 rank 1 在 209 天 validation 上变成 `-0.55%`、Sharpe `-0.01`。这是一轮明确的样本外衰减，不支持登记或 promotion。

合同：[btc-1d-qz-cpt-parameter-search-contract-2026-08-07.md](../specs/btc-1d-qz-cpt-parameter-search-contract-2026-08-07.md)

## 搜索协议

- Development：`2024-07-31` 至 `2026-01-01`，520 根
- Validation：`2026-01-02` 至 `2026-07-29`，209 根
- 去重随机参数：20,000 组，seed `20260807`
- 合资格组合：11,080 组；development 正收益组合 13,479 组，合资格且正收益 10,721 组
- Development 内部分为三折，以最差折、折中位数、全段收益和 MDD 共同排序
- Rank 1 在查看 validation 前冻结；validation 没有参与重新选参
- 成本：每 fill 手续费 `0.001` + 不利滑点 `4 bps`，纳入实际 funding
- OI：仍因只有 8 天覆盖而不使用，不能把本轮当作原叙述完整还原

## 原始基线失败位置

| 区间 | 净收益 | MDD | Sharpe | 交易 |
| --- | ---: | ---: | ---: | ---: |
| Development 全段 | `+0.32%` | `-13.38%` | `0.07` | 8 |
| Fold 1 | `+3.37%` | `-6.62%` | `0.61` | 2 |
| Fold 2 | `-3.07%` | `-5.38%` | `-0.82` | 3 |
| Fold 3 | `+0.54%` | `-3.91%` | `0.19` | 3 |
| Validation | `+2.95%` | `-5.06%` | `0.49` | 3 |

因此先前全窗口 `+0.88%` 不是因为 2026 validation 单独崩坏，而是 2024–2025 的基线信号本来就弱，尤其是 `2025-02-01～2025-07-31`。Validation 反而比 development 好，但仅 3 笔，不能反证稳健。

## 冻结的 Development Rank 1

| 参数 | 值 |
| --- | --- |
| 趋势 | `SMA40`，连续 2 日同侧，偏离至少 `1%` |
| A 突破 | 前 10 日极值，当日变动至少 `1%` |
| 成交量 | 当日量至少为前 3 日均量的 `1.75x` |
| B 蓄力 | 前 7 日、振幅 `<2%`、突破变动不超过 `1.5%` |
| ATR / stop | `ATR10` / `5 ATR` |
| 仓位 | `20% + 12% + 8%` 正金字塔 |

Development 表现：

- 净收益 `+21.94%`，MDD `-10.62%`，Sharpe `1.10`
- 6 笔，胜率 `66.67%`，PF `9.87`
- 三折分别 `+11.33% / +6.88% / +3.69%`
- 40% BTC buy-and-hold 同期 `+13.58%`

看似稳定，但交易层暴露出明显脆弱性：

1. 只有 6 笔交易；第一笔 `+12.99%`，前两笔主要盈利单合计贡献约九成逐笔净收益。
2. 所有 6 笔都来自 A 类信号；即使把 B 类振幅放宽到 `2%`、窄幅期改为 7 日，B 类仍没有一笔入场。
3. 搜索前六名的 development 分数和交易结果完全相同，只是部分未生效参数不同，说明参数身份不可辨识。
4. Development 峰值持仓市值暴露 `51.83%`；虽然下单分配合计 40%，持仓漂移已经超过“任何时刻不超过 40%”的严格解释。

## 锁定 Validation

| 指标 | Rank 1 | 原始基线 | 40% BTC buy-and-hold |
| --- | ---: | ---: | ---: |
| 净收益 | `-0.55%` | `+2.95%` | `-11.30%` |
| MDD | `-8.04%` | `-5.06%` | 未单列 |
| Sharpe | `-0.01` | `0.49` | 未单列 |
| 交易 | 4 | 3 | 1 次持有 |
| 胜率 | `50.00%` | `33.33%` | n/a |
| PF | `0.93` | `2.92` | n/a |

冻结 rank 1 虽然相对下跌的 40% buy-and-hold 仍有 `+10.75pct` 超额，但绝对收益转负，且明显落后于未调参原始基线。不能把弱基准下的相对防守解释成搜索成功。

Validation 四笔交易：

| 方向 | 入场 | 退出 | 净收益 |
| --- | --- | --- | ---: |
| Long | 2026-01-06 | 2026-01-26 | `-2.97%` |
| Short | 2026-01-30 | 2026-03-17 | `+2.98%` |
| Long | 2026-05-05 | 2026-05-28 | `-2.64%` |
| Short | 2026-06-02 | 2026-07-16 | `+2.22%` |

失败位置很具体：两笔空头延续单均盈利，但两笔多头均在反向趋势退出前亏损；更快的 SMA40 和更宽的 `5 ATR` stop 延长了错误多头持有，最终把空头利润吃光。

Validation 近期切片：

| 窗口 | 净收益 | MDD |
| --- | ---: | ---: |
| 1d | `0.00%` | `0.00%` |
| 7d | `0.00%` | `0.00%` |
| 1m | `-2.47%` | `-3.48%` |
| 3m | `-0.47%` | `-3.48%` |
| 6m | `+2.43%` | `-8.04%` |

Validation 短于一年，因此不伪造 `1y` 切片；这些切片只用于锁定后审计。

## 参数邻域诊断

Development top 20 打开 validation 后：

- 12/20 正收益；
- 中位数 `+0.61%`；
- 范围 `-0.55%～+3.74%`；
- development 收益与 validation 收益相关系数约 `0.41`。

这说明附近不是所有参数都完全失效，但冻结 rank 1 恰好落在 top-20 validation 最差端。不能事后改选 validation `+3.74%` 的 rank 7；那会污染 holdout。正确结论是：搜索排序对少量交易和行为等价参数过于敏感，当前 rank 身份不稳定。

Top 100 的共同倾向也很集中：

- 100/100 使用 `SMA40`；
- 69/100 使用 pyramiding；
- stop 只剩 `4 ATR` 或 `5 ATR`；
- 69/100 使用最高的 `1.75x` 成交量门槛；
- 没有 B-only 候选，只有 A 或 AB。

搜索实际上偏向“更快趋势 + 更严格放量 + 更宽止损”，主要捕捉 2024–2025 少数大趋势 campaign，而没有恢复 B 类机制或提高独立样本数。

## 决定

- 本轮判定：`locked holdout failed / explore / not promoted / not live-ready`。
- 不登记 rank 1，不用 validation 重选 rank 7，也不继续在同一 validation 上迭代。
- 若继续研究，必须换一段新的 clean OOS，或先补足历史 OI 后重建机制；当前 validation 已暴露，不能再次充当最终 holdout。
- “仓位≤40%”若是硬约束，后续引擎还必须加入动态暴露上限，而不是仅限制初始下单分配。

## 证据

- [机器摘要](../artifacts/btc_1d_qingze_parameter_search_summary_2026-08-07.json)
- [20,000 组候选](../artifacts/btc_1d_qingze_parameter_search_candidates_2026-08-07.csv)
- [Development Top 100](../artifacts/btc_1d_qingze_parameter_search_frontier_2026-08-07.csv)
- [Top 20 锁定验证](../artifacts/btc_1d_qingze_parameter_search_validation_2026-08-07.csv)
- [Rank 1 development 交易](../artifacts/btc_1d_qingze_parameter_search_selected_development_trades_2026-08-07.csv)
- [Rank 1 validation 交易](../artifacts/btc_1d_qingze_parameter_search_selected_validation_trades_2026-08-07.csv)
- [Rank 1 validation 路径](../artifacts/btc_1d_qingze_parameter_search_selected_validation_path_2026-08-07.csv)
- [Rank 1 validation 近期切片](../artifacts/btc_1d_qingze_parameter_search_selected_validation_recent_2026-08-07.csv)
- [Rank 1 validation 交互图](../artifacts/btc_1d_qingze_parameter_search_selected_validation_trade_path_2026-08-07.html)
- [搜索脚本](../scripts/search_btc_1d_qingze_parameters.py)
