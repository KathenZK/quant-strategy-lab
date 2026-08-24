# HYPE-1D-MA7-ABT V6 RSI6记忆×MA7 Cross新增入场合同（2026-08-10）

## 1. 研究问题与身份

本轮只检验：在exact V6上增加“过去5日RSI6极值记忆 + 当日MA7反向cross”的备选自然入场，能否提高收益并降低回撤。

新增规则按此前原始意图冻结为：

- long：cross日前5个完整UTC日中至少3日 `Wilder RSI6 < 30`，且当日 `close[t-1] <= MA7[t-1]`、`close[t] > MA7[t]`；
- short：cross日前5个完整UTC日中至少3日 `Wilder RSI6 > 70`，且当日 `close[t-1] >= MA7[t-1]`、`close[t] < MA7[t]`；
- 信号日只在日线收盘后形成，最早下一UTC日真实`1h` open成交；
- 新规则是exact V6 native entry的OR分支，忽略该方向原生entry slope与short `0.10ATR` buffer；
- exact V6全局cooldown、自然long-first优先级、forced reversal、V5 OAPP、short RSI6盈利止盈、PEHC_294、仓位、成本、funding及全部持仓退出不变；
- 因此“直接开仓”指合格且V6处于可自然入场的flat/unlocked状态时直接选择该方向，不绕过实际持仓和frozen cooldown。

V6及上游冻结代码不修改；本轮使用独立overlay，不登记V7，不触发promotion、runner或杠杆。

## 2. RSI与窗口语义

- RSI固定为Wilder RSI6，不搜索周期；
- 主口径 `PRIOR5`：只计 `[t-5,t-1]`，不包含cross日，避免用cross当日本身制造极值记忆；
- 不选参敏感性 `INCLUSIVE5`：计 `[t-4,t]`；只回答中文“过去5天”边界是否影响结论，不参与参数选择；
- 比较严格为 `<30` / `>70`，等于阈值不计；
- 至少3日，不要求连续；
- 历史不足5日、RSI非有限、MA7或close非有限时不触发。

## 3. 冻结arm

- `A0_EXACT_V6`；
- `A1_PRIOR5_BOTH`：主规则，多空均启用；
- `A2_PRIOR5_LONG_ONLY`；
- `A3_PRIOR5_SHORT_ONLY`；
- `A4_INCLUSIVE5_BOTH`：窗口边界敏感性；
- `A5_PRIOR5_BOTH_NO_NATIVE`：只保留新增RSI-memory cross入场，用于判断新增规则的独立质量；V6退出链全部保留。

不搜索RSI阈值、计数、lookback、cooldown或退出参数。

## 4. 数据、执行与比较

- 市场：Binance USD-M `HYPEUSDT` perpetual；
- 数据：432个完整UTC日，连续 `[0,432)`；全部researcher-exposed；
- 基础成本：fee `10bps/fill`、adverse slippage `4bps/fill`、funding启用；
- 压力：slippage `8bps/fill`；
- 风险：真实 `1h` chronological MDD；
- 稳定性：`8 × 54d` cold-flat block；每块重置仓位、cooldown、PEHC shadow和所有pending，只预热已冻结指标；
- 近期切片：数据尾部 `1d/7d/1m/3m/6m/1y`，仅作审计；
- 逐笔保留新增、删除、提前/延后和退出原因变化。

## 5. 裁决

主arm只有在以下条件全部满足时记为 `POST-REVEAL DIAGNOSTIC PASS`：

1. 全历史累计收益严格高于exact V6；
2. chronological `1h` MDD严格小于exact V6；
3. 至少2个新增RSI-memory实际成交；
4. 8bps与8块cold-flat均不双劣；
5. 不破产，OAPP、short RSI TP和PEHC仍接线。

即使通过，也不构成OOS、版本登记或上线资格；若不通过则保持V6不变。
