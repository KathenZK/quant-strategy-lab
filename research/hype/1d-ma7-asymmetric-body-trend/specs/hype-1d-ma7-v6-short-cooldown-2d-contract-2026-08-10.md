# HYPE 1D MA7 V6：Short Cooldown 5d → 2d 单变量合同

## 目标

回答一个且仅一个问题：把exact V6的short退出后cooldown从5个完整日缩短为2日，是否提高收益并降低回撤。

本轮是已暴露全历史上的单变量诊断，不登记版本、不搜索其他天数、不修改V6。

## 唯一变量

- Control：exact V6 `PEHC_294`，`short_config.cooldown_days=5`。
- Candidate：其余配置、数据、执行、OAPP、RSI6止盈与PEHC全部逐字段相同，只令`short_config.cooldown_days=2`。
- 原引擎只有一个全局`cooldown_left`。因此short仓位退出后设置的5日或2日cooldown会同时阻止flat状态下的自然long和natural short入场；本轮按现有V6真实语义测试，不把它静默改成只阻止short。
- Forced reversal与PEHC handoff继续沿用原时序；不新增pending，不恢复cooldown期间过期的fresh cross。

## 双重对照

1. `EXACT_V6_CD5` vs `EXACT_V6_CD2`：主结论。
2. `RSI_MEMORY_CD5` vs `RSI_MEMORY_CD2`：在刚完成的`PRIOR5 3-of-5` RSI6记忆cross主规则上检查交互，只作次级诊断。

## 数据、成本与风险

- Binance USD-M `HYPEUSDT` perpetual；完整`1h`聚合UTC日线。
- `[0,432)`，2025-05-31至2026-08-05共432个完整日；终止成交open为2026-08-06 00:00 UTC。
- `1x`、单仓、不加仓；日线close信号最早下一UTC日open成交。
- 手续费`0.001/fill`，base不利滑点`4bps/fill`，计实际funding；压力`8bps/fill`。
- 主风险为真实`1h`顺序MDD；另跑8个54日cold-flat块及最近`1d/7d/1m/3m/6m/1y`切片。

## 判定

候选只有在全历史收益严格更高、MDD严格更小，且8bps与cold-flat块不出现收益/MDD双劣时才可保留。否则结论为`FAIL`，V6继续使用short cooldown 5日。
