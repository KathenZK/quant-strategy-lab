# BIN-15M-TSM 决策日志

## 2026-07-28 立项并冻结研究契约

决策：新建 `Binance-15M-Multi-Asset-Trend-State-Machine` 家族并冻结研究契约；范围由用户选定为"Binance 全市场多资产、15m 采样 + 4h/1d 有效尺度状态定义"。立项依据是 emax 周期梯度测量（15m 交叉毛期望≈0、净期望 1h–4h 间穿零、1d 最强、空头侧跨周期更可靠），因此本线不在 15m 尺度定义趋势，只用 15m 提高状态切换的响应分辨率；与已归档 `BIN-15M-EMAX-LGBM` 的机制差异与 reused holdout 降级已写入契约第 1、4 节。

证据：[冻结契约](specs/bin-15m-tsm-research-contract-2026-07-28.md) · [15m emax P1 基线](../15m-ema-cross-lightgbm-event-selector/diagnostics/bin-15m-emax-lgbm-p1-baseline-2026-07-24.md) · [4h P1 基线](../4h-ema-cross-lightgbm-event-selector/diagnostics/bin-4h-emax-lgbm-p1-baseline-2026-07-24.md) · [1d P1 基线](../1d-ema-cross-lightgbm-event-selector/diagnostics/bin-1d-emax-lgbm-p1-baseline-2026-07-24.md) · [15m 数据湖 P0 冻结](../15m-ema-cross-lightgbm-event-selector/diagnostics/bin-15m-emax-lgbm-p0-data-freeze-2026-07-24.md)

## 2026-07-28 P1 段级裸基线：canonical 身份 gate 失败，备选核通过，待修约裁决

决策：P1 按冻结契约执行完毕。canonical `EMA96/384` 期望 gate 通过（交易池 `+0.656 ATR`/段）但尺度身份 gate 失败（84.5 次/池年 > 60），按契约该定义停止；预注册敏感性集中 `EMA336/1536` 核 27 组全部通过双 gate（约 27 次/池年、`+2.4~2.6 ATR`/段），建议修约改核（θ/N 不变），等待用户批准后进入 P2；锁定 OOS 未触碰。

证据：[P1 诊断](diagnostics/bin-15m-tsm-p1-segment-baseline-2026-07-28.md)

## 2026-07-28 用户批准契约修订：方向核改为 EMA336/1536，进入 P2

决策：用户批准将契约第 2 节方向核从 `EMA96/384` 修订为预注册备选 `EMA336/1536`（≡ 4h EMA21/96），`θ_in/θ_out/N = 1.0/0.25/4` 与其余条款不变；修订发生在锁定 OOS 揭示之前。家族进入 P2 组合基线（两层波动率目标、换手/成本预算 gate、BTC 买入持有对照）。

证据：[契约修订记录](specs/bin-15m-tsm-research-contract-2026-07-28.md) · [P1 诊断](diagnostics/bin-15m-tsm-p1-segment-baseline-2026-07-28.md)

## 2026-07-28 P2 组合基线：四项 kill gate 全部通过，取得锁定 OOS 揭示资格

决策：修订后 canonical 组合层（两层波动率目标）开发窗净 +111.3%、1.5x 压力 +77.5%、MaxDD −28.3%、成本拖累 5.8%/年，四项 kill gate 全过；2025 年 −9.0% 与近 1y 为负如实记录。锁定 OOS（二次 reused holdout）揭示为一次性动作，待用户裁决后执行。

证据：[P2 诊断](diagnostics/bin-15m-tsm-p2-portfolio-baseline-2026-07-28.md)

## 2026-07-28 锁定 OOS 一次性揭示（用户批准执行）：HARD-GATE-FAILED，家族归档

决策：五项硬门槛四过一败（段级 PF 1.162 < 1.2；组合净 +6.97%、1.5x 压力 +4.60%、MaxDD −12.1%、闭合段 1,779），按契约第 9 节判 HARD-GATE-FAILED，家族归档；已揭示窗口对任何后继线永久失效，延续研究须新契约 + 2026-07 之后前瞻数据。OOS 内多空换位（多头 −1.83 / 空头 +4.11 ATR）推翻开发窗"多头主导"先验，如实记录。

证据：[锁定 OOS 揭示报告](diagnostics/bin-15m-tsm-locked-oos-reveal-2026-07-28.md)
