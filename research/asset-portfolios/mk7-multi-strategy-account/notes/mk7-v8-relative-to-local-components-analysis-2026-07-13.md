# mk7-v8 相对本仓 MAE / K2 / MII 的改造与收益来源

状态：`explore / diagnostic comparison / not promoted / not live-ready`

## 结论先行

`mk7-v8` 不是简单把本仓 [`BIN-1H-AR-MAE-V1`](../../1h-adaptive-regime-multi-asset-ensemble/binance-1h-ar-mae-core-ledger.md)、[`HYPE-30M-Keltner-Trend-Breakout`](../../../hype/30m-keltner-trend-breakout/hype-30m-keltner-trend-breakout-core-ledger.md) 与 [`HYPE-15M-MII`](../../../hype/15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md) 原样相加。它同时做了三层改造：

1. **重写六币袖套参数**：多数资产改为“更少、更定向的信号 + 更高基础杠杆”，HYPE 1h 基本不变；
2. **把单槽全额账户改为双槽半仓账户**：两笔可并行，每槽使用入场前 NAV 的 50%，再对六币/K2FQ/MII 乘 `1.5/1.2/1.3` scale；
3. **将 K2 与 MII 改造成补空闲槽的低相关 sleeve**：它们单独并不比本仓当前版本更强，但与六币并行后产生乘法式复利。

因此“恐怖收益”的主要来源是**账户结构、资本利用率、条件杠杆和长样本复利共同放大**，不是某一个指标参数突然产生了数量级更高的独立 alpha。

## 指标统一后再比较

本仓 MAE 主账中的 `287.01x` 是**年化倍率**，不是 22.5 个月最终倍数。相同完整窗口内：

| 组合 | 最终倍数 | 年化倍率 | MDD | 入选交易 |
| --- | ---: | ---: | ---: | ---: |
| 本仓 `BIN-1H-AR-MAE-V1` | `39,998.48x` | `287.01x` | `-21.43%` | `371` |
| mk7 独立复现（当前） | `7,464,949.89x` | `4,686.05x` | `-18.90%` | `747` |
| mk7 外部规格声明 | `9,328,938.86x` | — | `-18.90%` | `743` |

当前 mk7 复现最终倍数约为本仓 MAE 的 `186.63` 倍，但身份仍有 `747 vs 743` 的残余偏差，不能把该比值当精确冻结结论。

## 收益来源分解

使用当前 mk7 交易生成器、同一完整窗口和 15m MTM 账户，分别移除组件：

| 组件组合 | 最终倍数 | MDD | 入选交易 |
| --- | ---: | ---: | ---: |
| 六币 only | `189,569.99x` | `-20.33%` | `386` |
| K2FQ only | `4.75x` | `-11.29%` | `69` |
| MII only | `9.32x` | `-18.61%` | `374` |
| K2FQ + MII | `46.28x` | `-18.25%` | `412` |
| 六币 + K2FQ | `875,560.21x` | `-18.90%` | `449` |
| 六币 + MII | `1,481,795.94x` | `-18.90%` | `712` |
| 完整 mk7 | `7,464,949.89x` | `-18.90%` | `747` |

重要解读：

- mk7 六币 only 约为本仓 MAE 最终倍数的 `4.74` 倍；
- K2FQ、MII 单独只有 `4.75x / 9.32x`，并不“恐怖”；
- 完整 mk7 相对六币 only 又放大约 `39.38` 倍；
- K2FQ 与 MII 的价值主要是**填充第二槽、提供不同时间尺度的正期望交易，并让账户在更多时间持续复利**。

这些是路径依赖反事实，不能把各倍率当独立因子机械相乘。机器证据见 [`mk7_v8_relative_component_decomposition_2026-07-13.json`](../artifacts/mk7_v8_relative_component_decomposition_2026-07-13.json)。

## 六币 1h 相对本仓 MAE 的参数变化

