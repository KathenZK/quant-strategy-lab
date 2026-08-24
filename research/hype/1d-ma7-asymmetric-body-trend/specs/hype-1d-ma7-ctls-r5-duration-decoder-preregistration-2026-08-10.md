# CTLS-R5因果持续期解码预注册合同

> 冻结时间：2026-08-10。R5只修复R4预测状态频繁改口，不改标签、特征、模型族、准确率门或数据窗口；未访问LES/PnL。

复用R4稳定方向标签、R3的31个模型、R4 EMA。为控制总格且覆盖R4有效区域，冻结：

```text
EMA alpha          ∈ {0.40,0.60,0.80}
enter_probability  ∈ {0.40,0.50}
base confirm       ∈ {1,2}
base exit confirm  ∈ {1,2}
minimum dwell days ∈ {3,5,7}
switch confirm days∈ {1,2}
```

先产生R4 base hysteresis状态，再做严格因果duration decoder：当前状态至少维持minimum dwell；base目标与当前不同须连续switch-confirm日才切换；计数中断即清零。每个fold cold-flat，所有计数重置。共`31×3×8×3×2=4,464`项。

方向门仍为balanced accuracy>=0.55、三类recall各>=0.40、flip<=0.15、至少4/5折>=0.50。若通过，按最差折、aggregate、最小recall、flip、复杂度、SHA冻结最多16条独立方向父项并进入阶段研究；若0项通过，状态准确率路线停止，不再扩大duration参数。

