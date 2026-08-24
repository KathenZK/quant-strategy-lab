# CTLS持续趋势生命周期最终失败复盘

## 裁决

CTLS R1–R6共完成`13,056`个状态/方向配置，所有冻结搜索均为0项通过。研究在状态识别门停止：没有运行PnL、没有访问LES、没有形成1x候选，也没有运行固定或动态杠杆。

因此本轮没有找到可登记的V7，也不能声称找到了比V4/V5/V6收益更高、回撤更低的版本。CTLS主状态保持`explore / not promoted / not live-ready`，本轮裁决为`HARD-GATE-FAILED`。

## 六轮研究结果

| Round | 研究问题 | 完成配置 | 结果 |
| --- | --- | ---: | --- |
| R1 | 以MA7距离、斜率、ER7和加速度构造十状态因果规则 | 324 | 最佳三方向balanced accuracy `0.4338`；慢涨recall为0，失败 |
| R2 | 把离散阈值改为连续趋势强度与迟滞状态 | 1,944 | 最佳balanced accuracy `0.5260`；flat与方向recall不能同时成立，失败 |
| R3 | 严格walk-forward Logistic / RF / LightGBM可辨识性检验 | 372 | 最佳balanced accuracy `0.6227`且5/5折稳定，但flip `0.4252`，失败 |
| R4 | 用转移代价与最短趋势段重定义稳定真值 | 1,488 | 最佳balanced accuracy `0.5949`，但flip `0.321`；低flip路径精度不足，失败 |
| R5 | 扩大最短持续期、进出确认和方向切换解码 | 4,464 | 一条路径5/5折稳定但flip `0.1807`；另一条flip `0.1084`但仅3/5折稳定，失败 |
| R6 | 加入HYPE日内路径/volume/funding及同窗BTC市场上下文 | 4,464 | 62项特征、3,941条独立路径，仍0项同时通过全部门 |

## 最终可达前沿

R6给出的两端已经把问题定位清楚：

- `R6D12_2_1_3`是“除flip外全部通过”的最优路径：RF `max_depth=5/min_samples_leaf=10`，概率EMA `0.6`，入场概率`0.4`，方向进/退确认`1/1d`，hold概率`0.35`，最短持续`5d`，切换确认`1d`。balanced accuracy `0.572946`，down/flat/up recall为`0.594595/0.563636/0.560606`，5/5折均高于`0.50`；但flip为`0.176707`，高于`0.15`硬门。
- `R6D01_2_2_6`是“除跨折稳定外全部通过”的代表路径：Logistic `C=0.01`，概率EMA `0.6`，入场概率`0.4`，进/退确认`1/2d`，最短持续`7d`，切换确认`2d`。balanced accuracy `0.553754`，flip `0.112450`，三方向recall均通过；但五折balanced accuracy为`0.3811/0.4969/0.7644/0.4040/0.5822`，只有2/5折达到`0.50`。
- 在“准确率、三类recall、五折稳定”都通过的路径中，最低flip仍为`0.172691`（`R6D01_2_5_1`），不是某一个局部阈值造成的漏门。

## 为什么慢涨、阴跌与完整阶段仍识别不稳

1. `432d`只有约250个严格walk-forward评估日，慢趋势、急趋势和震荡的独立episode太少；五个时间折的市场结构差异显著，同一解码器无法保持相同精度。
2. 日线因果信息对“今天属于趋势”有一定辨识力，但趋势开始/结束的边界本身模糊。快速响应会提高方向recall，同时产生过多`UP/FLAT/DOWN`切换；扩大确认和最短持续期能降flip，却会迟到或漏掉短趋势。
3. R6已经加入日内路径、量、funding和BTC上下文，说明瓶颈不再只是MA7或特征缺失；新增信息提高了部分折的准确率，但没有消除跨regime非平稳性。
4. 加速/减速建立在方向状态之上。方向层没有通过时，再优化十状态阶段标签会把基础方向误差包装成更细的类别，不能形成可信交易状态机。
5. V4–V6的高历史收益来自少数fresh reclaim、保护退出与handoff事件；它们是稀疏交易选择器，不等于连续趋势分类器。强行让连续状态覆盖慢涨/阴跌，会增加V4过去刻意过滤掉的低质量暴露与churn。

## 为什么没有收益、回撤和HTML结果

预注册要求先证明无绩效状态识别，再允许生命周期/PnL搜索。六轮均未通过第一层，因此：

- 没有合法的CTLS交易候选，不能计算“候选优于V4”的收益/MDD结论；
- LES `[324,432)`从未用于选择或评估CTLS候选；
- 没有1x PASS，所以`<=3x`固定/动态杠杆保持锁定；
- 没有逐笔交易，自然不存在CTLS交易路径HTML。为失败模型生成交易图会误导为已经形成策略。

## 后继边界

不能继续在同一432日上调门槛、改标签或挑模型后再称为验证。下一条合法路线只能是：

1. 继续积累从`2026-08-11`起的clean prospective，至少90个完整新UTC日，并在冻结模型上做真正外推；或
2. 另立跨资产/更长历史的趋势episode研究，先验证状态定义能否迁移，再冻结全新的HYPE前瞻合同；或
3. 把目标从“逐日十状态分类”改为更少、更经济化的事件任务，例如趋势启动、趋势延续、趋势衰竭三个独立hazard，但必须使用新的prospective lock，不能复用本轮LES作调参集。

V1与V6已有各自独立的前瞻observer，可以继续观察；CTLS本轮关闭，不登记版本、不promotion、不推进runner。

## 机器证据

- [R1 Stage A](../artifacts/hype_1d_ma7_ctls_2026-08-10_stage_a_v2.json)
- [R2 direction](../artifacts/hype_1d_ma7_ctls_r2_2026-08-10_direction_a1.json)
- [R3 direction](../artifacts/hype_1d_ma7_ctls_r3_2026-08-10_direction.json)
- [R4 stable segment](../artifacts/hype_1d_ma7_ctls_r4_2026-08-10_direction.json)
- [R5 duration decoder](../artifacts/hype_1d_ma7_ctls_r5_2026-08-10_direction.json)
- [R6 intraday context](../artifacts/hype_1d_ma7_ctls_r6_2026-08-10_direction.json)
