# BIN-MTF-DSTC E05 稳定性候选冻结

本冻结发生在任何 risk scaling、8/12bps、15m delay、long/short、rolling fold 或 historical final audit 运行前。

## BTC Pareto diagnostics

1. `BTC-BAL`：`wrong05+ma14::layers2_mfe50_adds`
   - 选择理由：两段 PF 均高于 1.5，回撤相对较低；代表“少层 + 只卸追加层”。
2. `BTC-GROWTH`：`wrong05+ma14::layers4_ladder_alt_no_mfe`
   - 选择理由：开发/验证年化较均衡；代表“慢 ladder + 容忍趋势回吐”。

## ETH Pareto diagnostics

1. `ETH-BAL`：`wrong05::layers4_mfe50_adds`
   - 选择理由：开发/验证 PF `1.60/1.41`，回撤 `9.3%/14.9%`；代表相对均衡路径。
2. `ETH-CONVEX`：`invalidation_slope_structure::layers4_no_mfe`
   - 选择理由：验证增长较高且 48 Campaign；代表“不给 MFE 截断”的凸性路径。开发期 PF 与 MDD 已接近/越过门槛，只保留作 Pareto 审计。

## HYPE

E02 无资格配置、E04 attribution 全失败，不进入 E05；不得通过 risk scaling 救援。

## 冻结审计矩阵

- total planned risk：`1/1.5/2/3%`，各层等比例缩放，3x effective leverage 硬上限保持；
- slippage：`4/8/12bps`；
- actual funding / funding-off attribution；
- discretionary execution delay：`0/1×15m`，stop 不延迟；
- long-only / short-only；
- 五个预定 18 个月 rolling folds；
- combined search-region concentration、remove-top-3 与 recent `1d/7d/1m/3m/6m/1y`。

上述四项只是 stability diagnostics。只有单一资产候选同时达到 `>=2x annual equity multiple`、MDD `<=20%`、PF `>=1.3`、concentration、rolling、stress、execution 全门槛，才允许冻结为 final candidate 并揭示一次 historical final audit。

## Hashes

- `dstc_data.py`：`1ddf3d5b1641f4b24e1de7b06d1c456dd7847eb4943215c0e3e1ac9fdf72a09b`
- `dstc_engine.py`：`7113d66477303a7b99226b60799d07c3031a2972ca20c228ea734f32c9761a95`
- data audit：`31e0634348ce3730e1a74279f9a9564d94119f7bc07514fbe77f8954e17b0a9c`
- E04 artifact：`4ce06f68f5951067abf08168dd9dcf58ff8a44bb9ce736053e95df4572a60c1b`
