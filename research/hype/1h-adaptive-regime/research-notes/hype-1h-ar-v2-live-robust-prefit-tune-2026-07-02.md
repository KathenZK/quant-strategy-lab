# HYPE-1H-Adaptive-Regime-V2 实盘稳健性前置微调 - 2026-07-02

## 结论

`research observation / not live-ready / not promoted`。

本轮不再先追 K+1 年化再验尸，而是在 prefit 内把 base K+1、K+2 延迟与 8 bps/fill 滑点共同纳入筛选。DI pool `800`、Stoch pool `800`、组合 `640000`；prefit 三场景稳健命中 `7613`。参数排序没有使用 reused holdout 或 current full。

冻结观察：`HYPE-1H-Adaptive-Regime-V2-LIVE-ROBUST-TUNE__di_cross_009764__stoch_reversal_005324`。

| Window | Annual multiple | Max DD | Win rate | Trades |
| --- | ---: | ---: | ---: | ---: |
| Prefit base K+1 | `23.95x` | `-15.26%` | `83.67%` | `49` |
| Prefit K+2 | `18.47x` | `-15.77%` | `81.63%` | `49` |
| Prefit 8 bps slip | `18.90x` | `-15.38%` | `83.33%` | `48` |
| Reused holdout | `2.01x` | `-32.69%` | `73.33%` | `15` |
| Current full | `13.65x` | `-32.69%` | `81.25%` | `64` |

Current full + reused holdout 完整硬门槛：`False`；K+2 与 8 bps 下 full/holdout 均保持正收益、胜率 >=50%、DD <20%：`False`。

## Promotion 边界

- 参数冻结只使用 prefit 三场景，流程上没有用后段选参。
- 但 reused holdout 此前已在本家族多轮研究中解锁，不能重新包装为 untouched OOS。
- 在新增 forward trades、生产 runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据完成前，不提升为 candidate、paper-live、dry-run、handoff 或 live。
