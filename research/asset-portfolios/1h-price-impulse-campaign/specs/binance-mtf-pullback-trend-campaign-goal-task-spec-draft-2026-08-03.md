# Binance 多周期回调趋势 Campaign Engine 目标任务 Spec（审阅稿）

> 日期：2026-08-03  
> 状态：`DRAFT / 尚未创建目标任务 / 不授权 promotion 或部署`  
> 用途：用户确认后，作为一个全新 Codex Goal 的完整输入合同。  
> 拟建家族：`Binance-MTF-Pullback-Trend-Campaign`（暂定 alias：`BIN-MTF-PTC`）。

## 0. 目标是否已经理解清楚

用户要的不是一个“回测中某个指标有效”的研究结论，而是一个最终可以进入线上执行流程的趋势策略：

1. 先确认市场可能已经进入趋势，而不是预测每根 K 线。
2. 不在冲量高点/低点立即追价，等待回调后从更有利的位置试单。
3. 行情用真实浮盈证明趋势仍在后，才获得加仓资格；加仓同样等待新的回调和重新启动，不追极值。
4. 错误假设要小亏、快速承认；正确趋势要允许持有 3–14 天，并通过分层仓位尽量获取右尾。
5. 原始 probe 与新增 layers 使用不同速度的保护：新增仓止损更近，原始 probe 使用慢速结构跟踪，避免小回调切断大趋势。
6. 最终追求较高净收益、较低回撤和比现有 V2 更好的胜率，但不得通过提高杠杆、隐藏成本、固定小止盈或事后筛选方向伪造改善。
7. 研究必须落到可复现订单状态机、逐笔账本、风险不变量、runner 能力合同和明确的 promotion 决策；只做分析不算完成。

目标允许最终得出 `not promoted / not live-ready`。不允许为了产出“成功策略”而不断增加过滤器或修改已揭示 OOS。

## 1. 独立身份与历史边界

### 1.1 新家族

本任务必须新建独立家族 `Binance-MTF-Pullback-Trend-Campaign`，不得覆盖或静默修改：

- `HYPE-EMA-Trend-Breakout` / V35TB；
- `HYPE-15M-Multidimensional-Trend-Pyramiding`；
- `Binance-1H-Price-Impulse-Campaign` V0–V2；
- 其他已登记或运行中的策略家族。

新家族可以复用经过验证的数据、成本、账本和通用内核，但不得继承旧家族的绩效结论、状态或 promotion 权限。

### 1.2 已揭示历史

HYPE/BTC/ETH/SOL 的现有历史已经在多轮研究中被反复观察。它们仍可用于：

- 机制诊断；
- 因果 walk-forward；
- 消融；
- 稳定性和成本压力；
- 发现实现错误；
- 筛除明显失败机制。

但不得再把现有历史中的任意切片描述为真正未见 OOS。最终候选形成后必须锁定新的 prospective OOS；在新 OOS 成熟前，历史通过最多只能标记为 research-pass candidate，不授权 live spec、dry-run 或 live。

## 2. Goal Objective

目标任务的推荐 objective：

> 在 `/Users/ZK/OpenCode/quant-strategy-lab` 中建立一个全新、独立、可复现、可证伪的 `Binance-MTF-Pullback-Trend-Campaign` 策略家族。用 4h 价格冲量和可选 ATR 扩张识别趋势候选，1h 识别 0.5×ATR 至冲量 50% 的健康回调，15m 确认顺势重新启动并 next-open 成交；实现 0.25% 风险 probe、三个独立结构止损的 0.25% add layers、每层最多一次重试、2R 后慢速结构跟踪、半 MFE 去新增层、24h 假设验证、14d 最大持有和 funding 后风险维护。对 ETH/HYPE/BTC/SOL 分资产研究，不强迫同参数有效；完成真实成本、逐笔账本、walk-forward、近期切片、稳定性、消融、压力成本、右尾归因和 runner 可执行性审计。以预先冻结的收益、回撤、胜率、正偏、稳定性和风险门禁决定 research-pass 或 not-promoted；禁止在揭示结果后救参数。若历史门禁通过，只建立不可篡改的 prospective OOS 合同和观察器，不绕过 promotion 门禁直接部署。

