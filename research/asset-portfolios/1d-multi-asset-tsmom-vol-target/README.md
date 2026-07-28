# Binance-1D-Multi-Asset-TSMOM-Vol-Target

- 完整家族名：`Binance-1D-Multi-Asset-TSMOM-Vol-Target`
- 别名：`BIN-1D-TSMOM-VT`
- 市场：Binance USD-M、USDT 加密永续、point-in-time 逐月前 30 大 ADV 币池、`1d`
- 机制：经典多资产时序动量（30/91/182/365 天收益符号集成，多空对称）+ 两层波动率目标仓位（单资产反波动加权 + 组合层 20% 年化目标、2× 杠杆上限），每日按 T−1 收盘信息调仓。
- 防串线：与 [`BIN-1D-EMAX-LGBM`](../1d-ema-cross-lightgbm-event-selector/README.md)（archived，事件驱动 bracket 出场）机制不同——本线是持续持仓的组合型 CTA，不是交叉事件研究；与 [`Binance-1D-Turtle-Breakout`](../1d-turtle-breakout/README.md)（Donchian 突破）亦不同源。
- 数据口径：复用已审计 `1h` 归档重采样的 `1d` 缓存；资金费逐日 as-of 计入。美股/商品 TradFi 永续历史（最长 5 个月、全落 2026H1 污染窗）暂不可用，为声明的扩展方向。`2026-01`–`2026-06` 为污染 holdout。

## 当前状态

- 状态：`explore / not promoted / not live-ready`
- 尚未注册版本；本 README 兼任临时主账。P0 演示基线结论：因子毛收益 2021–2025 逐年为正、多空腿轮动互补、波动率目标精确工作（实现 20.8% vs 目标 20%），但每日全量再平衡的 taker 成本 + 资金费吃掉 2021 以外全部净利，预注册评价 4 条过 2 条。改进方向（再平衡缓冲带、降频、maker 口径、跨资产扩展）需新契约。

## 入口

- 决策日志：[decision-log.md](decision-log.md)
- P0 演示契约：[bin-1d-tsmom-vt-demo-contract-2026-07-27.md](specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md)
- P0 演示诊断：[bin-1d-tsmom-vt-p0-demo-2026-07-27.md](diagnostics/bin-1d-tsmom-vt-p0-demo-2026-07-27.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
