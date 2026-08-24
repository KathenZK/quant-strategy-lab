# HYPE-1D-MA7-SNC02 风险覆盖 OAT 冻结合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / explore / not promoted / not live-ready`。本合同在首次运行候选结果前写入；结果揭示后不得修改阈值并重称预注册结果。

## 1. 研究问题与边界

冻结 [SNC02 裸信号合同](hype-1d-ma7-symmetric-naked-cross-slope-diagnostic-contract-2026-08-20.md) 的入场核：多空镜像 `fresh SMA7 cross + 1d directional slope >= 0.02ATR7`，下一 UTC 日 open 成交。只测试单一风险/利润覆盖层，不修改 `SMA7/ATR7`、cross、slope、成本、funding、目标 `1x` 或 V7.1 身份。

本轮所有历史均已揭示，只能做机制归因；不登记版本、不promotion、不修改runner。Stage A 只运行 control 与五个固定 OAT 臂，不根据 Stage A 结果临时拼接组合。

## 2. 固定实验臂

| Arm | 唯一变化 |
|---|---|
| `CTRL_SNC02` | exact SNC02；仅镜像合格信号翻仓 |
| `FF3` | 开仓日记作 held day 1；held day `1..3` 内，long 若 `close < SMA7` 且 `SMA7[t]-SMA7[t-1] <= 0`，short 镜像，则下一 UTC open 全平 |
| `MA05` | long 若 `close < SMA7 - 0.5ATR7` 且 SMA7 单日 slope `<=0`，short 镜像，则下一 UTC open 全平 |
| `HS25` | 入场后固定灾难止损：long `entry - 2.5*entry_ATR7`，short 镜像；`entry_ATR7` 取生成入场信号的完整日值，不追踪 |
| `BE20` | 入场后任一完整日 directional close-MFE 达到 `2.0*entry_ATR7`，从下一 UTC open 起把止损提高到成本后净保本价；只激活一次，不追踪 |
| `PT25_A3` | 入场后任一完整日 directional close-MFE 达到 `3.0*entry_ATR7`，下一 UTC open 精确卖出/买回当时数量的 `25%`；每笔最多一次，余仓数量固定并仍仅按镜像合格信号退出 |

成本后净保本参考价固定为：long `entry*(1+c)/(1-c)`，short `entry*(1-c)/(1+c)`，其中 `c=fee+slippage`。该公式只覆盖一进一出成本，不承诺覆盖 funding；报告另列实际净 PnL。

## 3. 事件优先级与可执行成交

### 3.1 日线收盘后

1. 若出现与当前仓位相反的 SNC02 合格信号，下一 UTC open 先平旧仓再以 `1x` 开反向仓；它优先于 FF3、MA05、BE20 激活与 PT25。
2. 无反向合格信号时，FF3/MA05 的全平优先于 PT25 降仓。
3. flat 时只有新的 SNC02 fresh qualified signal 才能重新入场；风险退出不自动反手、不保留 stale pending。
4. 日线条件额外 `1d lag` 压力时统一再延迟一个完整日；期间仍暴露于已有小时止损，若仓位先被止损则取消该 pending action。

### 3.2 小时止损

- 使用已闭合 Binance HYPEUSDT perpetual `1h` OHLC；stop 在入场小时即可生效。
- long：若小时 open `<= stop`，按该 open 成交；否则若小时 low `<= stop`，按 stop 成交。short 完全镜像。
- 成交价仍另扣手续费 `0.001/fill` 与不利滑点；不允许 crossed stop 仍按旧 stop 填单。
- 同一小时只存在单侧 stop，不使用小时 high/low 的先后顺序选择更优结果。

### 3.3 部分止盈

`PT25_A3` 在下一 UTC open 把当时 quantity 乘以 `0.75`，并对减少的 `25%` 名义收取成本；不按当前权益重新加仓。它是一次 resize，不拆成已结算子交易；整笔 campaign 的净 PnL 包含 resize 成本、余仓 PnL 与 funding。

## 4. 数据、成本与窗口

- 市场：Binance USDⓈ-M perpetual `HYPEUSDT`；信号 `1d`，风险路径 `1h`，UTC。
- 主窗：现有扩展数据 `2025-05-31 -> 2026-08-20 terminal`；同时报告 canonical `2025-05-31 -> 2026-08-06`。
- 成本：手续费 `0.001/fill`，基础滑点 `4bps/fill`，实际 funding；另做 `8bps`、funding-off、额外 `1d lag`。
- 最近 flat-start：`1d/7d/1m/3m/6m/1y`；年度 flat-start：2025 partial、2026 YTD。
- 风险：按小时 open、funding pre/post、实际 stop/resize/entry/exit 顺序计算 chronological `1h` MDD；不得用逐笔或日收盘 MDD替代。

## 5. 首次运行前冻结的判定

每个 arm 分别报告：净收益、真实 `1h` MDD、胜率、PF、交易数、成本、funding、暴露率、多空贡献、退出/resize触发数、最近08-09 long行为及压力结果。

- `MDD20_PASS`：扩展窗 chronological `1h MDD >= -20%`。
- `RISK_OVERLAY_PASS`：同时满足 MDD20、扩展窗净收益 `>0`、PF `>=1`、`8bps`净收益 `>0`、额外 `1d lag`净收益 `>0`。
- `DUAL_IMPROVEMENT`：相对 exact control 净收益更高且 MDD更小；只作 Pareto 标签。
- 任一候选即使通过也仍是 `post-reveal diagnostic`，不能据此登记或上线；Stage B 组合必须另立新合同。

## 6. 产物

- 研究脚本：`scripts/research_hype_1d_ma7_snc02_risk_overlay_oat.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_risk_overlay_oat_2026-08-20.json`
- 诊断报告：`diagnostics/hype-1d-ma7-snc02-risk-overlay-oat-2026-08-20.md`
