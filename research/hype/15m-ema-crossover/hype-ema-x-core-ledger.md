# HYPE-EMA-X 核心研究台账

> 迁移说明：本文由 legacy Cursor Canvas `hype-ema-crossover-evolution.canvas.tsx` 转换为 Markdown；原 Canvas 未删除，仅作为历史来源。

## Current State

- 当前版本：`HYPE-EMA-X-V18`。
- 状态：`dry-run / forward-test required / not live-ready`；实际实例启用、模式与 live 边界只以 quant-runner 为准。共享 15m 行情组曾于 2026-07-21→07-30 [group halt](runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md)，`d514e65` 部署后已恢复；停摆区间观察作废。
- 身份：V18 是 V17.1 的干净参数规格，成交逻辑与指标不变；1Y 冻结指标 `+3861.48% / -19.44% DD / 33 trades / 90.91% win`。
- 当前证据：[V18 参数规格](specs/hype-ema-x-v18-baseline-spec.md)；[runner tracking](runner-tracking/hype-ema-x-runner-2026-07-10.md)。
- 下一决策门：完成 parity、真实成交/保护单、重启恢复和 online open/close reconciliation；此前不得启用 live，也不得给出 dry-run/live 后终态。

## Shared Assumptions

- 数据：Binance HYPEUSDT perp `15m` normalized OHLCV data lake；V15-V18 使用最新 365-day research slice。
- 机制：EMA96/384 regime + 趋势质量过滤 + late re-entry + 结构/预警退出。
- V17 消融 `144` 项；V17.1 专项消融 `146` 项。V17.1/V18 是 sizing/规格清理演化，不是新的信号质量突破。

## Version Table

| 版本 | 定位 | 搜索候选名 | 1Y收益 | Final Equity | 最大回撤 | 胜率 | 交易数 | Late 交易 | 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HYPE-EMA-X-V15 | 高胜率 / 低回撤版 | V17_atr18_trend7_base_age384_d075_pnlm03_either2_stop8 | +2303.65% | 24.04x | -17.79% | 90.32% | 31 | 7 | 稳健观察版；牺牲部分收益换取 <20% 回撤和 90%+ 胜率 |
| HYPE-EMA-X-V16 | 高收益版 | V17_atr18_base_age384_pnlm03_either2_stop8 | +3202.92% | 33.03x | -28.19% | 86.84% | 38 | 10 | 进攻收益版；收益更高，但回撤回到 28% 左右 |
| HYPE-EMA-X-V17 | V15/V16 合体平衡版 | HYBRID_score5_dist04_atr11 / HYPE_EMA_X_V17 | +2910.74% | 30.11x | -17.79% | 90.91% | 33 | 7 | 当前平衡主候选；收益接近 V16，回撤保持 V15 水平，消融后仍保留官方仓位 1.0 |
| HYPE-EMA-X-V17.1 | V17 仓位增强版 | HYPE_EMA_X_V17__hq_scale=1p1 | +3861.48% | 39.61x | -19.44% | 90.91% | 33 | 7 | 收益最高且仍低于 20% 回撤；HQ×1.1 sizing 版本 |
| HYPE-EMA-X-V18 | V17.1 干净参数规格 / dry-run | V17_1_pruned_spec | +3861.48% | 39.61x | -19.44% | 90.91% | 33 | 7 | 逻辑同 V17.1；146 项消融后剔除 noop/关闭模块；当前 quant-runner dry-run / forward-test required |

## 历史版本演化（证据保留）

以下长表保存 V1-V18 研究演进；当前身份只以上方 Current State 与 Version Table 为准。

