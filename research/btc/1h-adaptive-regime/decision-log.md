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
- V1 身份固定为 Keltner breakout + CCI reversal ensemble；完整参数见 `specs/btc-1h-ar-v1-baseline-spec.md` 与 `artifacts/btc_1h_ar_v1_config_2026-07-02.json`。
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
- 当时决策：记录为 `BTC-1H-AR-V1-SCALED-FRONTIER-2026-07-02` audit observation；版本命名暂缓，不标记 live-ready。下一证据必须是冻结参数后的新增 forward trades 和生产 runner 审计。

## 2026-07-03 — 按用户要求登记 V2

- 将 `BTC-1H-AR-V1-SCALED-FRONTIER-2026-07-02` 正式登记为 `BTC-1H-Adaptive-Regime-V2`。
- V2 身份固定为 V1 clean surface scaled frontier：Keltner breakout + CCI reversal ensemble，Keltner `fixed_leverage=1.8`、CCI `fixed_leverage=2.7`。
- 参数、作用说明和证据链接已写入 `btc-1h-ar-core-ledger.md`；机器证据仍为 `artifacts/btc_1h_ar_v1_scaled_frontier_audit_2026-07-02.json`。
- 此登记覆盖上一条“版本命名暂缓”的决策，但不改变审计状态：`audit observation / forward-test required / not live-ready`。
- 下一证据仍必须来自 V2 冻结参数后的新增 forward trades、production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 与真实 stop-market 滑点审计。

## 2026-07-06 — V2 全参数消融

- 对 `BTC-1H-Adaptive-Regime-V2` 冻结参数执行 one-at-a-time 全参数消融，复现 V2 基线：prefit `3.1773x / -13.99% / 84.85%`，reused holdout `1.5232x / -13.48% / 81.82%`，current full `2.8817x / -13.99% / 84.42%`。
- 覆盖两条腿全部 `78/78` 个 `StrategyConfig` 字段槽，生成 `205` 行 baseline/variant 证据，coverage missing `0`。
- 字段分类沿用 V1 全消融语义：`27` active tunable、`12` contract fixed、`35` baseline fixed、`4` neutral fixed。
- 相对 V2 基线，one-at-a-time prefit 严格改善行数为 `5`；最强单字段方向为 CCI `tp_atr: 4.5 -> 5.0`，prefit `3.5469x / -13.99% / 84.85%`。
- 决策：记录为敏感性审计，不做组合搜索，不登记 V2.1，不改变 `audit observation / not live-ready`。证据见 `ablations/btc-1h-ar-v2-full-parameter-ablation-2026-07-06.md` 与 `artifacts/btc_1h_ar_v2_full_ablation_2026-07-06.json`。

## 2026-07-06 — V2 受约束微调观察

- 基于 V2 全参数消融的前沿方向，仅调整 active 参数：Keltner `fixed_leverage`，CCI `tp_atr`、`cooldown_bars`、`max_adx`、`fixed_leverage`，以及少量 Keltner 过滤参数候选；不改变 `style`、`side_mode`、`entry_delay_bars`、`exit_kind` 或 `sizing_kind` 等合同字段。
- 选参规则：只读取 train/validation/prefit；要求 prefit 年化高于 V2，train/validation/prefit 胜率均 `>=80%`、回撤均 `<20%`，并在通过 gate 的组合中最大化 prefit 年化。reused holdout 不参与选参。
- 网格 `7,200` 组，`3,852` 组通过 selection gate。首选 `BTC-1H-AR-V2-MICRO-TUNE-2026-07-06`：Keltner `fixed_leverage=2.4`；CCI `tp_atr=5.5`、`cooldown_bars=0`、`max_adx=40.0`、`fixed_leverage=3.5`。
- 指标：prefit `6.1574x / -12.87% / 87.30%`；reused holdout `1.8998x / -17.47% / 81.82%`；current full `5.2669x / -17.47% / 86.49%`。
- 决策：记录为 diagnostic micro-tune observation；不登记 V2.1，不标记 candidate/paper-live/live-ready。证据见 `research-notes/btc-1h-ar-v2-micro-tune-2026-07-06.md` 与 `artifacts/btc_1h_ar_v2_micro_tune_2026-07-06.json`。

## 2026-07-06 — 按用户要求登记 V3

- 将 `BTC-1H-AR-V2-MICRO-TUNE-2026-07-06` 正式登记为 `BTC-1H-Adaptive-Regime-V3`。
- V3 身份固定为 V2 micro-tune diagnostic observation：Keltner breakout + CCI reversal ensemble；Keltner `fixed_leverage=2.4`；CCI `tp_atr=5.5`、`cooldown_bars=0`、`max_adx=40.0`、`fixed_leverage=3.5`。
- 指标沿用冻结观察：prefit `6.1574x / -12.87% / 87.30%`；reused holdout `1.8998x / -17.47% / 81.82%`；current full `5.2669x / -17.47% / 86.49%`。
- 参数、作用说明和证据链接已写入 `btc-1h-ar-core-ledger.md`；机器证据仍为 `artifacts/btc_1h_ar_v2_micro_tune_2026-07-06.json`。
- 此登记覆盖上一条“不登记 V2.1 / 不登记新版本”的命名决策，但不改变审计状态：`diagnostic micro-tune observation / forward-test required / not live-ready`。

## 2026-07-06 — V3 全参数消融与多窗口回测

