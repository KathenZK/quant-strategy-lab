# HYPE-1D-MA7-ABT V6 漏趋势复盘与证据更正

## 结论

本轮没有找到可复现的 V7，也没有实现相对 V6 同时提高收益并降低风险。

复核后的证据边界是：

> ALTA 的未见时间窗已经否定 MA7 maturity event 的**无条件正 edge**，HYPE 同窗补丁也
> 没有找到双优；但 DSTO、TFML/P1E 与 QUML 的 held-source aggregate isolation
> 违反冻结合同，不能继续作为“OI、flow、quantile 均无增量”的证据。

因此，本报告撤回“当前全部可得信息下不可辨识”的终局归因。仍然成立的是：不得继续
在已揭示 HYPE 432 日或已揭示跨资产 holdout 上换模型、阈值和资产后宣称验证；若继续，
必须使用全新机制/target 与未见时间窗，并在每个 outer/inner fold 内重建 aggregates。

## 从现象到证据边界

### 1. 漏段真实存在，但全量补漏不经济

- 29 个事后稳定段中，V6 仅 15 段有同向暴露，时长加权覆盖 `39.51%`。
- 14 个完全漏段归因：freshness 10、全局 cooldown 3、单仓占用 1。
- 9 段主 root 的固定 5 日成本后收益为正，说明漏段不是纯视觉错觉。
- 但不读事后标签的 `0.25x` 隔离 probe 34 笔仅 11 笔盈利，把组合从 V6
  `+617.11%/-18.39%` 降为 `+496.39%/-21.72%`。

证据：[漏趋势归因](hype-1d-ma7-v6-missed-trend-attribution-2026-08-10.md)。

### 2. 机制级补丁没有解决选择性

- DTEC `1,152+16` 项无 PASS；最佳 long-only 仅一个确认样本，完整窗增收但 MDD 恶化。
- cooldown、late maturity、RSI memory、连续趋势与严格三门 overlay 均会释放更多假信号，
  或抢占 V6 的 OAPP/PEHC/long 路径。
- CTLS 六轮共 `13,056` 项，方向准确率、低 flip 与跨折稳定互斥，0 PASS。

证据：[DTEC 失败](hype-1d-ma7-v6-delayed-trend-episode-confirmation-failure-2026-08-10.md) ·
[连续趋势 overlay 失败](hype-1d-ma7-v6-continuous-trend-overlay-failure-2026-08-10.md) ·
[CTLS 最终失败](hype-1d-ma7-ctls-final-failure-2026-08-10.md)。

### 3. 跨资产路线必须区分有效失败与失效证据

| 路线 | 独立问题 | 结论 |
| --- | --- | --- |
| LMML | daily maturity price meta-label | OOF ranking 近零，仅 2/5 正资产 |
| RHT | `1h` hazard / first-hit timing | 等待后收益更差，root 内排序反向 |
| VIPR | 非 MA7 的 `1h` impulse/pullback/reclaim | 八配置、五资产均负 |
| DSML | OI/positioning/taker 贴冻结事件 | 官方历史容量不足，未建模 |
| DSTO | 高容量 daily anchor + OI/funding | P0R 有效；P1 aggregate isolation 违规，增量未知 |
| BPML | basis/premium meta-label | 19/20 folds 无选择，唯一 OOF 亏损 |
| TFML | native `5m` taker flow 增量 | P0 flow有效；P0E provenance blocker，P1/P1E aggregate isolation违规，增量未知 |

证据：[LMML](../../../asset-portfolios/1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md) ·
[RHT](../../../asset-portfolios/1h-ma7-root-hazard-timing/diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md) ·
[VIPR](../../../asset-portfolios/1h-volatility-impulse-pullback-reclaim/diagnostics/binance-1h-vipr-p1-development-2026-08-10.md) ·
[DSTO](../../../asset-portfolios/1d-derivatives-structure-trend-opportunity/diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md) ·
[BPML](../../../asset-portfolios/1d-ma7-basis-premium-meta-label/diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md) ·
[TFML fresh](../../../asset-portfolios/1d-ma7-taker-flow-meta-label/diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)。DSTO/TFML 链接中的复核更正优先于其保留的历史输出。

### 4. QUML second-fresh 输出已失效

QUML 在 BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL 上：

