# BIN-4H-EMAX K 族增补契约：交叉附近蜡烛形态（4h + 日级 + 周级）

> 跑数前冻结。K 族 18 个蜡烛形态特征的定义与 [15m K 族契约](../../15m-ema-cross-lightgbm-event-selector/specs/bin-15m-emax-k-candle-supplement-contract-2026-07-29.md)完全一致，本刻度＝4h 信号 K；日线/周线由 4h 缓存重采样。
>
> 变体 `local_trend_k` = [4h 移植契约](bin-4h-emax-local-trend-selector-contract-2026-07-29.md)的 local+trend 特征集 + K(18)，事件、协议、purge 17 天、权重全部不变；对照基准为 4h local+trend（顶桶净 +0.367 / 毛 +0.467）。判定沿用 Gate A + Gate B。家族维持 `archived`，诊断性质。

产物落 `artifacts/k_candle_supplement/`。
