# CTLS-R2连续强度状态机预注册合同

> 冻结时间：2026-08-10。R2由R1准确率结构性失败触发；本合同签署前未访问CTLS的LES、未运行任何CTLS PnL候选。R1的D准确率已暴露，R2仍只把D当开发集，LES访问顺序和clean prospective起点不变。

## 1. 不变项

- 身份仍为未登记的`CTLS`研究分支，R2是机制级后继，不是V6改参。
- 数据、成本、日线next-open、真实1h顺序账本、V4/V5/V6控制、D/LES/full/prospective窗口、准确率门、D/LES收益与MDD门、1x优先及杠杆禁入条件全部沿用R1合同。
- 离线标签只评估，不进入策略特征；不允许用PnL筛状态结构。

## 2. 连续方向强度

沿用R1的`z/s3/d3/er7`，把二元计数替换为连续分量：

```text
xz = tanh(z / z_scale)
xs = tanh(s3 / slope_scale)
xd = tanh(d3 / drift_scale)
xe = er7
q  = (wz*xz + ws*xs + wd*xd + we*xe) / (wz+ws+wd+we)
```

权重模板固定为：

```text
EQUAL       = (1.0,1.0,1.0,1.0)
PERSISTENCE = (0.5,1.5,1.5,1.0)
EARLY       = (1.5,0.5,1.5,0.5)
SMOOTH      = (0.5,1.5,0.5,1.5)
```

方向hysteresis：flat连续`enter_confirm`日满足`abs(q)>=enter_q`后入方向；已有方向在`side*q<=exit_q`连续`exit_confirm`日后转flat；`q`达到相反方向`enter_q`且连续`reverse_confirm`日则反转。flat是真实可输出状态，不再由“至少一项证据”无限维持方向。

## 3. 两阶段结果盲搜索

### R2-A1：方向结构，1,944项

```text
z_scale      ∈ {0.25,0.50,1.00}
slope_scale  ∈ {0.03,0.08,0.15}
drift_scale  ∈ {0.05,0.10,0.20}
weight       ∈ {EQUAL,PERSISTENCE,EARLY,SMOOTH}
enter_q      ∈ {0.20,0.35,0.50}
exit_q       ∈ {-0.05,0.05,0.15}
enter_confirm∈ {1,2}
```

固定`exit_confirm=2`、`reverse_confirm=1`。只按三方向balanced accuracy、flat/up/down recall、6个cold-flat block最差值、flip率和路径独立性筛最多32项；不计算10类阶段指标进行父项选择，不运行PnL。

方向父项最低资格：aggregate三方向balanced accuracy`>=0.55`、flat/up/down recall各`>=0.40`、flip率`<=0.15`，至少4/6 block balanced accuracy`>=0.50`。

### R2-A2：阶段结构，最多2,592项

对最多32个方向父项搜索：

```text
velocity_source ∈ {S3,D3,BLEND}
accel_source    ∈ {MA_CURVATURE,DRIFT_CURVATURE,BLEND}
slow_threshold  ∈ {0.05,0.10,0.20}
accel_threshold ∈ {0.02,0.05,0.10}
```

其中`DRIFT_CURVATURE=d1-d3`，`d1=(close_t-close_{t-1})/ATR7_t`；`BLEND`为对应两分量等权。方向存在时先判断`side*velocity<slow_threshold`为`SLOW`，再判断加速、减速，最后为`ESTABLISHED`，从结构上避免加减速吞掉慢趋势。flat时沿用R1的CHOP/NEUTRAL规则。

R2-A2按R1完整准确率硬门选最多24条独立10类路径；0条通过则R2停止，不运行PnL、不访问LES。通过后才可把唯一冻结的状态父项映射到R1已测试的生命周期交易账本，并继续原Stage B/C门禁。

## 4. 消融与停止规则

- A1必须分别消融四个方向分量、hysteresis和每个权重模板；A2必须分别消融slow优先级、三种velocity及三种acceleration来源。
- 任一启用分量在D没有改变状态路径，必须作为dormant删除后重新计算复杂度；不得因为某项收益好而保留准确率无贡献模块。
- A1无合格方向父项或A2无完整门通过项，立即`NO-GO`。后继若改标签、改时间尺度或引入监督模型，必须另写R3合同；不得在R2内继续扩格。
