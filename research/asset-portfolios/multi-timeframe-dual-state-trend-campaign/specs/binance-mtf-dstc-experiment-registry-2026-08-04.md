# BIN-MTF-DSTC 实验注册表

本表在相应实验启动前冻结。所有阶段只使用 development 与 mechanism validation；historical final audit 在最终候选、参数和代码 hash 冻结前不得运行。

## E00 数据与执行门

- 输入：三资产 cutoff-safe `15m`、funding、raw/normalized。
- 输出：数据审计、因果聚合、next-open、gap stop、retry、3x leverage 测试。
- 停止条件：任一 blocker 非零则停止。

## E01 三基线

- `daily_cross1_probe`
- `dual_state_probe`
- `dual_state_static_full`

选择用途：只作机制归因，不直接产生 final candidate。

## E02 单变量机制宽搜

中心配置为 `MA7 / persistence2 / band0.5ATR / band_structure / wrong1ATR×2d / pullback0.5ATR / retrace0.5 / structure6 / buffer0 / min-stop1.5% / restart2 / wait24h / retry1 / no-MFE / 1 layer`。

一次只改变一个槽位：

- MA：`5/10/14`；
- slope persistence：`1/3d`；
- candidate band：`0ATR`；
- invalidation：`slope_structure`、`structure_only`、`wrong0.5ATR`、`wrong1ATR×1d`；
- entry：`immediate_probe`、`restart4`、wait `12/36h`；
- pullback：minimum `0.25/0.75ATR`、maximum retracement `0.33/0.618`；
- stop：structure `12×4h`、buffer `0.25ATR1h`、minimum distance `3%`；
- retry：`0`。

每资产最多保留五个中心/单变量配置进入组合粗搜。资格：development 与 validation 复合后净正、validation PF `>1`、validation 至少 `10` 个 traded Campaign；不足时只保留诊断 Pareto，不进入收益放大。

## E03 组合粗搜

只允许组合 E02 中同资产通过单变量资格且相邻稳定的槽位；禁止把每个槽位的局部赢家任意全排列。每资产上限 `160` 个配置，预先记录生成 hash。

## E04 Probe/Add/MFE

对 E03 每资产最多十个 Pareto 配置机械比较：

- `1/2/4` layers；
- add ladder `0.5/1/2R`、`0.5/1.5/3R`；
- `no_mfe / mfe50_all / mfe50_adds`；
- 每层 retry `0/1`；Campaign loss budget `1.5%/2%/3%`；
- 默认总风险仍为 `1%`，不得在此阶段放大。

为满足 Goal 合同中的固定归因臂，即使某资产 E02 无候选，仍对该资产的冻结中心配置运行上述 `1/2/4 layers × MFE` 机械对照；这类结果标为 `attribution-only`，不能绕过 E02/E03 资格或用于 promotion。

## E05 稳定性与 final freeze

- 邻域、rolling folds、long/short、年度/季度、remove-top-N、8/12bps、15m delay、funding off 对照；
- 通过后才机械比较总风险 `1/1.5/2/3%`；
- 每资产最多冻结一个 candidate；代码、参数、数据 hash 冻结后才允许一次 historical final audit。

## 全局停止规则

- 无配置满足最低机制资格：该资产 NO-GO，不以放大风险救援；
- validation 或 final 揭示后不得同机制救参；
- 20x Stretch 不能改变最低 GO 门槛，也不能覆盖样本不足、集中度或执行失败。