| 版本 | 入场/方向 | 退出/风控 | 结论 |
| --- | --- | --- | --- |
| V1 裸 EMA 交叉基线 | EMA96 金叉 EMA384 做多；死叉做空 | 固定 10% 止盈；无止损；反向交叉翻仓 | 证明金叉/死叉本身有正收益，但趋势内反复开平仓，回撤大 |
| V1.1 4% 固定止损观察 | V1 + 多单跌 4% / 空单涨 4% 止损 | 固定 10% 止盈；4% 固定止损 | 止损过密，收益和 Sharpe 下降，只小幅降低回撤 |
| V2 EMA regime 趋势持有版 | 交叉只决定方向；同一 EMA regime 内等待 ADX/成交量/1h 确认后入场，可同向再入场 | 4.3 * entry ATR 止盈；9 * entry ATR 止损；ADX<22 连续 3 根退出；MFE>=2ATR 后关闭 ADX 退出 | 当前最接近目标：减少无效开平仓，更多捕捉交叉后的趋势段 |
| V3 交叉动能 + 趋势不坏就持有 | 只在 EMA96/EMA384 金叉/死叉当根检查动能；ADX、成交量、DI 同向才开仓 | 无固定止盈；无 ATR 止盈；反向交叉或 ADX<20 连续 3 根视为趋势坏掉后退出 | 最贴近最新目标：不赚固定点数就跑，趋势没坏就继续拿；但当前收益不如 V2 再入场版 |
| V4 新策略搜索版 | EMA96/384 交叉触发；EMA96 斜率、DI14、RSI14、4h EMA 趋势共同确认 | 无固定止盈；无 ATR 止盈；反向交叉或连续 2 根跌破/升破 EMA384 后退出 | 更贴近新策略目标：仍只在交叉触发入场，但用新指标组合判断动能与趋势完整性 |
| V5 EMA regime 趋势持有版 | EMA96/384 金叉后只找多；死叉后只找空；同一 regime 内等待动能/量能/1h 确认后入场 | 无固定止盈；无 ATR 止盈；无 timeout；ADX28<22 连续 3 根、反向交叉或 9ATR 灾难止损退出 | 当前最符合目标：趋势强度没坏就继续拿；收益低于 V2 是因为不再做 79 次 ATR 固定止盈复利 |
| V6 V5 + 3x 动态仓位 | 沿用 V5 信号；开仓时按 entry ATR672 动态计算仓位，多头目标 1.6% ATR、空头目标 1.4% ATR | 最大 3x；手续费按 allocation 放大；退出规则不变 | 同一趋势持有逻辑下放大收益：1Y +454.08%，但回撤扩大到 -26.77% |
| V7 EMA 交叉附近量能确认 + 衰竭退出 | EMA 交叉后 32 根 K 内，RVOL96 >= 1.5 且 K 线方向确认后入场 | 无固定止盈；MFE>=2.5ATR 后，放量衰竭退出；坏单用进场失效提前退出 | 验证量能衰竭信号有效，但单独替代 V6 会切碎趋势，收益低于 V6 |
| V8 V6 + 量能衰竭覆盖退出 | 保留 V6 的 regime 入场、动态 max 3x 仓位和趋势兜底退出 | MFE>=4ATR 后，RVOL96>=2.0 的量能衰竭 1 根确认即提前全平；否则按 V6 退出 | 当前最佳：1Y +493.56%，Sharpe 2.85；收益高于 V6，但交易次数增加 |
| V9 高周期 RSI 退出 | 保留 V6/V8 入场；尝试 1h/4h RSI 超买/超卖后的反转退出 | RSI 先 armed，再等回落/回升确认；只在已有 MFE 后监听 | 改善有限，单一高周期 RSI 不能稳定定位趋势末端 |
| V10 高周期综合震荡退出 | 保留趋势入场；组合 1h RSI、KDJ、MACD histogram、量价边缘信号 | 至少 2/4 或 3/4 信号确认短期顶/底，再提前退出 | 更干净但仍早退，说明问题不是继续堆指标，而是退出结构 |
| V11 交易路径诊断 | 不再新增指标；对 V6/V8/V10 逐笔计算 MFE、MAE、捕获率和退出后延续 | 识别 early_exit、bad_entry、late_exit_giveback、good_capture | 核心发现：早退率长期在 55% 左右，V8 的收益来自切碎趋势后的再入场 |
| V12 状态机退出 | 沿用 V6 入场和动态仓位；量能/震荡只作为 warning | warning 后必须等 EMA/Donchian/ATR trail 等价格结构 confirm；测试结构化再入场 | 高收益版 +792.86% 但回撤 -43.20%；风险受控版接近 V6，早退本质仍未解决 |
| V12.1 hard trend invalidation | 保留 V12 高收益版的 volume warning + EMA21 confirm | 新增不依赖 warning 的硬趋势失效：EMA96 break、swing24/48/96、ADX fallback 及组合 | swing96 最有效：1Y +1205.06%，回撤 -37.53%，stop_loss 从 11 笔降到 4 笔，但早退率仍 62.03% |
| V12.2 warning 过滤 | 保留 V12.1 swing96 hard exit | 拆解 volume warning：去掉 MFI divergence，或提高 MFI divergence 的 RVOL/wick 门槛 | no_mfi_div 最好：1Y +1547.98%，回撤 -37.53%，早退率降到 52.31%；说明 MFI 背离在强趋势中段误报 |
| V12.3 severe early exit guard | 保留 V12.2 no_mfi_div + swing96 hard exit | warning_confirm 退出前要求当前价格至少捕获历史 MFE 的 35%，低于该值继续持有到下一次确认或 hard exit | 严重早退从 6 笔降到 0；1Y +1587.09%，回撤 -37.53%，普通早退率仍 51.67% 但不再是低捕获率卖飞 |
| V12.4 bad entry filters | 保留 V12.3；诊断坏入场集中在趋势晚期和短线过度拉伸后入场 | 测试 entry_max_regime_age、entry_max_move48、entry_max_dist_ema96、entry_min_rvol96 | age128 风险最好：1Y +1258.43%，回撤 -29.47%，坏入场率 14.29%；move48_12 收益最高：1Y +1601.37%，回撤 -36.97% |
| V12.5 segmented trend exits | 验证“趋势弱了先退出，后续再找机会进”的分段趋势思路 | 在 V12.3 基础上测试 ADX18/22 弱化退出、EMA55 破坏退出、EMA+ADX 组合分段退出 | ADX 分段可把回撤降到约 -31.85%，但收益降到 +1061%~+1093%；EMA55 分段切碎趋势，不如 V12.4 |
| V12.6 age + segment ADX | 验证低回撤组合：entry_max_regime_age 叠加 segment ADX18/22 | 测试 age128/192/256 + ADX 分段，以及 age128 + move48 + ADX 分段 | 结论：age128 单独更优；age128+ADX22 收益仅 +473.49%，回撤仍 -29.47%；age128+move48+ADX18 回撤最低 -20.39% 但收益降到 +432.32% |
| V13 age128 + EMA96 distance | 保留 V12.4 age128；入场时要求同向 close 距 EMA96 不超过 8% | 沿用 V12.3 cap35 + swing96 hard exit；volume warning 仍使用 no_mfi_div | 当前主候选：1Y +1573.15%，回撤 -20.39%，交易 27 笔，胜率 85.19% |
| V14 late re-entry | 保留 V13 首入场过滤；同一 EMA regime 内盈利退出后允许 late re-entry | late 入场要求 regime_age <=256、dist_ema96 <=6%、冷却 16 根 K，且上一笔盈利、MFE>=4ATR、非止损 | 收益增强候选：1Y +2191.92%，回撤 -24.66%，33 笔交易，其中 6 笔 late re-entry |
| V15 高胜率 / 低回撤版 | V17 搜索中 promoted 的 atr18_trend7 版本：基础 EMA regime 信号 + ATR 不过热 + 10 项趋势质量至少 7 项通过 | V13/V14 状态机退出；8ATR 硬止损；swing96 结构破坏；利润后 volume/osc warning + EMA21 confirm 出场 | 当前低回撤主候选：1Y +2303.65%，最大回撤 -17.79%，胜率 90.32%，31 笔交易；满足 >80% 胜率和 <20% 回撤 |
| V16 高收益版 | V17 搜索中 promoted 的 atr18 版本：基础 EMA regime 信号 + ATR 不过热，不要求 trend_score >= 7 | 同 V15 的状态机退出；late re-entry 更挑上一笔 MFE，但信号过滤更宽 | 当前高收益主候选：1Y +3202.92%，最大回撤 -28.19%，胜率 86.84%，38 笔交易；收益更高但回撤超出 20% |
| V17 V15/V16 合体版 | V15 高质量主信号 + V16 低分卫星信号：trend_score 5-6、dir_dist_ema96 <= 4%、atr_ratio96_672 <= 1.1 | 沿用 V15 late re-entry 与退出引擎；HQ/LQ 官方仓位系数均为 1.0 | 正式合体候选：1Y +2910.74%，最大回撤 -17.79%，胜率 90.91%，33 笔交易；比 V15 多 2 笔有效卫星信号，回撤仍保持 V15 水平 |
| V17.1 HQ 仓位增强版 | 信号完全沿用 V17；只把 HQ 高质量主信号仓位系数从 1.0 提到 1.1，LQ 卫星仍为 1.0 | 退出、late re-entry、止损和结构破坏规则都不变 | 主台账仓位增强版：1Y +3861.48%，最大回撤 -19.44%，胜率 90.91%；收益最高且仍压在 20% 回撤内 |
| V18 干净参数规格 | 交易逻辑与 V17.1 完全相同 | 官方参数表只保留消融证明有效的项；删除 noop 过滤器与默认关闭模块的文档噪声 | 规格清理版：指标与 V17.1 相同；见 `specs/hype-ema-x-v18-baseline-spec.md` |

## 主结果对比

横向窗口表。交易数、胜率、止盈、止损和其他退出使用 1Y 窗口统计。

