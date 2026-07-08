# TRX-1H-Adaptive-Regime Decision Log

## 2026-07-03：初始化独立研究家族

- 将 `TRXUSDT` perpetual `1h` 作为独立资产 family，不继承其他资产的参数或版本号。
- 运行时拉取最近两年全部闭合 K；最近三个月一次性锁定为 OOS。
- 目标门槛原样执行：年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 搜索与排序不得读取 locked OOS；如无冻结 finalist 达标，则明确记录 `NO-GO`。
- 初始状态：`active diagnostic search / not promoted / not live-ready`。

## 2026-07-03：广搜、邻域精调和 locked OOS 揭盲

- 数据 gate：`17,520` 根闭合 `1h` K，UTC `2024-07-03T06:00:00Z` 至 `2026-07-03T05:00:00Z`；missing/duplicate/critical null/OHLC violation/raw-normalized mismatch 均为 `0`。
- 防泄漏：train `2024-08-17T06:00:00Z -> 2025-09-07T08:24:00Z`，validation 至 `2026-04-03T06:00:00Z`，随后三个月为 locked OOS；搜索与排序不读取 OOS。
- 第一阶段：`300,768` proposals，`109,143` 个可交易评估，`22,298` 个 prefit eligible，prefit hard-shape `0` 命中，locked target `0/500`。
- 第二阶段：`180,000` unique neighbors，`169,299` 个可交易评估，`126,780` 个 eligible，prefit hard-shape `0` 命中，locked target `0/500`。
- 领先 prefit-selected ensemble：full `4.077x annual / -19.84% DD / 86.54% win / 104 trades`；locked OOS `0.844x annual / -4.12% return / -11.42% DD / 75.00% win / 8 trades`。
- 决策：硬门槛失败，先记录 `NO-GO / not live-ready`；不把高全样本收益包装成可实盘策略。

## 2026-07-03：持续 regime 与实盘压力边界

- 持续持仓上界覆盖 `392` 个 causal states、`12,936` 个 side/leverage 变体；即使不计 intrabar adverse excursion、不给保护单约束这一偏乐观口径，prefit/locked target 仍均为 `0`。
- K+2 延迟使领先观察值 full DD 扩大到 `-34.46%`，OOS 仍亏损；`8 bps` 滑点使 full DD `-24.74%`、OOS return `-20.06%`。
- 订单时序可实现不等于策略可实盘；当前没有生产 runner、restart reconciliation、kill switch 和保护单监控实现。
- 最终状态保持 `NO-GO`，不生成 live spec，不登记可 promotion 的 V1。

## 2026-07-03：临时 V1base 命名与删参证据

- 当日按阶段性研究指令，将领先观察值 `ENS__TRX_1H_AR_N131875__TRX_1H_AR_N129128` 临时记为 `TRX-1H-Adaptive-Regime-V1base`；2026-07-05 后续正式收敛为 `TRX-1H-Adaptive-Regime-V1`。
- 新增全参数消融：覆盖两个组件全部 `78` 个 `StrategyConfig` 字段槽，coverage missing `0`；分类为 `33 active_tunable / 27 baseline_fixed_remove / 12 contract_fixed / 6 neutral_fixed_remove`。
- 移除 baseline/neutral fixed 字段后的干净参数面当时作为 V2 来源证据；2026-07-06 已按用户明确指令正式登记为 `TRX-1H-Adaptive-Regime-V2`。V2 与 V1 共享行为边界，仍为 full `4.077x annual / -19.84% DD / 86.54% win / 104 trades`、reused holdout `0.844x annual / -4.12% return / -11.42% DD / 75.00% win / 8 trades`。
- one-at-a-time 变体有 `4` 行 prefit 严格改善，但未用于 OOS 选参；当前 locked OOS 已解锁，只能作复用审计，不能再当新鲜 OOS。
- 决策：该观察值与删参结果均为 `NO-GO / diagnostic only / not promoted / not live-ready`；不得标记为 paper-live、dry-run、handoff 或 live。

## 2026-07-03：V2 严格分片、执行重放和不可实盘审计

