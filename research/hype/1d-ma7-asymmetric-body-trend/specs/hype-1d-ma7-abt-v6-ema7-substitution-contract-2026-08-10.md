# HYPE-1D-MA7-ABT-V6 EMA7 替换诊断合同

> 冻结时间：2026-08-10（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

回答一个且仅一个问题：登记的 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`
（`PEHC_294`）保持全部参数、OAPP、PEHC、退出、成本与执行顺序不变，只把所有读取
`MA7` 的位置改为 `EMA7`，已暴露历史表现会怎样。

本轮不搜索 EMA span，不重新调阈值，不修改 V6 的默认 SMA7 身份，不登记 V7，不用于
promotion 或 runner handoff，不生成交易路径 HTML。

## 唯一变量

- Control：exact V6 `PEHC_294`，使用原 `SMA7`。
- Candidate：exact V6 `PEHC_294`，将 `features.ma7` 整体替换为 `EMA7`。
- EMA 定义：`EMA(span=7, adjust=False, min_periods=7)`。
- `ATR7`、`RSI6`、entry quality、OAPP long MFE保护、short RSI6止盈、
  PEHC shadow/handoff、cooldown、max hold、保护止损、手续费、滑点、funding、
  signal lag、单仓约束全部不变。

## 必须输出

1. exact V6 SMA7 与 EMA7 替换版的全窗收益、真实顺序 `1h` MDD、日内极值 MDD、
   PF、胜率、交易数、多空笔数、成本、funding、最大 marked leverage；
2. `8 bps`、funding-off、额外一日 signal lag；
3. 最近 `1d/7d/1m/3m/6m/1y`、8个54日 cold-flat block、90日窗口每30日滚动；
4. `0h–23h` 日界相位；
5. 逐笔行为、handoff事件是否改变，以及核心链条事件变化。

## 裁决纪律

EMA7 只有在全窗收益更高、真实 `1h` MDD 更低、压力和分块不双劣、且没有削弱 V6
核心链条时，才允许成为后续前瞻观察假设。否则裁决为 `FAIL / diagnostic-only`。
