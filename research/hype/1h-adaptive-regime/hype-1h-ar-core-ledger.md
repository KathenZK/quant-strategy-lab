# HYPE-1H-Adaptive-Regime Core Ledger

## Family Identity

- 完整家族名：`HYPE-1H-Adaptive-Regime`
- 别名：`HYPE-1H-AR`
- 市场：Binance USD-M `HYPEUSDT` 永续，`1h`
- 机制：DI-cross 趋势腿 + Stoch-reversal 反转腿的精确单仓 ensemble。
- 边界：独立于 HYPE MII、EMA-X、EMA-TB 与 5M-PBTR；裸 V1–V4 不具身份。

## Current State

- 当前版本：`HYPE-1H-Adaptive-Regime-V4`。
- 状态：`registered / not promoted / not live-ready`；V1–V3 作为 historical pre-dry-run findings。
- 精确联合审计推翻“两腿独立模拟后合并”近似；V4 K+2 `7.8530x/-25.04%`，8bps/fill `14.1032x/-22.46%`，均超回撤门。
- 2400 个 VWAP 第三腿严格搜索精确联合 gate `0`；不得围绕已揭示失败对照追参。
- 下一门：不同于 VWAP/Stoch 的新信息源或事件机制，并继续使用精确联合增量门槛。

## Version Rules

- V1 为首个冻结基线；V2 删除 dormant 字段且逐笔等价。
- V3 是消融引导组合；V4 是 V3 剪枝与 prefit 微调，参数从 34 降至 25。
- 高年化但 K+2/成本压力失败的 tune 只作 rejected diagnostic；登记不代表 promotion。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V1` | historical / not live-ready | DI-cross + Stoch-reversal | current full `9.6838x/-19.64%/78.26%/69` | [spec](specs/hype-1h-ar-v1-baseline-spec.md) · [audit](diagnostics/hype-1h-adaptive-regime-boundary-audit-2026-07-01.md) | 未达硬门 |
| `V2` | historical / not live-ready | V1 clean-equivalent | 与 V1 逐笔等价 | [spec](specs/hype-1h-ar-v2-clean-baseline-spec.md) · [ablation](ablations/hype-1h-ar-v2-full-parameter-ablation-2026-07-02.md) | 无新增证据 |
| `V3` | historical / not live-ready | DI 去 ROC 下限，Stoch high=55 | full `15.0530x/-19.11%`；K+2/8bps 失败 | [spec](specs/hype-1h-ar-v3-baseline-spec.md) · [ablation](ablations/hype-1h-ar-v3-full-parameter-ablation-2026-07-06.md) | 不 promotion |
| `V4` | registered / not promoted / not live-ready | V3 剪枝后的 25 参数精确联合基线 | full `20.9748x/-19.11%/80%/75`；holdout `9.0210x/-19.11%/73.68%/19` | [spec](specs/hype-1h-ar-v4-pruned-tuned-baseline-spec.md) · [pressure](diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md) | 第三腿 `0/2400`，不登记 V5 |

## Shared Assumptions

- 数据：标准 raw/normalized，闭合 `1h` K `2025-05-30T10:00Z`–`2026-07-02T02:00Z`，9545 根；质量异常全 0。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，历史 funding 2385 条按持仓区间计。
- 执行：closed-bar、next-open；单仓；冲突 DI 优先；stop-first，gap-open stop 按 open。
- 计分起点：warmup 后 `2025-07-14T10:00Z`。
- 仓位与腿参数以对应版本 spec/配置为真值；没有生产 runner 授权。

## Evidence Map

- 参数剪枝与微调：[V3 prune and tune](notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md)
- 执行压力：[V4 pressure](diagnostics/hype-1h-ar-v4-execution-pressure-optimization-2026-07-10.md)
- 第三腿：[VWAP search](notes/hype-1h-ar-v4-vwap-third-leg-search-2026-07-13.md)
- 决策：[decision-log.md](decision-log.md) · 脚本/产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
