# Binance-15M-Multi-Asset-Trend-State-Machine

- 完整家族名：`Binance-15M-Multi-Asset-Trend-State-Machine`
- 别名：`BIN-15M-TSM`
- 市场：Binance USD-M、USDT perpetual、point-in-time 动态币池（交易池 ADV30 前 120）、`15m` 采样
- 机制：每根已闭合 `15m` K 重估每币三态趋势状态（`LONG/FLAT/SHORT`）。状态定义在 **4h 等效尺度**（`EMA96/384` on 15m ≡ `EMA6/24` on 4h，spread 以 `ATR672` 归一化），进出用迟滞阈值 + 4 根确认；状态切换在下一根 open 换仓。组合层两层波动率目标仓位。
- 防串线：不是已归档的 [`BIN-15M-EMAX-LGBM`](../15m-ema-cross-lightgbm-event-selector/README.md)（事件 + bracket + ML 打分；其 15m 交叉尺度毛期望≈0 是本线改变假设的直接依据）；不是 [`BIN-1D-TSMOM-VT`](../1d-multi-asset-tsmom-vol-target/README.md)（1d 连续信号定时调仓，无状态迟滞）；与 [`HYPE-EMA-Trend-Breakout`](../../hype/15m-ema-trend-breakout/README.md) 共享 EMA96/384 尺度血缘但机制不同（该家族是单资产事件突破 + bracket）。

## 当前状态

- 状态：`archived / HARD-GATE-FAILED`
- 未注册任何版本；本 README 兼任临时主账（家族已归档，无后续版本计划）。
- 全链路（2026-07-28 完成）：P1 原核 `EMA96/384` 身份 gate 失败 → 用户批准修约改核 `EMA336/1536`（段净期望 `+2.50 ATR`，双 gate 通过）→ P2 四项 kill gate 全过（净 +111.3%、MaxDD −28.3%）→ 锁定 OOS 揭示四过一败（段级 PF `1.162 < 1.2`）判 **HARD-GATE-FAILED** 归档。已揭示窗口 `2026H1` 对任何后继线永久失效。
- 保留的有效测量：4h 等效核（`EMA336/1536`）段级期望远优于 1d/4d 核且参数平面平坦；OOS 内多空换位（空头 `+4.11` / 多头 `−1.83 ATR`）推翻"多头主导"先验。

## 入口

- 锁定 OOS 揭示（终局裁决）：[bin-15m-tsm-locked-oos-reveal-2026-07-28.md](diagnostics/bin-15m-tsm-locked-oos-reveal-2026-07-28.md)
- P2 裁决报告：[bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md](diagnostics/bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md)
- P1 裁决报告：[bin-15m-tsm-p1-segment-baseline-2026-07-28.md](diagnostics/bin-15m-tsm-p1-segment-baseline-2026-07-28.md)
- 冻结研究契约：[bin-15m-tsm-research-contract-2026-07-28.md](specs/bin-15m-tsm-research-contract-2026-07-28.md)
- 决策日志：[decision-log.md](decision-log.md)
- 脚本：[scripts/README.md](scripts/README.md)；产物：[artifacts/README.md](artifacts/README.md)
