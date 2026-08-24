# HYPE-1D-MA7-ABT-V7.1 Parameter Cleanup 诊断合同

> 冻结时间：2026-08-11（首次运行前）。状态：`registered / not promoted / not live-ready`，目标为参数面精简，不是收益优化。

## 研究问题

在已登记 V7 上重新运行全参数消融，识别当前机制下无效或 dormant 的配置字段，并把功能等价的精简规格登记为 `V7.1`。

## V7.1 定义边界

- V7.1 必须与 V7 交易路径一致：同窗收益、真实 `1h` MDD、交易数、entry/exit 时间和方向不变。
- 只移除当前机制不会读取或明确关闭的 schema/dormant 字段。
- 不移除保护性风险参数，只因样本中未触发不等于没用。
- 不改变 OAPP/PEHC 行为，不改变 short cooldown，不改变成本、执行时序、资金费率、仓位和杠杆。
- 不生成 HTML，不创建 live spec，不推进 runner。

## 必测内容

复用 V6 全参数消融框架，但基线替换为 V7：

- exact V7 control；
- V7 全 active/dormant 参数 OAT；
- OAPP/PEHC 邻域；
- `8 bps`、funding-off、额外 `1d` signal lag；
- 8个54日 cold-flat block；
- 最近 `1d/7d/1m/3m/6m/1y` 切片。

## 可移除判定

字段必须满足以下之一才可从 V7.1 精简规格移除：

1. 当前 `entry_mode="reclaim"` 下不被读取，例如 pullback/breakout 专用字段；
2. 当前子模块明确 `mode/kind="off"`，其内部参数不参与决策；
3. 空列表或默认无约束字段只作为兼容 schema 占位，不定义版本行为。

以下不算可移除：

- 风险保护参数，即使历史未触发；
- max hold、cooldown、entry buffer、slope gate、exit buffer 等会改变未来行为的参数；
- PEHC/OAPP 总开关和实际启用的阈值。

## 裁决

- 若精简规格与 exact V7 路径完全一致，则登记 `V7.1` 为 `registered / not promoted / not live-ready`。
- 若任何路径或指标改变，不登记 V7.1，只记录失败诊断。
