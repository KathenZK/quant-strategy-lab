# HYPE 1D MA7 对称裸 Cross + Slope 诊断合同

> 冻结日期：2026-08-20。状态：`independent diagnostic branch / explore / not promoted / not live-ready`。本合同不修改 HYPE-1D-MA7-ABT V1–V7.1，也不登记新版本。

## 1. 研究问题

回答用户提出的“初始裸策略”在无 V7.1 后续机制时表现如何：前一完整日收盘在 SMA7 反侧，当日收盘穿到 SMA7 目标侧，同时 SMA7 有一定同向斜率，于下一 UTC open 入场；空单完全镜像。

本分支不同于既有 `original-trend-state-machine`：后者 fresh cross 入场不要求 slope，却在持仓中用单日 slope 消失平仓，并带 armed/ATR-band 状态。本轮只测试对称 cross + entry slope，不继承该持仓状态机。

## 2. 唯一主规则 `SNC02`

- `SMA7[t] = mean(close[t-6:t])`。
- `ATR7` 为七日简单 true-range 均值。
- slope threshold 固定继承 V1 的共同门槛 `0.02×ATR7`，但多空均使用 `lookback=1`：
  - long slope：`(SMA7[t]-SMA7[t-1])/ATR7[t] >= 0.02`；
  - short slope：`(SMA7[t-1]-SMA7[t])/ATR7[t] >= 0.02`。
- Long signal：`close[t-1] < SMA7[t-1]` 且 `close[t] > SMA7[t]` 且 long slope 通过。
- Short signal：`close[t-1] > SMA7[t-1]` 且 `close[t] < SMA7[t]` 且 short slope 通过。
- 等号不构成 cross；多空严格镜像；不搜索 threshold 或 lookback。

## 3. 持仓与退出

- flat 遇到合格信号：下一 UTC open 建立对应方向约 `1x` 仓位。
- 已持同向仓位：忽略新的同向信号，不加仓。
- 已持反向仓位：只有出现镜像的反向合格信号时，下一 UTC open 先平旧仓、再按同一 open 建新仓，各计一次 fill。
- 未出现镜像合格信号时持续持有；原方向 slope 后续消失不单独平仓。
- 数据 terminal open 只平已有仓位，不因最后一个信号新开仓。

## 4. 明确删除的模块

不使用 entry buffer、exit buffer、reclaim pending、armed、ATR hysteresis、hard/trailing stop、OAPP、short RSI、PEHC、forced reversal、max-hold、cooldown、仓位缩放或部分止盈。该定义故意暴露裸趋势风险，不能直接用于 live。

## 5. 数据、执行与成本

- Binance USD-M `HYPEUSDT` perpetual；accepted closed `1h` 聚合 UTC `1d`。
- 单仓、非加仓、约 `1x`；持仓期间数量固定。
- 收盘信号下一 UTC open 执行；额外延迟压力再晚 `1d`，等待期间冻结原 target。
- 手续费 `0.001/fill`，基准不利滑点 `4bps/fill`，压力 `8bps/fill`。
- funding 按真实 event timestamp/rate 和 event-hour open 结算。
- 真实 `1h` open 顺序重放 MDD；无 stop 不代表只看日线 MDD。

## 6. 必做输出

- 冻结窗 `2025-05-31 → 2026-08-06` 与扩展至 `2026-08-20` 的净收益、真实1h MDD、PF、胜率、交易数、多空贡献、成本、funding、暴露率。
- `8bps`、额外1日lag、funding-off。
- 最近 `1d/7d/1m/3m/6m/1y` flat-start。
- 2025 与 2026 YTD 子段。
- 逐笔交易和信号，特别报告是否在 `2026-08-09` 建立目标 long、截至 terminal 是否仍持有。
- 与 V7.1 只作同窗事实比较，不把已揭示结果用于回填参数。

## 7. 裁决

- 若 MDD 超过 `20%`，明确写风险门失败；即使抓住最新趋势也不得登记或替换 V7.1。
- 若收益为正但主要来自少数持仓，需报告集中度。
- 本轮只给出裸规则事实与机制归因；不搜索新 slope、stop、exit 或 filter。
