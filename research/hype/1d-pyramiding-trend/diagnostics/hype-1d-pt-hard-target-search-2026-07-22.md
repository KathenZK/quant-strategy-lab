# HYPE-1D-Pyramiding-Trend 硬目标广搜（2026-07-22）

## 结论

本轮没有找到同时满足以下三项硬条件的 HYPE 日线浮盈加仓趋势策略：年化权益倍数 `>=20.0x`、净胜率 `>=80%`、保守最大回撤 `<=20%`。在 `398,456` 个不重复配置中，prefit 三项数值同时命中数为 `0`；因此不登记版本，状态保持 `explore / not promoted / not live-ready`。

即使只看 prefit 且先锁死回撤上限，最高年化权益倍数也只有 `3.0346x`，不是接近 `20x` 的边缘失败。`20x` 年化等价于约 `1900% CAGR`；冻结 shortlist 中最好的可生存 full observation 只有 `2.4818x` 年化因子（约 `148.18% CAGR`）。

## 冻结契约与数据

- 市场：Binance USD-M `HYPEUSDT` perpetual；UTC `1d`。
- 日线输入：标准数据湖 `1h` raw/normalized K 线聚合；只保留恰好 24 根已收盘小时 K 的 UTC 自然日。
- 小时数据：`2025-05-30 10:00` 至 `2026-07-22 07:00 UTC`，`10,030` 根，缺口/重复/关键空值/raw-normalized 差异均为 `0`。
- 完整日线：`2025-05-31` 至 `2026-07-21`，共 `417` 根；以 `2026-07-22 00:00 UTC` open 作为终点执行/估值价。
- prefit：至 `2026-04-22 00:00 UTC`；锁定 OOS：`2026-04-23` 至 `2026-07-22`，固定最后 90 天；OOS 未参与参数排序。
- 仓位：初始 `1x`，仅在 campaign 浮盈且继续跨过 ATR 台阶后，允许两次各 `1x` 加仓，绝对上限 `3x`。
- 成本：手续费 `0.001/fill`、基础不利滑点 `4 bps/fill`、实际 funding；另审计 `8 bps` 与 `K+2` 延迟。
- 成交：日 K 收盘计算，下一日 open 执行；胜率按完整 campaign 统计，加仓 fill 不拆成新胜单。
- 回撤：按日内 high/low 的保守峰谷顺序计入潜在回撤，并包含成本和 funding。

完整冻结口径见[搜索契约](../specs/hype-1d-pt-search-contract-2026-07-22.md)，机器结果见[搜索摘要](../artifacts/hype-1d-pt-search-2026-07-22.json)与[prefit frontier](../artifacts/hype-1d-pt-prefit-frontier-2026-07-22.csv)。

## Frontier 对比

| Observation | Window | 年化因子 | 净胜率 | 保守 MDD | 已平 campaign | 浮盈加仓次数 | 判断 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| prefit joint-nearest | prefit | `4.4838x` | `90.91%` | `-25.52%` | 11 | 7 | 收益、回撤均失败 |
| prefit joint-nearest | locked OOS | `1.0565x` | `75.00%` | `-20.11%` | 8 | 1 | 三项均失败 |
| prefit joint-nearest | full | `3.2485x` | `84.21%` | `-25.52%` | 19 | 8 | 收益与回撤失败 |
| prefit DD-safe return leader | prefit | `3.0346x` | `80.00%` | `-18.58%` | 10 | 3 | 只有收益失败 |
| prefit DD-safe return leader | locked OOS | `0.3894x` | `33.33%` | `-27.21%` | 6 | 0 | OOS 崩溃 |
| full survival observation | prefit | `2.2758x` | `80.00%` | `-18.51%` | 10 | 2 | 收益失败 |
| full survival observation | locked OOS | `3.4303x` | `71.43%` | `-19.62%` | 7 | 1 | 收益与胜率失败 |
| full survival observation | full | `2.4818x` | `76.47%` | `-19.62%` | 17 | 3 | 收益与胜率失败 |
| high-win EMA observation | full | `1.6113x` | `92.31%` | `-19.23%` | 13 | 2 | 收益失败；OOS 未发生加仓 |

`full survival observation` 是冻结 shortlist 中最接近“守住回撤”的折中面，不是合格策略。其核心为双向 80 日时序动量 + EMA40/55 trend filter，ATR5，ADX20 `>=10`，初始 `1x`，浮盈每跨 `3 ATR` 加一层，最多 `3x`，3 日反向 channel / `1 ATR` trail / `0.5 ATR` profit-lock，最长持有 10 日、退出后冷却 7 日。完整参数保存在搜索摘要中。

## 生存 observation 的近期切片

以下是 full 连续路径的 open-to-open 近期切片，仅作审计；硬回撤判断仍使用上表更保守的日内峰谷口径。

| 切片 | 净收益 | open-to-open MDD | 终点仓位 |
| --- | ---: | ---: | ---: |
| 1d | `-2.55%` | `-2.55%` | `+1x` |
| 7d | `-2.69%` | `-2.69%` | `+1x` |
| 1m | `-1.76%` | `-8.01%` | `+1x` |
| 3m | `+35.50%` | `-13.88%` | `+1x` |
| 6m | `+105.06%` | `-13.88%` | `+1x` |
| 1y | `+182.29%` | `-13.88%` | `+1x` |

其 `8 bps` full 结果仍为 `2.4463x / 76.47% / -19.78%`，但 `K+2` 延迟恶化到 `1.2550x / 70.59% / -32.08%`，说明执行延迟稳健性也不成立。

## 基准与风险解释

同期 1x 永续买入持有（相同手续费、滑点、funding）终值约 `1.6747x`、年化因子 `1.5709x`，保守日内 MDD `-67.01%`；3x 买入持有终值仅 `0.2252x`，保守日内 MDD 会穿过 `-100%`。HYPE 样本内虽有强趋势，但日级反转幅度足以让 `3x` 暴露与 `20%` 回撤上限发生直接冲突。

## 决策

- 不把 joint-nearest、DD-safe leader 或 survival observation 包装成满足要求的策略。
- 不登记 `V1`，不写 live spec，不交接 runner。
- 本轮可以在新增日线历史后按原冻结机制重验；若目标必须保持不变，更合理的下一研究方向是降低信号周期或使用多资产/多策略组合分散，而不是继续在 417 根日 K 上扩大参数自由度。
