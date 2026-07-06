# HYPE-1H-Adaptive-Regime Decision Log

## 2026-07-01：初始化独立 1h 家族

- 用户要求抓取 Binance HYPE 永续全部 `1h` K，并尝试寻找年化权益倍率 `>=10x`、胜率 `>=50%`、最大回撤 `<20%`、可实盘的全新策略。
- 新建独立家族 `HYPE-1H-Adaptive-Regime`（`HYPE-1H-AR`），不把 `1h` 结果并入任何现有 `15m`、`5m`、`1m` 或 `6h` 家族。
- 在数据质量审计、时间外验证和 live-executable 审计完成前，状态固定为 `research in progress / not promoted`。

## 2026-07-01：两轮搜索完成，结论 NO-GO

- 全量数据为 `9,526` 根闭合 `1h` K，`0` 缺口、`0` 重复、`0` raw/normalized mismatch；另计入 `2,380` 条历史资金费。
- 第一轮生成 `120,768` 个配置，评估 `70,411` 个可交易单策略，并评估 `1,225` 个 ensemble；locked target pass `0`。
- 第二轮从 prefit Pareto 边界生成 `180,000` 个 unique neighbors，评估 `171,730` 个可交易单策略，并评估 `1,225` 个 ensemble；locked target pass `0`。
- 最强边界组合 `DI-cross + Stoch-reversal`：full `9.7333x` 年化权益倍率、`78.26%` 胜率、`-19.64%` 最大回撤；locked holdout `5.2151x`、`75.00%`、`-19.64%`。
- K+2、成本压力与 `164` 行 active-field 消融确认该边界没有实盘缓冲，状态冻结为 `NO-GO / not live-ready / not promoted`。
- 不创建 production runner，不将 `9.73x` 四舍五入为达标。

## 2026-07-02：登记 V1，完成全字段消融并登记 V2

- 刷新 Binance 数据至 `2026-07-02 02:00 UTC`：`9,545` 根闭合 `1h` K，missing/duplicate/null/OHLCV violation/raw-normalized mismatch 均为 `0`；资金费 `2,385` 条。
- 将冻结的 DI-cross + Stoch-reversal 边界正式登记为 `HYPE-1H-Adaptive-Regime-V1`。当前 full 为 `9.6838x / -19.64% / 78.26% / 69 trades`；版本登记不改变 `NO-GO`。
- 对两条腿各 `38` 个字段、共 `76` 个字段槽完成 one-at-a-time 消融，missing coverage `0`。分类为 structural dormant `24`、disabled/fixed `16`、active `36`。
- 删除 `40` 个 dormant 或固定状态机字段槽，登记 `HYPE-1H-Adaptive-Regime-V2`。V2 的 DI、Stoch、merged 逐笔交易签名与 V1 exact equal，全部指标完全相同。

## 2026-07-02：V2 微调未形成新版本

- 第一轮 active 参数微调：DI `30,000`、Stoch `30,000`、组合 `19,600`。prefit 冻结第一名后段回撤 `-36.57%`，拒绝。
- Post-hoc 前沿中基础 full + reused-holdout 三项门槛命中 `6` 组；要求 base K+1、K+2、8 bps/fill 都完整过门槛后为 `0` 组。
- 第二轮把 K+2 和 8 bps 直接放入 prefit gate，扩大为 DI `800`、Stoch `800`、组合 `640,000`；三场景 prefit 稳健命中 `7,613`。
- 预先评分第一名冻结后 current full `13.6490x / -32.69% / 81.25%`，回撤失败；稳健榜前 `1,000` 组后段审计的完整“更高收益 + 更低回撤 + 实盘压力”命中仍为 `0`。
- 决策：V2 保持干净等价基线；不创建 V2.1/V3，不把任何高年化但压力失败的结果包装为实盘版本。下一次 promotion 需要冻结参数后的新增 forward trades 和生产 runner 证据。

## 2026-07-02：修复未闭合 K 判定并全量重跑

- 最终时序验收发现抓取脚本对 `datetime64[ms]` 做整数转换后又按纳秒口径除以 `1,000,000`，可能把当前运行中的 `1h` K 误标为 closed。这是未来函数级 blocker，发现后立即撤销未复核结论。
- 改为 UTC datetime 与 Binance server cutoff 直接比较；读取缓存时也重新计算 raw `is_closed` 并从 raw 重建 normalized，不再信任旧标记。
- 新增 `normalized_bar_not_closed_at_cutoff`、`raw_closed_flag_at_or_after_cutoff` 两项硬 blocker，以及两个毫秒 dtype 回归测试。
- 修复后 server time `2026-07-02 03:40:55.224 UTC`，raw `9,546` 行中仅 `9,545` 行闭合；最后合法闭合 K 为 `02:00`，正在形成的 `03:00` K 被排除。
- V1、V2、`76/76` 消融、前沿压力、`30,000 + 30,000 + 19,600` 首轮微调和 `800 x 800` 扩大搜索全部从修复后的 closed-only 数据重新生成。V1/V2 最终指标与前次相同；未闭合末根当时没有形成可成交的下一根入场，但代码缺陷本身仍按最高优先级修复并留测试。

## 2026-07-06：V2 组合复测并按用户要求登记 V3

- V2 全参数消融提示的组合复测覆盖 DI `4` 个候选 × Stoch `4` 个候选，共 `16` 组；每组执行 base K+1、K+2 延迟和 `8 bps/fill` 滑点压力。
- 最佳 base 组合为 `di_roc_off__stoch_th55`，current full `15.0530x / -19.11% / 79.73% / 74 trades`；reused holdout `9.0300x / -19.11% / 76.47% / 17 trades`。
- 同一组合在 K+2 压力下 current full 为 `3.0574x / -31.93%`；在 `8 bps/fill` 下为 `9.4070x / -28.40%`。因此它不是 promotion，不可标记为 live、paper-live、dry-run、candidate 或 handoff。
- 按用户要求，将 `di_roc_off__stoch_th55` 正式登记为 `HYPE-1H-Adaptive-Regime-V3` diagnostic baseline，并创建 `canonical-specs/hype-1h-ar-v3-baseline-spec.md` 与主账条目。
- V3 全参数消融覆盖 clean 配置接口 `34` 个字段槽，输出 `98` 行，coverage missing fields 为 `0`；current full 严格改善行 `9`，基础 target-like 行 `5`。这些仍只作诊断，未完成 K+2/滑点/生产 runner/forward trades promotion 证据。
