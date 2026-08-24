# CTLS-R3因果监督可辨识性复盘

## 裁决

R3-DIR 31个模型×12个因果后处理=`372/372`完成，`337`条独立walk-forward方向路径，`0`项通过全部门。未运行阶段模型、PnL、LES或杠杆。

## 关键发现

- 信息量不是主要瓶颈：最佳LightGBM三方向balanced accuracy `0.6227`，down/flat/up recall为`0.5750/0.5918/0.7013`，5/5 eval折balanced accuracy均高于0.50。
- 该路径唯一失败项是direction flip rate `0.4252`，远高于`0.15`。
- 共有95项通过aggregate方向准确率、283项通过flat recall、108项通过4/5折稳定；但仅16项通过flip门。
- 通过flip门的最佳路径balanced accuracy只有`0.4238`：用两日确认和高概率阈值把日标签噪声压平时，同时漏掉大部分up/down。

## 归因

中心7日回归标签逐日独立赋值，允许`UP/FLAT/DOWN`在相邻日频繁切换；它适合局部形态评估，却与用户要求的“持续趋势段”定义冲突。监督模型可以预测这些局部标签，但要逐日追随就必然高flip；若强制持久化，又会在逐日标签上被判错。

R4因此改变**评估对象**而非交易阈值：对原始中心方向标签施加冻结的转移代价和最短3日段，形成离线稳定趋势段；预测侧只允许因果概率EMA与hysteresis。R4仍使用同一未来标签作为评估真值、不把标签放入X、不访问LES，并保留三方向准确率/召回/flip硬门。

## 证据

- [R3 direction](../artifacts/hype_1d_ma7_ctls_r3_2026-08-10_direction.json)
- [R3 manifest](../artifacts/hype_1d_ma7_ctls_r3_2026-08-10_manifest.json)

