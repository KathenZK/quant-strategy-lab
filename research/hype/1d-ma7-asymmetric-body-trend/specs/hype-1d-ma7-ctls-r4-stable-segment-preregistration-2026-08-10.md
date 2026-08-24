# CTLS-R4稳定趋势段预注册合同

> 冻结时间：2026-08-10。R4由R3“准确但高flip”的结构矛盾触发；本合同前未访问LES或CTLS PnL。

## 稳定方向标签

1. 先按R1中心7日回归生成原始`DOWN/FLAT/UP`方向，缺失保持缺失。
2. 对每个连续可评估区间用三状态Viterbi解码：匹配原始状态emission cost=0，不匹配=1；任意状态切换cost固定`2.0`。
3. Viterbi后任何少于3个完整日的内部run：若左右状态相同则并入该状态，否则改为FLAT；重复至不存在可合并短run。边界短run改FLAT。
4. 稳定标签仅用于离线评估和监督y，不进入特征X。因它额外依赖相邻原始标签，训练标签成熟延迟从`t+3`提高为`t+4`；eval fold末4日剔除指标。

该标签定义使“趋势段”最短3日，并显式惩罚逐日翻转；不使用PnL或V4交易选择标签。

## 因果预测

完全复用R3的23个因果特征、5个forward fold和31个模型配置。新增且仅新增概率平滑：

```text
EMA alpha ∈ {0.20,0.40,0.60,0.80}
enter_probability ∈ {0.40,0.50,0.60}
confirm_days ∈ {1,2}
exit_confirm_days ∈ {1,2}
```

每个fold从无状态开始，先对三类概率逐日因果EMA，再做R3 hysteresis。共`31×4×12=1,488`项；随机种子和线程不变。

## 方向门与后续

合并eval balanced accuracy>=0.55，down/flat/up recall各>=0.40，flip<=0.15，至少4/5折balanced accuracy>=0.50。按最差折、aggregate、最小召回、flip、复杂度、SHA选最多16条独立路径。

若0项通过，停止并确认日线稳定趋势段仍不可辨识。若通过，才在合格方向父项上定义稳定的slow/established/accelerating/decelerating阶段标签与模型合同；R4-DIR本身不运行PnL、不访问LES、不授权登记或杠杆。