| 版本 | 1W收益 | 1W回撤 | 1M收益 | 1M回撤 | 3M收益 | 3M回撤 | 6M收益 | 6M回撤 | 1Y收益 | 1Y回撤 | 交易数 | 胜率 | 止盈 | 止损 | 其他退出 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | +11.77% | -7.91% | +7.81% | -19.85% | +23.32% | -19.85% | +17.63% | -35.55% | +26.58% | -39.97% | 115 | 37.39% | 35 | 0 | 80 |
| V1.1 | +1.16% | -8.35% | +7.08% | -13.95% | +20.35% | -20.02% | +17.80% | -31.33% | -8.10% | -44.65% | 115 | 31.30% | 28 | 49 | 38 |
| V2 | +0.00% | +0.00% | +5.76% | -8.04% | +13.63% | -12.62% | +55.40% | -16.41% | +137.98% | -16.41% | 79 | 77.22% | 54 | 5 | 20 |
| V3 | -0.69% | -1.52% | +6.95% | -10.27% | +7.63% | -10.27% | +12.17% | -14.93% | +13.52% | -14.93% | 14 | 64.29% | 0 | 0 | 14 |
| V4 | +0.86% | -9.88% | +54.98% | -12.30% | +44.12% | -12.30% | +93.57% | -16.97% | +103.85% | -18.74% | 29 | 41.38% | 0 | 0 | 29 |
| V5 | -1.13% | -2.33% | +20.06% | -7.60% | +28.39% | -7.60% | +79.04% | -15.34% | +117.11% | -15.34% | 50 | 68.00% | 0 | 1 | 49 |
| V6 | -2.33% | -4.71% | +45.72% | -18.34% | +64.11% | -19.63% | +258.22% | -26.77% | +454.08% | -26.77% | 49 | 69.39% | 0 | 1 | 48 |
| V7 | +6.32% | -7.42% | +11.02% | -15.49% | +58.07% | -22.42% | +233.47% | -22.42% | +249.72% | -25.43% | 98 | 47.96% | 0 | 1 | 97 |
| V8 | -2.33% | -4.71% | +24.37% | -18.34% | +33.35% | -22.93% | +207.09% | -27.63% | +493.56% | -27.63% | 97 | 71.13% | 0 | 3 | 94 |
| V9 | -2.33% | -4.71% | +31.29% | -18.34% | +42.30% | -22.09% | +225.20% | -28.18% | +538.24% | -28.18% | 97 | 71.13% | 0 | 3 | 94 |
| V10 | -2.33% | -4.71% | +45.72% | -18.34% | +70.48% | -18.34% | +284.93% | -26.77% | +541.12% | -26.77% | 51 | 70.59% | 0 | 2 | 49 |
| V12 high | -2.33% | -4.71% | +25.99% | -24.42% | +58.10% | -28.80% | +197.73% | -43.20% | +792.86% | -43.20% | 76 | 76.32% | 0 | 11 | 65 |
| V12.1 swing96 | -2.33% | -4.71% | +22.88% | -23.00% | +60.32% | -29.77% | +224.31% | -37.53% | +1205.06% | -37.53% | 79 | 72.15% | 0 | 4 | 75 |
| V12.2 no MFI | -2.33% | -4.71% | +61.87% | -24.09% | +157.65% | -30.22% | +415.74% | -37.53% | +1547.98% | -37.53% | 65 | 66.15% | 0 | 4 | 61 |
| V12.3 cap35 | -2.33% | -4.71% | +80.22% | -24.09% | +186.85% | -30.22% | +413.76% | -37.53% | +1587.09% | -37.53% | 60 | 65.00% | 0 | 4 | 56 |
| V12.4 age128 | +0.00% | +0.00% | +82.57% | -20.39% | +206.96% | -20.39% | +654.23% | -29.47% | +1258.43% | -29.47% | 28 | 82.14% | 0 | 2 | 26 |
| V12.4 move48_12 | -2.33% | -4.71% | +78.63% | -24.76% | +184.33% | -30.83% | +391.20% | -36.97% | +1601.37% | -36.97% | 59 | 66.10% | 0 | 3 | 56 |
| V12.5 segment ADX18 | -2.33% | -4.71% | +39.06% | -23.39% | +92.94% | -23.39% | +320.01% | -31.85% | +1092.86% | -31.85% | 62 | 72.58% | 0 | 3 | 59 |
| V12.6 min DD | +0.00% | +0.00% | +6.14% | -20.39% | +54.21% | -20.39% | +293.39% | -20.39% | +432.32% | -20.39% | 27 | 77.78% | 0 | 1 | 26 |
| V13 | +0.00% | +0.00% | +94.11% | -20.39% | +226.36% | -20.39% | +837.68% | -20.39% | +1573.15% | -20.39% | 27 | 85.19% | 0 | 1 | 26 |
| V14 | +0.00% | +0.00% | +94.11% | -20.39% | +247.41% | -20.39% | +761.85% | -24.66% | +2191.92% | -24.66% | 33 | 81.82% | 0 | 1 | 32 |
| V15 | +0.00% | +0.00% | +126.76% | -17.79% | +243.04% | -17.79% | +695.87% | -17.79% | +2303.65% | -17.79% | 31 | 90.32% | 0 | 0 | 31 |
| V16 | +0.00% | +0.00% | +138.06% | -17.48% | +320.89% | -17.48% | +917.49% | -28.19% | +3202.92% | -28.19% | 38 | 86.84% | 0 | 1 | 37 |
| V17 | +0.00% | +0.00% | +136.84% | -17.79% | +305.21% | -17.79% | +840.11% | -17.79% | +2910.74% | -17.79% | 33 | 90.91% | 0 | 0 | 33 |
| V17.1 | +0.00% | +0.00% | +152.13% | -19.44% | +348.68% | -19.44% | +1021.61% | -19.44% | +3861.48% | -19.44% | 33 | 90.91% | 0 | 0 | 33 |
| V18 | +0.00% | +0.00% | +152.13% | -19.44% | +348.68% | -19.44% | +1021.61% | -19.44% | +3861.48% | -19.44% | 33 | 90.91% | 0 | 0 | 33 |

## V15 / V16 / V17 / V17.1 信号、买入、持有、卖出

| 项目 | 大白话规则 |
| --- | --- |
| 共同信号识别 | 先用 EMA96/EMA384 定方向：EMA96 在 EMA384 上方只找多，在下方只找空；再用 ADX、成交量和 1h 确认筛掉弱趋势。 |
| 多头基础信号 | ema_spread > 0；ADX28 >= 28；vol_surge192 >= 0.25；1h ADX21 > 18；1h +DI21 > 1h -DI21。 |
| 空头基础信号 | ema_spread < 0；ADX28 >= 36；vol_surge192 >= 0.50；1h ema_spread < 0。 |
| V15 额外过滤 | atr_ratio96_672 <= 1.8，且 trend_score >= 7/10。大白话：波动不能已经过热，趋势质量十项检查至少过七项。 |
| V16 额外过滤 | 只要求 atr_ratio96_672 <= 1.8。大白话：只挡掉爆波动追单，不再要求综合趋势分，所以进场更多。 |
| V17 主信号 | 先保留 V15 的高质量信号：atr_ratio96_672 <= 1.8，且 trend_score >= 7。大白话：主体仓位仍然只做趋势质量足够高的点。 |
| V17 卫星信号 | 再少量放回 V16 的低分信号：trend_score 只能是 5-6，价格离 EMA96 不超过 4%，atr_ratio96_672 不超过 1.1。大白话：只要“不远、不热”的低分趋势补单。 |
| 普通买入 | 信号在当前 15m K 收盘确认，下一根 open 成交；只允许 regime_age <= 128 且价格离 EMA96 不超过 8%。 |
| Late re-entry | 趋势过了普通入场窗口后，如果上一笔同方向交易曾经跑出足够 MFE，且不是止损退出，就允许同一 EMA regime 内再次进场。V17 使用 V15 的 late 参数。 |
| 持有 | 不设固定止盈，不按持仓时间强制卖出；持续记录 high_water / low_water / MFE ATR / hold_bars，让真实趋势尽量跑完。 |
| 卖出：硬止损 | 亏损碰到 8 * entry_atr 就盘中强制出场；entry_atr 用入场前一根的 atr_pct672。 |
| 卖出：趋势反转 | EMA96/EMA384 反向交叉，说明大方向切换，下一根 open 出场。 |
| 卖出：结构破坏 | hard_exit_mode = swing96；多头收盘跌破前 96 根低点，或空头收盘涨破前 96 根高点，下一根 open 出场。 |
| 卖出：利润后预警确认 | 单笔至少曾经赚到 4 ATR 后，volume warning 或 1h oscillator warning 任一出现，再等 EMA21 价格确认，并至少保住 35% 最大浮盈。 |

