# BIN-MTF-PTC Regime Campaign V1 搜索合同

Campaign V0 在已揭示 validation 上表明：BTC no-half 具正长尾，但收益集中于 2024，2025 为负，且最大赢家超过策略全部净利润；ETH/HYPE 不合格。该结果只用于提出一个事前可解释的新机制：补上用户原始交易流程里的“日/周方向先验”，禁止直接按 validation 的赢家方向筛选。

## 搜索数据

BTC/ETH 只使用 development 内 expanding rolling folds：

- train through 2020-12-31 → evaluate 2021；
- train through 2021-12-31 → evaluate 2022；
- train through 2022-12-31 → evaluate 2023；
- 每 fold 训练末端 purge 14d。

HYPE 历史不足，只允许 train through 2025-08-31 → exploratory evaluate 2025-09-01 至 2025-10-31；不得据此取得同等资产资格。

原 validation 已因 V0 揭示；V1 选参后只可作为 revealed diagnostic validation 再运行一次，不得称为新 OOS。Locked historical evaluation 仍不读取。

## 高周期方向先验

所有变化只用 candidate 可见时点的价格，不使用均线或未来路径：

1. `none`：不加方向先验；
2. `weekly`：candidate 方向与过去 168h close-to-close 变化同向；
3. `monthly`：candidate 方向与过去 672h close-to-close 变化同向；
4. `weekly_monthly_consensus`：168h 与 672h 方向一致，且均与 candidate 同向。

过滤只决定 candidate 是否可发起 Probe/Add；continuation probability 的模型、标签、阈值和入口参数不改。

## Campaign 邻域

- max added layers：`0 / 1 / 3`；
- added layers >0 时 half-MFE giveback reduction：`on / off`；
- 其余 risk、stop、retry、funding、成本、3x、24h validation、336h timeout 全部沿用 Campaign V0。

去重后每资产共 `4 × (1 + 2 × 2) = 20` 个组合。禁止扩大空间或看到 fold 结果后加入新阈值。

## 选择与压力

主排名为三个 expanding folds 的合并 net log growth；同时要求：

- 各 fold 逐 15m 与 bar 内 MDD 均不超过 20%；
- risk violation 为 0；
- BTC/ETH 至少 2/3 fold 净收益为正；
- 合并 PF >1、交易数 >=30；
- tie-break 依次为最差 fold return、合并 Calmar/PF、较少 layers。

每资产只冻结一个胜出组合；胜出后补跑 8bps stress 与 revealed diagnostic validation。Stress 或 diagnostic validation 为负、收益仍由单笔/单年主导、或没有明显优于 none/probe-only，则不取得 locked evaluation 资格。HYPE 单 fold 无论结果如何都只标 exploratory。