- 158 笔 mean `-0.0694%`、PF `0.910`；
- 正资产 `3/8`、正 folds `10/32`；
- ranking Spearman `0.0173`；
- cluster bootstrap `P(mean>0)=31.26%`；
- 相对 absolute control 的 `P(Δutility>0)=65.94%`。

上述数值来自 held source history 进入训练 aggregates 的实现，不能再归因成 ranking、
calibration 或 inner selection 的有效盲测失败。`z_lag1` 的口径审计仍能说明
executable-only 正值不可直接解释，但不恢复 P1 的 OOS 身份。

证据：[QUML P1 诊断](../../../asset-portfolios/1d-ma7-quantile-utility-meta-label/diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)。

### 5. 全新未见时间窗给出终局负证据

ALTA 在合同冻结后使用 21 个既有非 HYPE 资产的
`[2025-05-31, 2026-08-01)` 未见时间窗：

- source：966 个 Binance Vision 官方 ZIP，21 资产各 `10,248` 根完整 `1h`；
- capacity：`1,341` 个 test events，每资产 53–73，long/short `672/669`；
- `take_all`：mean `-0.1207%`、PF `0.829`、正资产 `8/21`；
- asset×90d bootstrap `P(mean>0)=0.16%`，95% 区间
  `[-0.1985%, -0.0403%]/event`，完整位于零下；
- 无网格 asset-local `Ridge(1000)+train q80`：276 笔 mean `-0.3107%`、
  PF `0.619`、正资产 `5/21`、bootstrap `0%`；
- local 相对少亏不能救援，因为其绝对经济性仍显著为负；
- common-event lag1 也分别比即时入场差 `26.0bps` 与 `15.4bps/event`。

这是有效的**未见时间**复制，且 HYPE requests/files/rows/features/train/evaluation
保持 `0/0/0/0/0/0`。它否定的是“substrate 无条件有正 edge”；它不能单独证明所有
未来独立信息 selector 都无效。

证据：[ALTA 合同](../../../asset-portfolios/1d-ma7-asset-local-temporal-audit/specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md) ·
[ALTA P1 诊断](../../../asset-portfolios/1d-ma7-asset-local-temporal-audit/diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md)。

## 失败原因归纳

1. **无条件 event edge 为负**：ALTA `take_all` 在未见时间窗显著为负，这是当前最强有效结论。
2. **HYPE 同窗补丁不经济**：隔离 probe、DTEC、cooldown、overlay 与状态机均未相对 V6 双优。
3. **独立信息尚未合法结算**：DSTO/TFML/QUML 的 aggregate isolation 违规，不能用于证明 OI/flow/quantile 不可辨识。
4. **历史 outcome 已暴露**：修实现后重复同一篮子只能作诊断，不能恢复盲测身份。
5. **机会成本仍是核心约束**：共享单仓时，即使 overlay 方向命中，也会破坏 V6 稀疏高价值路径；组合级仲裁尚未被本轮有效检验。

## 对 V6 的决定

- V6 身份、参数与 `registered / shadow-only / not promoted / not live-ready` 不变。
- 不登记 V7，不用杠杆掩盖 ALTA 已确认的无条件负 event edge。
- 关闭**已揭示历史上**基于同一 MA7 cross/maturity event 的 selector、threshold、
  model、late-entry、cooldown 与 overlay 搜索；这不是对所有未来独立信息的永久证伪。
- 组合级机会成本/资金仲裁仍是正交未检验问题，但必须先在非 HYPE、未见时间窗冻结，
  不能把 post-reveal satellite 结果回填到 V6。
- 唯一 clean 路径是继续执行冻结的 V6 prospective observer，等待至少 `90d` 与事件样本门；
  在样本到达前不作绩效判断。
- 若开新研究，优先使用**不以 MA7 maturity 为 root 的全新机制**或组合级机会成本
  仲裁；若重检 OI/flow，必须新合同、更大 universe、fold-local aggregates 与未见时间，
  且先在非 HYPE 上冻结，不能再用已揭示 432 日回填。

## 最终回答

V6 用 freshness/cooldown/单仓选择性换取少数高价值路径，简单放宽会释放更多负 EV
event；ALTA 已在未见时间确认这一点。但独立 OI/flow selector 的可辨识性仍属
**未结算**，不是已证伪。当前最严谨的回答是：

**“无条件补漏不经济；同一已揭示历史上的继续调参无效；独立信息需用修正后的全新
holdout 才能裁决。”**
