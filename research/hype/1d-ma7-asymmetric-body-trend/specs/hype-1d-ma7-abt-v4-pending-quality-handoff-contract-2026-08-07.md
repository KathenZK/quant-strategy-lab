# HYPE V4 Pending Quality / Handoff 第二轮局部修复合同

> 冻结时间：2026-08-07（第一轮有限pending结果揭示后、第二轮首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 第一轮已知问题

`SHORT_PENDING_1D`补上2025-06-19 short并赚`+7.23%`，但还新增4次延迟short，其中3次明显过度偏离MA7；新增short也可能在V4 opposite fresh reclaim当天退出，却因退出后cooldown/同open禁入而错过原V4仓位。

第二轮只分别检验两个局部问题，不改变V4其他规则。

## 固定修复A：pending anti-chase

只对“等待1日后才确认”的short增加上限：

`0.25×ATR7 < (MA7-close)/ATR7 <= 0.75×ATR7`

- 下限仍是V4原short `entry_buffer_atr`；
- 上限`0.75`复用V4 short迟滞尺度，不搜索新网格；
- fresh reclaim当日slope已通过的原V4入场不受上限影响；
- 超过上限的pending确认作废，不继续等待。

## 固定修复B：delayed-position opposite handoff

只在当前仓位本身由“延迟pending确认”建立时：

1. 该仓位按V4原`ma7_hysteresis_exit`、`ma7_slope_exit`或`max_hold`于次日open退出；
2. 同一决策日若相反方向的**原V4 fresh reclaim + 原slope + 原entry buffer**也通过；
3. 则在同一open完成平仓并建立相反仓位；
4. handoff不使用pending、不使用持续regime、不绕过原V4入场条件；
5. protective stop不允许handoff，仍转flat并执行原cooldown；
6. 非pending建立的V4仓位不改变退出后行为。

## 变体顺序

1. `V4_CONTROL`
2. `SP1_CONTROL`：第一轮short pending 1日
3. `SP1_CAP_075`：只加anti-chase
4. `SP1_HANDOFF`：只加delayed-position handoff
5. `SP1_CAP_075_HANDOFF`：前两项都通过后再看组合

## 输出与裁决

- 与第一轮相同的数据、`1x`仓位、成本、funding、分期、压力、延迟、近期、滚动、24相位和最新延伸；
- 单独核对2025-06 short、2025-06-28 long是否都保留；
- 逐笔列出anti-chase拒绝和handoff；
- 沿用第一轮稳健性底线：MDD相对V4不恶化超过5个百分点；延迟、`12h`、相位中位为正；有效相位至少`18/23`为正；
- 组合即使通过也只是post-reveal候选，不自动登记V5。
