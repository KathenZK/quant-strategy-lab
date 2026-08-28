# Binance-1D-MA7-Regime-Continuation Core Ledger

## Family Identity

- Full name / alias：`Binance-1D-MA7-Regime-Continuation` / `BIN-1D-MA7-RC`。
- Market / timeframe：Binance USD-M perpetual，UTC `1d`。
- Mechanism：MA7 close cross 只定义多空事件；比较 Slope/ER/RV 历史位置与 ATR 收缩/扩张路径对固定期限方向收益的解释力。
- Collision warning：本线不等于 `BIN-1D-GMA7T` 可执行 trend strategy，也不继承 HYPE V7.1 参数、止损、仓位或状态。

## Current State

- Current observation：`P0R2`、`P1`、`P2` historical diagnostics 与 `P3` locked confirmation completed。
- Status：`explore / diagnostic-only / not promoted / not live-ready`。
- Runner / dry-run / live：none。
- Result：P3 为 `NO-GO`。本地 ATR 路径对突破结果仍有分离力，但没有形成稳定的跨年份、多空与跨资产规则：锁定段 `P2_LOCAL_FIXED` 20-session 总体 `+2.07%`，由 long `+9.09%` 驱动，short `-1.85%`；breadth 版 `-0.77%`。Logistic 10/20 均负，LightGBM 仅 20-session 为正但历史五折仅两折为正。美股类只有 61 个事件、完整 10/20-session 标签 31/11 个。
- Next gate：不得从 P3 确认段回调阈值或模型。若继续须注册 materially new P4，专门预声明“方向 × 本地波动路径 × 稀缺相对强度/广度背离”机制，并等待新的未见确认段；在此之前不写 runner。

## Version Rules

- 本线尚无 registered strategy version；`P0` 是冻结 observation，不是 `V1`。
- 更换 regime 指标、lookback、分桶法、事件成交时序或资产池定义均须新 observation id 和预先冻结合同。
- MA5/10 只属 P0 邻域稳健性，不产生版本选择。

## Version Table

| Observation | Status | Role | Frozen evidence | Decision |
| --- | --- | --- | --- | --- |
| `P0R2` | completed / diagnostic-only | 全历史动态 universe 的 MA7 regime event study | [contract](specs/binance-1d-ma7-regime-continuation-p0-contract-2026-08-24.md) · [results](diagnostics/binance-1d-ma7-regime-continuation-p0-results-2026-08-24.md) | PARTIAL regime separation；universal 3D gate failed；not promoted |
| `P1` | completed / diagnostic-only | 四状态 × RV 五档、compression→expansion 与过滤前后频率 | [contract](specs/binance-1d-ma7-regime-continuation-p1-readable-state-frequency-contract-2026-08-24.md) · [results](diagnostics/binance-1d-ma7-regime-continuation-p1-readable-states-frequency-2026-08-24.md) | short-first account candidate only；not a strategy version；not promoted |
| `P2` | completed / diagnostic-only | causal 60-observation ATR path × breakout range burst，并与 RV252 做共同样本对比 | [contract](specs/binance-1d-ma7-regime-continuation-p2-atr-path-contract-2026-08-25.md) · [results](diagnostics/binance-1d-ma7-regime-continuation-p2-atr-path-2026-08-25.md) | market-style filtering supported but original directional hypothesis rejected；not a strategy version；not promoted |
| `P3` | completed / confirmatory diagnostic | asset-local direction/volatility + leave-one-out breadth；固定规则、Logistic、LightGBM；next-open 10/20-session hold | [contract](specs/binance-1d-ma7-regime-continuation-p3-confirmatory-fixed-ml-contract-2026-08-25.md) · [results](diagnostics/binance-1d-ma7-regime-continuation-p3-confirmatory-2026-08-25.md) | `NO-GO`；weak separation but unstable direction and insufficient non-crypto evidence；not promoted |

## Shared Assumptions

- Source：Binance Vision monthly + immutable Binance API legacy partitions；ETH 跨源重叠固定 Vision 优先，选后 union 唯一，因果聚合完整 UTC 日。P0R2 config SHA256 `15bc78f14bf3f7026440d778d849252e8ff0d1af1aa80d3d064bd569e850a84b`；两个旧 hash 均在 outcome 前作废。
- Event return：trigger close 到固定 future close；不含 fee、slippage、funding。
- Inference：symbol 与 event date 双向聚类；三维 cells 做 BH-FDR。
- P2 primary style：突破前 `ATR20[t-1]/ATR20[t-11]-1` 在同币 trailing 60 的 causal quintile；突破日 `TR/ATR20[t-1]` 固定为 weak/normal/burst。P2 不继承 RV252 eligibility，仍要求上市满 120 日。
- P3：完整 UTC 日由 96 根 `15m` 聚合，按资产自身 observed-session sequence、超过四个自然日才断段；不用 BTC、symbol 或 asset class 特征。next-open 成交，固定 10/20 session，往返成本 28 bps，最多五仓；funding 缺失，账户结果不能晋级。

## Evidence Map

- [Family README](README.md)
- [Frozen P0 contract](specs/binance-1d-ma7-regime-continuation-p0-contract-2026-08-24.md)
- [P0R2 results](diagnostics/binance-1d-ma7-regime-continuation-p0-results-2026-08-24.md)
- [P1 results](diagnostics/binance-1d-ma7-regime-continuation-p1-readable-states-frequency-2026-08-24.md)
- [P2 frozen contract](specs/binance-1d-ma7-regime-continuation-p2-atr-path-contract-2026-08-25.md)
- [P2 results](diagnostics/binance-1d-ma7-regime-continuation-p2-atr-path-2026-08-25.md)
- [P3 frozen contract](specs/binance-1d-ma7-regime-continuation-p3-confirmatory-fixed-ml-contract-2026-08-25.md)
- [P3 results](diagnostics/binance-1d-ma7-regime-continuation-p3-confirmatory-2026-08-25.md)
- [Short-first account backtest candidate](specs/binance-1d-ma7-regime-continuation-short-first-account-candidate-2026-08-24.md)
- [Decision log](decision-log.md)
- [Artifacts index](artifacts/README.md)