创建 Goal 时不设置 token budget，除非用户届时另行指定。

## 3. 研究对象与资产边界

### 3.1 第一层：分资产机制研究

资产：

- ETHUSDT perpetual；
- HYPEUSDT perpetual；
- BTCUSDT perpetual；
- SOLUSDT perpetual。

四个资产必须分别报告、分别判断资格。禁止因为 ETH 有效就默认 HYPE/SOL 有效，也禁止用一组“六币同参数”作为成功条件。

允许共享状态机结构；资产的波动尺度必须由各自 causal ATR/RMS 自适应。任何资产专属阈值必须在该资产自己的开发样本内形成，并受独立搜索预算限制。

### 3.2 第二层：组合装配

只有单资产历史门禁通过后才进入组合装配。初版组合：

- 合格资产等风险；
- 单资产 campaign 硬风险上限 1%；
- 组合同时开放风险上限 2%；
- 同方向加密 beta 暴露上限 1.5%；
- 超过组合上限时只缩减新订单，不放大其他资产；
- 不建立基于已揭示 OOS 收益排名的动态 selector。

若只有一个资产合格，允许输出单资产 research-pass，不得为了“跨资产”形式强行加入失败资产。

## 4. 数据、时序与成本合同

### 4.1 数据

- Binance USD-M perpetual 官方 `15m` closed OHLCV；
- 实际 funding history；
- 由完整 `15m` bars 聚合因果 `1h/4h`；
- raw/normalized parity、缺口、重复、null、OHLCV 合法性全部 fail-closed；
- 所有资产记录各自上市时间、有效样本长度、合约状态和数据 cutoff。

OI、主动买卖量、清算等不是初版必需数据。只有 price-only + ATR 主机制通过后，才允许作为单独预声明消融加入；它们不能成为失败后的救援过滤器。

### 4.2 时间顺序

- 4h 候选只使用完整 4h bar；
- 1h 回调只使用完整 1h bar；
- 15m 重新启动只使用完整 15m bar；
- 信号在 bar close 确认，订单默认下一根 15m open 成交；
- stop intrabar 使用保守成交；gap 穿越 stop 按实际 open + adverse slippage；
- 禁止使用未收盘高周期值、未来 pivot 或回填后的最终 funding 值做当时不可获得的决策。

### 4.3 成本

Binance 默认：

- fee：`10bps/fill`；
- base adverse slippage：`4bps/fill`；
- stress slippage：`8bps/fill`，并至少增加一档更严格压力；
- 实际 funding；
- quantity/price precision、step size、tick size、min notional；
- 每次 entry/add/retry/risk-trim/partial-exit/stop 都是独立 fill 并计费。

同时报告 gross、fee-only、base net、stress net。任何 gross-only 成功不得 promotion。

## 5. 冻结策略状态机

## 5.1 4h：趋势候选，不直接开仓

主方向信号保留纯价格定义：

```text
impulse_4h = log(close_t / close_t-4h)
scaled_impulse = abs(impulse_4h) / (prior_hourly_RMS × sqrt(4))
direction = sign(impulse_4h)
candidate = scaled_impulse >= 1.0
```

过去波动必须在冲量窗口之前结束，避免重叠泄漏。

预声明 admission arms：

- `P0 price_impulse`：只用上述方向性冲量；
- `P1 price_impulse_plus_atr_expansion`：冲量成立，且 4h true range/ATR 相对过去 causal 基准扩张；
- `C0 atr_expansion_only`：只做诊断控制，不作为默认方向模型。

