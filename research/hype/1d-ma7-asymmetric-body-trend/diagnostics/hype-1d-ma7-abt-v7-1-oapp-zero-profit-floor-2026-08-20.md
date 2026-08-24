# HYPE-1D-MA7-ABT-V7.1 OAPP 零利润回吐诊断

> 日期：2026-08-20。裁决：`NO-GO ZPF / KEEP V7.1`。状态：`diagnostic-only / not promoted / not live-ready`。未修改 V7.1 或 runner。

## 结论

“只要没回吐到0就一直持有”能解决 2026 年 8 月目标交易的过早退出，但不能作为 V7.1 的通用替代规则。

按[冻结合同](../specs/hype-1d-ma7-abt-v7-1-oapp-zero-profit-floor-diagnostic-contract-2026-08-20.md)，本轮只修改 long OAPP：最高收盘浮盈达到 `0.5×ATR7` 后，只要日线收盘仍高于开仓价就不由 OAPP 退出；首次收回开仓价或以下时，下一 UTC 日 open 全平。native MA7 exit、1h `1.5ATR` protective/trailing stop、short RSI、PEHC、成本和 funding 保持不变。

结果为 `NO-GO`：canonical 收益从 `+711.04%` 降至 `+469.37%`，真实 1h MDD 从 `-18.40%` 扩到 `-25.07%`，胜率从 `85.00%` 降至 `66.67%`。它既不满足收益要求，也突破 `20%` 回撤门。

## 1. 全路径结果

| 规则 | 净收益 | 真实1h MDD | 胜率 | PF | 交易数 | OAPP long exits | PEHC handoff |
|---|---:|---:|---:|---:|---:|---:|---:|
| V7.1 control | +711.04% | -18.40% | 85.00% | 17.51 | 20 | 8 | 5 |
| ZPF：回吐到0才退出 | +469.37% | -25.07% | 66.67% | 8.71 | 21 | 1 | 0 |
| long OAPP off | +547.65% | -25.08% | 70.00% | 10.64 | 20 | 0 | 0 |

ZPF 不完全等价于关闭 OAPP，但整体行为非常接近：OAPP exits 从 `8` 次降至 `1` 次，PEHC handoff 从 `5` 次降至 `0`。它保留的一次零利润退出反而使收益比完全关闭 OAPP 再少 `78.28` 个百分点。

## 2. 为什么“回吐到0”不是保本

历史上 ZPF 唯一一次实际触发发生在 `2026-03-05`：

- 开仓价：`31.204`。
- signal close：`30.535`，在产生信号时已经是 `-2.14%` 毛亏损。
- 下一 UTC open：`30.536`，再加双边手续费、滑点与 funding 后才是实际结果。

日线策略无法保证价格精确触碰开仓价时成交；只能等闭合日线确认，再于下一开盘执行。因此“回吐到0才跑”在实现上是“确认已经跌破0后再跑”，不是 break-even stop。

## 3. 路径破坏

ZPF 改变了至少八笔共享多头。除上述一次 ZPF exit 外，多数持仓在等待归零过程中先被 1h protective stop 退出：

- `2025-06-10` 多头：V7.1 在 `40.520` OAPP锁盈；ZPF 延迟后在 `37.623` protective stop。
- `2025-10-24` 多头：V7.1 在 `43.684` OAPP锁盈；ZPF 延迟后在 `41.728` protective stop。
- `2026-07-03` 多头：V7.1 在 `69.187` OAPP锁盈；ZPF 延迟后在 `66.465` protective stop，已经低于 `66.926` 开仓价。

与此同时，原 OAPP 退出后的 PEHC shadow/short handoff 基本消失，导致后续交易链发生变化。说明 OAPP 在 V7.1 中不只是止盈，还承担了与 PEHC 配合的趋势连续性角色。

## 4. 8月事件反事实

ZPF 会阻止 `2026-08-16 56.894` 的退出，并在数据终点 `2026-08-20 00:00 UTC / 69.787` 仍持有。但这仍是 terminal-censored 的已揭示反事实，没有产生真实 ZPF 退出，不能用来抵消完整历史中的失败。

扩展至 8 月 20 日后，V7.1 为 `+733.50%/-18.40%`，ZPF 为 `+617.87%/-25.07%`；即使计入这一段上涨，ZPF 仍同时输给控制的收益和回撤。

## 5. 压力结果

| 压力 | ZPF收益 | ZPF MDD |
|---|---:|---:|
| 8bps滑点 | +605.81% | -25.25% |
| 额外1日lag | +302.28% | -26.45% |
| funding-off | +627.64% | -25.07% |

所有主要压力口径均违反 `20%` MDD 门，不存在可推进的边界结果。

## 6. 建议

1. 不把“回吐到0才退出”写入 V7.1，也不作为 shadow 主候选；本分支裁决 `NO-GO`。
2. 生产继续 exact V7.1；上一轮 `RR` 仍是更合理的 shadow 语义候选，因为它只修正“反弹日仍累计确认”，没有彻底取消盈利保护。
3. 若要保留更多趋势利润，下一种值得独立预注册的结构不是等到0，而是 OAPP 首次触发时只部分锁盈、剩余仓位交给 RR + MA7/ATR；这属于仓位机制变更，需另行回测。

## 证据

- [机器证据 JSON](../artifacts/hype_1d_ma7_abt_v7_1_oapp_zero_profit_floor_2026-08-20.json)及其[SHA256](../artifacts/hype_1d_ma7_abt_v7_1_oapp_zero_profit_floor_2026-08-20.json.sha256)
- [可执行脚本](../scripts/diagnose_hype_1d_ma7_abt_v7_1_oapp_zero_profit_floor.py)
- [冻结合同](../specs/hype-1d-ma7-abt-v7-1-oapp-zero-profit-floor-diagnostic-contract-2026-08-20.md)
- [上一轮反弹重置诊断](hype-1d-ma7-abt-v7-1-oapp-rebound-reset-2026-08-20.md)
