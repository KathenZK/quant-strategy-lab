# BTC-1H-Adaptive-Regime Decision Log

## 2026-07-02 — 初始化独立 BTC 1h 家族

- 建立 `BTC-1H-Adaptive-Regime`，不继承 HYPE 策略版本或参数。
- 固定最近两年闭合 `1h` K 为研究数据范围，最后三个月为 locked OOS。
- locked OOS 在 finalist 冻结前不可用于生成参数、排序或 ensemble。
- Binance 执行成本固定为 `0.001` fee/fill 与 `4 bps` slippage/fill，并计入历史资金费。
- 达到收益/胜率/回撤硬门槛仍不是 promotion；必须继续通过 live-executable 审计。

## 2026-07-02 — 搜索与 locked OOS 结论

- 生成 `300,768` 组配置；实际产生足够信号并完成模拟 `131,565` 组，满足最低交易数并可评分 `41,898` 组，prefit 三项硬门槛命中 `0`。
- prefit 预冻结冠军为 `BTC_1H_AR_R199379`（Keltner breakout）+ `BTC_1H_AR_R130259`（CCI reversal）。prefit 年化倍率 `2.82x`、回撤 `-18.68%`、胜率 `68.29%`、`82` 笔。
- 最近三个月 locked OOS 为年化倍率 `0.17x`、总收益 `-35.74%`、回撤 `-42.73%`、胜率 `38.46%`、`13` 笔，三项硬门槛全部失败。
- K+2/K+3、8–12 bps 滑点、双倍成本、仓位缩放、单腿、73 个参数邻域、23 个按月块和 10,000 次 bootstrap 均没有产生联合通过。
- 决策：`NO-GO / not promoted / not live-ready`；不登记 `V1`，不生成 live spec 或 runner。

## 2026-07-02 — 按用户要求登记 V1

- 将原 prefit 预冻结冠军正式登记为 `BTC-1H-Adaptive-Regime-V1`。
- V1 身份固定为 Keltner breakout + CCI reversal ensemble；完整参数见 `canonical-specs/btc-1h-ar-v1-baseline-spec.md` 与 `artifacts/btc_1h_ar_v1_config_2026-07-02.json`。
- 此次登记只创建正式研究基线，不改变 `NO-GO / not live-ready`；此前“未登记 V1”决策由本条用户指令覆盖。
- V1 将作为全参数消融、删参和 prefit-only 微调的基线；reused holdout 不参与挑参数。
