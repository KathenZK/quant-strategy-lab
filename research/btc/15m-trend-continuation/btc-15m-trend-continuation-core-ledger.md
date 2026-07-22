# BTC-15M-Trend-Continuation Core Ledger

## Family Identity

- Full family name：`BTC-15M-Trend-Continuation`
- Alias：`BTC-15M-TC`
- Market / exchange / symbol / timeframe：Binance USD-M Futures perpetual / `BTCUSDT` / `15m`
- Mechanism summary：低波动压缩后，在 `EMA96 > EMA384` 且慢线向上时做 Donchian 收盘突破；仅做多，以 ATR 初始止损和定时退出捕捉趋势延续。
- Boundary / collision warnings：不是一般 [`BTC-15M-EMA-Trend-Breakout`](../15m-ema-trend-breakout/btc-15m-ema-tb-core-ledger.md) 模板，也不是 [`BTC-15M-Keltner-Trend-Breakout`](../15m-keltner-trend-breakout/btc-15m-keltner-trend-breakout-core-ledger.md)；裸 `Vx` 不得跨家族引用。

## Current State

- Current version(s)：无已登记版本；`lvcb-913f4ff89386` 仅为 `explore` 研究候选。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live status：无 runner 实现、无 dry-run、无 live。
- Live-readiness blockers：历史区间已被机制发现和参数筛选污染；缺 BTC `1m` 相位审计、CPCV、runner 状态机与重启/缺数/kill-switch 审计；最近 `1m/3m` 明显亏损；六轮多头迭代无采纳项，空头专属 `576` 个信号、`804` 个总配置也没有 development gate 通过项。
- Next decision gate：从 `2026-07-20 07:30 UTC` 起冻结参数，累计至少 `6m` 或 `30` 笔新交易后重审 prospective 表现；在此之前不得登记或 promotion。

## Version Rules

- Registration / freeze：只有用户明确要求登记 `Vx` 才进入 `registered`；冻结本次候选参数不产生版本号，也不表示 promotion。
- `V1`：必须基于当前候选或明确的新机制，补齐 prospective、相位、CPCV 与可执行性证据后由用户明确登记。
- `Vx.y`：仅用于同一信号和退出状态机内的有限参数观察；信号时序、方向、过滤器或退出状态机改变应升主版本。
- Observation / diagnostic rows：未登记的搜索候选使用日期或策略哈希，不占用 `Vx`。
- New version trigger：方向集合、压缩定义、趋势 regime、突破规则、持有/止损状态机或成本模型发生实质改变。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `lvcb-913f4ff89386`（未登记观察） | `explore / not promoted / not live-ready` | 低波动压缩 + EMA 趋势 + Donchian96 突破，只做多 | train `+30.96%`、validation `+29.30%`、复用诊断 `+54.55%`；对应 MDD `-13.68%/-10.26%/-14.23%`；复用期 `2x` 成本 `+6.29%` | [长历史诊断](diagnostics/btc-15m-trend-continuation-long-history-search-2026-07-20.md) · [六轮迭代](diagnostics/btc-15m-lvcb-iteration-rounds-2026-07-20.md) · [空头搜索](diagnostics/btc-15m-lvcb-short-search-2026-07-21.md) | 多头六轮无采纳；空头无门禁通过项；保持 long-only，仅 prospective 观察 |

## Shared Assumptions

- Data：官方 Binance `BTCUSDT` perpetual `15m`，`2020-01-01` 至 `2026-07-20 07:30 UTC`，共 `229,662` 根，DQ blocker `0`。
- Cost：每次成交 fee `0.001` + adverse slippage `4 bps`；另做双倍费用/滑点压力。
- Execution timing：信号只用已收盘 `15m`；下一根开盘成交；止损入场 bar 即生效，跳空按开盘价并施加 adverse slippage。
- Position sizing：单仓、`1.0x` equity allocation，不叠仓。
- Funding / carry：逐事件使用审计后的 Binance funding；不以零值代替。

## Evidence Map

- Specs：无版本 spec；尚未登记。
- Diagnostics / ablations：[长历史搜索](diagnostics/btc-15m-trend-continuation-long-history-search-2026-07-20.md) · [六轮迭代](diagnostics/btc-15m-lvcb-iteration-rounds-2026-07-20.md) · [空头专属搜索](diagnostics/btc-15m-lvcb-short-search-2026-07-21.md)
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[脚本入口](scripts/README.md) · [产物索引](artifacts/README.md)
