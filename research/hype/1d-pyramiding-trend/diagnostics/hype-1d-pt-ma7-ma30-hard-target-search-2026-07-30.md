# HYPE-1D-Pyramiding-Trend MA7/MA30 硬目标搜索（2026-07-30）

## 结论

本轮没有找到同时满足 `HYPEUSDT` 日级别、固定 `MA7/MA30`、下单目标杠杆不超过 `3x`、年化权益倍数严格大于 `20x`、保守最大回撤不超过 `20%` 的策略。

`496,050` 个不重复 prefit 配置中：

- `年化因子 >20x 且 MDD <=20%` 的数值命中数为 `0`；
- 同时满足交易数、实际发生浮盈加仓和杠杆上限的证据命中数也为 `0`；
- 锁住 `MDD <=20%` 后，未经交易数筛选的最高 prefit 年化因子仅 `2.2994x`；
- 放弃回撤限制后的最高 prefit 年化因子为 `18.9026x`，仍没有严格超过 `20x`，且对应 MDD 为 `-63.38%`。

因此本轮硬目标判定为 **NO-GO（研究决策语义）**。按仓库状态机，本家族仍是 `explore / not promoted / not live-ready`，不登记版本、不写 live spec、不交接 runner。

## 数据、冻结边界与成本

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 原始数据：`10,219` 根已收盘 `1h` K，`2025-05-30 10:00` 至 `2026-07-30 04:00 UTC`；缺口、重复、关键空值、OHLC 异常、raw/normalized 差异均为 `0`。
- 日线：只保留完整 `24` 根小时 K 的 UTC 自然日，共 `425` 根，`2025-05-31` 至 `2026-07-29`；终点 open 为 `2026-07-30 00:00 UTC`。
- prefit：至 `2026-04-30 00:00 UTC` open（exclusive）；`2026-04-30` 为 embargo。
- 锁定 holdout：`2026-05-01` 至 `2026-07-30 UTC`，flat-start，不参与排序。
- 限制：该 holdout 与 2026-07-22 同家族研究区间大幅重叠，只能称为 `researcher-exposed locked holdout`，不是研究者从未见过的纯净 OOS。
- 成本：每次成交按名义收取手续费 `0.001`、基础不利滑点 `4 bps`、实际 funding；另审计 `8 bps` 与 `K+2`。
- 杠杆账本：持仓数量在实际成交之间固定；只有入场、加仓、减仓和平仓改变数量并收费，不使用“每天免费把收益乘以 1/2/3”的近似。

完整规则见[冻结搜索契约](../specs/hype-1d-pt-ma7-ma30-search-contract-2026-07-30.md)，机器结果见[搜索摘要](../artifacts/hype-1d-pt-ma7-ma30-search-2026-07-30.json)与[prefit frontier](../artifacts/hype-1d-pt-ma7-ma30-prefit-frontier-2026-07-30.csv)。

## 用户示例

首要示例采用 SMA：

1. `MA7` 上穿 `MA30`，且 `close > MA7`、`MA7` 上行，下一日 open 做多；
2. `MA7` 下穿 `MA30`，且 `close < MA7`、`MA7` 下行，下一日 open 做空；
3. 收盘反向穿越 `MA7` 先退出；反向交叉允许下一 open 净翻仓；
4. 初始 `1x`，浮盈超过 `1 ATR7` 且仍沿 `MA7` 时重置到 `3x`。

| 窗口 | 净收益 | 年化因子 | 保守 MDD | campaign | 胜率 | 加仓 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| prefit | `-78.72%` | `0.1841x` | `-81.77%` | 12 | `0.00%` | 2 |
| researcher-exposed holdout | `-39.19%` | `0.1329x` | `-42.71%` | 7 | `0.00%` | 0 |
| full | `-87.06%` | `0.1725x` | `-89.14%` | 19 | `0.00%` | 2 |

浮盈加仓不是唯一问题：禁用加仓后的 full 结果仍为 `0.3706x` 年化因子、`-70.52%` MDD、19 个 campaign 中 1 个盈利。原始“只在交叉点追随、跌破/升破 MA7 就退出”的结构在这段日线历史中反复买在短期高点、卖在短期低点，不能继续微调包装。

## 替代机制搜索

固定 `7/30` 均线长度不变，搜索了：

- SMA / EMA；
- cross-only、regime-follow、MA7 reclaim、MA 趋势内 Donchian breakout；
- 双向、long-only、short-only；
- `1–3` 天趋势确认、MA7 斜率、ATR buffer、ADX 与波动率上限；
- 反向交叉、MA7/MA30、斜率反转、timeout 退出；
- 前一收盘即可确定的 ATR stop、trailing、profit lock；
- 初始 `0.5–1.5x`；
- `layers` 与盈利后 `reset_to_3x` 两种加仓语义。

第一阶段为 `300,005` 个不重复配置，第二阶段围绕联合、回撤安全、纯收益和最低回撤四类 prefit 前沿再搜索 `196,170` 个不重复配置。固定 seed 为 `20260730`；holdout 未用于父候选、变异或排序。

## 代表性冻结 observation