## V15 / V16 / V17 / V17.1 参数总表

| 参数 | 取值 | 大白话作用 |
| --- | --- | --- |
| symbol | HYPEUSDT perpetual | 只研究 HYPE 永续合约。 |
| timeframe | 15m | 每根 K 线是 15 分钟。 |
| lookback | latest 365 days | 主台账这两行使用最近一年回测窗口。 |
| slippage | 0.0005 | 每次成交按 0.05% 滑点惩罚。 |
| trade_cost | 0.00085 | 每次进出场按仓位扣 0.085% 成本。 |
| max_allocation | 3.0 | 最大 3 倍仓位。 |
| long_target_atr_pct | 0.016 | 做多仓位目标：一次 ATR 波动约等于 1.6% 账户风险单位。 |
| short_target_atr_pct | 0.014 | 做空仓位更保守：一次 ATR 波动约等于 1.4% 账户风险单位。 |
| allocation | min(3.0, target_atr_pct / atr_pct672) | 波动越大仓位越小，波动越小仓位越大，但最多 3 倍。 |
| atr_pct672 | 672 bars | 慢速 ATR，用来算仓位和止损距离。 |
| ema_fast | EMA96 | 快线，大约看 1 天趋势。 |
| ema_slow | EMA384 | 慢线，大约看 4 天趋势。 |
| ema_spread | EMA96 / EMA384 - 1 | 判断当前是多头 regime 还是空头 regime。 |
| regime_age | bars since EMA spread sign change | 趋势从 EMA 交叉后已经走了多久。 |
| dir_dist_ema96 | direction-adjusted close/EMA96 distance | 价格离 EMA96 有多远，用来防止追得太远。 |
| atr_ratio96_672 | <= 1.8 | 短期波动相对长期波动不能过热。 |
| vol_surge192 | volume / 192-bar avg - 1 | 成交量有没有比过去 192 根明显放大。 |
| ADX28 | long >= 28 / short >= 36 | 15m 趋势强度；做空要求更强。 |
| h1 confirmation | shifted 1h indicators | 用上一小时已完成数据确认，避免未来函数。 |
| trend_score | V15 >= 7 / V16 disabled / V17 HQ >= 7 + LQ 5-6 | V17 把高分信号当主体，只补少量 5-6 分卫星信号。 |
| v17_lq_max_dist_ema96 | 0.04 | V17 卫星信号离 EMA96 不能超过 4%，避免低分信号追得太远。 |
| v17_lq_max_atr_ratio | 1.1 | V17 卫星信号短期 ATR 只能比长期 ATR 热 10% 以内。 |
| v17_lq_require_obv/cmf | false | 消融显示额外 OBV/CMF 门槛没有改变实际成交，不作为官方规则。 |
| entry_max_regime_age | 128 bars | 普通入场只在趋势早期做，避免太晚追。 |
| entry_max_dist_ema96 | 0.08 | 普通入场离 EMA96 不能超过 8%。 |
| late_max_age | 384 bars | late re-entry 最晚允许到 EMA 交叉后 384 根。 |
| late_dist_ema96 | V15/V17 0.075 / V16 0.06 | late re-entry 离 EMA96 的最大距离；V17 沿用 V15。 |
| cooldown_bars | V15/V17 12 / V16 16 | 上一笔出场后至少等多少根 K 线才能 late re-entry。 |
| min_prev_pnl | -0.03 | 上一笔最多允许小亏 3%，因为可能只是被提前震出。 |
| min_prev_mfe_atr | V15/V17 3.0 / V16 4.0 | 上一笔至少曾经跑出多少 ATR 浮盈，证明趋势真实存在。 |
| require_pullback | false | late re-entry 不强制必须回踩。 |
| stop_atr | 8.0 | 硬止损距离：8 个入场 ATR。 |
| hard_exit_mode | swing96 | 用 96 根结构高低点判断趋势结构破坏。 |
| hard_exit_bars | 1 | 结构破位一次就出。 |
| min_mfe_atr | 4.0 | 至少曾经赚 4 ATR，才启动预警退出系统。 |
| warning_source | either | 成交量衰竭或振荡指标预警，任一类都可以。 |
| warning_exit_min_capture | 0.35 | 预警出场至少保住最大浮盈的 35%。 |
| confirm_mode | ema21 | 预警后必须跌破/涨破 EMA21 才确认出场。 |
| volume_warning_mode | no_mfi_div | 成交量预警不用 MFI 背离，只看爆量长影线或爆量无效推进。 |
| exit_rvol | 2.0 | 成交量达到 96 根均量的 2 倍才算爆量。 |
| wick_min | 0.55 | 长影线至少占整根 K 线 55%。 |
| osc_min_score | 2 | 1h RSI、KDJ、MACD 三个振荡警告至少中两个。 |
| osc_tf | 1h | 振荡预警看 1 小时级别。 |
| take_profit | disabled | 不固定止盈。 |
| max_hold_bars | disabled | 不按持仓时间强制退出。 |
| fallback_adx | 0 | 不启用 ADX 走弱兜底退出。 |
| segment_exit_mode | none | 不启用分段 EMA/ADX 减速退出。 |
| add_signal | none | 不启用额外 pullback/breakout/KDJ 补单信号。 |
| allocation_scale | V15/V16/V17 = 1.0；V17.1 HQ = 1.1 / LQ = 1.0 | V17.1 只放大高质量主信号仓位，卫星信号不加仓。 |

## V17 合体策略与消融

> **正式 V17：只放回一小类 V16 卫星信号**
> 简单把 V16 全部低分信号放回来会把回撤带回 -28%。V17 只放回 trend_score 为 5-6、距离 EMA96 不超过 4%、ATR 不过热到 1.1 以内的卫星信号，1Y 窗口做到 +2910.74%，最大回撤仍为 -17.79%。

| 版本/候选 | 1Y收益 | 最大回撤 | 胜率 | 交易数 | Late 交易 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| V15 official | +2303.65% | -17.79% | 90.32% | 31 | 7 | V16 的高质量子集：atr18 + trend_score >= 7 |
| V16 official | +3202.92% | -28.19% | 86.84% | 38 | 10 | 全量 atr18；收益最高但 6M/1Y 回撤被拉到 -28.19% |
| HYPE-EMA-X-V17 official | +2910.74% | -17.79% | 90.91% | 33 | 7 | V15 高质量信号 + 少量 V16 低分卫星：trend_score 5-6、dir_dist_ema96 <= 4%、atr_ratio96_672 <= 1.1 |
| HYPE-EMA-X-V17.1 | +3861.48% | -19.44% | 90.91% | 33 | 7 | V17 信号完全不变；HQ 主信号仓位系数 1.1，LQ 卫星仍为 1.0 |

### V17 分段窗口

