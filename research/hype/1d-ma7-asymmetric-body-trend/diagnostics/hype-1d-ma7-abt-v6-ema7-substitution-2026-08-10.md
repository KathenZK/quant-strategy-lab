# HYPE-1D-MA7-ABT-V6 EMA7 替换诊断

## 结论

只把 V6 的 `MA7` 全部替换为 `EMA7` 后，结果为 **`FAIL / diagnostic-only / not promoted / not live-ready`**。

EMA7 把 exact V6 从 `+617.11% / -18.39%` 变成 `-24.54% / -62.30%`，
交易数从19笔增至35笔，且逐笔行为和 handoff 事件均发生改变。V6 继续固定 SMA7；
本轮不登记 V7，不继续搜索 EMA span，不生成交易路径 HTML。

## 冻结口径

- Control：exact V6 `PEHC_294`，使用原 `SMA7`。
- Candidate：只将 `features.ma7` 替换为 `EMA(span=7, adjust=False, min_periods=7)`。
- `ATR7`、`RSI6`、OAPP、PEHC shadow/handoff、保护止损、cooldown、max hold、
  手续费、滑点、funding、signal lag 与单仓约束全部不变。
- 数据：Binance USD-M `HYPEUSDT` perpetual，`2025-05-31` 至 `2026-08-05 UTC`
  共432个完整日；风险回放使用真实 `1h` 顺序。

## 主结果

| 指标 | SMA7 V6 | EMA7 替换 |
| --- | ---: | ---: |
| 成本后收益 | `+617.11%` | `-24.54%` |
| 折算年化 | `+428.31%` | `-21.17%` |
| 真实顺序 1h MDD | `-18.39%` | `-62.30%` |
| 日内极值 MDD | `-20.27%` | `-62.79%` |
| Sharpe | `3.207` | `-0.152` |
| Profit Factor | `12.878` | `0.856` |
| 胜率 | `84.21%` | `54.29%` |
| 交易数（long / short） | `19 (10 / 9)` | `35 (15 / 20)` |
| 最大 marked leverage | `1.20x` | `1.33x` |
| 成本 / 初始权益 | `15.04%` | `10.62%` |
| funding / 初始权益 | `-0.55%` | `+0.49%` |

EMA7 不是“更快但收益少一点”，而是把 V6 的核心路径改坏：收益少 `641.64pp`，
真实 `1h` MDD 多 `43.90pp`，交易数多16笔。

## 压力与切片

- `8 bps`：EMA7 `-26.63% / -62.95%`，继续双劣。
- funding-off：EMA7 `-24.19% / -62.42%`，继续双劣。
- 额外一日 signal lag：EMA7 `+69.47% / -52.32%`，虽然转正，但仍双劣于同口径V6。
- 8个54日 cold-flat block：EMA7 复合 `+19.29%`，V6为 `+689.87%`；EMA7有6个block双劣。
- 13个90日滚动窗口：EMA7 复合 `+39.54%`，V6为 `+22,241.67%`；EMA7有11个窗口双劣。
- 24个日界相位：EMA7仅 `6/24` 为正，中位收益 `-22.27%`，最差收益 `-68.01%`，
  最差MDD `-79.68%`，22个相位双劣。

| 最近切片 | EMA7收益 | 1h MDD | 平仓 |
| --- | ---: | ---: | ---: |
| `1d` | `+3.12%` | `-1.78%` | 1 |
| `7d` | `+3.12%` | `-1.78%` | 1 |
| `1m` | `+5.86%` | `-8.31%` | 3 |
| `3m` | `-13.69%` | `-28.63%` | 7 |
| `6m` | `-42.48%` | `-52.54%` | 15 |
| `1y` | `-34.15%` | `-62.30%` | 30 |

近期短窗转正不改变全窗和滚动失败。

## 链条变化

EMA7 改变了 V6 的行为路径：

- `long_trail_exit`：`-1`
- `short_rsi_exit`：`-1`
- `shadow_start`：`-1`
- `handoff_accept`：`0`
- `protective_stop`：`+6`

保护止损从3次增至9次，说明 EMA7 的更快响应没有改善风险识别，反而让入场/退出链条更容易落入坏路径。
它还减少了 V6 的 long MFE 与 short RSI 保护事件，并改变 shadow/handoff 事件序列。

## 机制解释

EMA7 会更贴近价格，因此 raw cross 和斜率判断更容易提前或反复触发。但 V6 的阈值、
OAPP 和 PEHC 都是围绕 SMA7 的滞后/平滑特性形成的；直接换 EMA7 等于改变整条状态机的时间常数。
结果不是“更敏捷”，而是更多交易、更差时序、更多保护止损和更大的相位脆弱性。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v6-ema7-substitution-contract-2026-08-10.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v6_ema7_substitution_2026-08-10.json)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v6_ema7_substitution.py)
