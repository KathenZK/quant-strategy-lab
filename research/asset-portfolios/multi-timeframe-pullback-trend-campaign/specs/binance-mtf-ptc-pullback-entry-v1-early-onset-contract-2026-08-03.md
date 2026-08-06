# BIN-MTF-PTC Pullback Entry V1 Early-Onset Diagnostic（2026-08-03）

V0 的 24h onset + 冻结回调规则没有改善 ETH 72h entry success/MAE。V1 不修改 `0.5×ATR`、50%、24h wait、restart 或 stop buffer，只测试 Continuation Meter V0 已预声明的 4h/12h onset，判断失败是否来自候选确认过晚。

- development 拟合各 onset 的72h continuation model；
- development probability 80% 分位作为强候选；
- validation 公平比较 immediate 与 pullback；
- locked historical evaluation 仍不运行；
- 4h/12h 结果不得回写 V0；若均失败，停止在同一回调规则上继续调阈值。