| 候选 | 1W收益 | 1W回撤 | 1M收益 | 1M回撤 | 3M收益 | 3M回撤 | 6M收益 | 6M回撤 | 1Y收益 | 1Y回撤 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HYPE-EMA-X-V17 official | +0.00% | +0.00% | +136.84% | -17.79% | +305.21% | -17.79% | +840.11% | -17.79% | +2910.74% | -17.79% |
| HYPE-EMA-X-V17.1 | +0.00% | +0.00% | +152.13% | -19.44% | +348.68% | -19.44% | +1021.61% | -19.44% | +3861.48% | -19.44% |

### V17 交易归因

| 信号桶 | 交易数 | 胜率 | 累计单笔 PnL | 平均单笔 | 中位单笔 | 最差单笔 | 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HQ 主信号 | 29 | 89.66% | +353.32% | +12.18% | +10.69% | -8.33% | V17 的 V15 类高质量主信号，仍是收益主体 |
| LQ 卫星信号 | 4 | 100.00% | +38.11% | +9.53% | +8.42% | +2.90% | V17 只放回低分但不热、不远离 EMA96 的 V16 卫星信号；本轮没有止损 |

### V17 全参数消融 Top 结果

| 候选 | 消融类型 | 1Y收益 | 最大回撤 | 胜率 | 交易数 | Sharpe | 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HYPE-EMA-X-V17 official | baseline | +2910.74% | -17.79% | 90.91% | 33 | 4.79 | 正式 V17：HQ/LQ 仓位都用 1.0，回撤保持 V15 水平 |
| HYPE-EMA-X-V17.1 | 仓位增强 | +3861.48% | -19.44% | 90.91% | 33 | 4.77 | 收益最高且仍低于 20% 回撤；已记录为 HYPE-EMA-X-V17.1 主台账版本 |
| lq_scale = 1.25 | 卫星加仓 | +3171.45% | -17.79% | 90.91% | 33 | 4.84 | 只放大 4 笔卫星信号，Sharpe 略高；收益改善小于 HQ 加仓 |
| late_dist_ema96 = 0.06 | late 更靠近 EMA96 | +2965.72% | -17.49% | 90.91% | 33 | 4.82 | 小幅降回撤、小幅增收益；说明 V17 对 late 距离不敏感 |
| cooldown_bars = 8 | late 冷却缩短 | +2952.14% | -17.79% | 90.91% | 33 | 4.80 | 只带来轻微收益改善，不值得单独改官方版本 |
| hard_exit_mode = none | 去掉 swing96 硬结构退出 | +3074.74% | -20.55% | 93.94% | 33 | 4.82 | 收益略高但回撤突破 20%，因此不替代官方 swing96 |

### V17 参数敏感性

| 参数 | 敏感区间/最佳值 | 代表结果 | 结论 |
| --- | --- | --- | --- |
| hq_scale | 1.1 最强 / 0.75 最稳 | +3861.48% / -19.44% | 仓位是最有效的收益旋钮；官方暂不放大，因为回撤接近 20% |
| lq_scale | 1.25 | +3171.45% / -17.79% | 卫星信号质量不错，但样本只有 4 笔，放大后仍要谨慎 |
| lq_enabled | false | +2303.65% / -17.79% | 关掉卫星就退回接近 V15，说明 V17 的新增收益来自低分卫星 |
| lq_max_atr_ratio | 1.2 以上 | +2516.60%~+2977.36% / -28.29% | 一放宽卫星 ATR 过热门槛，回撤立刻回到 V16 水平 |
| hard_exit_mode | none | +3074.74% / -20.55% | 去掉结构退出能多吃一点趋势，但会越过 20% 回撤边界 |
| confirm_mode | donchian | +721.16% / -20.58% | 用 Donchian 替代 EMA21 确认会切碎利润，不建议 |
| hq_min_score | 6 或 9 | +2598.60% / -28.33% 或 +861.74% / -17.53% | 降低分数会引入坏单，提高分数会漏掉太多趋势 |
| segment_exit_mode | ADX/EMA segment | 普遍低于 baseline | 中段趋势减速退出继续过早切趋势，不适合作为 V17 默认退出 |

### V17.1 全参数消融 Top 结果

> **V17.1 专项结论：最佳行不是继续放大 HQ**
> 在 V17.1 baseline 上，20% 回撤约束内的最佳收益行是 LQ 卫星仓位从 1.0 提到 1.25，1Y +4204.53%，最大回撤仍为 -19.44%。但 LQ 卫星只有 4 笔交易，这一行更像风险预算提示，不宜直接改名为新官方版本。

| 候选 | 消融类型 | 1Y收益 | 最大回撤 | 胜率 | 交易数 | Sharpe | 判断 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HYPE-EMA-X-V17.1 official | baseline | +3861.48% | -19.44% | 90.91% | 33 | 4.77 | V17 信号不变；HQ=1.1、LQ=1.0，是本轮 V17.1 消融基准 |
| lq_scale = 1.25 | 卫星加仓 | +4204.53% | -19.44% | 90.91% | 33 | 4.82 | 20% 回撤约束内最佳收益行；只放大 4 笔 LQ 卫星，证据仍偏薄 |
| late_dist_ema96 = 0.06 | late 更靠近 EMA96 | +3941.60% | -19.11% | 90.91% | 33 | 4.80 | 收益和回撤都小幅改善，但不是结构性突破 |
| cooldown_bars = 8 | late 冷却缩短 | +3921.20% | -19.44% | 90.91% | 33 | 4.78 | 轻微改善，仍不足以替代官方冷却参数 |
| hard_exit_bars = 2 | 结构破坏多等一根 | +3917.41% | -19.58% | 93.94% | 33 | 4.76 | 胜率更高但新增 1 笔 stop_loss，风险质量不如 baseline 干净 |
| hq_scale = 1.0 | 退回 V17 仓位 | +2910.74% | -17.79% | 90.91% | 33 | 4.79 | 回撤更松，但收益退回 V17；说明 V17.1 的增益主要来自 HQ 仓位预算 |
| hq_scale = 1.2 | 继续放大 HQ | +5083.21% | -21.07% | 90.91% | 33 | 4.75 | 超过 50x return，但突破 20% 回撤边界，不作为当前官方参数 |
| hard_exit_mode = none | 去掉 swing96 硬结构退出 | +4096.89% | -22.40% | 93.94% | 33 | 4.80 | 收益略高但出现 2 笔 stop_loss，回撤越界 |

### V17.1 参数敏感性

| 参数 | 敏感区间/最佳值 | 代表结果 | 结论 |
| --- | --- | --- | --- |
| lq_scale | 1.25 | +4204.53% / -19.44% | 在 V17.1 的 20% 回撤约束内是最佳收益行，但只有 4 笔 LQ 卫星样本，不宜直接升格为新主版本 |
| hq_scale | 1.2 / 1.25 | +5083.21% / -21.07%；+5816.33% / -21.88% | 继续加 HQ 能越过 50x return，但回撤同步越过 20%，说明 V17.1 已贴近风险预算上沿 |
| hq_scale | 1.0 | +2910.74% / -17.79% | 退回 V17 官方仓位后回撤更低、收益少 950.75 个百分点；V17.1 的主要增益确实来自 HQ 仓位 |
| lq_enabled | false | +3100.78% / -19.44% | 关闭卫星会损失约 760.70 个百分点收益，说明 V17.1 仍需要 LQ 卫星补充趋势段 |
| lq_max_atr_ratio | 1.2 | +3342.88% / -29.68% | 一放宽卫星 ATR 过热门槛，风险立刻跳回高回撤区，1.1 仍是关键边界 |
| hard_exit_mode | none | +4096.89% / -22.40% | 去掉 swing96 只能换来小幅收益，代价是越过回撤边界并新增 stop_loss |
| late_dist_ema96 | 0.06 | +3941.60% / -19.11% | 这是较温和的改良候选，但收益增量小于 LQ 加仓，适合作为后续稳健性复查项 |
| segment_exit_mode | ADX/EMA segment | 普遍低于 baseline | 分段减速退出继续过早切断趋势，不适合作为 V17.1 默认退出 |

