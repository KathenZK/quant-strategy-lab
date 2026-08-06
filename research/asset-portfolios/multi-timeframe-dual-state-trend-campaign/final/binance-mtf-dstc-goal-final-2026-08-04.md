# BIN-MTF-DSTC Goal 最终报告

## 结论

**HARD-GATE-FAILED / NO-GO / not promoted / not live-ready。**

本轮不是“完全找不到趋势策略”：BTC、ETH 各找到一条在 development、validation、多数 rolling folds、8/12bps 与 15m delay 下仍为正的微弱机制。其中最干净的 `BTC-BAL` 在 1% 总计划风险下年化资本因子 `1.028x`、MDD `-12.2%`、PF `1.65`；但它离最终 `>=2x` 年化门槛极远。把计划风险提高到 1.5% 只有 `1.041x`、MDD `-17.2%`，提高到 2% 已 `-21.7%`，3% 为 `1.076x / -29.5%`。

因此失败点不是“完美趋势策略在数学上不存在”，也不只是选错 HYPE；更准确的结论是：**当前 daily-MA Campaign + 4h structure + 1h pullback + 15m restart 机制只提取到很弱、方向不对称、阶段集中的趋势溢价。动态加仓可以放大这点溢价，但无法把 3%–6% 年化 alpha 变成 2x，更不可能在 20% MDD 内变成 20x。**

historical final audit 没有揭示；HYPE `[2026-08-02, 2026-11-02)` prospective 与本家族 `2026-08-05` 后 fresh prospective 均未用于选参或回测。

## 数据与执行门

- BTC：`241,993` 根 closed 15m，`2019-09-08 17:45` 至 `2026-08-03 11:45 UTC`；
- ETH：`234,353` 根，`2019-11-27 07:45` 至相同 cutoff；
- HYPE：`41,108` 根，`2025-05-30 10:30` 至 `2026-08-01 15:15 UTC`；查询文件集合在 prospective 前截断；
- 三资产缺口、重复、关键空值、无效 OHLCV、raw/normalized 全字段 parity、funding 均 PASS；
- `1h/4h/1d` 只从完整 `15m` 聚合，索引移动到最早可见收盘时刻；
- closed decision → next 15m open；stop gap 用更差 open；同 bar 新仓可被 stop；funding、每笔 fee `0.1%` 与 4bps adverse slippage 逐 fill 入账；
- BTCUSDT、ETHUSDT、HYPEUSDT 在 `2026-08-04` 官方 `exchangeInfo` 快照均为 `TRADING / PERPETUAL`；tick/step/min-notional 已记录。因为无候选进入 final，未用交易所精度去“优化”历史收益；
- cutoff、因果聚合、restart、gap stop、retry 与 3x leverage 单元测试 `7/7 PASS`。

## 实验规模与治理

- E01：三基线 × 三资产 × 两阶段，`18` 个回测；
- E02：`23` 个中心/单变量配置，`138` 个回测；
- E03：只组合单变量通过槽位，`10` 个配置、`20` 个回测；
- E04：去除语义 path-equal 后 `96` 个 asset/config，development/validation 共 `192` 个回测；
- E05：四个事前冻结诊断候选、`64` 个 risk/stress/side/rolling 回测；
- 合计 `432` 个账户级回测；未在 historical final 或 prospective 上救参。

## 机制归因

### 1. 双状态值得保留，但不是充分 alpha

在 BTC 中心参数上，双状态 Probe 相对 daily cross 基线一度把开发 PF 从 `1.16` 提到 `3.02`，验证 PF 到 `1.34`；但验证只有 6 个 Campaign，年化 `1.003x`。说明“position stop 不自动终止 Campaign”方向正确，却不能独立解决机会少和收益弱。

### 2. 回调/restart 微调不是主要矛盾

restart `2/4`、wait `12/24/36h`、pullback `0.25/0.5/0.75ATR` 多处近似同路径。真正改变行为的是 MA 尺度和 Campaign invalidation；继续在 restart 根数上密集搜参没有证据价值。

### 3. 加仓只放大已有优势

BTC `slope_structure` 两层加仓把开发年化从 `1.045x` 提到 `1.091x`，验证仍约 `1.003x`；四层甚至验证转负。只有 `MA14 + wrong0.5ATR` 的较稳定底座，加仓后 development/validation 才同时改善，但 1% 风险下最高仍只约 `1.06x`。

### 4. MFE 规则必须资产/尺度分离

- BTC MA14 的慢 Campaign 使用 `mfe50_all` 或只卸 adds 有时改善 PF/MDD；
- ETH `slope_structure` 使用 `mfe50_all` 反而恶化，`no_mfe` 更能保留凸性；
- HYPE 中心参数所有 `1/2/4 layers × no_mfe/mfe50` 都亏。

所以“最多让回一半”是可测试的风险偏好，不是跨资产有效定律。

### 5. Long/short 不可共用结论

