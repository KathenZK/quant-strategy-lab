# Decision Log

## 2026-07-07 首次组合回测（V35 + V1.3）

- 问题：把 `HYPE-EMA-Trend-Breakout-V35` 与 `HYPE-15M-MII-V1.3` 结合为一个新策略会怎样。
- 做法：在标准数据湖共同窗口上测试双子账户组合（50/50、70/30、30/70 逐 K 再平衡、50/50 固定拆分）与单账户冲突仲裁（V35 优先 preempt / no-preempt），V1.3 腿含 K+2 延迟压力。
- 校验：组合循环中的 V35 腿与 canonical 引擎逐 K 权益曲线零差；V1.3 腿 engine-exact 复核与主账一致（K+1 `549.30% / -22.01% / 84.78% / 184` 笔）。
- 结果：两腿日收益相关 `-0.087`。50/50 子账户回撤最浅方向（`-13.96%`，Sharpe `5.99`）但收益让渡大；单账户 V35 优先收益最高（K+1 `+34987.81%`）但回撤叠加到 `-28.01%`（K+2 压力 `-33.59%`）。preempt 显著优于 no-preempt；preempt 实际仅触发 2 次。
- 决定：记录为 first combination diagnostic，不登记版本、不 promotion；两个母版本均为 NO-GO，组合继承全部 blocker。后续若推进，先统一成本口径、补 V1.3 腿 funding、做仲裁规则邻域与滚动切片复核。
- 证据：`research-notes/hype-15m-tb-mii-ensemble-first-combination-backtest-2026-07-07.md`。
