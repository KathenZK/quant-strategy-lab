# BIN-MTF-PTC Goal Research Contract（2026-08-03）

## 1. Objective 与不可偷换口径

在 BTC/ETH/HYPE 上研究一个真正可实盘执行的趋势 Campaign Engine：因果识别潜在趋势，持续度量趋势延续与失效，等待回调后的有利位置试仓，只有行情继续证明假设时才分层增加风险，并通过结构止损、风险维护和慢速退出尽可能获取完整 3–14d 趋势。

收益目标：完整成本后 annual equity multiple 尽量 `>=20×`，即一年净值达到至少 20 倍（约 `+1900%`），不是年化 20%。最大回撤硬约束 `<=20%`。

20×是极高目标，不是修改事实的授权：

- 不允许未来信息、不可执行 fill、忽略成本或浮盈冒充实赚；
- 不允许提高杠杆替代 alpha；
- 不允许根据锁定 OOS 或 prospective 失败救参；
- 不允许把达不到目标改写成“接近成功”；
- 若目标不可实现，必须给出最佳可信 Pareto frontier 和机制瓶颈。

## 2. 资产、周期和参数原则

- 初期资产：BTCUSDT、ETHUSDT、HYPEUSDT perpetual。
- 三资产分别研究、分别选择周期、分别冻结参数和资格；不要求同参数移植。
- Anchor 架构：4h candidate、1h pullback、15m restart/execute。
- 允许预声明比较：`1d/4h/1h`、`4h/1h/15m`、`1h/15m/5m` 等层级，但不能无限扩展；周期选择只能用开发/验证区。
- 传统指标允许使用，但必须被解释为方向、波动、路径、延伸或参与度测量；必须做增量消融和邻域稳定性。

## 3. 趋势识别与延续性是先验主任务

策略回测前先独立验证两个问题：

### 3.1 Onset：是否出现潜在趋势

候选特征可包括：

- 多期限 signed normalized displacement；
- ATR/realized-vol expansion；
- 路径效率、回归 slope/R²；
- higher-high/lower-low 结构；
- ADX、RSI/KDJ 位置或其他传统指标；
- volume/OI/funding（只有数据质量和增量证据允许时）。

ATR 不能单独决定方向；方向必须来自价格或明确的方向结构。

### 3.2 Survival：趋势未来是否仍可能延续

在每个 closed decision bar 计算 causal continuation state，目标不是“下一根涨跌”，而是未来路径事件：

```text
continue_event(H) = 顺趋势先达到 +aR，再触及 -bR / 结构失效
failure_event(H)  = 先触及 -bR / 结构失效
```

至少覆盖与 campaign 相符的多个 horizon，例如 6h/24h/3d/7d；具体组合在首次标签审计前冻结。

Continuation meter 候选：

- 透明 rule-based score；
- 正则化 logistic/discrete-hazard survival；
- 只有前两者证明特征/标签有效后，才允许浅层 tree model 对照。

Meter 必须在 walk-forward 中证明：

- score 分组后的 continuation rate 基本单调；
- top-bottom spread 稳定为正；
- calibration/Brier 或相应概率质量优于无信息基线；
- AUC/排序能力不是单一年份、单方向或单资产造成；
- 特征只使用当时可见历史，未来路径只存在 label y；
- 不完整 horizon 样本不得混入已知标签。

若 meter 无稳定增量，禁止把公式包装成趋势延续判断并直接驱动仓位。

## 4. Anchor 可执行状态机

### 4.1 Candidate → Await Pullback

- 4h 或所选高周期 closed bar 形成趋势候选；
- candidate 只授权观察，不立即入场；
- 最多等待 24h，无合格回调即取消；
- 方向结构失效立即取消。

### 4.2 合格 1h 回调

Anchor 主规则：

- 最浅 `0.5 × ATR1h(24)`；
- 最深不超过当前 impulse leg 的 50%；
- 1h close 穿过 impulse origin：失效；
- 主值不做大范围搜索，只做预声明邻域稳定性。

### 4.3 15m Restart

Anchor 主规则：

- 最近两根 closed 15m 不再创回调新低/新高；
- closed 15m 突破此前 4 根顺势极值；
- close 位于 bar 顺势半区；
- 下一根 15m open adverse fill。

其他周期组合必须保持 closed-bar → next-open 语义。

### 4.4 Risk Layers

- Probe：请求 0.25% equity risk；
- Add-1：campaign 达 +0.5R 后获得资格；
- Add-2：达 +1R 后获得资格；
- Add-3：达 +2R 后获得资格；
- 获得资格不等于立即成交，仍须新的结构回调 + restart；
- 每层请求 0.25% risk，按各自结构 stop 和完整成本换算 quantity；
- 每个 add 等级最多一次重试；第二次失败永久关闭；
- 总 operational stop-out risk `<=0.9%`，hard risk `<=1%`，有效杠杆 `<=3x`；
- 亏损中禁止 add，风险不足只允许 partial add。

### 4.5 Stops 与退出

