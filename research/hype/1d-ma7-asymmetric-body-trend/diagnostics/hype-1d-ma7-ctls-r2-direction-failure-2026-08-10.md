# CTLS-R2连续方向强度失败复盘

## 裁决

R2-A1 `1,944/1,944`完成、`1,687`条独立方向路径、`0`异常、`0`项通过方向资格门。R2-A2、PnL、LES与杠杆均未运行。

## 结果

- 最佳三方向balanced accuracy：`0.5260`，低于`0.55`；该路径up/down recall分别`0.7935/0.7766`，但flat recall仅`0.0079`，flip rate `0.2347`。
- 最高flat recall：`0.3730`，仍低于`0.40`；对应up/down recall降到`0.4130/0.2766`，balanced accuracy仅`0.3542`。
- `181/1,944`项可使至少4/6 block的balanced accuracy达到0.50，但没有一项同时满足aggregate方向、三类召回和flip门。
- 所有配置up recall达标，`1,774/1,944`项down recall达标；真正的结构矛盾是“保持趋势方向”与“及时输出flat”的不可兼得。

## 归因

连续强度修复了R1“永不flat”的代码结构，却没有解决可辨识性：同一时点的`z/s3/d3/er7`对未来中心7日标签中的flat与短暂趋势没有足够分离度。提高`enter_q`和确认天数会增加flat输出，但同时大量漏掉真实up/down；降低门槛保住方向又把neutral/chop吞掉。继续扩相同阈值只能沿这条前沿移动，不能同时跨过全部门。

因此R3不再手工叠加同类阈值，而做严格walk-forward的监督可辨识性测试：扩大因果特征，训练时只使用预测时已成熟的`t+3`标签，用模型概率和因果hysteresis输出状态。若监督模型仍不能过门，说明当前日线信息与中心未来标签本身不匹配，应重新定义“识别准确”标签或引入更高频/跨市场信息，而不能继续参数搜索。

## 证据

- [R2 A1](../artifacts/hype_1d_ma7_ctls_r2_2026-08-10_direction_a1.json)
- [R2 manifest](../artifacts/hype_1d_ma7_ctls_r2_2026-08-10_manifest.json)

