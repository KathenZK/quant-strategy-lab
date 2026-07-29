# HYPE-15M-SMA-Crossover-Slope

- Full family name：`HYPE-15M-SMA-Crossover-Slope`（alias：`HYPE-15M-SMA-XS`）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `15m`
- 机制：`SMA30/SMA120` 金叉开多、死叉开空；反向交叉翻仓，或用快线斜率与均线距离收缩提前退出。
- 当前状态：`explore / not promoted / not live-ready`；首轮 37 个冻结定义全部未通过 prefit，尚无登记版本。

## 边界

这是针对用户截图中 `MA(30)/MA(120)` 的独立简单移动平均线研究，不是现有 `HYPE-EMA-Crossover` 的 EMA96/384 版本，也不继承 `HYPE-EMA-Trend-Breakout` 的身份、过滤器或结论。

## 入口

- 主账：[hype-15m-sma-xs-core-ledger.md](hype-15m-sma-xs-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 数据冻结：[hype-15m-sma-xs-data-freeze-2026-07-28.md](diagnostics/hype-15m-sma-xs-data-freeze-2026-07-28.md)
- 首轮报告：[hype-15m-sma-xs-baseline-and-slope-exits-2026-07-28.md](notes/hype-15m-sma-xs-baseline-and-slope-exits-2026-07-28.md)
- 脚本：[scripts/](scripts/)
- 机器产物：[artifacts/](artifacts/)
