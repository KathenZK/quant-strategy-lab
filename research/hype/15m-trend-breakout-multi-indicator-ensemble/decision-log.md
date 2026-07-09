# Decision Log

## 2026-07-09 V2 live validation spec 导出（非实盘批准）

- 问题：用户说明此前 `HYPE-EMA-Trend-Breakout-V35` 在实盘运行过，现在希望把 `HYPE-15M-TB-MII-ENS-V2` “实盘看看”，要求先出一份 live spec 文档。
- 做法：导出 V2 live validation spec，明确 V2 不是 V35 runner 配置改参即可运行，而是需要新增组合状态机、`HYPE-15M-MII-V1.4` 腿、全局单仓仲裁、`preempted_by_v39` 强平让位流程、保护单、重启恢复、交易所对账和 kill switch。
- 关键边界：V2 live 前不得与现有 V35 live service 在同一 Binance 账户 / `HYPEUSDT` 上同时真单运行；若只做 shadow/dry-run，可以并行但不得提交真实订单或撤改 V35 订单。preempt 必须先取消 V1.4 保护单、只减仓平 V1.4、确认 flat，再开 V39。
- 决定：状态更新为 `live validation spec draft / NO-GO / not promoted / not live-ready`，不构成 dry-run 或 live 批准。下一步应先实现 runner replay，对拍标准数据湖 `291` 笔、V39 `107` 笔、V1.4 `184` 笔、preempt `3` 次，再做 shadow/dry-run。
- 证据：[V2 live validation spec](live-specs/hype-15m-tb-mii-ens-v2-live-validation-spec-not-live-ready-2026-07-09.md)、[V2 主账](hype-15m-tb-mii-ens-core-ledger.md)。

## 2026-07-09 V2 登记与近一年周度开单审计

- 问题：用户要求把 `HYPE-EMA-TB-V39 + HYPE-15M-MII-V1.4` 组合记录为 `V2`，并查看过去一年每周开单数与周胜率。
- 登记：`V2` 固定为单账户主口径 `single_v39_priority_k1`，即 V39 优先、V1.4 只在 V39 空档开仓，若 V39 入场信号出现则强平 V1.4 让位；MII 腿使用 K+1 open。
- 周度审计：窗口锚定数据末尾 `2026-07-08T05:30:00Z` 向前一年；按 `entry_ts` 归入 UTC ISO 周。过去一年共 `274` 笔，`228` 胜 / `46` 负，整体胜率 `83.21%`；V39 `104` 笔，V1.4 `170` 笔；有交易周 `48` 个，零交易周 `5` 个；最高开单周为 `2026-W05`，`20` 笔，胜率 `90.00%`。
- 决定：主账登记为 `V2 registered diagnostic / NO-GO / not promoted / not live-ready`。登记只表示组合版本留名，不构成 promotion；仍继承 V39 未跨所/未 walk-forward/未 live-executable 审计、V1.4 未 runner dry-run 与同样本选参风险，以及组合特有 preempt 换仓时序风险。
- 证据：[组合回测报告](notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md)、[V2 周度审计](notes/hype-15m-tb-mii-ens-v2-weekly-trade-audit-2026-07-09.md)、[V2 周度 CSV](artifacts/hype_15m_tb_mii_ens_v2_single_v39_priority_k1_weekly_trades_1y_2026-07-09.csv)。

## 2026-07-09 V39 + V1.4 组合复测（含门禁校验）

