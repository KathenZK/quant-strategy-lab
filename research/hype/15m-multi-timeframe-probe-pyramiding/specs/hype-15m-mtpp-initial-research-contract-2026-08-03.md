# HYPE-15M-MTPP 初始研究合同（2026-08-03）

## 1. 研究问题与证据边界

本轮不再要求先预测“趋势未来会不会延续”，而是验证更贴近人工交易的可证伪命题：

1. 日/周价格方向只产生一个可错的假设；`4h/1h/15m` RSI/KDJ 只寻找风险收益更合适的位置。
2. 初始只试仓；行情先按方向走出真实浮盈后，等待新的低周期回踩恢复再加仓；亏损中绝不补仓。
3. 普通指标波动只停止加仓，不触发退出；错误由原始结构 stop 结束，正确行情由慢速结构保护和 `2R` 后半 MFE 保护尽量持有。

HYPE 历史已被相邻研究查看，本轮全部 historical 结果只称 causal diagnostic，不称 locked OOS。`[2026-08-02,2026-11-02 UTC)` prospective OOS 不得读取、选参或回测。

## 2. 数据与因果时序

- Binance USD-M `HYPE/USDT:USDT` perpetual 标准数据湖 `15m` OHLCV 与 funding。
- 先审计 UTC、连续性、重复、关键空值、OHLCV 合法性、raw/normalized parity 与 funding 来源。
- `1h/4h/1d/1w` 全由连续 `15m` 聚合；只有预期源 K 数完整的 bar 可用。
- 高周期特征的可见时间为 bar 结束时刻；在该时刻闭合的 `15m` 上计算动作，最早下一根 `15m open` 成交。
- stop 在下单后的下一根 bar 起生效；gap 穿越按更差 open，不能用旧 stop price 美化成交。

## 3. 冻结方向假设与位置触发

Long/Short 完全分开报告，规则镜像：

- 日周假设：Long 要求最近完整周 close 高于两周前完整周 close，且最近完整日 close 高于七日前完整日 close；Short 全部反向。
- `4h` 上下文：Long `RSI(14)>=50`；Short `RSI(14)<=50`。
- `1h` 位置：Long `RSI(14)` 在 `[40,60]` 且 KDJ `K<=55`；Short `RSI(14)` 在 `[40,60]` 且 `K>=45`。
- `15m` 触发：Long `RSI(14)<=55` 且 KDJ K 从下向上穿 D；Short `RSI(14)>=45` 且 K 从上向下穿 D。
- KDJ 固定为 RSV `9`、K/D 指数平滑 `3/3`；RSI 使用 Wilder `14`。
- 同一方向只有空仓时可试单；不做固定止盈。

## 4. 冻结 stop、确认、滚仓与退出

- 原始结构 stop：Long 放在入场前最近六根完整 `4h` low 的最低点再下移 `0.25%`；Short 镜像。价格 stop 距离小于 `1.5%` 时扩到 `1.5%`，超过 `15%` 的试单跳过。
- 计划 full quantity：按 entry-to-stop 加预计双边 fee/slippage 反推计划风险，同时受 entry equity `3x` notional cap；`3x` 是上限而非目标。
- 试仓：计划 full quantity 的 `25%`。
- 第一次确认：价格 MFE 达 `0.5R`、当前净浮盈为正、日周假设仍在，且出现新的同向 `15m` 回踩恢复后，提高到 `50%`。
- 第二次确认：MFE 达 `1R` 且满足同样条件，提高到 `75%`。
- 成熟趋势：MFE 达 `2R` 且满足同样条件，提高到 `100%`。每次 add 至少间隔 `4h`，亏损中禁止增加 quantity。
- stop 迟滞：MFE 未达 `1R` 前不得因 RSI/KDJ 变弱收紧；达到 `1R` 后，只在完整 `4h` 更新同向六根结构 stop，且 stop 只能收紧；达到 `2R` 后，另设从 entry 到价格 MFE 的 `50%` 保留线。
- 退出：原始/动态 stop、日周假设双重反向或 `14d` 到期；没有 RSI/KDJ exit，没有延续概率 exit，没有固定 take-profit。

这里的 `R` 是入场价格到原始结构 stop 的单单位价格距离；账户的 `1%/3%/10%` 是愿意为该距离配置多少 quantity，二者不是同一个概念。

## 5. 预声明对照与风险梯度

对每个方向和每个风险预算 `1%/3%/10%`，至少运行：

- `static_seed`：相同入场与退出控制，全程固定 `25%` 计划 quantity。
- `static_full`：相同入场与退出控制，从入场即持有 `100%`。
- `profit_step`：`25/50/75/100%`，达到 MFE 门槛即加，不等回踩恢复。
- `timed_pyramid`：只有 MFE 门槛与新回踩恢复同时满足才加，仍用原始 stop。
- `trader_full`：`timed_pyramid` 加 `1R` 后结构收紧和 `2R` 后半 MFE 保护。

政策独立运行；另做入场事件级同路径归因，避免把不同再入场时机误报成模块增量。参数在查看结果前冻结，本轮不做阈值搜索。

## 6. 评估与门禁

- 成本：gross、fee `10bps/fill` + base adverse slippage `4bps/fill` + actual funding、slippage `8bps` stress。
- 报告：净收益、Sharpe、MDD、campaign 数、胜率、平均/中位/最大持有、换手、add 数、达到 `0.5/1/2R` 数、止损/假设反向/到期退出、平均价格 MFE 捕获率、最大 fill/effective leverage 与最差 campaign。
- 默认 recent slices：数据末端前 `1d/7d/1m/3m/6m/1y`，只作审计不作选择。
- Long/Short 分开；至少五个连续时间块报告，不因全样本最好结果合并方向。
- `trader_full` 只有在 base/stress 均为正、相对 `static_seed` 和 `timed_pyramid` 有净增量、平均持有至少 `24h`、无 `3x`/因果/数据质量 breach，且块稳定性不过度依赖单一阶段时，才算得到 historical mechanism support。
- `10%` 只代表接受范围上限。若它只是线性放大同一负 edge、显著恶化 MDD 或风险集中，则明确判定不可采用，不以“用户能承受”替代策略证据。

本轮只作机制诊断：不登记版本、不 promotion、不交接 runner。