ATR 只衡量波动扩张，不负责决定多空。初版 ATR 周期和扩张阈值必须在首次运行前冻结；不得根据最终收益选择。推荐默认使用 `ATR(24)` 作为 1h 一日波动尺度，ATR expansion 使用短/长固定比率并只做一次主值 + 邻域稳定性，不做大范围搜索。

候选出现后进入 `AWAIT_PULLBACK`，禁止立即下单。

## 5.2 1h：健康回调

以做多为例，做空完全对称。

候选出现后持续记录顺势新高和冲量 leg：

```text
impulse_origin = 候选冲量起点
running_extreme = 候选后最高价
pullback_depth = running_extreme - 当前回调低点
impulse_leg = running_extreme - impulse_origin
```

合格回调冻结为：

- 最浅深度：`0.5 × ATR1h(24)`；
- 最深深度：不超过当前 impulse leg 的 `50%`；
- 任意完整 1h close 穿过 impulse origin：候选失效；
- 等待超过 24h 仍无合格回调：候选失效；
- 回调太浅：继续等待，不追；
- 回调超过 50%：放弃，不把深跌解释成更便宜的入场。

`0.5×ATR` 和 `50%` 是用户已确认的主合同，不进行大范围参数搜索。只允许预声明邻域做稳定性，不允许选邻域最优替换主版本。

## 5.3 15m：重新启动确认

合格 1h 回调只把状态变为 `ARMED`，仍不下单。做多的初版 causal restart 定义：

1. 最近两个完整 15m bars 不再创本轮 pullback 新低；
2. 当前完整 15m close 突破此前 4 个完整 15m bars 的最高价；
3. close 位于该 15m bar 的上半区；
4. 下一根 15m open adverse fill 买入。

做空完全对称。

默认 restart lookback 为 4 根，只允许 3/5 根邻域稳定性；不得在 OOS 后选择最优窗口。若实现审计证明“两个 bar 不创新低”与突破条件 path-equal，可保留更简单的等价规则，但必须提供逐笔签名证据。

## 5.4 分层风险与仓位

四层均为风险预算，不是固定 quantity 百分比：

| Layer | 获得资格 | 请求风险预算 | 最大尝试次数 |
| --- | --- | ---: | ---: |
| Probe | 首个候选回调 + restart | 0.25% | 1 |
| Add-1 | campaign MFE 首次达到 +0.5R | 0.25% | 首次 + 1次重试 |
| Add-2 | campaign MFE 首次达到 +1R | 0.25% | 首次 + 1次重试 |
| Add-3 | campaign MFE 首次达到 +2R | 0.25% | 首次 + 1次重试 |

资格达到后不得立即加仓，必须重新经历：

```text
新的完整1h健康回调 → 15m重新启动 → next 15m open add
```

每层 quantity：

```text
layer_qty = requested_layer_risk /
            (entry_to_layer_stop_loss + entry_fee + stop_fee + slippage)
```

同时受以下限制：

- 总 operational stop-out risk ≤ entry-equity 的 0.9%；
- hard stop-out risk ≤ 1%；
- 有效杠杆 ≤ 3x；
- 组合开放风险上限；
- 当前 campaign 按预计立即退出计成本后必须净浮盈，亏损中禁止 add；
- 风险空间不足只允许 partial add，不能移动 stop 容纳目标 quantity。

## 5.5 每层独立止损

每次 probe/add 的初始结构止损：

- 做多：本次合格 1h pullback low 下方 `0.25 × ATR1h(24)`；
- 做空：本次合格 1h pullback high 上方 `0.25 × ATR1h(24)`；
- stop buffer 主值 `0.25×ATR`，只允许 0.15/0.35 邻域稳定性；
- stop 只能收紧，不能放宽。

新增层被自己的 stop 打掉：

- probe 和其他 layers 不自动退出；
- 只要 4h candidate/campaign 仍有效，该层可以等待一次全新的 1h 回调 + 15m restart；
- 每个 add 等级最多重试一次；第二次失败后该等级永久关闭；
- 禁止在同一回调内立即重新入场。

## 5.6 Probe 慢速结构跟踪