- 问题：反转腿从 `HYPE-15M-MII-V1.3` 升级为 `HYPE-15M-MII-V1.4`（`min_rvol96 1.0 -> 0.85`）后，与 `HYPE-EMA-TB-V39` 的组合结果如何；全链路门禁校验。
- 门禁：数据质量 gate 全 `0`（同 2026-07-08 窗口）；V39 腿与 canonical 引擎逐 K 零差且与主账登记值一致；V1.4 engine 全样本与 MII 主账登记值逐项一致（K+1 `+978.36% / -24.70% / 232 笔`；K+2 `+535.54% / -38.30%`）；V1.4 腿单仓链逐笔一致（K+1 `221` 笔、K+2 `228` 笔），终值零差。全部通过。
- 结果：`single_v39_priority_k1` 全样本 `+68192.54% / -28.01% / Sharpe 5.79 / 291 笔`（V39 `107` + V1.4 `184`，让位 `3` 次），比 V1.3 轮收益 +71% 而全样本回撤不变；K+2 压力回撤从 `-33.82%` 收敛到 `-30.98%`；`portfolio_5050_rebal_k1` `+3733.19% / -13.96% / 6.23`；两腿日收益相关 `-0.074`。最近 1 月 MII 腿 `-3.50%`（V1.3 轮 `-11.02%`），仍拖累组合（`+14.85%` vs V39 单独 `+23.40%`）。
- 决定：当时维持 `combination diagnostic / NO-GO / not live-ready`，暂不登记版本；后续同日按用户要求登记为 `V2`，见上方记录。V1.4 的 `min_rvol96=0.85` 是同一数据湖上选出的进取观察点，组合层改善继承同样本选参风险；组合继承 V39（未跨所/未 walk-forward/未 live-executable 审计）与 V1.4（registered、未 runner dry-run）的全部 blocker。
- 证据：[hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md](notes/hype-15m-tb-mii-ensemble-v39-v14-combination-backtest-2026-07-09.md)。

## 2026-07-08 V39 + V1.3 组合复测（含门禁校验）

- 问题：趋势腿从 `HYPE-EMA-TB-V35` 升级为 `HYPE-EMA-TB-V39` 后，与 `HYPE-15M-MII-V1.3` 的组合结果如何；同时对全链路做门禁校验。
- 门禁：数据质量 gate（`38765` 根，缺口/重复/无效 OHLC/空值/raw-normalized mismatch 全 `0`）；V39 腿与 canonical 引擎逐 K 权益零差；V39 canonical 与主账登记值逐项一致（`+9969.45% / -23.46% / 107 笔 / 79.44%`）；V1.3 腿单仓选择链与 MII 引擎逐笔一致（K+1 `176` 笔、K+2 `181` 笔），终值零差。全部通过。
- 结果：结构性结论与 V35 版一致。`single_v39_priority_k1` 全样本 `+39829.29% / -28.01% / Sharpe 5.47 / 248 笔`（V39 `107` + V1.3 `141`，让位 `2` 次）；`portfolio_5050_rebal_k1` `+2748.51% / -13.96% / 5.87`；两腿日收益相关 `-0.084`。新增发现：最近 1 月 V1.3 腿 `-11.02%` 把单账户组合拖到 `+5.89%`（V39 单独 `+23.40%`），低波动期 V1.3 不只是不开单，还可能贡献负收益段。
- 决定：维持 `combination diagnostic / NO-GO / not live-ready`，不登记版本；组合继承 V39（未跨所/未 walk-forward/未 live-executable 审计）与 V1.3（dry-run 观察中）的全部 blocker。
- 证据：[hype-15m-tb-mii-ensemble-v39-combination-backtest-2026-07-08.md](notes/hype-15m-tb-mii-ensemble-v39-combination-backtest-2026-07-08.md)。

## 2026-07-07 首次组合回测（V35 + V1.3）

- 问题：把 `HYPE-EMA-Trend-Breakout-V35` 与 `HYPE-15M-MII-V1.3` 结合为一个新策略会怎样。
- 做法：在标准数据湖共同窗口上测试双子账户组合（50/50、70/30、30/70 逐 K 再平衡、50/50 固定拆分）与单账户冲突仲裁（V35 优先 preempt / no-preempt），V1.3 腿含 K+2 延迟压力。
- 校验：组合循环中的 V35 腿与 canonical 引擎逐 K 权益曲线零差；V1.3 腿 engine-exact 复核与主账一致（K+1 `549.30% / -22.01% / 84.78% / 184` 笔）。
- 结果：两腿日收益相关 `-0.087`。50/50 子账户回撤最浅方向（`-13.96%`，Sharpe `5.99`）但收益让渡大；单账户 V35 优先收益最高（K+1 `+34987.81%`）但回撤叠加到 `-28.01%`（K+2 压力 `-33.59%`）。preempt 显著优于 no-preempt；preempt 实际仅触发 2 次。
- 决定：记录为 first combination diagnostic，不登记版本、不 promotion；两个母版本均为 NO-GO，组合继承全部 blocker。后续若推进，先统一成本口径、补 V1.3 腿 funding、做仲裁规则邻域与滚动切片复核。
- 证据：[hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md](notes/hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md)。
