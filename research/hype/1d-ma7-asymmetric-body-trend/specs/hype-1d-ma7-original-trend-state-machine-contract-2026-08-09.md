# HYPE 1D MA7 原始趋势状态机研究合同

> 初次冻结：`2026-08-09T10:20:16Z`；首次绩效运行前因因果测试发现执行账本缺陷，于 `2026-08-09T10:29:01Z` 重新冻结。首次绩效揭示后于 `2026-08-09T10:33:11Z` 补齐 phase-8 可执行窗口回退，并于 `2026-08-09T10:40:43Z` 让 MC3 对各臂使用共同随机数；两项均不改变 UTC-0 主路径或策略规则。状态：`explore / not promoted / not live-ready`。用户于 2026-08-09 对冻结前提出的六项建议回复“都按建议”。本合同不登记 V5，也不改变 V1–V4。

## 1. 身份与边界

- Family：`HYPE-1D-MA7-Asymmetric-Body-Trend`；研究分支：`original-trend-state-machine`。
- 市场：Binance USD-M `HYPEUSDT` perpetual；主信号周期：UTC `1d`。
- 单仓、约 `1x`、非加仓；成交间数量固定。
- 现有 `HYPE-1D-MA7-ABT-V1` 至 `V4` 的参数、逐笔路径、状态和 prospective 台账全部冻结，只作历史对照。
- 本分支来自用户对原始 MA7 趋势跟随思想的重新澄清；任何结果均先保持 `explore`。只有用户明确要求登记且主账完成登记，才可创建新主版本。

## 2. 数据与揭示边界

- 首次 development 运行固定使用当前已接受的标准数据湖：`1h` OHLCV 截止 `2026-08-06 07:00 UTC`，funding 截止 `2026-08-06 08:00 UTC`。
- 由恰好 24 根连续、闭合、已接受的 `1h` 聚合完整 UTC 日；可用最后完整日为 `2026-08-05`，`2026-08-06 00:00` 只作 terminal open。
- 上述全部历史已被研究者查看，只是 researcher-exposed development / internal validation；任何 rolling、CPCV、近期或相位结果都不是 clean OOS。
- 新 prospective 从冻结后第一根完整 UTC 日 `2026-08-10 00:00–2026-08-11 00:00` flat-start；最早信号在该日闭合后生成，最早于 `2026-08-11 00:00` 执行。
- 后续补入 `2026-08-06 08:00` 至冻结时刻之间的数据仍属 pre-freeze backfill，不得冒充 prospective。
- prospective 至少累计 `90` 个自然日且 `5` 笔平仓前，不讨论 promotion；观察数据不得用于改参数或选择实验臂。

## 3. 指标

- `SMA7[t] = mean(close[t-6:t])`。
- `ATR7`：日线 true range 的七期简单移动平均；信号使用日 `t` 已闭合后的 `ATR7[t]`。
- `RSI6`：TradingView/Wilder 口径；首个六期 gain/loss 为简单平均，随后 `RMA[t]=(RMA[t-1]×5+value[t])/6`。
- slope 只判断 `SMA7[t]-SMA7[t-1]` 的严格符号：long 要求 `>0`，short 要求 `<0`；等于 0 视为 slope 消失，不继承 V1–V4 的 `0.02×ATR7` 阈值。
- 等号不触发 fresh cross、RSI 阈值或方向 slope。

## 4. Fresh cross 与入场

- 主值 `N_cross=1`；前一完整日必须严格位于目标方向反侧，当前完整日严格穿到目标侧：
  - `flat -> long`：`close[t-1] < SMA7[t-1]` 且 `close[t] > SMA7[t]`；
  - `flat -> short`：`close[t-1] > SMA7[t-1]` 且 `close[t] < SMA7[t]`。
- fresh cross 直接产生入场信号，不要求入场日 slope；信号在下一 UTC open 执行。
- `N_cross={2,3}` 只作敏感性检查，不能用赢家替换主值。

## 5. 持仓、armed 与 `0.75×ATR7`

### Long

1. slope 严格向上且未出现反侧确认时继续持有；
2. fresh down-cross 后记 `short-armed`；只要尚未重新收回 MA7 上方，armed 持续有效，不设固定天数；
3. 若 armed 后 `close <= SMA7-0.75×ATR7` 且 short slope `<0`，次 open `long -> short`；
4. 若尚未越过下容错带但 long slope 已不再 `>0`，次 open 只平多转 flat；`short-armed` 跨 flat 保留；
5. armed 后重新严格收回 MA7 上方则取消。

### Short

完全镜像：fresh up-cross 记 `long-armed`；`close >= SMA7+0.75×ATR7` 且 long slope `>0` 后次 open 反多；short slope 不再 `<0` 时先平空转 flat并保留 armed；重新收回 MA7 下方则取消。

翻仓必须先平旧仓再开新仓，计两次真实 fill；不允许同一收盘价成交。

## 6. RSI6 模块与四个互斥实验臂

- `A_CORE`：仅第 4–5 节核心。
- `B_SHORT_RSI_EXIT`：A + 空头连续 3 个完整日严格 `RSI6<30`，并且信号收盘价低于空头入场价时，次 open 平空转 flat；不反多。
- `C_OVERBOUGHT_REVERSAL`：A + 在 fresh down-cross 之前连续 3 个完整日严格 `RSI6>70`，且 fresh down-cross 当日 short slope `<0` 时，允许次 open `long -> short`，不等待下容错带。
- `D_BOTH_RSI`：同时启用 B 与 C。
- RSI 连续日只读信号日以前的 overbought 记忆；short take-profit 的 3 日包含信号日。
- `N_RSI={2,4}`、short 阈值 `{25,35}`、overbought 阈值 `{65,75}` 只作 `mc4` 邻域检查，不能在本历史上替换 `3/30/70`。

