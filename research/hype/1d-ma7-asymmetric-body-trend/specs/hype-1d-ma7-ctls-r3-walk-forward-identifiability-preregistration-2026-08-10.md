# CTLS-R3因果监督可辨识性预注册合同

> 冻结时间：2026-08-10。R3由R1/R2在PnL前连续失败触发。R3只研究D内状态标签的因果可预测性；未访问LES，不以收益选模型。

## 1. 问题

检验“使用日线收盘时已知信息，中心7日趋势方向/阶段标签是否可预测”。模型X不得含未来价格；标签`y_t`使用`t+3`，因此在预测日`T`训练集只允许使用`t<=T-3`且标签完整的样本。

## 2. 因果特征

使用截至`t`的：`z/s1/s3/d1/d3/er7/MA曲率/价格曲率`、1/2/3/5/7日ATR归一化收益、3/5/10日效率、日range/body相对ATR、ATR7一日/三日变化、Wilder RSI6、最近5日MA侧别翻转数、正负收益比例。所有rolling只向后；非有限行不参与训练/预测。

## 3. Walk-forward

固定5折：train `[0,54)->eval[54,108)`、`[0,108)->[108,162)`、…、`[0,270)->[270,324)`。每折训练末端剔除尚未成熟的最后3日标签；不回填第一块预测，不用未来fold训练过去fold。每个eval fold末端的最3日因中心标签跨越fold边界从该折指标剔除，但预测和状态路径仍完整保留。

### R3-DIR

三类`DOWN/FLAT/UP`，候选仅为：

- multinomial logistic：`C∈{0.01,0.1,1,10}`，balanced class weight；
- random forest：`max_depth∈{2,3,5}`、`min_samples_leaf∈{5,10,20}`，200树，balanced class weight；
- LightGBM multiclass：`num_leaves∈{3,7,15}`、`min_child_samples∈{10,20,40}`、`learning_rate∈{0.02,0.05}`、200轮，balanced sample weight。

概率后处理固定搜索：`enter_probability∈{0.40,0.50,0.60}`、方向确认`{1,2}`；已有方向若flat概率最高或当前方向概率低于`0.35`连续`{1,2}`日则flat，相反方向满足entry概率则反转。所有模型/后处理组合均预先枚举。

资格门改为可执行的5折口径：合并eval三方向balanced accuracy`>=0.55`，flat/up/down recall各`>=0.40`，flip率`<=0.15`，至少4/5折balanced accuracy`>=0.50`。按最差折、aggregate、最小类召回、flip、复杂度和config SHA选最多16条独立方向路径。

### R3-PHASE

只对合格方向父项训练四类`SLOW/ESTABLISHED/ACCELERATING/DECELERATING`分层模型；训练用真实方向把方向性特征统一为正，预测用R3-DIR预测方向。模型族与超参数仅复用DIR已列三族，不新增网格；方向预测为flat时输出R1的CHOP/NEUTRAL规则。

完整10类仍必须通过R1冻结门：macro-F1>=0.35、slow双向recall各>=0.35、accel/decel macro-F1>=0.25、flip<=0.15；方向门使用上述5折口径。0项通过即确认“当前日线信息对该标签不可辨识”，停止PnL并另议标签/数据机制。

## 4. 治理

- 不以收益、交易数或V4/V5/V6表现筛模型；不访问LES。
- scaler/模型只能在各fold训练段拟合；随机种子固定`20260810`，线程固定1。
- 输出每折训练末标签时间、预测起止、类计数、混淆与路径SHA，证明标签成熟和无未来训练。
- R3通过准确率门后，才允许写新的交易搜索合同；R3本身不授权PnL、登记、promotion或杠杆。