| Sleeve | 本仓 MAE V1 | mk7-v8 变化 | 主要效果 |
| --- | --- | --- | --- |
| TRX MACD | `5x`；`min_rvol=0`；方向 ROC6 `>=-100bps` | 基础杠杆 `12.5x`；`min_rvol=0.75`；ROC6 `>=+100bps` | 强化量价质量，显著放大少数强趋势交易 |
| TRX Stoch | 双向；Stoch21、`25/90`；`3.5x`；EMA 距离/funding 拥挤受限 | 仅做多；Stoch24、`20/75`；`8.75x`；放宽 EMA/funding，ROC `-500bps` | 从双向反转改为高杠杆深超卖多头 |
| SOL Donchian | 双向；窗口24；RVOL `1.0`；ROC `+100bps`；`3x` | 仅做空；窗口12；RVOL `0.5`；ROC `0`；关闭 MACD turn；`6x` | 更快、更偏空、更高杠杆 |
| SOL VWAP | 仅空；RVOL 关闭；要求实体方向；`1.5x` | RVOL `0.75`；关闭实体方向；`1.5x` | 用成交量门替代 K 线实体门 |
| HYPE DI / Stoch | DI `3x`、Stoch `2x` | 基本保持相同 | 不是主要改造来源 |
| ETH BB | 仅多；ATR 上限250bps；ROC `+200bps`；TP3ATR/hold72 | 双向；取消 ATR 上限；ROC `+100bps`；TP2.5ATR/hold60 | 大幅扩展 ETH 候选，缩短兑现周期 |
| ETH RSI | 双向；ADX20–45；ATR 上限600；实体/funding 门；TP2ATR/hold48 | 仅空；ADX15–55；放开 ATR/实体/funding；TP2.5ATR/hold36 | 更宽 regime 内集中做空 |
| BTC Keltner | 双向；RVOL `1.25`；`2.4x` | 仅空；RVOL `0.75`；`4.8x` | 将 BTC 突破腿改为高杠杆空头 sleeve |
| BTC CCI | 仅多；ADX 上限40；`3.5x` | ADX 上限30；`3.5x` | 更严格筛选均值回归多头 |
| BNB EMA pullback | EMA55；RVOL `1.0`；ATR下限50；`2.5x` | EMA89；RVOL `1.25`；ATR下限75；ADX上限40；`3.75x` | 慢趋势 + 更强质量门 + 更高仓位 |
| BNB Wick | `1x`，无 trade-count RVOL | 加 `trade_RVOL48>=2.25`；`3.5x` | 只放大量能确认的影线拒绝 |

组合层还会在上述基础杠杆上对六币乘 `1.5`，但每笔只占 50% 槽份额，并受单笔全账户止损风险 `17.5%` 上限约束。当前实际有效 NAV 暴露：

- 六币平均约 `2.53x`，最大 `9.375x`；
- TRX MACD 平均约 `6.85x`、最大 `9.375x`；
- TRX Stoch 平均约 `5.65x`；
- BTC Keltner 平均约 `3.30x`。

这说明 mk7 的收益放大高度集中于少数定向腿，并非平均把所有交易简单提高 1.5 倍。

## 账户结构才是关键放大器

对 mk7 六币使用相同候选，只改变槽位数和账户 scale：

| 账户结构 | 最终倍数 | MDD | 交易数 |
| --- | ---: | ---: | ---: |
| 单槽、原生 exposure | `1,080.04x` | `-15.48%` | `293` |
| 单槽、加账户 scale | `8,861.35x` | `-19.66%` | `293` |
| 双槽、原生 exposure | `11,211.54x` | `-23.16%` | `386` |
| 双槽、加账户 scale | `189,569.99x` | `-20.33%` | `386` |

单独增加槽位或单独增加 scale 都没有超过本仓 MAE 的 `39,998x` 最终倍数；只有“双槽 + scale + 新参数集”同时存在时才跃升到 `189,570x`。这属于强烈的非线性复利协同，不是可线性外推的参数贡献。

本仓 MAE V1 只有一个全账户槽位，候选 `522` 笔但只执行 `371` 笔，平均暴露 `2.60x`、最大 `5x`，有持仓小时仅 `35.6%`。mk7 虽然六币原始候选降到约 `402`，双槽却可执行约 `375` 笔六币交易，再叠加 K2FQ/MII 后总入选约 `743` 笔，复利机会接近翻倍。

## K2FQ 相对本仓 K2 V3

| 项 | 本仓 K2 V3 | mk7 K2FQ |
| --- | --- | --- |
| Keltner | EMA10 / RMA10 / `2.0x` | EMA10 / RMA10 / `2.05x` |
| 1h regime | EMA16/44 + slow slope5 | EMA16/48，仅方向符号 |
| 入场 | 信号后下一根 30m open | 信号 bar close |
| 质量门 | ATR84 cap + close location 65% | premium + top-trader position L/S ratio |
| TP / SL | `10% / 2.5%` | `5% / 2.5%` |
| ATRVT | ATR84，target2.7%，无 floor，cap3x | ATR96，target2.24%，floor1.6x，cap4x |
| 成本 | fee10bps + slippage4bps / side | taker cost6bps / side；SL另加10bps |
| 账户 | 独立全权益 | 50%槽 × account scale1.2 |

mk7 K2FQ 更像“小目标、高命中、拥挤过滤、保证最低仓位”的组合卫星。它 standalone 仅约 `4.75x`，明显弱于本仓 K2 V3 同类样本的约 `64.29x`，所以它不是巨额收益的主发动机。其价值是与六币信号错位，并在同刻竞争时获得 `+1000` 优先级。

执行风险：mk7 在看到 30m close 突破后仍按同一个 close 成交；本仓 K2 用下一根 open，更接近实盘可执行。该差异会美化 mk7 的价格路径，不能忽略。

## MII 相对本仓 V1.4 / V1.4A

