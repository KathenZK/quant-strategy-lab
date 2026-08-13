# Binance 1D MA7 BTC/ETH 共享参数演进 P2 冻结合同

## 1. 研究身份与目标

- Family：`Binance-1D-MA7-Asset-Specific-Search`
- Campaign：`P2 shared-parameter evolution`；它是寻找下一登记版本的研究活动，不是 `V2` 登记。
- Baseline：已登记但未晋升的 `BIN-1D-MA7-AS-SEARCH-V1`，固定 `SMA7/ATR7`、约 `1x`、单仓、非加仓。
- 研究目标：学习 `HYPE-1D-MA7-ABT` 从 V1 到 V7.1 的方法级演进，寻找一组 BTC/ETH 共用、可执行且稳健的参数/状态机，使 BTC 与 ETH 各自的累计成本后权益倍数都达到 `>=20x`，同时各自全路径最大回撤都不超过 `20%`。
- 组合报告：另报 BTC/ETH 每日等权组合；组合达标不能替代任一单资产硬门槛。
- 当前状态：`explore / not promoted / not live-ready`。即使历史门槛命中，也不得自动登记 V2 或推进 runner。

这里的“20倍”固定解释为 `terminal_equity / initial_equity >= 20.0`，不是 `+20%`，也不是通过年化外推得到的倍数。

## 2. 不可迁移内容与可迁移方法

### 2.1 禁止直接迁移

- 不直接复制 HYPE V7.1 的 long/short 参数、OAPP、PEHC、RSI 阈值、cooldown 或其收益结论。
- 不把 HYPE 的 post-reveal 候选、Top15/Top30 迁移失败样本或杠杆诊断当作 BTC/ETH 的 OOS。
- 不使用杠杆、波动率缩放或资金分配缩放来把未达标的 alpha “救”到 20x；发现策略在 `1x` 不成立时应报告失败原因。

### 2.2 允许迁移的方法

1. 先冻结/复现 baseline，再改变机制；
2. 多空分离归因，区分 entry、hold、exit、protection 与 post-exit handoff；
3. 全 active-parameter OAT 消融，先删除 dormant/path-equal 字段，再做邻域搜索；
4. 只在 development 内排名，使用滚动 OOS/CPCV、分块、成本和延迟共同筛选；
5. 所有改动用 closed-bar 信号、next-open 执行，并用真实 `1h` 路径处理 stop；
6. 先证明无杠杆 edge，再单独研究风险缩放；风险缩放不得改写基础策略达标结论。

## 3. 冻结数据快照

本轮历史研究只使用已经完成质量审计的 `BIN-1D-MA7-RSI6-DAPML P0` 价格/funding 快照：

- BTC 直接 `1h`：`2019-09-08 18:00 UTC` 至 `2026-08-10 08:00 UTC`；
- ETH 直接 `1h`：`2019-11-27 08:00 UTC` 至 `2026-08-10 08:00 UTC`；
- 两资产实际 funding + mark 可共同解析起点：`2019-12-23 16:00 UTC`；
- 共同主评估起点：`2019-12-24 00:00 UTC`；
- 主相位最后完整 UTC 日：`2026-08-09`，terminal open：`2026-08-10 00:00 UTC`；
- 原始来源：Binance USD-M `/fapi/v1/klines`、`/fapi/v1/fundingRate`、`/fapi/v1/markPriceKlines`；
- 快照质量要求：manifest 总 blocker、BTC blocker、ETH blocker 均必须为 `0`，且脚本复核冻结 frame hash。

数据证据：

- [P0 数据质量审计](../../1d-ma7-rsi6-direction-aligned-pooled-ml/diagnostics/binance-1d-ma7-rsi6-dapml-p0-data-capacity-2026-08-10.md)
- [P0 质量 manifest](../../1d-ma7-rsi6-direction-aligned-pooled-ml/artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json)

## 4. 时间治理

### 4.1 历史发现区

- Development：共同主评估起点至 `2025-08-07 00:00 UTC` exclusive。
- Researcher-exposed audit：`2025-08-07 00:00 UTC` 至冻结 terminal；该段价格及同资产历史已被其他研究接触，只能作诊断，不能宣称 clean OOS。
- 所有参数生成、机制选择、消融排序、组合选择和停止/继续决定只能读取 development 的绩效结果。
- researcher-exposed audit 只能在候选和选择规则冻结后一次性运行；失败后不得回到同一候选池救参。

### 4.2 新 prospective 区