- BTC-BAL：long-only `1.011x / PF 1.30`，short-only `0.995x / PF 0.81`；
- ETH-BAL：long-only `1.061x / PF 2.45`，short-only `0.978x / PF 0.55`。

优势主要来自长期上涨生态；空头 Campaign 未验证。

## E05 冻结候选

| Candidate | 1% annual | MDD | PF | 正 rolling | 8bps | 12bps | 15m delay | 结论 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BTC-BAL | 1.028x | -12.2% | 1.65 | 4/5 | 1.026x | 1.011x | 1.030x | 仅 annual 2x 失败；最干净的微弱优势 |
| BTC-GROWTH | 1.061x | -18.8% | 2.02 | 4/5 | 1.042x | 1.011x | 1.055x | 单一 2023–24 窗驱动、remove-top-3 失败 |
| ETH-BAL | 1.036x | -14.9% | 1.54 | 5/5 | 1.032x | 1.030x | 1.040x | 稳定但 remove-top-3 与 annual 失败；short 负 |
| ETH-CONVEX | 1.033x | -20.0% | 1.20 | 5/5 | 1.030x | 1.022x | 1.033x | PF/MDD/remove-top-3/annual 多门失败 |

`BTC-BAL` combined 区间 top-1/top-3 gross-profit share 为 `20.3%/49.6%`，remove-top-3 为 `-4.43%`，集中度门勉强通过；其他增长候选大多在 remove-top-3 后明显为负。

## 风险缩放为什么救不了

| Candidate | Risk | Annual | MDD | PF |
|---|---:|---:|---:|---:|
| BTC-BAL | 1.0% | 1.028x | -12.2% | 1.65 |
|  | 1.5% | 1.041x | -17.2% | 1.64 |
|  | 2.0% | 1.053x | -21.7% | 1.63 |
|  | 3.0% | 1.076x | -29.5% | 1.61 |
| BTC-GROWTH | 1.0% | 1.061x | -18.8% | 2.02 |
|  | 3.0% | 1.155x | -42.4% | 1.89 |
| ETH-BAL | 1.0% | 1.036x | -14.9% | 1.54 |
|  | 1.5% | 1.052x | -21.0% | 1.50 |
|  | 3.0% | 1.092x | -35.9% | 1.39 |

最大 effective leverage 仍显著低于 3x。限制策略的不是杠杆 cap，而是持仓时间、stop distance、机会密度和真实趋势延续优势。风险增加先撞上 MDD，远早于收益接近目标。

## HYPE 为什么视觉 MA7 好、落地仍失败

MA7 视觉上是价格的平滑轨迹，天然会在已经发生的长坡上显得“贴合”；但交易需要回答四个不同问题：何时因果确认、回调后何时成交、错了损失多少、趋势中的深回撤是否允许继续持有。HYPE 的结果是：

- daily cross 开发 `1.048x / PF1.81`，validation `0.936x / PF0.40`；
- 双状态中心 Probe development/validation 均亏，只有 `2/3` 个 Campaign；
- 放宽结构失效虽增加样本，validation 仍亏；
- add 与 MFE attribution 全部亏，不能把视觉趋势转成账户收益。

因此 HYPE 不是“选错了一个完全无趋势的币”，而是短历史中少数大坡过于显眼，MA7 的描述能力没有转化为稳定、可成交的条件优势。

## 最终状态与下一门

- 不登记 V1；不创建 live spec；不交接 quant-runner；不进入 dry-run/live；
- historical final audit 保持未揭示，不能为了 2x/20x 目标继续在同机制上救参；
- `BIN-MTF-DSTC` 关账为 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；
- 若继续，必须是 materially new successor：优先验证 long-only 跨资产 Campaign selector、相对强弱/资产轮动或加入 OI/basis/liquidation 等独立信息；不能只是 MA14、ATR band、MFE 比例继续细调。

## Evidence

- [Goal 合同](../specs/binance-mtf-dstc-goal-contract-2026-08-04.md)
- [数据与评估合同](../specs/binance-mtf-dstc-data-evaluation-contract-2026-08-04.md)
- [实验注册表](../specs/binance-mtf-dstc-experiment-registry-2026-08-04.md)
- [E05 候选冻结](../specs/binance-mtf-dstc-stability-candidate-freeze-2026-08-04.md)
- [数据审计](../artifacts/binance_mtf_dstc_data_audit_2026-08-04.json)
- [当前合约状态](../artifacts/binance_mtf_dstc_contract_status_2026-08-04.json)
- [E02 单变量](../artifacts/binance_mtf_dstc_single_variable_2026-08-04.json)
- [E03 组合](../artifacts/binance_mtf_dstc_combinations_2026-08-04.json)
- [E04 Add/MFE](../artifacts/binance_mtf_dstc_layers_mfe_2026-08-04.json)
- [E05 稳定性](../artifacts/binance_mtf_dstc_stability_2026-08-04.json)
- [交互式 Campaign 审计](../artifacts/binance_mtf_dstc_campaign_audit_2026-08-04.html)