mk7 MII 的父结构更接近本仓 `V1.4 baseline`（TP1.25ATR / SL5ATR），而不是当前 dry-run 的 `V1.4A`（TP1.4ATR / SL3ATR）。

| 项 | 本仓 MII V1.4 | mk7 MII |
| --- | --- | --- |
| RSI / MACD | RSI7 `40/60` + MACD方向 | 保持 |
| ATR 门 | `0.75%-2.80%` | `0.60%-0.75%` 仅 ER96>=0.20；`0.75%-2.80%` 放行 |
| RVOL | `RVOL96>=0.85` | 关闭 |
| 微观结构 | 无 | 中单 CVD 空头门、大单 credit、1m blowoff |
| 参谋 | 无 | 96-bar flow + BTC tide 减仓；无反对时 unanimous ×1.25 |
| 出场 | TP1.25ATR / SL5ATR / hold24 | TP1.25ATR / SL5ATR / hold96；72根后 giveup |
| 仓位 | 固定2.5x | ATR风险预算 + credit/blowoff/advisor，再乘账户 scale1.3 |
| 成本/funding | 28bps round trip；不计 funding | 相同 |

这些修改把低波动区从“一律拒绝”改成“ER 有效率足够才放行”，关闭 RVOL 后再用 CVD/flow/tide 控制方向与仓位；同时把最长持仓从6小时延长到24小时，但在18小时后用 giveup 退出。结果是 raw 交易从本仓 V1.4 的约 `232` 笔扩大到 mk7 的约 `375` 笔。

然而 mk7 MII only 约 `9.32x`，与本仓 V1.4 baseline 的约 `10.78x` 相近且略低；高于当前 V1.4A 的约 `6.85x`，但并非数量级突破。它的核心贡献仍是第二槽填充和与六币/K2FQ 的时间分散。

## 为什么收益看起来如此夸张

1. **初始六币底座已经高复利**：外部规格主窗前142笔六币把 NAV 推到约 `247.7x`；后续任何正期望 sleeve 都是在数百倍底座上继续按 NAV 复利。
2. **交易数近乎翻倍**：本仓 MAE 执行371笔；mk7 完整账户约743笔。每笔收益不需要更高，只要长期正期望且相关性低，复利次数增加就会指数放大。
3. **双槽减少阻塞**：本仓单槽会永久丢弃持仓期间所有信号；mk7 可并行两笔，并允许不同资产/不同 family 补空闲槽。
4. **定向高杠杆集中在高胜率腿**：TRX、SOL、BTC、BNB 若通过更严质量门，就使用远高于本仓的基础 leverage；50%槽份额只部分抵消。
5. **K2FQ/MII 提供乘法而非加法贡献**：它们 standalone 不强，但与六币错时后，完整账户相对六币 only 又放大约 `39.4x`。
6. **全部来自同一段已反复研究的数据**：参数、方向、过滤、scale 与账户规则都在已知样本上形成，不能把最终倍数解释为未来预期。

## 风险与否定性证据

- mk7 外部规格自身的额外相位测试失败：整点约 `9.33M x`，偏移5分钟只剩约 `52x`，15/30分钟相位 MDD 可恶化到约 `-50%/-47%`；
- 本仓 K2 V3 也未通过 30m phase 与 start-time gate；
- mk7 K2FQ 同 close 成交存在实时执行不可能精确复制的问题；
- MII 不计 funding，且 microstructure/advisor 参数多、样本内自由度高；
- 当前独立复现仍为 `747 vs 743`，没有逐笔哈希对齐；
- 本仓 MAE、K2、MII 各自也都带有 NO-GO、not-promoted 或 not-live-ready 边界。

因此更准确的评价是：**mk7 展示了如何用账户工程把多个中等正期望 sleeve 放大成极端样本内复利曲线，但没有证明这些参数创造了可外推的超额收益。** 真正值得借鉴的是双槽互斥、风险预算、跨时间尺度填槽和因果仲裁；最不应该直接复制的是高 scale、同 close 成交和依赖原生相位的收益数字。

## 证据

- [本仓 MAE V1 主账](../../1h-adaptive-regime-multi-asset-ensemble/binance-1h-ar-mae-core-ledger.md)
- [本仓 MAE V1 完整 artifact](../../1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_single_position_2026-07-07.json)
- [本仓 K2 主账](../../../hype/30m-keltner-trend-breakout/hype-30m-keltner-trend-breakout-core-ledger.md)
- [本仓 K2 V3 规格](../../../hype/30m-keltner-trend-breakout/specs/hype-30m-keltner-trend-breakout-v3-spec.md)
- [本仓 MII 主账](../../../hype/15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md)
- [本仓 MII V1.4 规格](../../../hype/15m-multi-indicator-intraday/specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md)
- [mk7 独立复现摘要](../artifacts/mk7_v8_backtest_summary_2026-07-13.json)
- [组件分解 artifact](../artifacts/mk7_v8_relative_component_decomposition_2026-07-13.json)
