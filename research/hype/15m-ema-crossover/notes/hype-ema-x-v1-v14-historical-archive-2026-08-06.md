# HYPE-EMA-X V1–V14 历史研究归档

本文承接主账压缩前的 V1–V14 演化叙事；V15 以后身份与指标留在主账。参数与逐项结果仍以 notes、diagnostics、ablations 和 artifacts 为准。

## V1–V6：从交叉到 regime 持有

- V1 裸 EMA96/384 交叉证明方向信号有正收益，但趋势内反复开平仓、回撤大。
- V1.1 固定 4% 止损过密，只小幅降回撤却损害收益与 Sharpe。
- V2 把交叉改为 regime 方向，在 regime 内等待 ADX/成交量/1h 确认并允许再入场；固定 ATR 止盈复利使其显著强于裸交叉。
- V3 只在交叉当根做动能确认、趋势不坏则持有；机制更纯，但样本少、收益弱。
- V4 引入 EMA96 斜率、DI14、RSI14 与 4h EMA 确认；窗口化再入场会吸入趋势晚期和震荡交易。
- V5 删除固定 TP/timeout，只在 ADX、反向交叉或灾难止损时退出，成为趋势持有基线。
- V6 在 V5 上按 ATR 动态仓位、cap 3x；1Y `+454.08%`、DD `-26.77%`。收益放大伴随风险放大。

## V7–V12.3：退出状态机

- V7 验证 volume exhaustion 退出有信息，但单独替代 V6 会切碎趋势。
- V8 将 volume exhaustion 作为 V6 overlay，1Y `+493.56%`、DD `-27.63%`、97 笔；提升来自退出后再入场。
- V9/V10 的高周期 RSI、KDJ、MACD histogram 和量价组合改善有限，继续堆指标不能解决退出。
- V11 交易路径诊断确认主要瓶颈是 early exit 与 bad entry；长期 early-exit rate 约 55%。
- V12 把量能/震荡降级为 warning，等 EMA/Donchian/ATR price structure confirm；高收益版 `+792.86%` 但 DD `-43.20%`。
- V12.1 swing96 hard invalidation 把 stop-loss 从 11 笔降至 4 笔，1Y `+1205.06%`，但 early exit 仍约 62%。
- V12.2 删除 MFI divergence 后 1Y `+1547.98%`、early exit 降至 52.31%，说明 MFI 背离在强趋势中段误报。
- V12.3 要求 warning exit 至少捕获历史 MFE 的 35%，严重早退从 6 笔降至 0；1Y `+1587.09%`。

## V12.4–V14：坏入场与再入场

- V12.4 发现坏入场集中在过老 regime 和短线拉伸。`age128` 将 DD 降至 `-29.47%`、坏入场率 `14.29%`；`move48_12` 收益更高但风险更大。
- V12.5 ADX 分段退出能把 DD 压到约 `-31.85%`，但牺牲收益；EMA55 分段过早切碎趋势。
- V12.6 age + segment ADX 没有优于 age128 单独；最低 DD 组合约 `-20.39%`，收益牺牲过大。
- V13 使用 `age128 + dist_ema96<=8%`，1Y `+1573.15%`、DD `-20.39%`、27 笔、胜率 `85.19%`。
- V14 在盈利退出后允许受限 late re-entry，1Y `+2191.92%`、DD `-24.66%`、33 笔；收益提高但路径依赖增加。

## 通用负结论

- 早退问题不能靠更多震荡指标解决，必须用价格结构与 MFE capture guard。
- 固定 ATR 止盈曾贡献 V2 高复利，但不等于纯趋势持有；比较版本时必须区分收益来源。
- 更高收益常来自动态杠杆、再入场或切碎趋势后的复利，不能当作独立 signal quality 突破。
- 版本全样本指标高度依赖冻结 365-day slice，不能替代 forward、parity 和真实成交审计。

## 证据入口

- [V15/V16 规格说明](hype-ema-x-v15-v16-promoted-strategy-specs.md)
- [V16/V17 状态搜索](hype-ema-x-v16-v17-trend-state-search.md)
- [V17 hybrid 消融](../ablations/hype-ema-x-v17-hybrid-ablation.md)
- [V17.1 参数剪枝](../diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md)
- [V17.1 strict live audit](../diagnostics/hype-ema-x-v17-1-strict-live-audit-2026-07-01.md)
- [V18 rolling retest](../diagnostics/hype-ema-x-v18-retest-and-rolling-windows-2026-07-01.md)
