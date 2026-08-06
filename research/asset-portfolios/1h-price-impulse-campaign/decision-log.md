# Decision Log

## 2026-08-03：冻结从 habitat 到可执行订单状态机的 V0

用户要求不再停留于趋势分析，而要形成可线上运行的量化策略。本轮冻结 ETH 为执行候选、BTC/HYPE/SOL 为同规则控制；使用每日 `4h` 纯价格冲量、真实 quantity、`1%` 计划风险、`3x` leverage cap、`1R` stop、24h 验证、`2R` 后半 MFE 和 14d timeout。历史规则在 FATHA 结果揭示后形成，所以回测只能筛除失败和执行错误，不能被描述成新 OOS。冻结后不做 threshold rescue。

## 2026-08-03：V0 未过最低门禁，冻结 materially new V1 分层订单结构

ETH 扩展至 2019-11-27 后，V0 base `+5.52% / Sharpe 0.13 / MDD -27.46% / 402 campaigns`，8bps stress `-1.60%`，最近 6m `-1.02%`，120d rolling 正窗口 `48.1%`，未过冻结门禁。收益集中在 7 个 336h timeout 右尾，而满额 probe 与半 MFE 全平造成大量试错和提前离场。V0 保持 `explore / not promoted / not live-ready`，不接 runner。

在运行 V1 前另行冻结 materially new 的订单结构：初始只承担完整计划风险的 25%，达到 `0.5R/1R/2R` 后在 open-risk 允许时加到 `50%/75%/100%`；半 MFE 回吐只去掉新增风险并永久保留 probe，不再把整个趋势仓平掉。V1 不改变 admission threshold，不使用 V0 消融中的更优替代参数。

## 2026-08-03：V1 揭示 funding 风险漂移，运行前冻结 V2 风险不变量

V1 ETH base 为 `+53.93% / Sharpe 0.82 / MDD -11.64% / 273 campaigns`，8bps stress `+49.22%`，120d rolling 正窗口 `75.3%`；但最近 6m 为 `-0.20%`，且 62 个 campaign 的 projected stop-out 损失曾超过 entry equity 的 `1%`，最坏 `2.06%`。不含 funding 时风险超限为 0，确认根因是长持有期间 funding 累积，而不是 add 当下的 quantity 公式。V1 未过冻结门禁，保持 `explore / not promoted / not live-ready`。

在运行 V2 前冻结单一机制修复：add 只使用 `0.9%` operational stop-out budget，并在每次 funding 入账后以 LIFO `risk_trim` 持续恢复该预算；去掉全部新增层仍不够时退出 probe。V2 不改变任何 admission、方向或趋势退出阈值，结果不得用于回写本合同。

## 2026-08-03：V2 风险修复通过，但最近 6m 门禁失败

V2 ETH base `+47.93% / Sharpe 0.82 / MDD -11.05% / 273 campaigns`，8bps stress `+43.54%`，120d rolling 正窗口 `74.0%`。718 次 funding 后 risk trim 已计入真实 fill 成本；projected stop-out 最坏 `0.90%`，硬风险违规为 0。最近 6m 为 `-0.23% / 24 campaigns`，因此全部最低门禁为 false。V2 保持 `explore / not promoted / not live-ready`，不生成 live spec、不接 runner、不事后选择 long-only 或修改最近 6m 门禁。
