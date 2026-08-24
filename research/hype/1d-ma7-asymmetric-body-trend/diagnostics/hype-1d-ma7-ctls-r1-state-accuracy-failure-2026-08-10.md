# CTLS-R1持续趋势状态识别失败复盘

## 裁决

`CTLS-R1`在任何PnL搜索之前即停止：Stage A `324/324`完成、`190`条独立状态路径、`0`异常、`0`项通过准确率门。因此没有运行Stage B/C、没有访问`LES=[324,432)`、没有研究杠杆，也不存在可登记候选。

## 最佳可达值

| 冻结指标 | R1最佳 | 门槛 | 通过配置数 |
| --- | ---: | ---: | ---: |
| 三方向balanced accuracy | 0.4338 | 0.55 | 0/324 |
| 10类macro-F1 | 0.0569 | 0.35 | 0/324 |
| slow-up recall | 0.0000 | 0.35 | 0/324 |
| slow-down recall | 0.1429 | 0.35 | 0/324 |
| accel/decel macro-F1 | 0.0973 | 0.25 | 0/324 |
| direction flip rate | 0.0579 | <=0.15 | 324/324 |
| 至少4/6 block方向准确率>=0.50 | 0 block（最佳配置） | 4 block | 0/324 |

## 机制归因

1. **不是状态翻转过多**：全部324项都通过flip-rate门，失败不应靠增加确认天数修复。
2. **二元证据计数几乎不产生flat**：最佳路径真实标签含`98 neutral + 28 chop`，预测却没有任何neutral/chop；`hold_score_min=1`使任意单项残余证据都能无限维持旧方向。方向balanced accuracy因flat recall为0被压至0.4338。
3. **阶段优先级吞掉慢趋势**：固定规则先判断`acceleration`，再判断`slow`；MA7一日噪声相对三日斜率的差值经常先命中加/减速，使slow-up召回恒为0，slow-down最高仅1/7。
4. **阈值搜索没有触及真正缺失变量**：R1只搜索四项证据各自门槛和入场确认，没有搜索方向强度的连续合成、flat hysteresis、hold/exit强度或阶段阈值；324项只是同一结构的局部参数变化。
5. **当前加减速特征与评估标签错位**：策略只用`SMA7一日斜率-三日斜率`，标签用中心窗口的未来三日减过去三日；单一当前曲率对该标签的macro-F1最高仅0.0973。

## 后继约束

不放宽原准确率门，不把收益用作状态标签，不读取LES救参数。后继`CTLS-R2`必须换成连续方向强度+hysteresis，并把slow置于阶段判定首位；先做方向结构广搜，再在冻结的方向父项上搜索阶段特征和阈值。只有R2准确率门通过才允许复用既有交易账本进入PnL搜索。

## 机器证据

- [R1 Stage A](../artifacts/hype_1d_ma7_ctls_2026-08-10_stage_a_v2.json)
- [R1有效manifest](../artifacts/hype_1d_ma7_ctls_2026-08-10_manifest_v2.json)
- [首次落盘失败修复附录](../specs/hype-1d-ma7-ctls-preperformance-repair-2026-08-10.md)