- Probe 入场后使用首个 1h pullback structure stop；
- campaign MFE 未达到 +2R 前，probe stop 不移动；
- 达到 +2R 后，只有当新的 1h 健康回调已经被随后的 15m restart 确认，才把该 pullback extreme 认定为 causal higher-low/lower-high；
- 下一根 15m open 更新 probe stop 到该结构点外 `0.25×ATR1h(24)`；
- stop 永不放宽；
- 不使用固定 take-profit。

## 5.7 半 MFE 保护

campaign MFE 达到至少 +2R 后，如果完整 1h close 的当前 progress 小于 peak MFE 的 50%：

- 下一根 15m open 平掉所有新增 layers；
- probe 不因半 MFE 单独退出，由自己的结构 stop 决定；
- 所有尚未使用的 add 资格冻结；已平 add 不再重试；
- 禁止同一 campaign 在大幅回吐后重新堆满风险。

## 5.8 24h 验证与 14d 上限

- Probe 入场后 24h 内从未达到 +1R：下一根 15m open 全部退出，`validation_failed_24h`；
- 最大持有 336h：下一根 15m open 全部退出，`timeout_336h`；
- 14d 是研究边界，不因历史赢家集中在 timeout 而事后延长；
- 没有合格回调导致从未入场，不计作 campaign 交易。

## 5.9 Funding 后风险维护

每次 funding 入账后重新计算所有 layers 在各自 stop 下的组合 worst-case equity：

- operational risk >0.9%：先 LIFO 减新增 layers；
- 仍超限：取消未成交 add、关闭已失败重试资格；
- 去掉全部新增层仍超限：减/平 probe，直到恢复风险不变量；
- 任意时点 hard risk >1% 为实现 blocker；
- 资金费风险维护必须计入真实 fill fee，不能只调整账面 target。

## 5.10 同一时点冲突优先级

冻结优先级：

1. gap stop / 强平安全检查；
2. 已触发的 layer/probe stop；
3. 24h validation / 14d timeout；
4. funding 入账与 risk maintenance；
5. 半 MFE 去新增层；
6. probe 结构 stop 更新；
7. 已确认 restart 的 entry/add；
8. 新的 4h candidate 和 1h/15m 状态更新。

同一 bar 不允许先看 high 获得加仓资格、再假设在该 bar low 的更优价格成交。所有 close-derived 动作只在 next open 执行。

## 6. 实验设计

### 6.1 冻结对照臂

必须保留：

- `B0 PIC-V2 immediate-entry benchmark`：当前 V2，只作历史参考；
- `B1 pullback-entry only`：回调入场，但无独立 add stops/retry/结构跟踪；
- `B2 pullback + independent layers`：加入等风险分层和独立 stop；
- `B3 full V3 price-only`：完整状态机，不含 ATR expansion admission filter；
- `B4 full V3 + ATR expansion`：只增加 ATR expansion；
- `C0 ATR-only direction control`：证明 ATR 本身不能替代方向；
- `P0 probe-only`：验证 add 是否真正贡献；
- `X0 no structural trail`：验证慢速 probe trail；
- `R0 no retry`：验证一次重试的贡献与成本；
- `M0 no half-MFE layer unload`：验证回吐保护。

消融只解释模块贡献，不允许从消融中挑一个历史最优版本冒充预先冻结主版本。

### 6.2 搜索预算

主合同先运行，不做 Cartesian 大搜索。稳定性只允许围绕主值 one-at-a-time：

- pullback min：0.35 / **0.50** / 0.75 ATR；
- pullback max：40% / **50%** / 60%；
- restart lookback：3 / **4** / 5 根 15m；
- structure stop buffer：0.15 / **0.25** / 0.35 ATR；
- ATR period：16 / **24** / 32 根 1h。

规则：

