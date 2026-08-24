# Binance-1D-BTCETH-Crisis-Override-Shadow-Trend V1 规格

## 身份与证据角色

- Family：`Binance-1D-BTCETH-Crisis-Override-Shadow-Trend`
- Version：`V1`
- Alias：`BIN-1D-BE-COST-V1`
- 状态：`registered / not promoted / not live-ready`
- 市场/周期：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual；日线信号、真实 `1h` 路径执行与风险计量
- 登记日期：`2026-08-14`
- 证据角色：只登记 2026-08-12 已揭示 development 搜索的最佳增长路径；不是 clean OOS，不构成 promotion

V1 的登记只固定策略身份和参数。P0 的 `HARD-GATE-FAILED` 裁决不变，research line 仍关闭；本规格不授权 live spec、runner handoff、dry-run 或 live。

## 冻结参数

### CBCT P1 growth shadow

| 参数 | V1 |
| --- | ---: |
| `entry_lookback` | `20` |
| `exit_lookback` | `10` |
| `trend_ema` | `50` |
| `trail_atr` | `5` |
| `confirm_days` | `2` |
| `cooldown_days` | `7` |
| `max_hold_days` | `120` |
| `profit_protection_activation_atr` | `1` |
| `profit_protection_giveback` | `35%` |
| `profit_protection_confirm_days` | `2` |

### Crisis override

| 参数 | V1 |
| --- | ---: |
| `crisis_ema` | `200` |
| `slope_days` | `60` |
| `confirm_days` | `3` |
| crisis BTC short weight | `50%` equity |
| crisis ETH short weight | `50%` equity |
| account gross target | `<=1x` |

## 信号与账户路由

- Shadow 始终按冻结 CBCT P1 规则独立推进；账户分配不反向改变 shadow 状态。
- 对 BTC/ETH 分别计算完整日线 `EMA200`。两资产同时 `close<EMA200`，且各自 `EMA200[t]<EMA200[t-60]` 时，raw state 为 crisis。
- raw state 连续 `3` 个完整 UTC 日与当前 state 不同才切换；闭合日确认，下一 UTC 日 open 生效。
- Normal：账户 flat 时只复制下一笔 fresh shadow entry，并跟随其冻结 exit timestamp/reason；约 `1x` 单仓。
- Crisis enter：下一 open 先平账户已有 shadow position，再以当时总权益各 `50%` 建 BTC/ETH short；两腿合计初始 gross 约 `1x`。
- Crisis hold：不 resize、不加仓、无额外 stop/TP；只计价格、真实手续费、滑点和 funding。
- Crisis exit：下一 open 同时平两腿并转 flat；同一 open 不接回 shadow，之后只等待 fresh shadow entry。
- Crisis basket 与 shadow 仓位互斥，不允许 gross 叠加。

## 执行、成本与数据边界

- 日内顺序：日开盘路由/订单 → funding → shadow intrahour stop → favorable → adverse → close。
- 所有日线状态只使用闭合 K 线并在下一 open 执行；dual-short ordered risk 使用两腿 low/high 的保守同现假设。
- 手续费 `0.001/fill`；base/stress 滑点分别 `4/8 bps/fill`；funding 使用 Binance event-time actual funding。
- 冻结 development 窗口：`[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` sealed，未读取。
- prospective 未读取、未回填；既有 prospective 锚点不因 V1 登记而重置或打开。
- terminal open 强制平掉所有账户仓位。

## 冻结 development 指标

| 场景 | Equity multiple | Ordered MDD | 其他 |
| --- | ---: | ---: | --- |
| Base | `23.132090x` | `-35.2226%` | 24 笔 shadow + 3 个 crisis episodes；27 笔账户交易 |
| Stress `8bps` | `22.655605x` | `-35.2226%` | log-growth retention `99.34%` |
| Delay `+1d` | `7.274619x` | `-36.9956%` | log-growth retention `63.17%` |

- Crisis：3 episodes / 6 asset legs；`override_base_exits=0`。
- 完整年正收益比例 `80.00%`；rolling 365d 正收益比例 `88.90%`。
- 最大单笔正 log-growth 占比 `39.25%`。
- Base 收益超过 `20x`，但 MDD、delay 和集中度门禁失败；P0 为 `0` hard-pass。

## 决策边界

- V1 固定为 BTC/ETH 账户级组合策略，不能拆成“BTC 单独使用”或“ETH 单独使用”的同一版本。
- 改动任一 shadow 参数、crisis 参数、资产权重、gross、执行顺序或成本模型，都不再是 V1。
- 当前最大风险来自 `2020-10-21` 至 `2021-02-18` BTC 盈利 long 的持仓内回吐；不得在 COST 内追加 stop/TP 或继续救参。
- 如研究 partial-profit runner，必须另立 family；如尝试 promotion，必须另获用户授权并完成 clean prospective OOS、runner parity、执行时序和线上对账门禁。

## 证据

- [P0 冻结合同](binance-1d-be-cost-p0-contract-2026-08-12.md)
- [P0 裁决](../diagnostics/binance-1d-be-cost-p0-2026-08-12.md)
- [机器摘要](../artifacts/binance_1d_be_cost_p0_2026-08-12.json)
- [V1 完整交易路径](../artifacts/binance_1d_be_cost_v1_trade_path_2026-08-14.html)
- [V1 路径渲染脚本](../scripts/render_binance_1d_be_cost_v1_trade_path.py)
- [主账](../binance-1d-be-cost-core-ledger.md)