### 版本收益对比

原 Canvas 使用 BarChart；这里保留图表底层数据。

| 版本 | 1Y累计收益率 |
| --- | --- |
| V8 | +493.56% |
| V12.3 | +1587.09% |
| V13 | +1573.15% |
| V14 | +2191.92% |
| V15 | +2303.65% |
| V16 | +3202.92% |
| V17 | +2910.74% |
| V17.1 | +3861.48% |

### 版本回撤对比

原 Canvas 使用 BarChart；这里保留图表底层数据。

| 版本 | 1Y最大回撤 |
| --- | --- |
| V8 | -27.63% |
| V12.3 | -37.53% |
| V13 | -20.39% |
| V14 | -24.66% |
| V15 | -17.79% |
| V16 | -28.19% |
| V17 | -17.79% |
| V17.1 | -19.44% |

## V2 规则

| 项目 | 说明 |
| --- | --- |
| 方向定义 | EMA96 / EMA384 金叉后只找多单；死叉后只找空单 |
| 入场时机 | 不要求交叉当根入场；在同一 EMA regime 内等待过滤通过，下根 15m open 成交 |
| 15m 多头过滤 | ADX28 >= 28；volume_surge_192 >= 0.25 |
| 15m 空头过滤 | ADX28 >= 36；volume_surge_192 >= 0.50 |
| 1h 多头确认 | 1h ADX21 > 18 且 1h +DI > 1h -DI |
| 1h 空头确认 | 1h EMA24 / EMA96 - 1 < 0 |
| 止盈 | 固定 entry ATR：4.3 * ATR672 |
| 止损 | 固定 entry ATR：9.0 * ATR672 |
| 指标退出 | ADX28 < 22 连续 3 根退出 |
| 利润奔跑 | 单笔 MFE >= 2 * entry ATR 后关闭 ADX 指标退出，只保留 TP/SL/timeout |
| 再入场 | 同一 EMA regime 内止盈或退出后，允许再次等待过滤通过入场 |
| 成本 | 5bps 滑点；每次成交 0.00085 成本 |

## V3 规则

| 项目 | 说明 |
| --- | --- |
| 方向定义 | EMA96 上穿 EMA384 只允许做多；EMA96 下穿 EMA384 只允许做空 |
| 入场时机 | 必须是金叉/死叉当根触发；信号在收盘确认，下根 15m open 成交 |
| 动能过滤 | ADX28 >= 24；volume_surge_192 >= 0；DI 必须同向 |
| 多头 DI | +DI28 > -DI28 |
| 空头 DI | -DI28 > +DI28 |
| 止盈 | 不设固定 10% 止盈；不设固定 ATR 止盈 |
| 趋势坏掉退出 | 反向 EMA 交叉，或 ADX28 < 20 连续 3 根 |
| 持仓原则 | 趋势指标未破坏就继续持有，让利润奔跑 |
| 成本 | 5bps 滑点；每次成交 0.00085 成本 |

## V4 规则

| 项目 | 说明 |
| --- | --- |
| 搜索空间 | 12600 个入场组合 * 10 类退出，保留 86110 个有效结果 |
| 触发器 | EMA96 上穿 EMA384 触发多头候选；EMA96 下穿 EMA384 触发空头候选 |
| 15m 动能 | EMA96 过去 48 根斜率必须同向 |
| 15m 方向 | DI14 必须同向；多头 +DI14 > -DI14，空头 -DI14 > +DI14 |
| 15m RSI | 多头 RSI14 >= 52；空头 RSI14 <= 48 |
| 4h 趋势 | 4h EMA24 / EMA96 spread 必须同向 |
| 止盈 | 不设固定止盈，不设 ATR 止盈 |
| 趋势坏掉退出 | 反向 EMA96/384 交叉，或连续 2 根 close 跌破/升破 EMA384 |
| 执行成本 | 信号收盘确认，下根 15m open 成交；5bps 滑点；每次成交 0.00085 成本 |

## V5 规则

| 项目 | 说明 |
| --- | --- |
| 数据口径 | 数据湖 HYPEUSDT Binance perp 15m：2025-05-30 10:30 UTC → 2026-06-01 03:00 UTC，共 35203 根 |
| 方向定义 | EMA96 > EMA384 为多头 regime；EMA96 < EMA384 为空头 regime |
| 多头入场 | ema_spread > 0；ADX28 >= 28；volume_surge_192 >= 0.25；1h ADX21 > 18；1h +DI21 > 1h -DI21 |
| 空头入场 | ema_spread < 0；ADX28 >= 36；volume_surge_192 >= 0.50；1h EMA24 / EMA96 spread < 0 |
| 入场时机 | 不要求交叉当根入场；交叉后同一 EMA regime 内等待过滤通过，下根 15m open 成交 |
| 止盈 | 不设固定 10% 止盈；不设固定 ATR 止盈 |
| 趋势退出 | ADX28 < 22 连续 3 根，或 EMA96/384 反向交叉 |
| 灾难止损 | 9 * entry ATR672，仅用于极端反向波动，不作为止盈逻辑 |
| 明确移除 | 移除 V2 的 max_hold_bars / timeout；移除 MFE 后关闭 ADX 退出 |

## V5 / V6 仓位实验

同一 V5 信号，数据湖 HYPEUSDT 15m；动态仓位只改变 allocation，不改变入场/退出规则。

| 口径 | 1Y收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 仓位 | 中位单笔 | 退出结构 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V5 fixed 1x | +117.11% | -15.34% | 2.43 | 50 | 68.00% | 1.00x | +0.82% | 48 trend_break；1 stop_loss；1 opposite_cross |
| V6 dynamic max 3x | +454.08% | -26.77% | 2.66 | 49 | 69.39% | avg 2.31x / median 2.28x / max 3.00x | +1.52% | 47 trend_break；1 stop_loss；1 opposite_cross |

## V7 / V8 量能衰竭实验

目标：金叉/死叉附近用量能确认参与趋势，在趋势末端出现量能衰竭时退出或覆盖 V6 退出。

| 项目 | 说明 |
| --- | --- |
| V7 入场 | EMA96/384 交叉后 32 根 15m K 内；RVOL96 >= 1.5；K 线收盘位置与方向一致 |
| V7 退出 | MFE >= 2.5 * entry ATR 后，放量衰竭连续 2 根确认退出；若趋势未展开且量价/EMA 失效，提前 entry_invalidated |
| V7 结论 | volume_exhaustion 出口质量高，但完整替换 V6 后会切掉大趋势；1Y +249.72%，最大回撤 -25.43% |
| V8 入场 | 完全沿用 V6：EMA regime 内等待 ADX/成交量/1h 确认；下根 15m open 成交；ATR 动态 max 3x 仓位 |
| V8 退出覆盖 | MFE >= 4 * entry ATR 后，若 RVOL96 >= 2.0 的量能衰竭出现，1 根确认即提前全平 |
| V8 兜底退出 | 若没有触发量能衰竭，则继续使用 V6 的 ADX28<22 连续 3 根、反向交叉、9ATR 灾难止损 |
| V8 结论 | 收益和 Sharpe 当前最佳：1Y +493.56%，最大回撤 -27.63%，交易 97，胜率 71.13% |