- 每层 stop 在对应 1h pullback extreme 外 `0.25×ATR1h(24)`；
- Probe 达 +2R 前 stop 不移动；
- +2R 后只在新 1h higher-low/lower-high 被 causal restart 确认后收紧；
- stop 永不放宽；
- +2R 后 1h close 回吐 peak MFE 的 50%：下一执行 open 卸掉新增 layers，probe 由结构 stop 管理；
- 入场 24h 未达到 +1R：全退；
- 最大持有 336h：全退；
- 无固定 take-profit；
- funding 后持续重算 stop-out risk，超 0.9% 先 LIFO 减新增层，hard risk 任意超 1% 为 blocker。

## 5. 周期、指标和参数优化治理

### 5.1 数据分区

本轮开始先对每资产冻结：

- development；
- validation；
- locked evaluation；
- purge/embargo；
- 当前全历史已揭示说明；
- final prospective start。

Development 可拟合/搜索；validation 可选择机制和参数；locked evaluation 只揭示一次且不可救参。由于历史价格与部分结果已揭示，locked evaluation 仍需标为 historical locked evaluation，不冒充 fresh OOS。

### 5.2 搜索阶段

1. 标签与 meter validity；
2. 时间层级；
3. onset feature family；
4. pullback/restart；
5. layer/stop/exit；
6. 资产专属小范围参数；
7. 风险机械 scaling。

每阶段预先记录候选数、选择指标和停止条件。不得在一次全空间搜索中同时优化所有模块。

### 5.3 选择目标

Validation 主目标必须是约束优化：

```text
maximize net log-growth / CAGR
subject to MDD <= 20%, hard-risk=0, executable=true
```

并以 Sharpe、Calmar、PF、win rate、turnover、tail concentration 和稳定性作为共同约束。不能只按最终收益排名。

20×结果必须拆分：

- 无杠杆/1% campaign risk 的机制 alpha；
- 2%/3% mechanical scaling；
- 实际 effective leverage；
- leverage contribution 与 signal contribution。

若只有超出 3x cap 或突破 20% MDD 才达到20×，判定目标未实现。

## 6. 成本和实盘可执行合同

- Binance fee `10bps/fill`；
- base adverse slippage `4bps/fill`；至少一档 8bps stress；
- 实际 funding；
- tick/step/min-notional/precision；
- 每次 add/retry/partial exit/risk trim 独立计费；
- gap stop 按实际 open adverse fill；
- 同一 bar 禁止使用 high 触发资格再用 low 成交；
- 真实 lot ledger、partial resize、保护订单 quantity、pending action、restart recovery、幂等和 kill switch 必须可映射到 runner。

任何无法由当前或明确可扩展 runner 复现的状态机，其绩效无效，不得描述为策略成功。

## 7. 三资产与组合验收

### 7.1 单资产

必须报告：

- gross/base/stress；
- CAGR/annual multiple、MDD、Sharpe、Sortino、Calmar；
- campaign/layer win rate、PF、avg win/loss、PnL-R skew；
- 1d/7d/1m/3m/6m/1y；
- rolling/walk-forward、年度、方向、regime；
- top winners concentration 与 remove-top-N；
- turnover、fees、funding、slippage；
- meter calibration/monotonicity；
- max effective leverage、stop-out risk、gap risk。

20×目标与 MDD 20% 必须在 base net 同时满足。若不能满足，报告距离与 Pareto frontier，不降低标准。

### 7.2 组合

- 只纳入预先通过资产资格门禁的 BTC/ETH/HYPE；
- 不按 locked evaluation 最终收益事后挑币；
- 初始 equal-risk，组合 open-risk cap 预先冻结；
- 检查加密 beta 相关性、同方向拥挤和资产利润集中度；
- 组合20×不能来自单资产超限风险或隐含高杠杆。

## 8. Fresh prospective 与 promotion

- 最终候选冻结 code/spec/data hashes；
- prospective 至少 180 天且 30 个 closed campaigns，除非冻结前基于事件率给出更严格标准；
- 未成熟前 outcome-blind，不反复窥视 PnL；
- 历史通过只可保持 `explore` 或用户明确登记后的 `registered / not promoted / not live-ready`；
- fresh prospective、完整 validation gates 和 live-executable review 通过后才允许 `live spec`；
- runner parity/smoke/recovery 通过后才允许 dry-run；
- dry-run 观察和对账通过后才允许 live。

## 9. 交付与终止条件

必须交付独立家族、合同、core ledger、数据质量、meter validation、真实回测、搜索注册表、逐笔账本、测试、消融、压力、交互式 campaign HTML、runner 差距和明确状态决定。

终止结果可以是：

- 达到或接近20×且满足所有可信度门禁的 historical candidate，锁 prospective；
- 找到低于20×但可信的 Pareto-optimal 趋势策略，明确差距并锁 prospective（是否继续由用户决定）；
- 所有机制失败，保持 `explore / not promoted / not live-ready`；
- 数据或执行 blocker，fail closed。

Goal 不以“写完报告”为完成，而以：实现和证据链完成、所有安全可行路径已验证、且给出不可歧义的下一状态为完成。

