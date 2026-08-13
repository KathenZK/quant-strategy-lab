# Binance 1D MA7 BTC/ETH Shared V1 长历史零调参审计

## 结论

`BIN-1D-MA7-AS-SEARCH-V1` 在 2019–2026 多轮牛熊上的收益和回撤均未达到 P2 目标。BTC 成本后终值为 `1.6652x`、MDD `-60.41%`；ETH 为 `2.6747x`、MDD `-65.67%`；BTC/ETH 每日等权组合为 `2.1699x`、日收盘 MDD `-59.24%`。两资产的 `>=20x / MDD<=20%` 均失败。

本轮是 V1 冻结参数的零调参长历史诊断，不改变 V1 的 `registered / not promoted / not live-ready` 状态，不登记 V2，不产生 promotion 或 runner 授权。P2 下一步进入 active-parameter 全消融和因果归因，不在已揭示 audit 段救参。

## 冻结合同与数据

- 合同：[P2 共享参数演进合同](../specs/binance-1d-ma7-shared-evolution-p2-contract-2026-08-12.md)
- 市场：Binance USD-M `BTCUSDT` / `ETHUSDT` perpetual，UTC `1d`
- 共同评估窗口：`2019-12-24 00:00 UTC` 至 terminal open `2026-08-10 00:00 UTC`，`2,421d`
- Development：`2019-12-24` 至 `2025-08-07` exclusive
- Researcher-exposed audit：`2025-08-07` 至 terminal；不是 clean OOS
- 输入：经 `BIN-1D-MA7-RSI6-DAPML P0` 审计的直接 `1h`、实际 funding 与 mark 快照
- 质量：manifest、BTC hourly/funding、ETH hourly/funding blocker 均为 `0`；脚本复核四个冻结 frame hash
- 成本：`0.001/fill` 手续费 + `4 bps/fill` 不利滑点；压力为 `8 bps/fill`
- 执行：闭合日线信号下一 open；stop 用真实 `1h` 路径；约 `1x`，单仓、非加仓

## 长历史结果

### Combined

| Asset | Base equity | Net return | MDD | Trades | Win rate | PF | 8 bps equity | +1d delay equity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | `1.6652x` | `+66.52%` | `-60.41%` | 94 | `44.68%` | `1.260` | `1.5454x` | `1.1703x` |
| ETH | `2.6747x` | `+167.47%` | `-65.67%` | 89 | `47.19%` | `1.428` | `2.4907x` | `3.0125x` |

压力结果仍为正，但不能弥补全路径回撤超过 `60%` 和累计终值远低于 `20x`。BTC 额外一日延迟后仅余 `1.1703x`，同时 MDD 恶化至 `-73.70%`；说明 BTC 的 entry/exit 时序优势脆弱。ETH 延迟收益提高但 MDD 仍为 `-67.28%`，不能解释为稳健通过。

### 时间段

| Asset | Window | Equity | MDD | Trades | PF |
| --- | --- | ---: | ---: | ---: | ---: |
| BTC | Development | `1.2235x` | `-60.41%` | 81 | `1.096` |
| BTC | Researcher-exposed audit | `1.3609x` | `-14.78%` | 13 | `2.845` |
| ETH | Development | `2.2988x` | `-65.67%` | 80 | `1.413` |
| ETH | Researcher-exposed audit | `1.1635x` | `-18.26%` | 9 | `1.489` |

V1 原登记窗口主要落在近期的有利区域；扩展到完整历史后，development 已暴露严重回撤。researcher-exposed audit 的近期正收益不能用来覆盖早期失败，也不能作为下一轮调参目标。

## 多空归因

| Asset | Leg | Full equity | MDD | Trades | PF | 归因 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| BTC | Long-only | `0.5632x` | `-74.13%` | 49 | `0.599` | 主要负贡献；不是可保留 alpha |
| BTC | Short-only | `2.3878x` | `-49.06%` | 49 | `1.788` | 有正贡献，但回撤仍严重超标 |
| ETH | Long-only | `1.4431x` | `-71.03%` | 49 | `1.219` | 小幅正终值、尾部风险失控 |
| ETH | Short-only | `1.2201x` | `-65.86%` | 46 | `1.150` | 弱 edge、尾部风险失控 |

第一层因果结论：

1. BTC V1 的 long reclaim/hold/exit 链是显著负贡献，应在 P2-B 中优先拆解，而不是围绕近期 BTC 表现继续微调；
2. BTC short 有历史 edge，但其 `-49.06%` MDD 表明 hard stop、trail、max-hold 与 MA7 迟滞的组合没有形成合格保护；
3. ETH 两条腿都不是单独可靠来源，combined 的正终值来自两条弱且高回撤路径的时序拼接；
4. 当前问题主要是跨 regime 的状态/退出生命周期失效，不是单纯多加手续费或少延迟一天造成。

## 与原 V1 登记窗口的关系

原 V1 约两年窗口为 BTC `2.1234x/-17.96%`、ETH `2.6146x/-29.29%`。本轮扩展历史后 ETH 在同一原窗口可逐位复现；BTC 使用长历史 warm-up 后在原窗口多出一笔早期 short，得到 `2.2422x/-18.03%`。差异来自长历史提供了原冷启动窗口之前的 SMA7/ATR7/pullback 状态，不是参数变化或未来数据 lookahead。

长历史主结论不依赖该锚点差异：无论保留原冷启动指标还是使用真实 warm-up，BTC/ETH 全周期均远低于 `20x`，且 MDD 远超 `20%`。

## P2-A 裁决

- 数据与冻结参数复核：`PASS`
- 零调参长历史复算：`PASS`
- `>=20x` 收益门槛：BTC `FAIL`，ETH `FAIL`
- `MDD<=20%` 门槛：BTC `FAIL`，ETH `FAIL`
- P2-A 总裁决：`HARD-TARGET-FAILED / explore / not promoted / not live-ready`

允许继续的是预注册的 P2-B 全 active-parameter 消融与机制归因；不允许按 researcher-exposed audit 或未来 prospective 结果回头挑参数。

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_shared_v1_long_history_2026-08-12.json) — SHA256 `35614a8ae491f93e6669f386883594d536e94e87c10359498d31ba0a633f667a`
- [指标 CSV](../artifacts/binance_1d_ma7_shared_v1_long_history_2026-08-12_metrics.csv) — SHA256 `59e3a5f4d48152bf83f3dde911406171c0e5311ccc3025cf7442e2d00971a548`
- [逐笔 CSV](../artifacts/binance_1d_ma7_shared_v1_long_history_2026-08-12_trades.csv) — SHA256 `c9a8ab730d3d7e2f8c57bdbf68fe64b251a62e0719a47132885de386beb67042`
- [完整路径 CSV](../artifacts/binance_1d_ma7_shared_v1_long_history_2026-08-12_path.csv) — SHA256 `4d3e3bcd0e8abd23b8efb6e8444350ba55a8f83ec81ee3c9a079f8b06ad4dd34`
- [复现脚本](../scripts/audit_binance_1d_ma7_shared_v1_long_history.py)