- 新增 `TRX-1H-Adaptive-Regime-V2` clean 参数全量 one-at-a-time 消融：覆盖 V2 retained 字段 `45/45`，行数 `135`（含 baseline），prefit 严格改善 `4` 行；这些行未用于 locked OOS 选参。
- 按新的基础回测分片标准审计最近 `1d/7d/1m/3m/6m/1y`：`1d` 与 `7d` 无交易，`1m` 收益 `-10.12%`、`3m` 收益 `-4.12%`、`6m` 收益 `+12.80%`、`1y` 收益 `+45.18%`。
- 逐笔执行重放覆盖 warmup 后全路径 merged `107` 笔交易（full 指标窗口 `104` 笔）和两个组件交易；违规计数 `0`，merged 违规 `0`。
- stop gap/open 穿越按 open 成交 `22` 次，未发现穿越 stop 后仍按旧 stop 价成交；有利 target gap 以 target 价保守记账 `0` 次。
- 因果审计：信号使用闭合 `1h` K，`K+1 open` 入场；HTF/funding 特征按已知时间 `merge_asof` 对齐；未发现 OOS 排序或 K 内决策依赖。
- 决策：没有发现价格穿越/未来函数导致的新增不可实盘问题，但因收益目标、OOS/近期分片和 production runner 仍失败，V2 保持 `NO-GO / not promoted / not live-ready`。

## 2026-07-03：近期适配复搜

- 因 V2 最近 `1m/3m` 亏损，重新以最近 `1y/6m/3m/1m` 适配为目标做 diagnostic search；该过程直接使用已解锁近期行情，不能作为新鲜 OOS 或 promotion 证据。
- 搜索覆盖 `80,800` 个 unique configs、`42,905` 个可评估配置、`600` 个保留单腿和 `1,225` 个 ensemble；recent hard hits `0`。
- 最佳观察值为 `ENS_REC__TRX_1H_AR_REC_N011284__TRX_1H_AR_REC_N031489`（`momentum_break + wick_reject`）：最近 `1y 2.227x annual / +122.58% / -10.67% DD / 79.49% win / 39 trades`，最近 `3m +22.40% / -4.14% DD / 100% win / 9 trades`，最近 `1m +3.37% / -1.40% DD / 100% win / 2 trades`。
- 曝光缩放边界：同一观察值缩放至 `5x` 时最近 `1y` 仅 `4.724x annual`，DD `-20.74%` 已超过硬门槛；full DD 扩大至 `-34.93%`。
- 逐笔执行重放违规 `0`，stop/target gap 乐观穿越 `0`；但收益上限未达到 `>=10x` 年化门槛，且没有冻结后 forward OOS 和生产 runner。
- 决策：不登记 V3，不标记 candidate；仅保留为近期适配边界观察，家族状态仍为 `NO-GO / not promoted / not live-ready`。

## 2026-07-06：正式登记 V2 并完成 V2 全参数消融

- 按用户明确指令，将此前 V1 clean-equivalent 干净参数面正式登记为 `TRX-1H-Adaptive-Regime-V2`。此前 `V1base` 为临时命名；当前正式版本为 `V1` 与 `V2`。
- `V2` 与 `V1` 逐交易路径完全一致，仍共享 full `4.077x annual / -19.84% DD / 86.54% win / 104 trades` 与 reused holdout `0.844x annual / -4.12% return / -11.42% DD / 75.00% win / 8 trades` 的行为边界。
- 新增 `trx_1h_ar_v2.py`，输出 `artifacts/trx_1h_ar_v2_config_2026-07-06.json`；该 artifact 记录 V2 暴露 `36` 个 clean 参数槽，移除 `33` 个 dormant/neutral 字段，并硬编码 `9` 个版本身份/订单契约字段。
- 新增 V2 全参数消融：覆盖 V2 对外暴露 clean 字段槽 `36/36`，one-at-a-time 行数 `211`（含 baseline），prefit 严格改善 `8` 行；这些行只作诊断，不使用 reused holdout 或近期分片选参。
- V2 严格近期分片：`1d/7d` 无交易，`1m -10.12%`，`3m -4.12%`，`6m +12.80%`，`1y +45.18%`；近期适配性仍不满足 promotion。
- 逐笔执行重放覆盖 warmup 后全路径 merged `107` 笔交易（full 指标窗口 `104` 笔）和组件交易；违规计数 `0`，merged 违规 `0`；stop gap 按 open 成交 `22` 次，有利 target gap 以 target 价保守记账 `0` 次。
- 决策：`V2` 登记完成，但只是 clean 参数 diagnostic version，不是 candidate、paper-live、dry-run、handoff 或 live；家族状态保持 `NO-GO / not promoted / not live-ready`。

## 2026-07-06：V2 消融引导微调观察

