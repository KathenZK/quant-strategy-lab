# HYPE Cross-Strategy Account Decision Log

## 2026-07-02：`HYPE-5M-PBTR-V6.2.1` + `HYPE-15M-MII-V1.3` 共享子账户单仓诊断

- 问题：如果 `HYPE-5M-PBTR-V6.2.1` 与 `HYPE-15M-MII-V1.3` 跑同一个 HYPEUSDT 子账户，并且全局只允许一个持仓，会怎样。
- 口径：共同窗口 `2025-06-02T21:40:00+00:00` 到 `2026-06-18T18:45:00+00:00`；候选信号按 entry time 排序；已有持仓未退出时后续候选信号视为 blocked；entry 与上一笔 exit 同 timestamp 保守 blocked；未计资金费和盘口级滑点。
- 结果：`PBTR only` 为 `218` 笔、总收益 `1078.68%`、已平仓 DD `-22.35%`、Close MTM DD `-26.10%`、Intrabar adverse DD `-54.93%`；`MII only` 为 `182` 笔、总收益 `523.41%`、已平仓 DD `-17.23%`、Close MTM DD `-21.54%`、Intrabar adverse DD `-22.24%`；组合为 `368` 笔、总收益 `7187.12%`、已平仓 DD `-30.28%`、Close MTM DD `-32.34%`、Intrabar adverse DD `-55.23%`、胜率 `74.73%`、PF `2.050`。
- 阻塞：组合中 PBTR 成交/阻塞 `206/211`，MII 成交/阻塞 `162/61`；跨策略阻塞为 MII 被 PBTR 阻塞 `27` 次、PBTR 被 MII 阻塞 `23` 次。同 timestamp 优先级在该样本内没有改变结果。
- 判断：组合提高了样本内交易频率和复利收益，但已平仓 DD 从两个单策略的 `-22%`/`-17%` 扩到 `-30.28%`，逐 K close MTM DD 为 `-32.34%`；只有在每根 K 使用最不利 high/low 做强制平仓式标记时，账户浮亏压力才接近 `-55%`。这不是更安全的合并。两个子策略原状态不变：`HYPE-15M-MII-V1.3` 仍为 `not live-ready`，`HYPE-5M-PBTR-V6.2.1` 仍只适合低 notional dry-run 观察。
- 证据：[hype-pbtr-v6-2-1-mii-v1-3-shared-account-2026-07-02.md](diagnostics/hype-pbtr-v6-2-1-mii-v1-3-shared-account-2026-07-02.md)；脚本 [research_hype_pbtr_v621_mii_v13_shared_account.py](scripts/research_hype_pbtr_v621_mii_v13_shared_account.py)；artifacts [artifacts/](artifacts/) 下的 `hype_pbtr_v621_mii_v13_shared_account_*_2026-07-02.*`。