### V6 / V7 / V8 对比

| 版本/实验 | 1Y收益 | 最大回撤 | Sharpe | 交易数 | 胜率 | 退出结构 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V6 baseline | +454.08% | -26.77% | 2.66 | 49 | 69.39% | 47 trend_break；1 stop_loss；1 opposite_cross | 趋势持有最简洁，交易少，仍是稳定基线 |
| V7 volume exhaustion standalone | +249.72% | -25.43% | 2.04 | 98 | 47.96% | 45 volume_exhaustion；41 entry_invalidated；11 opposite_cross；1 stop_loss | 验证量能衰竭出口有效，但整体替代 V6 会过早切碎趋势 |
| V8 volume overlay | +493.56% | -27.63% | 2.85 | 97 | 71.13% | 55 volume_exhaustion；38 trend_break；3 stop_loss；1 opposite_cross | 当前最佳：在 V6 上叠加衰竭提前退出，提高收益和胜率 |
| V8 half reduce best | +409.57% | -26.64% | 2.81 | 49 | 69.39% | 11 次减半仓；最终仍由 V6 退出结构结束 | 路径更像 V6，但收益低于 V6；不如直接全平覆盖版 |
| V8 cooldown best | +374.03% | -27.61% | 2.55 | 57 | 66.67% | 12 volume_exhaustion；43 trend_break；1 stop_loss；1 opposite_cross | 减少同一趋势内重复进场，但收益明显低于不冷却版本 |

## V2 / V4 收益差异

同一 Binance HYPEUSDT 15m 缓存复跑；V2 recreated 为按 Canvas V2 规则重建的对比口径，窗口结束 2026-06-12 06:15 UTC。

| 版本/实验 | 1Y收益 | 最大回撤 | 交易数 | 胜率 | 中位单笔 | 退出结构 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V2 dynamic max 3x | +985.13% | -30.58% | 110 | 76.36% | +5.96% | 79 次止盈；20 次趋势坏掉；8 次止损 | 收益最高，但核心仍是固定 ATR 止盈复利，不是纯趋势持有口径 |
| V2 recreated | +175.04% | -16.88% | 108 | 75.00% | +2.54% | 76 次止盈；21 次趋势坏掉；8 次止损 | 收益来自高胜率的小段复利：同一 EMA regime 内可多次等待过滤通过再入场 |
| V4 current | +103.85% | -18.74% | 29 | 41.38% | -0.79% | 29 次趋势坏掉退出；无固定止盈 | 单笔右尾很大，最好一笔 +36.66%，但交易少且中位数为负 |
| V2 no fixed TP | +151.40% | -20.38% | 47 | 59.57% | +0.72% | 28 次 timeout；11 次趋势坏掉；5 次止损 | 去掉 ATR 止盈后仍强于 V4，说明关键不是固定止盈，而是 regime 再入场质量 |
| V2 no TP / no timeout | +31.91% | -33.67% | 38 | 39.47% | -1.23% | 23 次反向交叉；8 次趋势坏掉；7 次止损 | 只靠当前趋势坏掉定义会拿过头，必须补更好的趋势失效条件 |
| V4 window reentry | +22.10% | -41.96% | 61 | 31.15% | -1.30% | 交叉后 96 根窗口内允许再入场 | V4 过滤器不适合扩成 regime 再入场，会吸入太多晚期/震荡交易 |

## 候选实验记录

| 实验 | 收益 | 最大回撤 | Sharpe | 交易数 | 判断 |
| --- | --- | --- | --- | --- | --- |
| Cross only + V30 filters | +9.76% | -13.47% | 0.76 | 1 | 交叉当根过滤太严格，样本不足 |
| Regime once V30 filters take10 | +20.86% | -65.26% | 0.69 | 5 | 只做一次会漏掉长趋势多段行情 |
| Regime once take10 stop4 | +98.44% | -18.95% | 1.91 | 35 | 比固定 4% 止损好，但仍不如 ATR 风控 |
| Regime once ATR take/stop | +79.27% | -15.46% | 2.62 | 35 | 低回撤，但同一 regime 只做一次 |
| Regime once ATR + ADX exit | +59.48% | -10.98% | 2.41 | 35 | 回撤最低，但收益不如再入场版 |
| Regime reentry ATR + ADX exit | +150.92% | -16.41% | 3.19 | 82 | 当前最佳：趋势里允许同向再入场 |
| Regime once no take trail | +76.71% | -22.77% | 1.48 | 34 | 不固定止盈不如 ATR 止盈稳定 |
| V3 cross momentum no take | +13.52% | -14.93% | 0.68 | 14 | 最符合新定义，但严格交叉入场导致样本少、收益低于 V2 |
| V4 full search best fitness | +103.85% | -18.74% | 1.84 | 29 | 新策略搜索胜出：不靠固定止盈，靠高周期趋势和 EMA384 破坏退出 |
| V2 no fixed TP ADX exit | +151.40% | -20.38% | 2.27 | 47 | 优化方向：保留 regime 再入场，去掉固定止盈，重做趋势坏掉退出 |
| V4 window reentry test | +22.10% | -41.96% | 0.62 | 61 | 不建议：V4 过滤器窗口化后胜率和回撤显著恶化 |
| V5 data-lake no TP hold | +117.11% | -15.34% | 2.43 | 50 | 目标对齐版：无固定止盈、无 timeout，ADX 趋势强度坏掉才退出 |
| V6 dynamic max 3x | +454.08% | -26.77% | 2.66 | 49 | 同一 V5 信号，按 ATR 动态仓位，平均 2.31x，收益放大但回撤也放大 |
| V2 dynamic max 3x | +985.13% | -30.58% | 3.45 | 110 | 收益最高，但 79 次固定 ATR 止盈，不符合纯趋势持有目标 |
| V7 volume exhaustion | +249.72% | -25.43% | 2.04 | 98 | EMA 交叉附近量能确认入场，衰竭退出有效，但单独版本过早切碎趋势 |
| V8 V6 + volume overlay | +493.56% | -27.63% | 2.85 | 97 | 保留 V6 入场和趋势兜底，量能衰竭只做提前退出；当前最佳版本 |
| V9 HTF RSI exit | +516.68% | -28.45% | 2.81 | 79 | 高周期 RSI 能过滤部分顶部/底部，但整体提升不稳定 |
| V10 oscillator combo | +474.68% | -27.09% | 2.62 | 51 | 组合震荡信号更克制，但 V11 诊断仍显示早退率 54.90% |
| V11 path diagnostics | 诊断 | 诊断 | - | 194 | 确认主要瓶颈是 early_exit 与 bad_entry，不是缺少新指标 |
| V12 state machine high return | +792.86% | -43.20% | 2.72 | 76 | warning/confirm 能拉高收益，但放大回撤且早退率仍高 |
| V12 state machine controlled | +470.99% | -26.77% | 2.71 | 50 | 风险接近 V6；多数退出退回 fallback_trend_break，状态机贡献有限 |
| V12.1 swing96 hard | +1205.06% | -37.53% | 3.25 | 79 | 96 根结构破坏硬退出有效减少大止损，但早退率仍 62.03% |
| V12.1 swing96 + ADX18 | +527.24% | -31.85% | 2.79 | 82 | 回撤压低但利润奔跑被砍，收益接近 V8 clean |
| V12.2 swing96 no MFI div | +1547.98% | -37.53% | 3.24 | 65 | 去掉 MFI divergence 后交易更少、持仓更久，早退率降到 52.31% |
| V12.3 no MFI + cap35 | +1587.09% | -37.53% | 3.23 | 60 | warning 退出需捕获 >=35% MFE，严重早退降为 0 |
| V12.4 cap35 age128 | +1258.43% | -29.47% | 3.94 | 28 | 限制 regime age <=128，坏入场率降到 14.29%，当前低回撤候选 |
| V12.4 cap35 move48_12 | +1601.37% | -36.97% | 3.27 | 59 | 过滤 48 根过度拉伸，收益最高但坏入场率仍 28.81% |
| V12.5 segment ADX18 | +1092.86% | -31.85% | 3.37 | 62 | 趋势弱了先退可降回撤，但收益低于 V12.4 高收益候选 |
| V12.5 segment EMA55 | +728.09% | -37.53% | 2.69 | 62 | EMA55 分段过早切碎趋势，不建议 |
| V12.6 age128 + ADX22 | +473.49% | -29.47% | 3.42 | 28 | 叠加分段后收益远低于 age128 单独，不建议 |
| V12.6 age128 + move48 + ADX18 | +432.32% | -20.39% | 3.30 | 27 | 回撤最低，但收益牺牲过大，可作极端稳健参考 |
| V13 age128 + dist08 | +1573.15% | -20.39% | 4.29 | 27 | 在 age128 上增加 EMA96 距离过滤，收益接近高收益分支，回撤降到最低档 |
| V14 late re-entry | +2191.92% | -24.66% | 4.30 | 33 | 保留 V13 首入场过滤，只补同一 regime 盈利后的 late re-entry，收益显著增强 |
| V15 atr18_trend7 | +2303.65% | -17.79% | - | 31 | 高胜率/低回撤 registered version；trend_score >= 7 后回撤压进 20% |
| V16 atr18 | +3202.92% | -28.19% | - | 38 | 高收益 registered version；只挡 ATR 过热，放宽趋势质量过滤 |
| V17 hybrid | +2910.74% | -17.79% | 4.79 | 33 | V15 高质量主信号 + 少量 V16 卫星信号；收益接近 V16，回撤保持 V15 |
| V17.1 hq_scale=1.1 | +3861.48% | -19.44% | 4.77 | 33 | V17 信号不变，只放大 HQ 主信号仓位；收益最高但贴近 20% 风险边界 |