- 粗体为唯一主版本；
- 邻域仅检查方向、幅度和逐笔稳定性；
- 不把邻域最优替换主版本；
- 不组合搜索邻域；
- 不根据最终 OOS、最近 6m 或单个大赢家调阈值；
- 任何 materially new 机制必须另立合同和新的 prospective boundary。

### 6.3 Walk-forward 与时间切分

对现有已揭示历史：

- anchored/rolling walk-forward；
- purge 覆盖最长 14d label/持仓路径；
- embargo 至少覆盖高周期聚合和最长信号依赖；
- 报告每折 train/validation/test 时间、campaign 数和资产覆盖；
- 结果标为 revealed-history diagnostic，不冒充 fresh OOS。

最终候选冻结后：

- 写出不可修改的 prospective start timestamp；
- 锁定代码/spec/data cutoff hash；
- prospective 期间禁止参数修改、方向删除和资产资格事后调整；
- 未成熟前只报告数据完整性、信号/订单计数和实现健康，不反复窥视绩效；
- 成熟门槛建议为至少 180 天且至少 30 个 closed campaigns；两者必须同时满足。

## 7. 目标函数与验收标准

“高收益、低回撤、较好胜率”必须在同一个公平风险尺度下判断。

### 7.1 统一研究风险尺度

- 主研究结果使用单 campaign hard risk 1%；
- 不用提高到 3% 来通过机制门禁；
- 只有 1% 风险版本通过后，才机械测试 2%/3% scaling；
- scaling 不允许改变信号、stop、过滤器或资产选择；
- 报告实际有效杠杆漂移，而不仅是订单时 target leverage。

### 7.2 单资产硬门禁

候选资产必须同时满足：

| 指标 | 最低硬门禁 | 目标值 |
| --- | ---: | ---: |
| Base net CAGR | ≥8% | ≥12% |
| Base net Sharpe | ≥0.80 | ≥1.00 |
| Max drawdown | 不差于 -15% | 不差于 -10% |
| Calmar | ≥0.60 | ≥1.00 |
| Profit factor | ≥1.30 | ≥1.50 |
| Win rate | ≥35% | ≥40% |
| Avg win / avg loss | ≥1.8 | ≥2.5 |
| PnL-R skew | >1.0 | >2.0 |
| Closed campaigns | 全历史 ≥80；评估段 ≥30 | 越多越好但不靠高换手 |
| 120d rolling positive ratio | ≥65% | ≥75% |
| 最近 6m / 1y | 均非负 | 均为正且非单笔主导 |
| Stress cost return | ≥0 | 保留大部分 base 收益 |
| Hard-risk violations | 0 | 0 |

其中 CAGR、Sharpe、MDD、胜率不是可互相补偿的加权分数；任一硬门禁失败即不得 promotion。

若某资产上市历史不足以满足 campaign 数，不把“小样本高收益”判为通过，只能标记 insufficient evidence。

### 7.3 胜率解释约束

提高胜率必须来自更好的回调位置和假设验证，不能来自：

- 很近的固定止盈；
- 把浮盈未平仓算作胜单；
- 删除已揭示历史中的空头/某年份；
- 只保留大赢家资产；
- 改变 trade definition 把一次 campaign 拆成多个胜单；
- 忽略 partial stop、retry 和 risk-trim 的亏损 fill。

同时报告 layer fill 胜率、campaign 胜率和完整账户收益，三者不得混用。

### 7.4 右尾与集中度

趋势策略允许少数大赢家贡献主要利润，但必须报告：

- top 1/3/5/10 campaigns 的净利润贡献；
- 去掉最大 1/3/5 个赢家后的收益；
- timeout、structure stop、validation、layer stop、risk exhaustion 归因；
- MFE/MAE、捕获率和盈利回吐；
- long/short 独立结果；
- calendar year、bull/bear/range、高低波动状态。

去掉 top 5 后可以不盈利，但不能出现无法解释的灾难性崩溃；结论必须明确策略依赖右尾的程度。

### 7.5 组合门禁

进入组合层后：

