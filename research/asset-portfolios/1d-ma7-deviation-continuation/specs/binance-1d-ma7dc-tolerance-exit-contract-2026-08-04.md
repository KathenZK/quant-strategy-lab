# Binance 1D MA7 容忍带与半 MFE 退出验证合同

## 1. 研究问题

上一轮确认：HYPE 日线 SMA7 能较早对齐部分上涨 campaign，但“一次收盘跌破 MA7、下一日开盘退出”只捕获完整 `3–14d` 波段中位数 `18.7%`，且在截图主体长趋势中会过早退出。

本轮只验证一个实质变化：**价格对 MA7 的小幅反向偏离是否应被视为趋势噪声，并用浮盈回吐保护替代一次跌破即退。**不改变 MA7 长度、趋势评分基准或入场对齐规则。

## 2. 数据、资产与评分边界

- Binance USD-M perpetual；HYPEUSDT 为 primary，BTCUSDT、ETHUSDT 只作 control。
- 使用标准数据湖与完整 UTC `1d`；数据质量、raw/normalized parity 与 funding 口径继承本家族已接受审计。
- MA7 状态只使用闭合日 K；日线退出信号在下一日 open 成交。
- ex-post close-based ATR ZigZag 仍只定义 completed swing 和评分，不得作为真实入场或退出信号。
- Primary：`HYPE / 2 ATR reversal / long / 3–14d`；同时固定报告 `all >=3d`、`15–30d`、`31d+` 与 `1.5/3 ATR` sensitivity。
- 既有历史已揭示；本轮只能形成 diagnostic evidence，不能充当 prospective OOS 或 promotion 证据。

## 3. 共同入场与风险单位

沿用上一轮首次可执行对齐：

```text
sign(MA7_t - MA7_t-1) == side
sign(Close_t - MA7_t) == side
```

信号在闭合日线可见后，下一日 open 成交。

每一腿冻结：

```text
R_price = ATR7_at_entry
initial_stop = entry_fill - side × R_price
```

- 硬止损从入场成交后立即有效；若下一根 OHLC 显示穿越，保守假定止损先发生，不利用同一日未知的 high/low 顺序美化 MFE。
- 若日 open 已跳过 stop，按该 open 再叠加不利滑点成交；否则按 stop 价再叠加不利滑点。
- 三条实验臂使用完全相同的 1R hard stop，防止 MA7 容忍带变成无限扛亏。

账户风险百分比和杠杆不属于本轮 swing-normalized 诊断；本轮只定义每腿价格风险单位，不能把结果解释为账户收益或最大回撤。

## 4. 固定偏离定义

```text
wrong_side_deviation_atr
= max(0, -side × (Close_t - MA7_t)) / ATR7_t
```

多头等价于 `max(0, MA7-Close)/ATR7`；空头完全镜像。

- `<=0.5 ATR`：浅度偏离，继续持仓；
- `0.5–1.0 ATR`：警戒；第一次出现不退出，但禁止把它解释为可加仓状态；
- `>1.0 ATR`：单日明显失配；
- 连续两次日收盘均 `>0.5 ATR`：持续失配。

阈值 `0.5/1.0 ATR` 为本轮冻结值，不搜索 MA5–MA30，也不扫描连续确认天数。

## 5. 三条固定实验臂

### A. `cross1_risk`

- 一次收盘到 MA7 反侧，下一日 open 退出；
- 或 1R hard stop 先触发。

它是加入共同风险底线后的旧规则参考，不覆盖上一轮无 hard stop 的 `cross1` 结果。

### B. `band05_confirm2_risk`

- `wrong_side_deviation_atr >1.0`：下一日 open 退出；
- 或连续两日日收盘 `wrong_side_deviation_atr >0.5`：下一日 open 退出；
- 或 1R hard stop 先触发；
- 单次 `<=1.0 ATR` 偏离不退出。

### C. `band05_confirm2_mfe50_risk`

包含 B 的全部规则，并增加：

```text
MFE_R = side × (best_favorable_price - entry_fill) / R_price
close_profit_R = side × (Close_t - entry_fill) / R_price
giveback = (MFE_R - close_profit_R) / MFE_R
```

当 `MFE_R >=2` 且 `giveback >50%`，在该日收盘确认，下一日 open 退出。`MFE <2R` 时不启动半 MFE 保护，只由共同 hard stop 与 MA7 偏离带保护。

MFE 使用持仓以来已发生的 high/low；giveback 使用当日 close，二者在日线闭合时均已知。

## 6. 同趋势重入对照

三条实验臂均输出 supplementary reentry：若某腿退出时 ex-post swing 尚未结束，之后 MA7 再次满足共同对齐条件，则下一日 open 重新进入。

- 每个 swing 最多 20 腿，仅作为防御性上限；
- 每腿重新计算 `R_price`、hard stop 与 MFE；
- 每次成交重新收取 fee、slippage 和 funding；
- primary 结论先看单次轨道；reentry 只回答容忍带能否减少追回同一趋势所需的往返次数。

## 7. 成本和可执行时序

- fee：每次成交名义 `0.001`；
- adverse slippage：每次成交 `4 bps`；
- funding：完整持仓日按实际历史 funding 扣减；日线 OHLC 无法确定盘中 stop 与 funding 时点的先后，因此 stop 当日保守计入整日不利 funding、忽略整日有利 funding；
- 日线规则：信号日 close 已闭合，下一日 open 成交；
- stop-market：日内触发，跳空按更差 open，不允许 stale stop fill；
- swing end 后最多继续等待 30 日；无退出标记 censored。

## 8. 固定指标与近期切片

每资产、方向、ATR threshold、时长桶、实验臂与单次/重入分别输出：

- admission、timely admission、完整/可用波段捕获；
- MFE retention、giveback、净正比例与中位净收益；
- first/final premature exit、退出延迟；
- 每腿最大持仓内 peak-to-trough drawdown、MAE_R、holding days；
- hard-stop/band/cross/MFE 各退出原因；
- round trips、reentries、fees 与 funding。

按数据终点锚定最近 `1d/7d/1m/3m/6m/1y`，以首次 entry 时间归属；零样本必须显式输出，不用更早交易填充近期结果。

## 9. 预声明比较门禁

Primary 比较 B/C 相对 A，且 HYPE `2 ATR / long / 3–14d` 至少需要 12 个 completed swings。样本不足一律写 `insufficient`。

在样本足够时，候选至少满足以下五项中的四项，才写 `tolerance exit supported`：

1. median full-swing capture 相对 A 提高至少 `15` 个百分点；
2. median MFE retention 相对 A 提高至少 `15` 个百分点；
3. median intratrade drawdown 不比 A 恶化超过 `5` 个百分点；
4. reentry 对照的 total reentries 相对 A 减少至少 `30%`；
5. median net return 高于 A 且仍为正。

满足两到三项写 `partial`；零到一项写 `not supported`。这是退出机制标签，不是策略主状态。

## 10. 停止边界

- 不因结果改成 MA5、MA10 或别的均线；
- 不搜索 `0.1–2 ATR` 或 `20%–80% MFE` 网格；
- 固定 sensitivity 只能报告 `0.25/0.75 ATR` 与 `40%/60% MFE` 的局部稳定性时另立补充，不参与本轮选择；本轮先不运行该 sensitivity；
- 不把 ex-post swing 变成交易信号；
- 即使退出机制改善，也必须另行建立账户级仓位、加减仓、杠杆、组合风险和 prospective OOS 才能讨论版本登记或上线。
