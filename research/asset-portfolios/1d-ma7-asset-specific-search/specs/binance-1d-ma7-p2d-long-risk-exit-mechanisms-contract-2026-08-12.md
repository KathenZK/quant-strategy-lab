# Binance 1D MA7 P2-D Long Risk / Exit 机制合同

## 1. 研究身份

- Family：`Binance-1D-MA7-Asset-Specific-Search`
- Campaign：`P2-D long risk/exit mechanisms`
- 状态：`explore / not promoted / not live-ready`
- Parent probe：P2-C long `pullback_reclaim` + exact V1 short
- 证据角色：development-only mechanism ablation；不是 V2，不打开 audit/prospective

## 2. 因果来源

[P2-C episode 归因](../diagnostics/binance-1d-ma7-p2c-long-pullback-episode-attribution-2026-08-12.md) 预先给出两项跨资产证据：

1. `-2 ATR` 几乎不伤害历史赢家，但命中大量亏损单；
2. `ma7_hysteresis_exit` 在 BTC/ETH 上复合因子仅 `0.485x / 0.328x`。

本轮只测试对应机制，不搜索更优阈值，也不加入 profit protection、cooldown、trend age 或 short 改动。

## 3. 冻结臂

| Arm | Long 改动 | Short |
| --- | --- | --- |
| `P0_PULLBACK` | P2-C parent：`entry_mode=pullback_reclaim` | exact V1 |
| `H2_INITIAL_STOP` | parent + `hard_stop_atr=2.0` | exact V1 |
| `X0_STRUCTURE_EXIT` | parent + `exit_confirm_days=1`、`exit_buffer_atr=0.0` | exact V1 |
| `H2_X0_COMBINED` | parent + 上述 `H2` 与 `X0` | exact V1 |

其它 long 字段保持 V1；特别是 slope exit、pullback lookback/touch、entry buffer、仓位和 leverage 不变。

## 4. 数据与执行

- 只运行 `2019-12-24 00:00 UTC` 至 `2025-08-07 00:00 UTC` exclusive；
- fee `0.001/fill`，base slippage `4 bps/fill`，stress `8 bps/fill`；实际 funding；
- closed UTC daily signal、next-open；hard stop 用真实 direct `1h` 路径；
- 约 `1x`，单仓、非加仓，数量持有期固定；
- researcher-exposed audit 与 prospective 继续封存。

## 5. 固定输出

每臂、每资产输出：

- combined 与 long-only；
- base、`8 bps`、额外 `1d` delay；
- full development、calendar-year flat reset、rolling `365d` step `90d`；
- equity、MDD、Sharpe、trades、PF、turnover、成本、funding、最大实际杠杆；
- exit reason counts 与 protective-stop 触发数。

## 6. 裁决顺序

1. 先检查 hard target：BTC、ETH combined 均 `>=20x` 且 MDD `>=-20%`；
2. 未达 hard target 时，不得称 champion；
3. 机制归因另报：相对 P0 是否在两资产同时降低 MDD、是否保留正收益、是否把损失转移到更差 rolling/year block；
4. 只有某机制在两资产同时降低 MDD 至 `<=35%`、base/stress/delay 均为正、且最差 calendar year 与 rolling 正收益比例改善，才允许作为下一轮组合基础；该软门只允许继续研究，不代表 V2 资格；
5. 若三臂均失败，关闭当前 risk/exit 修复路径；不得在看到结果后追加 `1.5/2.5/3 ATR` 或其它 MA buffer。

## 7. 交付边界

- 输出 JSON/CSV 与中文 diagnostic；
- 本轮不生成 HTML、不登记版本、不更新 core ledger 状态、不创建 live spec、不推进 runner。