- 组合 base Sharpe ≥1.0；
- MDD 不差于 -15%；
- Calmar ≥0.8；
- stress net ≥0；
- 任一资产贡献不超过组合总净利润 70%；
- 组合结果不是单纯增加名义杠杆；
- portfolio open-risk、同方向 beta cap 和 effective leverage 全程无违规。

## 8. 必须完成的实现与审计

### 8.1 回测内核

- 真实 lot-level ledger；
- 每层 entry/fill/stop/retry/fee/funding；
- partial resize；
- next-open pending actions；
- stop order quantity 同步；
- balance、marked equity、realized/unrealized、funding 分离；
- restart 后状态恢复；
- 同一 bar 冲突和 gap 审计；
- campaign 与 layer 两级 trade signature。

### 8.2 必须测试

- 高周期 closed-bar/as-of 对齐；
- 4h impulse 不读取重叠未来波动；
- 1h pullback 深度和 24h expiry；
- 15m restart 不读取未来 pivot；
- next-open entry/add；
- 每层独立 stop 与 LIFO risk trim；
- 每层最多一次 retry；
- 2R 前 probe stop 不移动；
- 2R 后只向盈利方向更新；
- 半 MFE 只卸新增层；
- 24h validation / 336h timeout；
- fee/slippage/funding/precision；
- aggregate hard risk ≤1%；
- effective leverage ≤3x；
- restart recovery 与重复订单幂等；
- research-to-runner parity fixture。

### 8.3 Runner 能力边界

在历史门禁和 fresh prospective OOS 通过前，不修改生产 manifest，不部署实例。

进入 live spec 前必须确认 `quant-runner` 支持：

- 同方向 partial add/reduce，而不是 flat-and-reopen；
- 多 layer 独立 stop 或等价的保护订单管理；
- stop quantity 在 partial fill 后原子同步；
- funding 后 risk maintenance；
- pending action/retry 状态持久化；
- 重启恢复、missing-bar fail-closed、kill switch；
- research/runner 逐 bar 和逐订单 parity。

如果 runner 不支持，先写能力差距报告；历史收益不能授权临时简化策略语义。

## 9. 研究阶段与停止规则

### Phase 0：审计与冻结

- 读取仓库规则、路由、现有家族和主账；
- 新建独立家族；
- 冻结数据 cutoff、成本、主状态机、搜索预算和门禁；
- 记录现有全历史已揭示边界。

### Phase 1：数据与共享内核

- 四资产 closed 15m/funding 质量审计；
- 4h/1h/15m causal alignment；
- ATR/impulse/pullback/restart 单元测试。

### Phase 2：最小机制

- 先跑 B0/B1，回答“等待回调是否改善入场位置、胜率和 MAE”；
- 如果 B1 连 gross 或基本路径证据都失败，停止增加复杂度并报告。

### Phase 3：分层与退出

- B2/B3；
- 独立 layer stop、retry、probe trail、half-MFE；
- 逐模块消融和成本归因。

### Phase 4：ATR admission

- 只有 price-only 完整机制有基础证据时，运行 B4/C0；
- ATR 只允许证明增量价值，不允许救援已失败的订单状态机。

### Phase 5：稳健性与组合

- walk-forward、近期切片、邻域稳定性、压力成本、方向/年份/状态归因；
- 单资产资格判断；
- 只对合格资产装配组合。

### Phase 6：最终决定

合法结果：

- `explore / historical research-pass / prospective OOS required / not promoted / not live-ready`；
- `explore / insufficient evidence / not promoted / not live-ready`；
- `explore / historical gates failed / not promoted / not live-ready`；
- 数据或实现阻塞时保持 `explore` 并列出 blocker。

未经历 runner dry-run/live，不使用 `NO-GO` 作为当前主状态。

### 停止规则

- 主 price-only 机制在 gross、base、rolling 中同时失败：停止添加 ATR/OI/volume 过滤器；
- base 仅靠一个资产或 top 3 winners 为正：不得称为跨资产通过；
- 硬风险、时序、账本、data quality 任一 blocker：绩效无效；
- 揭示 OOS 后不得救参数；
- 没有达到门禁时不接 runner。

