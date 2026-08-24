# HYPE-1D-MA7-ABT-V6 连续趋势 Overlay 诊断合同

> 冻结时间：2026-08-10（首次运行前）。状态：`diagnostic-only / not promoted / not live-ready`。

## 研究问题

本轮只回答一个问题：能否在不替代 `HYPE-1D-MA7-Asymmetric-Body-Trend-V6`
（`PEHC_294`）的前提下，用一个连续趋势 overlay 补充 V6 漏掉的趋势机会，并且在
完整经济路径上同时提高收益、降低真实 `1h` MDD。

本轮不改写 V6，不登记 V7，不研究杠杆，不生成交互式交易路径 HTML，除非用户另行
明确要求看路径。

## 设计边界

- Control：exact V6 `PEHC_294`，固定 `1x`、单仓、非加仓。
- Overlay 只允许在 V6 baseline 为 flat，或 V6 已退出但 shadow/PEHC 仍处于观察链时
  评估候选；不得覆盖 baseline 正在持有的真实仓位。
- 候选机会来自已知可执行事件族：raw MA7 cross 后延迟成熟、cooldown 释放、buffer /
  slope 晚成熟、RSI6 止盈后再弱，以及 OAPP/PEHC 断链后的同向机会。
- 方向命中不是通过条件。每个候选必须同时评估：
  1. 未来 `3d/5d/10d` 趋势延续或反向风险；
  2. 完整 replay 后相对 V6 的收益和真实 `1h` MDD；
  3. 是否占用单仓并破坏后续 V6 long、OAPP 或 PEHC handoff 链条。

## 本轮冻结候选

本轮不重新细搜阈值，而是复用已完成 DTEC 与转换链研究中最有代表性的四类经济路径：

1. `CTO_L189`：DTEC long-only，连续 `3d` 在 MA7 上方、`2d` MA7 slope / ATR
   `>0.04`、距 MA7 不超过 `1.5ATR`。
2. `CTO_S005`：DTEC short-only，连续 `2d` 在 MA7 下方、`2d` MA7 slope / ATR
   `>0`、距 MA7 不超过 `1.0ATR`。
3. `CTO_L189_S005`：同时启用上述 long 与 short delayed episode。
4. `CTO_C001`：转换链代表候选，directional cooldown `1d`、episode `3d`、
   `BUFFER` 成熟、anti-chase `0.75ATR`、RSI reobserve 关闭。

这些候选覆盖“慢涨补入”“阴跌补入”“多空同时补入”和“cooldown / transition 释放”
四个问题，不允许在结果后继续删除坏事件或调窄阈值。

## 数据、执行与成本

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 数据：accepted、closed-only 的真实 `1h` 数据聚合完整 UTC 日 K。
- 主窗：`2025-05-31` 至 `2026-08-05 UTC`，432 个完整日。
- 执行：只读上一完整日和已闭合 `1h`；信号最早在下一可执行 open 成交。
- 成本：手续费 `0.001/fill`、base 不利滑点 `4 bps/fill`，压力滑点 `8 bps/fill`；
  计真实 Binance funding，并单独报告 funding-off。

## 必须输出

1. exact V6 与四个 overlay 候选的全窗收益、真实 `1h` MDD、日内极值 MDD、PF、
   胜率、交易数、多空分布、成本、funding、最大 marked leverage；
2. 每个候选相对 V6 的收益差、MDD差、交易数差、交易路径是否变化；
3. 方向识别摘要：候选确认次数、`5d` 方向命中、`5d` 同侧持续命中；
4. 机会成本摘要：新增交易、被删除/替换的 V6 交易、V6 long trail / short RSI /
   shadow / handoff 是否被削弱；
5. `8 bps`、funding-off、额外一日 signal lag；
6. `8 × 54d` cold-flat block、最近 `1d/7d/1m/3m/6m/1y` 切片；
7. 最终裁决：只有在全窗、压力、分块、lag 和机会成本全部不双劣，且全窗收益更高、
   真实 `1h` MDD 更小，才允许标记为 `diagnostic passer`。

## 裁决纪律

- 如果方向命中率较高但组合层收益/MDD双劣，必须判失败。
- 如果候选补到了肉眼趋势段但释放更多假信号或破坏 V6 后续高价值路径，必须判失败。
- 若无候选同时提高收益并降低 MDD，本轮停止，不得在同一 432 日继续微调阈值救援。
- 任何正结果也只是已暴露历史诊断，不能 promotion，不能解锁杠杆，也不能替代 V6
  前瞻 observer。