- 按用户要求，根据 V2 消融结果做微调，目标为提高收益率、胜率维持 `80%+`、回撤 `<20%`。
- 选择过程只使用 train/validation/prefit；reused holdout 和最近 `1d/7d/1m/3m/6m/1y` 分片均为冻结后审计，不参与选参。
- pair pool `500` 行，满足 train/validation/prefit `win>=80%`、DD `<20%`、train/validation 正收益且 prefit annual 高于 V2 的候选 `41` 行。
- 选中观察值 `TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06`：prefit `7.330x annual / +2452.42% / -17.17% DD / 94.05% win / 84 trades`，current full `5.686x annual / +2503.89% / -17.17% DD / 92.47% win / 93 trades`。后续按用户明确指令正式登记为 `TRX-1H-Adaptive-Regime-V3`。
- 冻结后 reused holdout 为 `1.083x annual / +2.02% / -15.23% DD / 77.78% win / 9 trades`，收益和回撤改善，但胜率未达 `80%`。
- 标准近期分片：`1m +3.52% / -1.56% DD / 100% win / 2 trades`，`3m +2.02% / -15.23% DD / 77.78% win / 9 trades`，`6m +80.29% / -15.23% DD / 91.30% win / 23 trades`，`1y +191.14% / -15.71% DD / 91.84% win / 49 trades`。
- 逐笔执行重放违规 `0`，merged 违规 `0`；stop gap/open 按 open 成交 `10` 次，target gap 保守记账 `0` 次。
- 决策：该结果满足 current full 目标，但 reused holdout 胜率未达 `80%`，且没有新增 forward trades 和 TRX production runner；登记为 `V3` 后仍不 promotion。

## 2026-07-06：登记 V3 与参数说明

- 按用户明确指令，将 `TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06` 正式登记为 `TRX-1H-Adaptive-Regime-V3`。
- 新增 `scripts/trx_1h_ar_v3.py` 和 `artifacts/trx_1h_ar_v3_config_2026-07-06.json`，校验 V3 指标与微调观察值一致。
- 新增 `specs/trx-1h-ar-v3-parameter-spec-2026-07-06.md`，逐项列出 V3 全部 `36` 个参数、作用、V2/V3 参数值和变化含义。
- V3 相比 V2：不再与 V1/V2 逐交易等价；MACD leg 更快 HTF、更窄 ADX/ATR、放宽 MACD turn 与 EMA 距离、杠杆提高到 `5x`；Stochastic leg 从 long-only 改为 both，使用更慢 EMA 参考、严格 ADX、较宽 trailing、较短 cooldown 和 `2h` 入场延迟。
- 决策：`V3` 为 registered tuned version。current full 满足收益更高、win `>80%`、DD `<20%`，但 reused holdout 胜率 `77.78%`，且缺 fresh forward OOS 与 production runner，仍为 `NO-GO / not promoted / not live-ready`。

## 2026-07-07：V3 全参数消融、clean 参数面与微调（no-hit）

- 按用户要求，对 V3 做全参数消融，移除无作用参数生成干净参数面，并在干净面上微调，目标为收益更高、胜率更高、回撤更小。
- V3 全参数消融覆盖 `36/36` 个对外参数槽，one-at-a-time 行数 `215`（含 baseline），coverage missing `0`；prefit 严格改善行 `0`，即没有任何单字段方向能在不恶化胜率/回撤的前提下提高 prefit 年化。
- 按 merged 交易路径识别 `5` 个 dormant 字段并固定为 V3 值：`macd_flip` 的 `ema_htf`、`max_atr_bps`、`max_hold_bars`、`require_macd_turn` 与 `stoch_reversal` 的 `ema_htf`。新增 `scripts/trx_1h_ar_v3_clean.py`，确认 clean 面（`31` 个可调槽）与 V3 逐交易路径完全一致，输出 `artifacts/trx_1h_ar_v3_clean_config_2026-07-07.json`。
- V3 基线逐笔执行重放违规 `0`，merged 违规 `0`；stop gap 按 open 成交 `10` 次，target gap 乐观穿越 `0` 次。
- clean 面微调：随机邻域 1-5 字段变更，选择只使用 train/validation/prefit，硬约束要求 prefit 年化、胜率、回撤同时严格优于 V3（`7.3305x / 94.05% / -17.17%`）。seed `20260707` 评估 `3,420` 个唯一候选 + 独立 seed `99120707` 追加 `9,111` 个，三指标同时改善命中 `0`。
- 单指标改善存在（annual `114`、win `145`、DD `719`），但 annual+win 仅 `1`、annual+DD 仅 `1`、三者同收 `0`；收益与胜率/回撤形成明确 trade-off。
- 决策：本轮为 no-hit 诊断结论，V3 参数保持不变，不产生 `V3.1`/`V4`；家族状态保持 `NO-GO / not promoted / not live-ready`。
