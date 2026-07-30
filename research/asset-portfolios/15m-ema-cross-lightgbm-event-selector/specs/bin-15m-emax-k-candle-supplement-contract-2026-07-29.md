# BIN-15M-EMAX K 族增补契约：交叉附近蜡烛形态（本刻度 + 日级 + 周级）

> 跑数前冻结。动机：用户提出补齐蜡烛实体/影线形态特征——交叉附近的本刻度 K 线形态、日级形态、周级形态。零下载，全部由现有 K 线计算。同一特征定义同步在 4h 家族验证（[4h K 族契约](../../4h-ema-cross-lightgbm-event-selector/specs/bin-4h-emax-k-candle-supplement-contract-2026-07-29.md)）。家族维持 `archived`，2026H1 不使用。

## K 族特征定义（18 个，只用信号 K 收盘前可知数据）

记 `body = close − open`，`rng = high − low`（为 0 记缺失）。"顺势影线"：多头取下影、空头取上影；"逆势影线"反之（条件交换实现方向对齐）。

**本刻度（信号 K，7 个）**：`kbar_body_atr`（body/ATR，×side）、`kbar_body_ratio`（|body|/rng）、`kbar_shadow_with` / `kbar_shadow_against`（影线/rng，条件对齐）、`kbar_close_bias`（收盘在 rng 内位置映射到 [−1,1]，×side）、`kbar_body3_atr`（近 3 根 body 和/ATR，×side）、`kbar_engulf`（|body| ÷ 前一根 |body|）。

**日级（上一完整 UTC 日，6 个）**：`d1_body_atr`（×side，日线 ATR14 归一）、`d1_body_ratio`、`d1_shadow_with` / `d1_shadow_against`、`d1_close_bias`（×side）、`d1_body3_atr`（近 3 完整日 body 和/日线 ATR14，×side）。日线由本刻度重采样，ATR14 历史不足记缺失。

**周级（上一完整 UTC 周一起算周，5 个）**：`w1_body_atr`（×side，周线 ATR14 归一，需 ≥14 完整周）、`w1_body_ratio`、`w1_shadow_with` / `w1_shadow_against`、`w1_close_bias`（×side）。

## 变体与判定

- `local_trend_k` = LOCAL(37) + a2 趋势(7) + K(18)；绝对标签 `b4_2_net_atr`；协议（超参、扩窗 purged 年度 OOF 2022–2025、权重）与 a2 完全一致。F/A 两族已证冗余，不入本变体，对照基准为 a2（净 −0.134 / 毛 +0.167）。
- 判定沿用 Gate A（十分位 Spearman > 0.8）+ Gate B（顶桶净 > 0 且 ≥3/4 年为正）。

产物落 `artifacts/k_candle_supplement/`。
