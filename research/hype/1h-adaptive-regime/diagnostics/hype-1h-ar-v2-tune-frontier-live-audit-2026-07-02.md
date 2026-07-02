# HYPE-1H-Adaptive-Regime-V2 微调前沿实盘压力审计 - 2026-07-02

## 结论

`diagnostic observation / not live-ready / not promoted`。

基础 full + reused-holdout 三项硬门槛命中 `6` 组；进一步要求 base K+1、K+2 延迟、8 bps/fill 滑点三个场景都同时满足 full 与 reused-holdout 硬门槛后，剩余 `0` 组。

压力门槛后的最高 current-full 年化观察为 `None`。这一步查看了 reused holdout 与 current full，因此它是 post-hoc frontier observation，不是新的 untouched OOS 结果。