同一收盘的优先级固定为：已 armed 的反向外带确认 > short RSI 止盈 > slope 消失转 flat；long 侧 overbought fresh down-cross 早于普通 armed 外带与 slope 退出。

若 short RSI 止盈日同时产生 `long-armed`，止盈仍只平空、不立即反多，但该 armed 状态跨 flat 保留；后续仍须满足上容错带与 long slope 才能开多，重新收回 MA7 下方则取消。

## 7. 执行、成本与风险保护分臂

- 收盘信号最早下一 session open 执行；额外延迟压力为再晚 `1d`。等待日仍以闭合数据推进 relation、RSI 与 armed 的年龄/recross 取消，但原决策冻结，不产生替代决策。
- 手续费 `0.001/fill`；基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`；funding 按实际事件时间、费率与事件小时 open 结算。
- 主 A–D 不继承 V4 的 trailing、hard stop、max hold 或 cooldown。
- 独立 `E_EXECUTION_PROTECTION`：分别在 A–D 上增加对称、入场即固定的 `1.5×entry ATR7` emergency stop；真实 `1h` open 跳空穿越按更差 open，小时内触发按 stop 价。止损只转 flat，不同小时重入。
- E 只回答执行保护是否降低裸仓/尾部风险，不参与 RSI alpha 臂选择；即使 E 改善也不得静默并入 A–D。
- terminal open 只平已有仓位，不执行新开仓。

## 8. 预注册实验与裁决

必须输出：

1. A–D 全期、`8 bps`、额外延迟 `1d`、E 保护；
2. 同成本/funding 的 `1x` buy-and-hold；
3. 最近 `1d/7d/1m/3m/6m/1y` 连续路径；
4. `90d` flat-start、步长 `30d` rolling；
5. 六个连续块、每次留二块、边界 purge `10d` 的 CPCV；交易不足须写 insufficient evidence；
6. 每臂分层 long/short campaign bootstrap `10,000` 次（`mc3`）；
7. 第 4、6 节所列邻域与核心模块消融（`mc4` / OAT）；
8. 从真实 `1h` 重聚合 `0–23h` 相位；相位只作检查项，不单独否决；
9. long/short 单腿、MFE、MAE、short profit giveback、成本、funding、有效杠杆与破产路径；
10. 同一 retained backtest 生成的自包含完整交易路径 HTML。

RSI 模块只在相对 parent 显示可解释的正贡献时保留：改善净收益或至少改善 `2pp` MDD且净收益不低于 parent 的 `90%`；`8 bps` 与延迟结果必须仍为正；多数 rolling 窗口不能恶化；short RSI 止盈还必须降低 short giveback 且不把 short 腿转负。D 只有在组合不破坏已被单独接受的模块时才可作为主观察候选。

无论历史结果如何，缺少 clean prospective、交易样本不足、CPCV/MC/执行压力未通过时均保持 `explore / not promoted / not live-ready`；本合同不授权 runner 或 live spec。

## 9. 冻结实现

- 状态机：[hype_1d_ma7_original_trend_engine.py](../scripts/hype_1d_ma7_original_trend_engine.py)，SHA256 `4e2bcfda0dd693968687f3cff1ca845df892e88d0eb5c82029333e828274f403`。
- 研究器：[research_hype_1d_ma7_original_trend.py](../scripts/research_hype_1d_ma7_original_trend.py)：首次绩效运行前 SHA256 `cea16c6a28b2f8c4eb5110acd0460e6f8b3d11354c4f70a9b7a2043b4c8be398`；phase-8 审计修正后为 `016d66b31a833293423b7962dd677c4f81e8f1d3c3d23aac6d6c67570f7ed767`；MC3 共同随机数修正后为 `961c9acdd888c2edd3b3cd88818b34dbe02cc15308bd1919f5e789d16a126087`。
- 测试：[test_hype_1d_ma7_original_trend_engine.py](../../../../tests/test_hype_1d_ma7_original_trend_engine.py) 与 [test_hype_1d_ma7_original_trend_research.py](../../../../tests/test_hype_1d_ma7_original_trend_research.py)，当前共 `23 passed`。
- 重新冻结只修正测试揭示的三项账本语义：延迟日推进历史但不替换信号；emergency stop 成交前先 mark-to-fill 且不读取止损后的小时极值；terminal execution point 纳入 retained equity path。此时尚未读取任何本分支真实历史绩效。
- 首次揭示后发现 phase `08:00 UTC` 的最后完整信号日缺少下一 session open；审计器固定回退到前一个同时具备 24 根小时线和 terminal open 的完整窗口。该修正只补齐 24 相位覆盖，UTC-0 A–E、压力、rolling、CPCV、MC 与逐笔路径不变，修正后结果不得再称为“首次未揭示运行”。
- MC3 最初按实验臂偏移 seed，导致路径完全相同的 A/C 与 B/D 产生纯随机差异；现固定用同一 seed 与共同随机数。该修正只让相同 trade-return 序列得到相同 MC3 结果，不改变任何回测路径或确定性指标。
- 任何改变逐笔路径的修正必须更新本合同、重新冻结代码 hash，并在再次读取绩效前说明；首次揭示后不得把修正后的结果称为同一 clean 选择。
