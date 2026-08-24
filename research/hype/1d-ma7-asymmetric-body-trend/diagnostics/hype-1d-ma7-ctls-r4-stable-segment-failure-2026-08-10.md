# CTLS-R4稳定趋势段失败复盘

R4方向搜索`1,488/1,488`完成、`1,336`条独立路径、0项通过全部门；未运行阶段、PnL、LES或杠杆。

稳定真值D内方向计数为down/flat/up=`87/152/78`，5个eval折真值合并flip约`0.1084`，因此R4已解决R3“真值逐日跳变”的定义问题。最佳预测LightGBM为balanced accuracy `0.5949`、三类recall `0.5270/0.5909/0.6667`、5/5折过0.50，但预测flip仍为`0.3213`。两日确认的最佳折中为accuracy `0.5602`、recall `0.4595/0.6455/0.5758`、flip `0.1968`；只差flip门。

R5保持R4标签、特征和模型不变，只为预测状态加入因果minimum dwell与switch confirmation。若该单模块不能把flip压到0.15同时保住准确率，则停止状态准确率路线。

证据：[R4 direction](../artifacts/hype_1d_ma7_ctls_r4_2026-08-10_direction.json)。

