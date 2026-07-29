# HYPE-15M-SDS Decision Log

- 2026-07-28：建立独立 `HYPE-15M-Sequential-Drift-State` 家族。未编号顺序漂移/CUSUM 基线在冻结前写定参数，family-local reused OOS 只揭示一次；prefit、OOS 和 full 均显著亏损，因此不登记版本、不进入消融或 promotion。[报告](notes/hype-15m-sds-baseline-and-prefit-search-2026-07-28.md)
- 2026-07-28：只在 prefit 内测试 432 个滚动回归趋势状态配置；满足 train/validation 最低样本量的 144 个配置中，没有一个两段同时正收益。停止当前回归搜索表面，不读取或重测已揭示 OOS；后续只接受 materially new 机制和 `2026-07-28 08:00 UTC` 后 prospective OOS。[报告](notes/hype-15m-sds-baseline-and-prefit-search-2026-07-28.md)
- 2026-07-28：按“趋势发现 → armed → 回踩重测 → active → weakening”测试 384 个 prefit-only campaign 配置；288 个满足样本量，但 train/validation 同时正收益仍为 0。停止当前纯 OHLCV 15m 搜索，不揭示或重测 locked reused OOS。[报告](notes/hype-15m-sds-baseline-and-prefit-search-2026-07-28.md)
- 2026-07-28：用户明确要求后，将 causal Kalman slope/uncertainty、Page CUSUM、Donchian/efficiency 结构确认和非对称迟滞状态机作为第四机制，仅在 prefit 搜索 384 个冻结组合。全部组合 train 和 validation 均为负；最不差参考为 `-10.02% / -5.93%`，零成本 prefit 仍 `-0.70%`。不登记、不读取已揭示 reused OOS，纯 OHLCV 搜索继续停止。[报告](notes/hype-15m-sds-kalman-cusum-structure-2026-07-28.md)
- 2026-07-28：按用户要求冻结 KCS 最不差失败参考，对 18 个信号/状态参数和 3 个执行风险参数完成 85 个 one-at-a-time 全参数消融。73 个变体满足样本量，validation 正收益与合格候选仍均为 0；`max_hold` dormant，杠杆仅缩放，严格过滤产生低样本伪改善。禁止组合各单项最好值或读取 reused OOS。[报告](ablations/hype-15m-sds-kcs-full-parameter-ablation-2026-07-28.md)