## 实现状态

| 项目 | 记录 |
| --- | --- |
| 策略文件 | archive/code/platform/src/strategy_lab/strategies/hype_ema_crossover_trend/strategy.py |
| 基础 factor | ema_spread_96_384 |
| 当前代码状态 | 已实现 V1 裸交叉策略；V2/V3/V4/V5/V6 仍是研究参数，尚未固化到策略类 |
| V1 测试 | tests/test_strategies.py 覆盖交叉入场、10% 止盈、registry 创建 |
| 研究脚本 | research/hype/15m-ema-crossover/scripts/research_hype_ema_cross_strategy.py；结果报告 artifacts/hype_ema_cross_research.json |
| 对比脚本 | research/hype/15m-ema-crossover/scripts/compare_hype_ema_v2_v4.py；结果报告 artifacts/hype_ema_v2_v4_compare.json |
| V5 脚本 | research/hype/15m-ema-crossover/scripts/research_hype_ema_regime_hold_v5.py；结果报告 artifacts/hype_ema_v5_data_lake_compare.json |
| V7 脚本 | research/hype/15m-ema-crossover/scripts/research_hype_ema_volume_exhaustion_v7.py；结果报告 artifacts/hype_ema_volume_exhaustion_v7.json |
| V8 脚本 | research/hype/15m-ema-crossover/scripts/research_hype_ema_volume_overlay_v8.py；结果报告 artifacts/hype_ema_volume_overlay_v8.json |
| V9/V10 脚本 | research/hype/15m-ema-crossover/scripts/research_hype_ema_htf_rsi_exit_v9.py；research/hype/15m-ema-crossover/scripts/research_hype_ema_oscillator_top_exit_v10.py |
| V11 诊断 | research/hype/15m-ema-crossover/scripts/research_hype_trade_path_diagnostics_v11.py；artifacts/hype_trade_path_diagnostics_v11.json |
| V12 脚本 | research/hype/15m-ema-crossover/scripts/research_hype_state_machine_v12.py；artifacts/hype_state_machine_v12.json |
| V12.1 hard exit | research/hype/15m-ema-crossover/scripts/research_hype_state_machine_v12_hard_exit.py；artifacts/hype_state_machine_v12_hard_exit.json |
| 主结果补齐 | artifacts/hype_main_result_backfill_v12.csv；artifacts/hype_main_result_backfill_v12.json；artifacts/hype_main_result_backfill_v13.csv；artifacts/hype_main_result_backfill_v13.json；artifacts/hype_main_result_backfill_v14.csv；artifacts/hype_main_result_backfill_v14.json |
| V13 横向回测 | research/hype/15m-ema-crossover/scripts/research_hype_v13_main_backfill.py；V13 = V12.4 age128 + entry_max_dist_ema96 <= 8% |
| V14 横向回测 | research/hype/15m-ema-crossover/scripts/research_hype_v14_main_backfill.py；V14 = V13 + same-regime profitable late re-entry |
| V16/V17 搜索 | research/hype/15m-ema-crossover/scripts/research_hype_v16_indicator_expansion.py；research/hype/15m-ema-crossover/scripts/research_hype_v17_trend_state_search.py |
| V15/V16/V17/V17.1 分段回测与消融 | artifacts/hype_v15_v16_promoted_window_backfill.*；artifacts/hype_v17_hybrid_ablation*；artifacts/hype_v17_1_full_ablation* |
| V17.1 严格口径审计 | research/hype/15m-ema-crossover/scripts/research_hype_ema_x_v17_1_strict_live_audit.py；diagnostics/hype-ema-x-v17-1-strict-live-audit-2026-07-01.md；artifacts/hype_ema_x_v17_1_strict_live_audit_*_2026-07-01.* |
| V17.1 全参数消融与精简 | `scripts/research_hype_v17_1_full_ablation.py`；`scripts/research_hype_v17_1_parameter_prune_audit.py`；`diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md`；`artifacts/hype_v17_1_full_ablation*` |
| V18 干净参数规格 | `specs/hype-ema-x-v18-baseline-spec.md` |
| V17 合体消融 | `ablations/hype-ema-x-v17-hybrid-ablation.md` |
| V15/V16 规则镜像 | `notes/hype-ema-x-v15-v16-promoted-strategy-specs.md` |
| V6 图表 | artifacts/hype_ema_v6_binance_trade_chart.html；含 K 线、开平仓文字和交易连线 |
| 当前候选 | 信号层：`HYPE-EMA-X-V17`；收益增强：`HYPE-EMA-X-V17.1`；干净规格：`HYPE-EMA-X-V18` |