- 冻结时点：`2026-08-12`（Asia/Shanghai）。
- 首个允许进入 clean observer 的决策收盘：`2026-08-13 00:00 UTC`；其对应订单最早在下一可执行 open 成交。
- 观察前不得因市场后续走势修改候选、阈值、排序或 hard gate。
- prospective 最低判定样本：至少 `180` 个自然日且 BTC、ETH 各至少 `8` 笔独立平仓；两者取更晚者。低频导致样本不足时延长，不用零交易窗口机械通过。

## 5. 成交、成本与仓位

- 信号：只使用闭合 UTC 日 K；禁止用当日未闭合 high/low/close。
- 执行：日线信号下一日 open；额外延迟审计为再延迟一日。
- Stop：使用真实直接 `1h` 路径；gap 穿越先按小时 open，否则按保护价并计不利滑点。
- 基准成本：手续费 `0.001/fill` + 不利滑点 `4 bps/fill`；压力滑点 `8 bps/fill`。
- Funding：按实际事件时间、实际费率和持仓方向计入。
- 仓位：成交后目标约 `1x`，数量持有期固定；单仓、非加仓；记录持仓中实际杠杆漂移和 intraday bankruptcy。

## 6. P2 实验顺序

### P2-A：V1 长历史零调参复算

- 逐位复核 V1 long/short 参数；
- 报告 development、researcher-exposed audit、full-history；
- 报告 combined、long-only、short-only、BTC/ETH 等权组合、buy-and-hold；
- 报告 base、`8 bps`、`+1d` delay、最近切片、滚动窗口和逐笔路径；
- 如果 V1 在长历史出现数据、时序或路径不一致，先修复复现，不进入搜索。

### P2-B：V1 active-parameter 全消融

- 只对实际接线且能改变成交路径的字段做 OAT；
- 先运行 `off/remove`，再运行相邻离散值；
- path-equal 字段标记 dormant，下一候选规格删除；
- 每项记录 BTC、ETH 的交易签名变化、收益、MDD、交易数和退出原因变化。

### P2-C：方法级机制臂

按独立臂逐步测试，禁止一次把 HYPE V7.1 整体移植：

1. `entry lifecycle`：regime/reclaim/pullback、pending maturity、斜率与 ATR 距离；
2. `exit lifecycle`：MA7 hysteresis、slope、timeout、hard/trailing protection；
3. `profit protection`：只在已有浮盈后工作的 giveback/RSI/ATR 保护；
4. `handoff continuity`：利润退出后保留无仓位 shadow 状态，只有冻结的反向确认才允许 handoff；
5. `cooldown/re-entry`：区分止损冷却、利润退出冷却和同方向重新入场。

每个机制先单项消融，单项未显示跨资产可解释贡献时不得进入组合广搜。

### P2-D：共享参数搜索与验证

- 目标函数首先最大化 BTC/ETH 两侧的最差值，不优化平均收益掩盖弱侧；
- `MDD >20%` 的候选在排名前 hard reject；
- 使用 expanding/rolling walk-forward 或 CPCV；每窗报告收益、MDD、交易数和零交易状态；
- 只有 development 内通过的唯一候选才可打开 researcher-exposed audit；
- 历史命中后仍只称 frozen prospective candidate，不登记、不 promotion。

## 7. 硬门槛与停止规则

历史研究的最低候选门槛：

1. BTC base 成本后权益倍数 `>=20.0` 且 MDD `>=-20%`；
2. ETH base 成本后权益倍数 `>=20.0` 且 MDD `>=-20%`；
3. 两资产均无 intraday bankruptcy、无 lookahead、无无效保护单；
4. `8 bps` 与 `+1d` delay 下两资产仍为正，且不得靠单笔异常交易贡献大部分终值；
5. 结构化 OOS/CPCV 不能接近抛硬币，主要 regime 不得系统性崩塌；
6. 相对各自 buy-and-hold 有可解释超额收益；
7. active component 消融、交易 bootstrap 和参数邻域必须支持非针尖结论。

任一硬门槛失败：保持 `explore / not promoted / not live-ready`，记录 causal attribution；不得用已揭示 audit/prospective 结果二次调参。若同一 MA7-root substrate 经穷尽消融和预注册机制臂仍失败，应停止该 substrate，另立 materially new family 并使用新的 prospective 合同。

## 8. 固定交付物

- P2-A 长历史零调参诊断、JSON、metrics/trades/path CSV；
- P2-B 全 active-parameter 消融报告与机器证据；
- P2-C 每个机制臂的冻结合同、诊断和失败归因；
- P2-D 候选与 walk-forward/CPCV、bootstrap、邻域、成本/延迟证据；
- 初步成形或逐笔行为重大变化时，生成 BTC 和 ETH 完整交易路径 HTML，每笔 entry 与对应 exit 连线；
- 只有用户明确要求“登记 V2”时，才更新 core ledger、decision log 与路由状态。