- 对 `BTC-1H-Adaptive-Regime-V3` 冻结参数执行 one-at-a-time 全参数消融，复现 V3 基线：prefit `6.1574x / -12.87% / 87.30%`，reused holdout `1.8998x / -17.47% / 81.82%`，current full `5.2669x / -17.47% / 86.49%`。
- 覆盖两条腿全部 `78/78` 个 `StrategyConfig` 字段槽，生成 `205` 行 baseline/variant 证据，coverage missing `0`；字段分类沿用 V1/V2：`27` active tunable、`12` contract fixed、`35` baseline fixed、`4` neutral fixed。
- 相对 V3 基线，同时满足 prefit 年化更高、回撤更小、train/validation/prefit 胜率均 `>=80%`、train/validation 同正且 validation DD<20% 的 one-at-a-time 严格改善行数为 `0`。
- 多窗口回测显示：recent 90d `1.9134x / +17.34% / -17.47% / 81.82% / 11`；recent 30d `1.2931x / +2.13% / -17.47% / 75.00% / 4`；recent 7d 无交易；2026 YTD `3.9017x / +97.37% / -17.47% / 84.00% / 25`。
- 决策：记录为 V3 敏感性与时间稳定性诊断，不做组合搜索；原“不登记 V3.1/V4”的诊断口径后续已被用户指令覆盖，但不标记 candidate/paper-live/live-ready。证据见 `ablations/btc-1h-ar-v3-full-parameter-ablation-2026-07-06.md`、`research-notes/btc-1h-ar-v3-window-backtest-2026-07-06.md`、`artifacts/btc_1h_ar_v3_full_ablation_2026-07-06.json` 与 `artifacts/btc_1h_ar_v3_window_backtest_2026-07-06.json`。

## 2026-07-07 — V3 参数必要性审计与最小表面微调

- 基于 V3 全消融的路径等价证据，对 `27` 个 clean active 槽位逐项中和验证（贪心累积 + 逐笔交易签名比对）。
- `8` 个槽位在 V3 冻结值下从不生效并被移除：Keltner `max_atr_bps=200`、`min_dir_roc_bps=-200`、`roc_window=24`（依附方向 ROC 过滤）、`max_aligned_funding_bps=4.0`、`max_hold_bars=240`、`cooldown_bars=0`，CCI `max_atr_bps=600`、`cooldown_bars=0`。最小等价表面为 `19` 个必要参数，逐笔路径与 V3 完全一致。
- 在最小表面上执行受约束微调：两腿杠杆冻结为 V3 值（Keltner `2.4x`、CCI `3.5x`），只触碰必要参数；选参只读取 train/validation/prefit，附加 train/validation 胜率 `>=80%`、回撤 `<20%`、同正约束；reused holdout 不参与选参。
- 结果：腿级变体 Keltner `486`、CCI `1,728`，组合网格 `24,576` 组。严格三项改善（prefit 年化更高、回撤更小、胜率更高）命中 `0` 组；Pareto 口径（年化严格更高、回撤与胜率不劣）`8` 组。
- 首选观察 `BTC-1H-AR-V3-MINIMAL-MICRO-TUNE-2026-07-07`：CCI `max_hold_bars 72->96`、`max_dist_ema_bps 750->700`，prefit `6.2430x / -12.87% / 87.30%`（vs V3 `6.1574x`），reused holdout `1.8998x / -17.47% / 81.82%` 与 V3 完全相同，current full `5.3303x / -17.47% / 86.49%`。
- 决策：改善幅度约 `+1.4%` 年化倍率、回撤与胜率无变化，属噪声级别；V3 在其冻结邻域判定为局部最优。该“最小等价表面不登记新版本”的诊断口径后续已被用户要求登记 V4 覆盖；不改变 `diagnostic observation / not live-ready`。证据见 `research-notes/btc-1h-ar-v3-param-necessity-2026-07-07.md`、`research-notes/btc-1h-ar-v3-minimal-micro-tune-2026-07-07.md`、`artifacts/btc_1h_ar_v3_param_necessity_2026-07-07.json` 与 `artifacts/btc_1h_ar_v3_minimal_micro_tune_2026-07-07.json`。

## 2026-07-07 — 按用户要求登记 V4 并分时间片回测

- 将 V3 参数必要性审计得到的 `19` 参数最小等价表面正式登记为 `BTC-1H-Adaptive-Regime-V4`。
- V4 身份固定为 V3 minimal-equivalent clean observation：Keltner 保留 `8` 个必要参数，CCI 保留 `11` 个必要参数；`8` 个非必要槽位以中和值固定。脚本强制校验 V4 与 V3 逐笔交易签名完全一致。
- V4 指标与 V3 完全一致：prefit `6.1574x / -12.87% / 87.30%`；reused holdout `1.8998x / -17.47% / 81.82%`；current full `5.2669x / -17.47% / 86.49%`。
- 分时间片回测：recent 7d 无交易；recent 30d `1.2931x / +2.13% / -17.47% / 75.00% / 4`；recent 90d `1.9134x / +17.34% / -17.47% / 81.82% / 11`；2025 全年 `4.4421x / +343.75% / -11.04% / 88.24% / 34`；2026 YTD `3.9017x / +97.37% / -17.47% / 84.00% / 25`。
- 决策：V4 登记只固定“参数干净版”身份，不是新增 OOS 或收益证据；不标记 candidate/paper-live/live-ready。证据见 `artifacts/btc_1h_ar_v4_config_2026-07-07.json`、`research-notes/btc-1h-ar-v4-window-backtest-2026-07-07.md`、`artifacts/btc_1h_ar_v4_window_backtest_2026-07-07.json`。
