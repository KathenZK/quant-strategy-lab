# SOL-1H-Adaptive-Regime Decision Log

## 2026-07-03：建立独立 SOL 1h 家族并锁定最近三个月 OOS

- 新建 `SOL-1H-Adaptive-Regime`，不继承 BTC/HYPE 版本身份。
- 数据固定为 Binance USD-M Futures `SOLUSDT` perpetual 最近两年全部闭合 `1h` K。
- 最近三个月固定为 locked OOS；参数生成、搜索、排序和 ensemble 选择仅允许使用此前的 train/validation。
- 目标保持原始硬门槛：年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤严格小于 `20%`。
- 采用下一根 open 成交、即时保护 bracket、stop-first、跳空按 open、闭合 K 更新 trailing 的可实盘时序。
- 成本固定为 `0.001` fee/fill、`4 bps` adverse slippage/fill，并计入真实历史资金费。
- 在 locked OOS 和 live-executable 审计完成前，状态保持 `diagnostic / not promoted / not live-ready`。

## 2026-07-03：固定 V1、消融、clean tune 顺序

- 百万组广搜按 prefit 规则冻结的最终基线直接登记为 `SOL-1H-Adaptive-Regime-V1`；不允许先用 OOS 或额外精调替换 V1 身份。
- V1 登记后覆盖每条腿全部配置字段做全参数消融，区分 active tunable、contract fixed、baseline fixed、neutral/dormant。
- 删除或硬编码不必要字段，建立逐笔等价的 clean interface；后续微调只能从 clean 参数面出发，并只使用 train/validation 选择。

## 2026-07-06：补齐 V1 主账、消融和 clean interface 持久报告

- 主账和 README 已对齐为：`SOL-1H-Adaptive-Regime-V1 registered baseline / NO-GO / not promoted / not live-ready`。
- V1 冻结身份来自 2026-07-03 广搜最佳 finalist `ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318`，机制为 `donchian_break + bb_revert` ensemble；新增 `scripts/sol_1h_ar_v1.py` 作为 V1 冻结 wrapper。
- V1 full annual `2.18x`、return `330.75%`、DD `-18.86%`、win `76.60%`、trades `94`；最近三个月 locked OOS annual `0.71x`、return `-8.09%`、DD `-16.19%`、win `50.00%`、trades `8`，不通过 `10x / 50% / <20% DD` 硬门槛。
- V1 全参数消融报告：`ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`；覆盖 `78/78` 个字段槽，clean surface 保留 `40` 个 active tunable 字段槽。
- V1 clean interface 报告：`notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`；原始 `78` 个字段槽收敛为 `40` 个 clean tunable 字段槽，逐笔交易签名与 V1 相等。
- V1 clean tune 报告：`notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`；每腿随机样本 `250000`，组合评估 `160000`，K+2/8 bps prefit 稳健候选 `395`。
- clean tune 只能作为 diagnostic observation；prefit annual `5.7104x`、DD `-18.81%`、win `85.71%`，但 reused holdout annual `0.1607x`、DD `-42.87%`、win `0.00%`，current full DD `-42.87%`，不能登记为 `V1.1/V2`，也不能 promotion。

## 2026-07-07：高胜率硬目标（10x / 80% / <20% DD）重新搜索，结论 NO-GO

