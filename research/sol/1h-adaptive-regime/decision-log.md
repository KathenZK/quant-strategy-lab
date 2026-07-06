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

- 主账和 README 已对齐为：`SOL-1H-Adaptive-Regime-V1 registered diagnostic baseline / NO-GO / not promoted / not live-ready`。
- V1 冻结身份来自 2026-07-03 广搜最佳 finalist `ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318`，机制为 `donchian_break + bb_revert` ensemble；新增 `scripts/sol_1h_ar_v1.py` 作为 V1 冻结 wrapper。
- V1 full annual `2.18x`、return `330.75%`、DD `-18.86%`、win `76.60%`、trades `94`；最近三个月 locked OOS annual `0.71x`、return `-8.09%`、DD `-16.19%`、win `50.00%`、trades `8`，不通过 `10x / 50% / <20% DD` 硬门槛。
- V1 全参数消融报告：`ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`；覆盖 `78/78` 个字段槽，clean surface 保留 `40` 个 active tunable 字段槽。
- V1 clean interface 报告：`research-notes/sol-1h-ar-v1-clean-interface-2026-07-03.md`；原始 `78` 个字段槽收敛为 `40` 个 clean tunable 字段槽，逐笔交易签名与 V1 相等。
- V1 clean tune 报告：`research-notes/sol-1h-ar-v1-clean-parameter-tune-2026-07-03.md`；每腿随机样本 `250000`，组合评估 `160000`，K+2/8 bps prefit 稳健候选 `395`。
- clean tune 只能作为 diagnostic observation；prefit annual `5.7104x`、DD `-18.81%`、win `85.71%`，但 reused holdout annual `0.1607x`、DD `-42.87%`、win `0.00%`，current full DD `-42.87%`，不能登记为 `V1.1/V2`，也不能 promotion。
