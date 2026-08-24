# Binance-1D-Generic-MA7-Trend-v0 冻结研究规格

## 身份与冻结边界

- Full name：`Binance-1D-Generic-MA7-Trend-v0`
- Alias：`BIN-1D-GMA7T-V0`
- 主状态：`explore / not promoted / not live-ready`
- 角色：冻结的跨资产研究合同；不是 `HYPE-1D-MA7-ABT-V7.1` 的新版本，也不修改其身份。
- 冻结日期：`2026-08-18`；本任务的 current-market-cap universe 回测结果在冻结时尚未生成。
- 参数唯一机器源：[冻结配置](../configs/binance-1d-generic-ma7-trend-v0.json)。

`v0` 只回答“去除 HYPE 专属状态链后是否仍存在可迁移的 MA7 trend core”。它不以单币或全池最高收益为目标，任何回测、扰动或分币结果都不得回写参数。

## 对称趋势核心

令完整 UTC 日 `t` 的收盘为 `C_t`：

```text
SMA7_t = mean(C_{t-6}, ..., C_t)
TR_t   = max(H_t-L_t, abs(H_t-C_{t-1}), abs(L_t-C_{t-1}))
ATR7_t = mean(TR_{t-6}, ..., TR_t)
```

多头 reclaim：

```text
C_{t-1} <= SMA7_{t-1}
and C_t > SMA7_t
and (SMA7_t - SMA7_{t-1}) / ATR7_t >= 0.02
```

空头严格镜像：

```text
C_{t-1} >= SMA7_{t-1}
and C_t < SMA7_t
and (SMA7_t - SMA7_{t-1}) / ATR7_t <= -0.02
```

信号只使用完整日 K；最早在 `t+1 00:00 UTC` open 成交。单资产同一时刻最多一仓，目标名义 `1x`，不加仓。

## 对称退出与风险

- 日线退出：long 在 `C_t < SMA7_t - 0.75*ATR7_t`、short 在 `C_t > SMA7_t + 0.75*ATR7_t` 时，于下一 UTC 日 open 退出。
- 固定 hard stop：entry reference 的反方向 `1.5*entry_ATR7`。
- trailing stop：上一完整日为止的最有利日收盘，反方向 `1.5*ATR7`；日收盘后更新，下一小时起生效。
- 真实 `1h` replay：逐小时按 high/low 首次触发；若该小时 open 已跳过 stop，按该 open 再计不利滑点，否则按 stop 价再计不利滑点。
- 同一小时只存在同方向的 hard/trailing 合成保护价，选择离市价更近的有效保护价；没有 TP/SL 同时命中的歧义。
- 不设 slope exit、max hold、cooldown、forced reversal、OAPP、short RSI 或 PEHC。

## 成本与总账

- 主净值：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、真实 Binance funding timestamp/rate。
- Gross：同成交路径的零手续费、零滑点、funding off 对照。
- 压力：不利滑点 `8 bps/fill`，手续费与 funding 不变。
- Funding 在事件时刻仅对真实持仓结算；mark 使用事件所在 `1h` close 近似，并逐笔归入对应 trade。
- 输出同时保存真实 `1h` 顺序 MDD 与日末收益序列；年化因子为 `365`。

## Universe 冻结规则

1. 运行时调用 CoinGecko `/coins/markets`，以 `usd`、`market_cap_desc` 抓取快照并保留原始字段、抓取 UTC 和 SHA256。
2. 按 rank 扫描，排除 fiat/commodity 稳定币、收益型美元锚定资产、包装币、tokenized fund/credit exposure，并把同一底层经济暴露只保留一次；取得前 30 个非稳定、非锚定、非包装的独立 crypto exposures。
3. 与运行时 Binance USD-M `quoteAsset=USDT`、`contractType=PERPETUAL`、`status=TRADING` 取交集；`1000SHIBUSDT` 只作为 SHIB 的合约单位映射，不是第二个经济暴露。
4. 每个合约至少需要 `365` 个连续已闭合 UTC 日 K 及对应连续 `1h` K；最多回测最近 `730` 日。历史不足、缺 K、重复、非法 OHLC、非 closed bar 或 funding 请求失败均 fail closed。
5. 不向 rank 30 以外回填以凑数。最终不足 30 时如实报告；这是 **current-top30 retrospective backtest**，不是历史动态成分回测，存在 survivorship bias。

## 组合与统计

- 单币完全使用同一 v0 参数。
- 组合使用仓库既有 EWMAC 组合口径：资产层 inverse-vol equal-risk，20 日 EWMA half-life，全部只用 `T-1` 信息；组合再以 20 日 EWMA 波动率目标到年化 `20%`，gross cap `3x`，不基于事后盈利筛币。
- 报告每币 gross/net、CAGR、Sharpe、Sortino、MDD、Calmar、PF、交易数、胜率、平均持仓、long/short 交易与 PnL contribution；全池均值/中位数、正 Sharpe/PF>1 比例、年份/季度与 recent slices。
- Leave-one-asset-out 只重算冻结组合，不选择资产。

## 稳定性检查（禁止选择）

仅做 one-at-a-time、约 `±20%` 的预注册扰动：`MA 6/7/8`、`ATR 6/7/8`、slope `0.016/0.020/0.024`、exit buffer `0.60/0.75/0.90`、protective/trail `1.20/1.50/1.80`。所有扰动都在完整冻结 universe 上报告横截面分布；不得按最优值登记 v0.1 或回写 v0。

## 对照与裁决问题

- A：exact `HYPE-1D-MA7-ABT-V7.1` 在 HYPE 当前共同窗口。
- B：Generic v0 在 HYPE 同窗。
- C：Generic v0 在冻结 market-cap universe。
- 最终只回答：generic core 是否存在、多少资产有正期望迹象、HYPE specialization 的同窗性能差、是否值得进入下一阶段；没有 clean prospective 就不得 promotion。

## 非复现依赖：形成证据

- [Genericization audit](../diagnostics/binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md)
- [HYPE V7.1规格](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-v7-1-spec.md)
- [V7全参数清理消融](../../../hype/1d-ma7-asymmetric-body-trend/ablations/hype-1d-ma7-abt-v7-full-parameter-cleanup-ablation-2026-08-11.md)
