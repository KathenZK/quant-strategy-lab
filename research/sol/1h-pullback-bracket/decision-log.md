# SOL-1H-Pullback-Bracket Decision Log

## 2026-07-13：建立独立回踩 bracket family

- 按新机制优先级建立 `SOL-1H-Pullback-Bracket`，不继承 SOL-1H-AR 版本身份。
- 机制固定为趋势持续、回踩 arm、有限窗口恢复确认、下一根 open 与即时 ATR bracket。
- 使用 2026-07-13 刷新的最近两年 SOL `1h` 数据；选择只使用 train/validation/prefit。
- reused holdout 与约 10 天 fresh forward 只作冻结后审计。

## 2026-07-13：首轮搜索 NO-GO

- 生成 `1500` 个候选，评估 `1376`，eligible `45`，hard pass `0`。
- 最好观察 `SOL_1H_PB_R01145`：prefit annual `1.1576x`、DD `-9.56%`、win `38.30%`；reused holdout return `+2.95%`、3 笔。
- fresh forward return `-2.01%`、2 笔；full annual `1.1382x`。
- K+2 full annual `1.0255x`；8 bps slippage full annual `1.1246x`。
- 决策：回撤和 payoff 可控，但收益过低且 fresh forward 为负；`NO-GO / explore / not promoted / not live-ready`，不登记 V1。