## 10. 必须交付的文件和产物

至少包括：

1. 新家族 `README.md`；
2. core ledger 与 decision log；
3. 冻结 strategy contract；
4. 数据质量报告；
5. 共享 causal feature/state-machine kernel；
6. 真实 lot/quantity 回测脚本；
7. 单元、时序、风险、账本和 parity tests；
8. 四资产 gross/base/stress metrics；
9. recent `1d/7d/1m/3m/6m/1y`；
10. walk-forward/rolling/neighbor stability；
11. admission、pullback、restart、layers、retry、trail、half-MFE 消融；
12. campaign/layer/action/equity 机器账本；
13. long/short、年份、regime、exit、right-tail 归因；
14. 交互式 HTML campaign explorer：可查看 4h 候选、1h 回调、15m restart、每层 entry/stop/retry/exit 和账户权益；
15. 完整中文诊断报告；
16. promotion review 或明确 not-promoted 决策；
17. 若历史门禁通过：prospective OOS lock + hash + outcome-blind 观察器；
18. 只有 prospective 通过后：runner live spec 和能力差距/对拍计划。

## 11. 最终回答必须回答的问题

1. 等待回调是否真的降低 MAE、改善成交位置和 campaign 胜率？
2. 15m restart 是否提供增量，还是只增加延迟和成本？
3. ATR expansion 是否有独立增量，还是与价格冲量重复？
4. 独立 layer stop 是否提高收益/回撤，还是造成过度止损和重试？
5. 每层一次 retry 是否有正期望，成本后是否仍成立？
6. probe 慢速结构 trail 是否保留右尾，同时减少 V2 的大幅回吐？
7. add 是否提高 risk-adjusted return，而不只是提高名义风险？
8. 胜率提升是否来自更好的 entry，还是来自 trade 统计口径？
9. ETH/HYPE/BTC/SOL 哪些资产真正合格，哪些应明确排除？
10. 策略是否达到统一1%风险下的收益、回撤、胜率和正偏门禁？
11. 2%/3%机械 scaling 后是否仍符合用户可接受回撤，而没有风险漂移？
12. 当前结论属于 historical research-pass、insufficient evidence 还是 historical gates failed？
13. 距离 live spec、dry-run 和 live 分别还缺什么证据与 runner 能力？

## 12. 明确禁止

- 不追 4h impulse 立即进场；
- 不在达到 +0.5R/+1R/+2R 的极值处立即加仓；
- 不使用亏损加仓或摊低成本；
- 不把所有资产强制为同参数；
- 不在最终 OOS 后删掉 short、某年份或失败资产；
- 不用提高风险/杠杆救 Sharpe 或 CAGR；
- 不把 gross、浮盈、未成交 target 当净收益；
- 不忽略 add/retry/risk-trim 的换手和费用；
- 不用 ATR 单独判断方向；
- 不用大量指标堆叠替代清晰状态机；
- 不覆盖 V35TB、PIC V2 或现有 runner；
- 不因为用户希望高收益就承诺一定找到可上线策略。

## 13. 用户审阅点

启动 Goal 前，用户只需确认以下内容：

1. 新独立家族身份和四资产分开研究；
2. 15m restart 主规则：两根不创新低/高 + 突破此前 4 根 + close 位于 bar 顺势半区；
3. ATR 主周期 `1h ATR(24)`、structure stop buffer `0.25×ATR`；
4. 单资产硬门禁：CAGR 8%、Sharpe 0.8、MDD 15%、PF 1.3、胜率 35%；
5. prospective 至少 180 天且 30 个 closed campaigns；
6. Goal 的终点可能是可信的 not-promoted，而不是强制部署。

用户确认本审阅稿后，才调用 Goal 创建工具；目标任务执行中不得静默改变本 Spec。