| Observation | 窗口 | 年化因子 | 保守 MDD | campaign | 胜率 | 加仓 | 判断 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 回撤安全证据冠军 | prefit | `2.0340x` | `-18.14%` | 9 | `44.44%` | 5 | 收益失败 |
| 回撤安全证据冠军 | holdout | `4.2565x` | `-24.44%` | 5 | `60.00%` | 1 | 收益、回撤失败 |
| 回撤安全证据冠军 | full | `2.4500x` | `-24.44%` | 13 | `53.85%` | 6 | 收益、回撤失败 |
| 纯收益冠军 | prefit | `18.9026x` | `-63.38%` | 10 | `80.00%` | 8 | 收益仍未严格超过 20x，回撤严重失败 |
| 纯收益冠军 | holdout | `16.7981x` | `-57.78%` | 5 | `60.00%` | 4 | 收益、回撤失败 |
| 纯收益冠军 | full | `18.3089x` | `-63.38%` | 15 | `73.33%` | 12 | 收益、回撤失败 |
| 联合 primary | prefit | `4.1466x` | `-26.66%` | 8 | `50.00%` | 4 | 收益、回撤失败 |
| 联合 primary | holdout | `4.7059x` | `-33.82%` | 5 | `40.00%` | 2 | 收益、回撤失败 |
| 联合 primary | full | `4.2450x` | `-33.82%` | 13 | `46.15%` | 6 | 收益、回撤失败 |

回撤安全证据冠军是 EMA7/EMA30 long-only、三日确认后的 MA7 reclaim、初始 `0.5x`、分层加仓、10 日 timeout 的观察项。它只用于说明可生存前沿，不是合格策略。

纯收益冠军以 `0.5x` 入场、盈利后重置 `3x`，prefit 已有 `-63.38%` MDD；持仓逆向波动时有效杠杆最高漂移到约 `6.86x`。它展示了“接近 20x”只能通过接受远超 20% 的风险得到，不能推荐。

## 消融、延迟与滚动窗口

联合 primary 的 prefit 消融显示：

- 禁用浮盈加仓后，年化因子从 `4.1466x` 降至 `1.2297x`，MDD 从 `-26.66%` 改善到 `-10.35%`。加仓扩大收益，也直接破坏回撤门槛，但仍远不足以达到 `20x`。
- 禁用 10 日 timeout 后，年化因子降至 `1.1653x`、MDD 恶化到 `-48.56%`，timeout 是有效风控。
- `ADX=0`、无固定 stop、无 trailing 的开关与 full campaign 边界相同，属于当前 primary 的 dormant 槽；若未来登记必须删除，而不能把它们当 alpha。
- primary 的 full `K+2` 结果为 `0.9327x` 年化因子、`-54.26%` MDD，延迟稳健性失败。

90 天滚动审计存在年化因子超过 `20x` 的窗口，但对应 MDD 至少约 `-23.47%` 或 `-33.82%`，且只有 `4–5` 个 campaign；另有多个零交易窗口。短窗口复利年化不能替代完整样本、回撤和交易数门槛。

消融、滚动窗口和 primary 路径分别见[消融 CSV](../artifacts/hype-1d-pt-ma7-ma30-prefit-ablation-2026-07-30.csv)、[滚动审计 CSV](../artifacts/hype-1d-pt-ma7-ma30-rolling-audit-2026-07-30.csv)、[交易 CSV](../artifacts/hype-1d-pt-ma7-ma30-primary-trades-2026-07-30.csv)和[路径 CSV](../artifacts/hype-1d-pt-ma7-ma30-primary-path-2026-07-30.csv)。

## 已处理边界

- `MA7 == MA30`、均线/ATR warmup 不足、价格确认与均线方向冲突：保持 flat。
- 同一收盘退出与加仓冲突：退出优先，加仓取消。
- 反向交叉：下一 open 先结束旧 campaign；允许 flip 时用净翻仓成交，不同时保留多空。
- holdout：flat-start，不继承 prefit 仓位、pending order、峰值、冷却或加仓状态。
- 浮盈加仓：campaign 净浮盈、价格相对加权入场价盈利、MA7/MA30 方向和沿 MA7 条件必须同时成立。
- 止损：只能使用前一已收盘日可知的价格；若开盘跳空穿过止损，按 open 立即成交，不读取当日后续极值。
- 终点：不允许在 terminal open 新开或加仓；已有仓位强制平仓并计成本。

## 决策与后续

- 不把任何 observation 登记为 `V1`。
- 不继续使用已揭示 holdout 调参。
- 若硬目标不变，下一次有效尝试必须是新增的 prospective OOS，或明确改为新的机制/周期/多资产组合；继续在 `425` 根日 K 上增加自由度只会扩大选择偏差。
- 若仍坚持 `MA7/MA30 + HYPE 1D + 3x`，当前诚实结论是：没有找到满足 `>20x / <=20% MDD` 的可推荐策略。

复现命令：

```bash
uv run python research/hype/1d-pyramiding-trend/scripts/research_hype_1d_ma7_ma30.py \
  --seed 20260730 --stage1 300000 --stage2 200000 \
  --shortlist 160 --workers 8 --run-date 2026-07-30
```
