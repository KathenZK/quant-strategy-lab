# BNB-1H-Adaptive-Regime Decision Log

## 2026-07-03：建立独立研究家族

- 使用 Binance USD-M Futures `BNBUSDT` perpetual `1h` 最近两年闭合 K。
- 最近三个月严格锁定为 OOS；搜索和排序只读取更早的 train/validation。
- 硬目标保持原义：年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤严格小于 `20%`。
- Binance 成本固定为 `0.001` fee/fill、`4 bps` adverse slippage/fill，并计入历史资金费。
- 在 locked OOS 与 live-executable 审计完成前保持 `not promoted / not live-ready`。

## 2026-07-05：完整搜索 NO-GO，转向独立 15m 家族

- 完成 `1,000,000` 组随机配置、`500,000` 组邻域请求与 `200` 个保留组合；prefit hard-gate 命中为 `0`。
- 唯一预冻结 primary 为 `bb_break + stoch_reversal`，prefit 年化倍率 `6.36x`、胜率 `77.05%`、最大回撤 `-19.75%`，仍未达到 `10x`。
- locked OOS 年化倍率 `0.28x`、胜率 `42.86%`、最大回撤 `-31.90%`；full 也因 `-31.90%` 回撤失败。
- 结论：`BNB-1H-Adaptive-Regime` 为 `NO-GO / not promoted / not live-ready`，不登记版本。
- 后续单独建立 `BNB-15M-Adaptive-Regime`，不在 1h 失效 primary 上继续 OOS 后调参。

## 2026-07-06：1h 趋势/反转 rerun 仍未达标

- 按用户要求在 Binance USD-M Futures `BNBUSDT` perpetual `1h` 上再做一次宽搜索，覆盖趋势、反转及二者 ensemble；成本仍为 `0.001` fee/fill、`4 bps` slippage/fill，并计入真实 funding。
- 本轮为 `500,000` random + `250,000` neighbors；first-pass eligible `55,282`、neighbor eligible `117,627`，两阶段 prefit hard-gate 命中均为 `0`。
- 唯一冻结 primary 为 `ENS__BNB_1H_AR_N0559088__BNB_1H_AR_N0610751`，机制为趋势 `keltner_break` + 反转 `cci_reversal`。
- prefit 为 `3.13x annual / -19.44% DD / 91.49% win`，未达到 `10x` 年化倍率；locked OOS 为 `0.31x annual / -37.14% DD / 75.00% win / 4 trades`，同时低于最低 OOS 交易数 `12`。
- full 为 `2.30x annual / -37.14% DD / 91.03% win / 145 trades`；回撤穿越 `20%` 硬边界。
- 结论维持：`BNB-1H-Adaptive-Regime` 仍为 `NO-GO / not promoted / not live-ready`，不登记版本；证据见 `diagnostics/bnb-1h-adaptive-regime-search-2026-07-06-rerun.md`。

## 2026-07-06：用户约束 BNB 1h 最大杠杆不超过 3x

- 用户明确指出 4x 版本回撤过大，后续 BNB `1h` 研究最大只能使用 `3x` 杠杆。
- 对 2026-07-06 rerun primary 做 3x cap 重放：train `2.42x / -14.58% DD / 91.26% win`，validation `2.52x / -13.74% DD / 92.11% win`。
- locked OOS 仍为 `0.44x / -28.30% DD / 75.00% win / 4 trades`；full 为 `1.95x / -28.30% DD / 91.03% win / 145 trades`。
- 结论：3x cap 降低尾部亏损，但仍未通过 `20%` 回撤 hard gate；未来搜索必须硬性约束 `max_leverage <= 3.0`，并继续降低单笔权益风险。证据见 `diagnostics/bnb-1h-ar-rerun-cap3-replay-2026-07-06.md`。

## 2026-07-06：cap3 高胜率趋势/反转搜索未通过 locked OOS

- 按用户要求重新寻找趋势或反转策略，约束最大杠杆 `<=3x`，诊断目标为高收益、最大回撤不超过 `20%`、胜率约 `80%`。
- 本轮为 `500,000` random + `250,000` neighbors；first-pass evaluated `208,885`、neighbor evaluated `198,447`；first/neighbors 单策略 prefit pass 均为 `0`，最终通过趋势+反转 ensemble 得到唯一冻结 primary。
- 冻结 primary 为 `ENS__BNB_1H_CAP3_HW_N0501751__BNB_1H_CAP3_HW_N0663797`，机制为趋势 `ema_pullback` + 反转 `wick_reject`，实际最大暴露 `2x`。
- prefit 命中诊断目标：`2.20x annual / -18.66% DD / 87.04% win / 108 trades`。
- locked OOS 失败：`0.64x annual / -22.86% DD / 68.42% win / 19 trades`；full 也为 `1.87x annual / -22.86% DD / 84.25% win / 127 trades`，回撤略穿 `20%` 上限且收益低于 `2x` 诊断目标。
- 结论：存在样本内接近用户偏好的趋势+反转形态，但未通过 locked OOS，不得登记为 candidate、paper-live 或 live；证据见 `diagnostics/bnb-1h-ar-cap3-highwin-search-2026-07-06-cap3-highwin.md`。

## 2026-07-06：登记 `BNB-1H-Adaptive-Regime-V1`

- 按用户要求，将 `ema_pullback + wick_reject` cap3 high-win primary 登记为 `BNB-1H-Adaptive-Regime-V1`。
- V1 状态为 `diagnostic observation baseline / not promoted / not live-ready`；它只是样本内观察形态，不是 candidate。
- 参数规格见 `specs/bnb-1h-ar-v1-parameter-spec-2026-07-06.md`；后续全参数消融只允许删除交易路径完全不变的 no-op 参数，或另行登记 clean diagnostic version。

