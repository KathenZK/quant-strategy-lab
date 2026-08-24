# HYPE-1D-MA7-SNC02 MA05 单笔ATR风险预算 Stage E 冻结合同

> 冻结日期：2026-08-20。状态：`CANCELLED_BEFORE_RUN / no artifact / no result`。本合同原在首次运行 Stage E 结果前写入；用户随后明确把“完整发现并跟踪趋势”设为第一目标，故在任何Stage E结果揭示前终止，不得运行或引用为绩效证据。

## 0. 终止记录

Stage E 未生成脚本、机器证据或回测结果。终止原因不是风险预算机制已失败，而是研究顺序被纠正：趋势发现、持有连续性和趋势捕获率必须先于仓位与回撤优化。若未来恢复风险预算研究，必须等趋势路径冻结后另立新合同，不得直接复用本合同的网格。

## 1. 研究问题与边界

Stage B 的固定0.5x虽满足MDD20却损失过多趋势收益，确认扩仓失败；Stage C固定价格stop无法切断连续亏损；Stage D权益回撤节流会长期困在低风险状态。Stage E 测试更局部的风险归一化：只在每笔fresh入场时根据当时ATR占价格比例确定整笔固定杠杆，使高波动信号少承担、低波动趋势仍可达到1x。

所有臂固定 exact SNC02、`MA05=0.5ATR7`结构退出、相同信号/退出路径；不设硬stop、不日内调仓、不确认加仓、不按权益高水位节流。全部历史已揭示，只作机制诊断；不登记版本、不promotion、不修改V7.1或runner。

## 2. 固定实验臂与公式

| Arm | 单笔ATR风险预算 `B` |
|---|---:|
| `MA05_CTRL` | 固定1.00x |
| `VT04` | 4%权益/1ATR |
| `VT05` | 5%权益/1ATR |
| `VT06` | 6%权益/1ATR |

对每笔交易：

```text
atr_fraction = entry_ATR7 / entry_price
entry_leverage = min(1.0, B / atr_fraction)
```

- `entry_ATR7` 取生成该fresh SNC02入场信号当日的已闭合ATR7；`entry_price`为实际下一UTC open（lag压力下为实际延迟open）。
- 不设杠杆下限；若波动极高，仓位可以自然低于0.25x。
- 入场后quantity固定至MA05/镜像信号退出，不因ATR、价格、浮盈或权益变化rebalance。
- 上限固定1x，不使用风险预算加杠杆。三档为首次结果前冻结的有限网格，不补搜4.5%、5.5%或其他预算。

## 3. 可执行成交与路径

- 入场/反手仍按已闭合UTC日信号，于下一UTC open成交；MA05仍于条件日下一UTC open全平。
- 每笔入场按当时权益、价格、冻结leverage和执行成本求目标quantity；退出按实际quantity全平。
- 手续费、滑点、funding均按实际quantity计入；不同仓位不得用线性缩放收益替代真实复利回放。
- 仓位机制不改变信号/退出日期；control必须与Stage A MA05在扩展和canonical的收益、MDD、交易数、成本、funding精确一致。

## 4. 数据、成本与窗口

- 市场：Binance USDⓈ-M perpetual `HYPEUSDT`；信号 `1d`，风险回放 `1h`，UTC。
- 主窗：扩展 `2025-05-31 -> 2026-08-20 terminal`；同时报告canonical `2025-05-31 -> 2026-08-06`。
- 成本：手续费 `0.001/fill`，基础滑点 `4bps/fill`，实际funding；压力为 `8bps`、funding-off、额外 `1d lag`。
- 最近flat-start：`1d/7d/1m/3m/6m/1y`；年度flat-start：2025 partial、2026 YTD。
- 风险：按小时open与funding pre/post计算chronological `1h` MDD。

## 5. 首次运行前冻结的判定

以 `MA05_CTRL` 与其2026-08-09 long为参照：

- `MDD20_PASS`：扩展窗真实1h MDD `>= -20%`。
- `ROBUSTNESS_PASS`：扩展窗净收益 `>0`、PF `>=1`、8bps净收益 `>0`、额外1日lag净收益 `>0`。
- `RETURN_RETENTION_PASS`：扩展窗净收益至少为control的 `50%`。
- `LATEST_TREND_CAPTURE_PASS`：存在2026-08-09 long、截至terminal仍持有，且campaign净收益至少为control同笔的 `60%`。
- `CONTINUATION_CANDIDATE`：同时满足上述四项。

另报告杠杆分布、低于1x交易数、年度/近期flat-start。若多个预算通过，优先风险预算更低且仍过全部保留门者；通过仍只是post-reveal风险候选，不代表新增alpha、版本或上线资格。

## 6. 产物

- 研究脚本：`scripts/research_hype_1d_ma7_snc02_ma05_atr_risk_budget_stage_e.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_ma05_atr_risk_budget_stage_e_2026-08-20.json`
- 诊断报告：`diagnostics/hype-1d-ma7-snc02-ma05-atr-risk-budget-stage-e-2026-08-20.md`
