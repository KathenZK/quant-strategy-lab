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

## 2026-07-02 — V1 全参数消融与 clean interface

- 两条腿各覆盖 `39` 个 `StrategyConfig` 字段槽，总计 `78/78`；生成 `205` 行 baseline/variant 证据，coverage missing `0`。
- 字段分类：`27` active tunable、`12` contract fixed、`35` baseline fixed、`4` neutral fixed。
- clean interface 只暴露 `27` 个 active 参数；其余 `51` 个槽删除或硬编码。clean 与 V1 逐笔交易签名完全一致。
- one-at-a-time prefit 同时提高年化、降低回撤、胜率 >=50%、train/validation 同正且 validation DD<20% 的观察共 `5` 行；最强单字段方向为 Keltner `band_k: 2.5 -> 2.0`。

## 2026-07-02 — Clean tune 与缩放前沿

- 只使用 train/validation/prefit：Keltner/CCI 每腿各 `150,000` 组，保留各 `350` 组，组合评估 `122,500` 组；prefit 严格改善观察 `809` 个。
- 500 个前沿进入 K+2/8 bps 预拟合审计；`15` 个在两个场景的 train、validation、prefit 全部正收益、胜率 >=50%、DD<20%。
- 硬 gate 第一名 prefit `3.52x / -18.06% / 80.33%`，但 reused holdout `0.60x / -26.07% / 54.55%`，因此否决为最终观察。
- 第一次 prefit-only soft frontier 的原曝光为 Keltner `2.0x`、CCI `3.0x`，K+2 prefit DD `-21.77%`；按 prefit K+2 回撤机械统一缩放 `0.90`，得到 `1.8x/2.7x`，没有读取 reused holdout 决定 scale。
- 缩放前沿 prefit `3.18x / -13.99% / 84.85%`，K+2 prefit `2.50x / -19.70% / 80.30%`，reused holdout `1.52x / -13.48% / 81.82%`，current full `2.88x / -13.99% / 84.42%`。
- 当时决策：记录为 `BTC-1H-AR-V1-SCALED-FRONTIER-2026-07-02` paper-audit observation；版本命名暂缓，不标记 live-ready。下一证据必须是冻结参数后的新增 forward trades 和生产 runner 审计。

## 2026-07-03 — 按用户要求登记 V2

- 将 `BTC-1H-AR-V1-SCALED-FRONTIER-2026-07-02` 正式登记为 `BTC-1H-Adaptive-Regime-V2`。
- V2 身份固定为 V1 clean surface scaled frontier：Keltner breakout + CCI reversal ensemble，Keltner `fixed_leverage=1.8`、CCI `fixed_leverage=2.7`。
- 参数、作用说明和证据链接已写入 `btc-1h-ar-core-ledger.md`；机器证据仍为 `artifacts/btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json`。
- 此登记覆盖上一条“版本命名暂缓”的决策，但不改变审计状态：`paper-audit observation / forward-test required / not live-ready`。
- 下一证据仍必须来自 V2 冻结参数后的新增 forward trades、production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 与真实 stop-market 滑点审计。
