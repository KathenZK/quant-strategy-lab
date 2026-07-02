# BTC-1H-Adaptive-Regime 冻结边界与实盘可执行审计 - 2026-07-02

## 最终结论

`NO-GO / not promoted / not live-ready`。

30 万组搜索的 prefit 冻结冠军没有达到 `10x` 年化门槛；最近三个月 locked OOS 更出现明显反转：年化倍率低于 `1x`、胜率低于 `50%`、回撤超过 `20%`。因此不存在可登记、可交接或可实盘的版本。

## 冻结冠军

- ensemble：`BTC_1H_AR_R199379` + `BTC_1H_AR_R130259`。
- prefit：annual `2.82x`，DD `-18.68%`，win `68.29%`，trades `82`。
- locked OOS：annual `0.17x`，return `-35.74%`，DD `-42.73%`，win `38.46%`，trades `13`。
- full：annual `1.94x`，return `246.95%`，DD `-42.73%`，win `64.21%`，trades `95`。

## 延迟、成本与仓位压力

| Scenario | Full ann | Full DD | Full win | OOS ann | OOS DD | OOS win | Joint gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_k1` | `1.94x` | `-42.73%` | `64.21%` | `0.17x` | `-42.73%` | `38.46%` | `False` |
| `delay_k2` | `0.98x` | `-54.03%` | `54.35%` | `0.39x` | `-33.23%` | `42.86%` | `False` |
| `delay_k3` | `0.95x` | `-65.76%` | `53.68%` | `0.75x` | `-25.32%` | `46.67%` | `False` |
| `slip_8bps` | `1.69x` | `-43.76%` | `63.16%` | `0.16x` | `-43.76%` | `38.46%` | `False` |
| `slip_12bps` | `1.44x` | `-44.74%` | `61.05%` | `0.15x` | `-44.74%` | `38.46%` | `False` |
| `fee12_slip8` | `1.58x` | `-44.75%` | `63.16%` | `0.15x` | `-44.75%` | `38.46%` | `False` |
| `double_cost` | `1.19x` | `-49.14%` | `62.11%` | `0.11x` | `-48.55%` | `38.46%` | `False` |
| `exposure_050x` | `1.44x` | `-23.04%` | `64.21%` | `0.43x` | `-23.04%` | `38.46%` | `False` |
| `exposure_075x` | `1.68x` | `-33.30%` | `64.21%` | `0.27x` | `-33.30%` | `38.46%` | `False` |
| `exposure_125x` | `2.21x` | `-51.33%` | `64.21%` | `0.10x` | `-51.33%` | `38.46%` | `False` |
| `leg_1_only` | `1.33x` | `-25.43%` | `87.76%` | `0.39x` | `-25.43%` | `66.67%` | `False` |
| `leg_2_only` | `1.52x` | `-30.36%` | `39.58%` | `0.38x` | `-30.10%` | `12.50%` | `False` |

## 参数邻域

- one-at-a-time 变体：`73`。
- prefit/full/OOS 联合通过：`0`。
- OOS 回撤仍小于 20% 的变体：`1`；这不代表收益门槛通过。
- 邻域只用于脆弱性审计，OOS 已解锁后不得据此回头挑参数。

## 月度与 bootstrap

- 月度块：`23`，负收益月：`9`。
- bootstrap `10000` 次：annual 5/50/95 分位 `[1.041997358923178, 1.89891773526035, 3.3658756400794956]`；DD 5/50/95 分位 `[-0.570498975234719, -0.3616329960295175, -0.23305893031973107]`；三项硬形状命中率 `0.00%`。
- bootstrap 只能重采样已发生交易，不能修复真实 OOS 失败。

## 实盘可执行审计

- 成交模型可在线表达：闭合 K 信号、下一根 open 市价、入场即有 stop/TP、stop-first、gap-open、单仓不加仓。
- 合约过滤器：tickSize `0.10`，market stepSize `0.001`，min notional `50` USDT。
- 研究仓库当前没有 BTC production runner、交易所订单/仓位对账、重启恢复、missing-bar fail-closed、kill switch 与真实 stop-market 滑点证据。
- 即使补齐 runner，也不能绕过策略本身的 locked OOS 失败；因此不生成 live spec，不登记 V1。

## 证据

- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_boundary_audit_2026-07-02.json`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_audit_scenarios_2026-07-02.csv`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_neighborhood_2026-07-02.csv`
- `research/btc/1h-adaptive-regime/artifacts/btc_1h_adaptive_regime_monthly_2026-07-02.csv`