## 2026-07-06：V1 全参数消融与 clean spec

- 完成 `BNB-1H-Adaptive-Regime-V1` 全参数消融，共 `60` 个消融 row；baseline 仍为 prefit `2.20x / -18.66% DD / 87.04% win`、locked OOS `0.64x / -22.86% DD / 68.42% win`、full `1.87x / -22.86% DD / 84.25% win`。
- 识别出 `32` 个交易路径完全不变的 no-op 字段；已整理为等价 clean spec：`specs/bnb-1h-ar-v1-clean-parameter-spec-2026-07-06.md`。
- `ema_pullback.ema_slow` 与 `wick_reject.sl_atr` 的单项替换在样本内不差但改变交易路径，不能作为 V1 clean 直接采用；如继续研究需另行冻结。
- 结论不变：V1 clean 只删除无用参数，不修复 locked OOS 失败，不 promotion；证据见 `ablations/bnb-1h-ar-v1-full-parameter-ablation-2026-07-06.md`。

## 2026-07-07：登记 `BNB-1H-Adaptive-Regime-V2` 并完成多窗口验证

- 按用户要求，将 V1 clean 参数版本落成可执行定义 `scripts/bnb_1h_ar_v2.py` 并登记为 `BNB-1H-Adaptive-Regime-V2`。
- no-op 字段固定为 V1 消融验证的 neutral 值；逐笔重放确认 V2 与 V1 trade signature 完全相等，指标原样继承。
- 多时间窗口回测已落盘：train/validation/prefit/locked OOS/full、8 个 90d block、last `1d/7d/1m/3m/6m/1y`（锚定数据集末端 `2026-07-03T06:00Z`，数据未刷新）。
- 分片显示亏损集中在 `block_90d_04`（2025-05 至 2025-08，`-8.09%`）与 locked OOS（last_3m `0.64x / -22.86% DD / 68.42% win`）；其余 block 均为正。
- V2 状态：`clean-equivalent diagnostic observation / not promoted / not live-ready`；证据见 `notes/bnb-1h-ar-v2-multiwindow-backtest-2026-07-07.md`。

## 2026-07-07：V2 全参数消融

- 对 V2 全部 `29` 个受检字段做 one-at-a-time 域扫描（`122` rows，含 component removal 与 exit_kind 联动变体）。
- 结果：`27` 个字段 active、`2` 个为执行时序参数（`entry_delay_bars`）、`0` 个可再移除。V2 已是最小活动参数集，本轮没有新的无效参数可删。
- 消融给出 `8` 个 prefit-only 改进方向（如 `ema_pullback` trailing 出场、`ema_slow=144`、`min_rvol=0.8`、`wick_reject.threshold_high=0.75/0.80`），作为微调搜索输入；这些变体改变交易路径，不构成 V2 变更。
- 证据见 `ablations/bnb-1h-ar-v2-full-parameter-ablation-2026-07-07.md`。

## 2026-07-07：V2 消融引导微调找到更优观察值

- 在 V2 上做 prefit-only 微调：leg 级采样（`ema_pullback` `2000`、`wick_reject` `1600`），每侧 top `40` 组成 `1600` 个 ensemble；gate 要求相对 V2 prefit 同时做到收益更高、回撤更小、胜率更高，通过 `168` 个。
- 首选组合（按 prefit score 唯一选出后才复用 OOS 一次）：`ema_pullback` 改 `ema_slow=144`、trailing 出场（activation `2.0`、trail `1.5` ATR）、`max_hold=240`、`cooldown=12`、`2.5x`；`wick_reject` 改 `threshold 0.40/0.75`、`min_adx=28`、`max_hold=48`、`1.0x`。
- 结果：prefit `3.37x / -18.24% DD / 89.42% win / 104 trades`；reused locked OOS 观察值 `1.22x / -15.53% DD / 81.25% win / 16 trades`；full `2.94x / -18.24% DD / 88.33% win / 120 trades`；实际最大暴露 `2.5x`。
- 三个维度均优于 V2（收益 `1.87x -> 2.94x`、回撤 `-22.86% -> -18.24%`、胜率 `84.25% -> 88.33%`），但 locked OOS 为二次读取，只能作为 tuned observation；后续按用户要求登记为 V3，不 promotion。
- 证据见 `notes/bnb-1h-ar-v2-micro-tune-2026-07-07.md`。

## 2026-07-07：登记 `BNB-1H-Adaptive-Regime-V3`

- 按用户要求，将 V2 消融引导微调首选组合登记为 `BNB-1H-Adaptive-Regime-V3`。
- V3 状态为 `tuned diagnostic observation / not promoted / not live-ready`；不是 candidate、paper-live、dry-run、handoff 或 live。
- 当前实际最大杠杆为 `2.5x`：`ema_pullback` 固定 `2.5x`，`wick_reject` 固定 `1.0x`，单仓 merge 后组合最大暴露为 `2.5x`。
- 参数规格已逐项解释：`specs/bnb-1h-ar-v3-parameter-spec-2026-07-07.md`。
- 指标登记为 prefit `3.37x / -18.24% DD / 89.42% win / 104 trades`，reused locked OOS `1.22x / -15.53% DD / 81.25% win / 16 trades`，full `2.94x / -18.24% DD / 88.33% win / 120 trades`。
- Promotion 边界不变：OOS 为 reused observation，必须等待未读 forward 数据或重新冻结流程，才能讨论 candidate/live-readiness。
