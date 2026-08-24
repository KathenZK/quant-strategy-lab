# CTLS-R5持续期解码失败复盘

R5 `4,464/4,464`完成、`4,033`条独立方向路径、0项通过全部门；未运行阶段、PnL、LES或杠杆。

两个互斥前沿说明duration参数已穷尽：

- `R5D16_2_3_1`：balanced accuracy `0.5679`，三类recall `0.4189/0.7545/0.5303`，5/5折过0.50，但flip `0.1807`失败。
- `R5D14_2_1_5`：balanced accuracy `0.5702`，recall `0.5135/0.6818/0.5152`，flip `0.1084`全部达标，但仅3/5折过0.50；第一/第四折只有`0.383/0.318`。

因此不能再扩大确认/持续期。最后一个后继R6只扩大当日因果信息集：HYPE 24根1h路径、volume、funding以及同窗BTC 1h市场状态；标签、模型族、decoder和门槛不变。R6失败即停止本目标的状态准确率/PnL路线。

证据：[R5 direction](../artifacts/hype_1d_ma7_ctls_r5_2026-08-10_direction.json)。