- 应用户要求以更严格目标重新搜参：年化权益倍率 `>=10.0x`、胜率 `>=80%`、最大回撤严格小于 `20%`；打分函数向高胜率倾斜（win-rate 奖励封顶 `90%`，低于 `80%` 罚分）。
- 数据沿用 V1 冻结研究帧（`2024-07-03` 至 `2026-07-03`，17520 根闭合 K）；最近三个月已在 2026-07-03 V1 广搜揭盲，本轮按 reused holdout 处理，选择只用 train/validation。
- 覆盖 `600768` 个 configs（curated `768` + random `600000`），评估 `370589`，prefit eligible `141925`；prefit pass `0`，reused-holdout target pass `0`，last-1y 硬形状命中 `0`。结论 `NO-GO / not promoted / not live-ready`。
- 最佳冻结 finalist `ENS__SOL_1H_AR_HW_R132002__SOL_1H_AR_HW_R243705`（`donchian_break + vwap_revert` ensemble）：full annual `2.07x`、DD `-17.41%`、win `93.91%`、trades `115`；last-1y annual `1.60x`、win `92.31%`；但 reused holdout annual `0.70x`、return `-8.53%`、win `66.67%`。
- 诊断含义：在本机制面和成本口径下，胜率 `>=80%` 与 DD `<20%` 可以同时达到，约束瓶颈是年化 `>=10x`——最好观察值离目标差约 5 倍，且最近三个月持续走弱。
- 报告：`diagnostics/sol-1h-ar-high-win-target-search-2026-07-07.md`；脚本：`scripts/research_sol_1h_ar_high_win_target_search.py`；产物：`artifacts/sol_1h_ar_high_win_*_2026-07-07.*`。

## 2026-07-07：按用户要求将高胜率最佳观察值登记为 V2

- 将 `ENS__SOL_1H_AR_HW_R132002__SOL_1H_AR_HW_R243705` 登记为 `SOL-1H-Adaptive-Regime-V2`。
- V2 机制：`donchian_break + vwap_revert` 双腿 ensemble；完整参数规格见 `specs/sol-1h-ar-v2-parameter-spec-2026-07-07.md`。
- V2 指标：full annual `2.07x`、return `290.00%`、DD `-17.41%`、win `93.91%`、trades `115`；last `1y` annual `1.60x`、win `92.31%`；reused holdout annual `0.70x`、return `-8.53%`、DD `-15.69%`、win `66.67%`、trades `6`。
- V2 状态：`registered observation / NO-GO / not promoted / not live-ready`。登记 V2 只固定高胜率观察参数，不代表 candidate、paper-live、dry-run、handoff 或 live。

## 2026-07-10：V2 机制诊断与改进方向

- V2 的高胜率来自大量小 TP；full 平均盈利 `+1.75%`、平均亏损 `-6.89%`、payoff `0.253`，最大单笔亏损 `-14.36%`。少数 stop 是收益上限的主要约束。
- 双腿拆分显示：收益结构重做后的 Donchian core full annual `2.0023x`、DD `-17.41%`、win `98.00%`，reused holdout return `+4.89%`；VWAP satellite full annual `1.5110x`，但 reused holdout return `-11.05%`、win `25.00%`。近期失效来自 VWAP short。
- 收益结构重做的 prefit-only 观察将 ensemble full annual 提升到 `3.0520x`，payoff 提升到 `0.616`，reused holdout DD 压至 `-10.04%`，但 reused holdout 仍为 `-6.71%`，不登记版本。
- 快速 entry veto 没有进入 prefit 前 100；分段止盈/failure exit 的 full annual `2.6188x`、reused holdout `-7.59%`，弱于收益结构重做；腿级 cooldown 的 prefit 最优仍为 `0 bars`。这些机制均不足以修复 VWAP regime 定义。
- `arm → confirm → expire` 状态机已完成验证：prefit-only 选中 `3-bar roc6+MACD confirm`，prefit annual `2.3129x`、DD `-19.05%`；full annual `2.0977x`；reused holdout 从负转为 return `+2.61%`、annual `1.1089x`、DD `-4.55%`，但只有 `3` 笔。
- 决策：冻结 V2 身份，不登记 V3。将状态机观察记为 `V2-SM-OBS`，不再依据 reused holdout 调参；后续采用 `Donchian core + VWAP arm-confirm-expire satellite`，等待新增 fresh forward trades。
- 综合结论：`notes/sol-1h-ar-v2-improvement-conclusion-2026-07-10.md`。
