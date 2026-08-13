# Decision Log

## 2026-08-13 — 用户授权 dry-run observer

决定：按用户明确要求启动 `HYPE-1D-MA7-ABT-V7.1` dry-run observer。runner lock 将 `hype-1d-ma7-abt-v7-1-dry-run` 设为 `enabled_allowed=true`、`approval_level=dry_run`，`configs/dryrun.toml` 设 `enabled=true`。live 仍 `enabled=false`、`approval_level=none`。状态保持 `registered / not promoted / not live-ready`；dry-run 空仓启动，不根据当前行情重建 8 月 9 日研究路径上的多头。观察目标仍是至少 90 天或 5 笔闭合交易后再做开平仓对账。证据：[Lab live spec](live-specs/hype-1d-ma7-abt-v7-1-lab-live-spec.md) · [observer start](runner-tracking/hype-1d-ma7-abt-v7-1-dry-run-observer-2026-08-13.md)。

## 2026-08-13 — Runtime 保护/forced-reversal/PEHC 合同修补

决定：按 `quant-runner` 未提交代码审计修复 runtime 与 Lab live spec 的偏差，不改变 V7.1 身份、canonical 20 笔或 promotion 状态。修补包括：dry-run TouchOnly 原因 `stop` 视为保护止损并点亮 forced short；`1h` 保护序列缺失时 fail-closed，禁止回退日线 OHLC，并按 `last_protection_poll_ts` 补检漏掉小时线；`pending_forced_short` / PEHC next-open pending 在 `Opened` 前保留，拒绝反手立即 Hold 并写入多头冷却；持仓中日线软出场不再因 `1h` 失败而硬中断。Lab live spec 与 runner SPEC 已同步这些执行合同。`enabled_allowed=false`、`approval_level=none` 不变，不启用 dry-run/live。证据：[Lab live spec](live-specs/hype-1d-ma7-abt-v7-1-lab-live-spec.md) · [runner SPEC](/Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/hype_1d_ma7_abt/HYPE-1D-MA7-ABT-V7.1-SPEC.md)。

## 2026-08-12 — Runner strict parity 逐笔通过

决定：完成 `HYPE-1D-MA7-ABT-V7.1` runner strict parity，并以 V7 冻结 artifact `artifacts/hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json`（SHA256 `d7fbcdcb911c0fb7bda9cfdb08f6717b6d0b016be8b8ede380702f5eed28e324`）为 canonical source。最终复核命令为 `DINGTALK_WEBHOOK_URL=https://example.com cargo run -q -p quant-runner -- replay-dry-run --config configs/dryrun.toml --name hype-1d-ma7-abt-v7-1-dry-run --limit 500 --start-ts 2025-05-31T00:00:00Z --end-ts 2026-08-06T00:00:00Z`；432 根日线、10368 根小时线、2591 条 funding 事件下，runner 20 笔与 canonical 20 笔在 side、entry/exit timestamp、entry/exit reference price、bars held、exit reason、raw PnL、raw return 全部一致，`full_trade_matches=20`、mismatch `0`。headline 为 `+711.035936775286%`、chronological 1h MDD `-18.395542229660567%`、cost `16.72696722738397%`、funding `-1.3232555109724276%`、PF `17.509233233044547`，冻结目标 delta 均为 `0`；8bps 为 `+698.7499654030659%/-18.52798408021893%`。先前 FAIL 记录中“缺 exact V4 fair adapter / transition-repair”的根因判断已被源码还原推翻：实际差异来自 global cooldown、protective-stop forced reversal、PEHC 两阶段调度、exit priority 与 chronological accounting。runner runtime Driver 已同步修正普通反向 reclaim、首日 long protection、1h mark protection clock、forced reversal 与 PEHC 状态语义。`configs/active-strategy.lock.json` 的 parity 状态更新为 `PASS`，但 dry-run/live 继续 `enabled_allowed=false`、`approval_level=none`，不发布、不启用、不代表 live-ready。证据：[逐笔 runner tracking](runner-tracking/hype-1d-ma7-abt-v7-1-strict-parity-2026-08-12.md) · [runner strict parity PASS](artifacts/hype_1d_ma7_abt_v7_1_runner_strict_parity_2026-08-12.json) · [Lab live spec](live-specs/hype-1d-ma7-abt-v7-1-lab-live-spec.md)。

## 2026-08-12 — Runner strict replay 接入但 parity 未通过

决定：按用户要求推进 `quant-runner` 侧 strict parity，对 `kind = "hype_1d_ma7_abt"` 接入 Binance public `1d + 1h + funding` replay，并以 V7 冻结 artifact `artifacts/hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json` 作为 V7.1 canonical source（V7.1 与 V7 同路径同指标，只删除 dormant/schema 字段）。复核命令：`DINGTALK_WEBHOOK_URL=https://example.com cargo run -p quant-runner -- replay-dry-run --config configs/dryrun.toml --name hype-1d-ma7-abt-v7-1-dry-run --limit 500 --start-ts 2025-05-31T00:00:00Z --end-ts 2026-08-06T00:00:00Z`；数据窗口为 432 根日线、10368 根小时线、2591 条 funding 事件。当前 runner strict replay 输出 `FAIL`：约 `23` 笔、`+297.28%`、1h MDD `-29.55%`，未对齐 canonical `20` 笔、`+711.04%`、1h MDD `-18.40%`。根因不是数据源或 smoke 口径，而是 runner 仍使用简化 reclaim/slope entry；canonical V7/V7.1 继承 Lab exact V4 fair adapter 与 transition-repair entry state machine。状态继续保持 `registered / not promoted / not live-ready`，`configs/active-strategy.lock.json` 的 dry-run/live `parity_status` 仍必须为 `PENDING`，不得启用或发布。

## 2026-08-11 — Runner 实现但不启用

决定：按用户要求在 `quant-runner` 中实现 `HYPE-1D-MA7-ABT-V7.1` 的 `kind = "hype_1d_ma7_abt"`，并补 runner SPEC、disabled dry-run/live TOML 实例和 runner-owned lock 条目；但 dry-run/live 均保持 `enabled=false`、lock `enabled_allowed=false`、`approval_level=none`，不发布、不授权真实下单。runner 侧 `cargo clippy -p quant-runner --all-targets -- -D warnings`、`cargo test -p quant-runner`、dryrun/live config validate 均通过；`replay-dry-run --limit 300` 和复核 `--limit 500` 均只作为 runner smoke，分别覆盖 300/439 根公开日线，输出 `+42.18%/-16.85%/17笔` 与 `+29.47%/-24.66%/27笔`。这些数值不是 Lab V7.1 canonical 回测结果，不能用于收益验收；它们只证明 runner 代码路径、配置解析和基础交易生命周期可跑。canonical 仍以 Lab 1h/funding strict parity 为准（V7.1 历史口径为同 V7 的 `+711.04%/-18.40%/20笔`），当前 runner parity 尚未完成；clean prospective、dry-run observer、线上开平仓对账、tiny-live launch decision 与资金边界也仍未完成，状态保持 `registered / not promoted / not live-ready`。证据：[runner smoke artifact](artifacts/hype_1d_ma7_abt_v7_1_runner_smoke_2026-08-11.json) · [Lab live spec](live-specs/hype-1d-ma7-abt-v7-1-lab-live-spec.md)。

## 2026-08-04

决定：将用户提出的固定 `SMA7` 非对称多空规则建立为独立 `HYPE-1D-MA7-Asymmetric-Body-Trend` 研究线；由于“MA7 不穿过实体”存在方向歧义，保留字面版、方向性实体反转版和对称收盘反转版分别审计。三种解释在成本后全期均大幅亏损且相位/参数不稳，因此保持 `explore / not promoted / not live-ready`，不登记版本、不继续在已揭示历史上调参。证据：[初始合同](specs/hype-1d-ma7-abt-initial-contract-2026-08-04.md) · [初始报告](diagnostics/hype-1d-ma7-abt-initial-validation-2026-08-04.md) · [机器摘要](artifacts/hype_1d_ma7_abt_summary_2026-08-04.json)。

## 2026-08-04 — 多空分离趋势候选

决定：按用户要求保留固定 `SMA7`，搜索多空独立的 reclaim、斜率、迟滞退出和 ATR 保护，记录一个全期成本后 `+293.20%` 的 post-reveal 历史候选；因最终选择使用了已揭示最后 `90d`、仅 13 笔且相位门槛失败，继续保持 `explore / not promoted / not live-ready`，不登记版本。证据：[候选观察规格](specs/hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md) · [搜索报告](diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md) · [机器摘要](artifacts/hype_1d_ma7_separated_summary_2026-08-04.json)。

## 2026-08-05 — BTC/ETH 零调参迁移

决定：第 `041` 组原参数迁移到 BTC/ETH 后，组合在共同 `425d` 均亏损；UTC short-only 虽同向盈利，但 `12h` 相位同时翻负且样本低，不改变 HYPE 候选的 `explore / not promoted / not live-ready` 状态，也不在目标资产历史上继续调参。证据：[跨资产迁移诊断](../../asset-portfolios/1d-ma7-separated-trend-transfer/diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md)。

## 2026-08-05 — 登记 V1

决定：按用户要求将第 `041` 组多空分离参数登记为 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1`；登记只冻结身份，已知 post-reveal、低样本、相位失败、跨资产组合迁移失败和长仓首日无 hard stop 等缺口全部保留，状态为 `registered / not promoted / not live-ready`。证据：[V1 规格](specs/hype-1d-ma7-abt-v1-spec.md) · [家族主账](hype-1d-ma7-abt-core-ledger.md)。

## 2026-08-05 — SOX 全历史迁移

决定：V1 原参数在 Yahoo `^SOX` 的 `1994-2026` 全历史零成本回测为 `-36.29%`、MDD `-76.58%`，长期绝对与超额收益均失败；该证据不改变 V1 的登记身份，但进一步阻止 promotion，状态保持 `registered / not promoted / not live-ready`。证据：[SOX 全历史诊断](../../sox/1d-ma7-separated-trend-transfer/diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md)。

## 2026-08-05 — EMA7 替换

决定：只把 V1 的 SMA7 换成 `EMA(span=7)` 后，全期组合为 `+35.93%`、MDD `-46.15%`，但 long-only / short-only 均亏损且 `12h` 相位转为 `-19.34%`；EMA7 不登记、不替换 V1，不继续在已揭示历史上搜索 EMA span。证据：[EMA7 诊断](diagnostics/hype-1d-v1-ema7-substitution-2026-08-05.md)。

## 2026-08-05 — 迁移到 HYPE 4H

决定：日线 V1 状态机迁移到独立 HYPE 4H 家族后，bar-transfer / clock-equivalent combined 分别为 `-67.72% / -2.61%`，后者 long-only 虽为 `+17.07%`，但 short-only、成本、延迟、相位和超额收益均失败；不改变日线 V1 身份，不登记 4H 版本。证据：[4H 迁移诊断](../4h-ma7-asymmetric-body-trend/diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)。

## 2026-08-05 — 3x 杠杆

决定：每次入场目标 `3x`、持仓期间数量固定时，已揭示历史 combined 为 `+2,907.12%`、MDD `-56.40%`，但 `12h` 相位仅 `+6.98%`、MDD `-91.11%`，实际杠杆最高漂至约 `4.28x`，且未建模精确 maintenance margin 和 liquidation fee；V1 继续固定 `1x`，3x 不登记、不推进 runner。证据：[3x 杠杆诊断](diagnostics/hype-1d-v1-3x-leverage-2026-08-05.md)。

## 2026-08-05 — MU 双市场迁移

决定：V1 原参数在 Binance `MUUSDT` 上 combined 为 `-12.30%`，在 Nasdaq `MU` 上虽为 `+51.51%`，但只触发多头、远逊于 buy-and-hold，且股票数据为 `raw_unaccepted`；该结果不改变 HYPE V1 身份，只增加跨市场无超额与空头不可迁移证据。证据：[MU 双市场诊断](../../mu/1d-ma7-separated-trend-transfer/diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md)。

## 2026-08-05 — BTC 周 K 迁移

决定：V1 状态机换成 Binance BTC 周 K 后，两种时间合同 combined 均为 `-21.72%`、MDD `-29.61%`，long-only / short-only 与半周偏移相位也全部亏损；该结果不改变 HYPE V1 登记身份，只增加 timeframe transfer 失败证据，BTC 周线不登记版本。证据：[BTC 周 K 迁移诊断](../../btc/1w-ma7-asymmetric-body-trend/diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md)。

## 2026-08-05 — BTC/ETH 共享参数回测 HYPE

决定：BTC/ETH development 选出的共享 MA7 参数原样用于 HYPE 后 combined `-65.15%`、MDD `-73.47%`，long-only / short-only 和两个日界均亏损；共享参数不替换 HYPE V1，也不根据 HYPE 已揭示结果重新调参。证据：[共享参数 HYPE control 诊断](../../asset-portfolios/1d-ma7-asset-specific-search/diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)。

## 2026-08-06 — 冻结前瞻观察协议并完成观察 #1

决定：数据湖经零 blocker 补充至 `2026-08-06 07:00 UTC` 后，在产生任何新数据策略输出前冻结 V1 前瞻观察协议（锚点复算校验、观察窗定义、累计判定纪律 `>=90d` 且 `>=5` 笔）；观察 #1 锚点逐位一致，窗口（7 日）净 `-1.69%`、1 笔平仓，如实入账，不触发任何参数或状态变化。证据：[协议](specs/hype-1d-ma7-abt-v1-prospective-observation-protocol-2026-08-06.md) · [观察 #1](diagnostics/hype-1d-ma7-abt-v1-prospective-obs-2026-08-06.md)。

## 2026-08-06 — 首日保护与相位/起跑点审计

决定：补齐 V1 两项审计缺口——多头首日 MAE 最差 `0.76x ATR7`、假设首日 `1-3x ATR` 止损历史零触发（契约缺口保留）；60 起跑点全部为正；23 个有效相位中位 `+26.94%`、17 正 6 负。按同日修订的全局治理口径，相位改为非强制检查项：该结果降低历史收益置信度但不单独构成 blocker；V1 仍因 post-reveal、小样本、prospective/OOS 与执行缺口维持 `registered / not promoted / not live-ready`。证据：[审计诊断](diagnostics/hype-1d-ma7-abt-v1-protection-phase-audit-2026-08-06.md) · [全局门禁规范](../../../docs/research-governance/strategy-validation-gates.md)。

## 2026-08-06 — 多头 MA7 退出同开盘反手空

决定：冻结后检验“V1 多头 `ma7_hysteresis_exit` 时同 open 平多并反手空”；全期只新增 1 笔空单且成本后亏损约 `-0.14%`，组合由 `+293.20%` 降至 `+292.64%`，压力结果也下降。V1 原 5 笔空单全部盈利，问题是触发覆盖少而非已成交空单质量差；该变体不采纳、不登记、不改写 V1。证据：[跨资产反手诊断](../../asset-portfolios/1d-ma7-asset-specific-search/diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md)。

## 2026-08-06 — 多头 trailing stop 后反手空

决定：首次运行前冻结“V1 多头 trailing stop 后在下一根真实 `1h` open 反手空，并沿用 V1 原 short exit”的执行合同；历史主相位全期由 `+293.20%` 提高到 `+322.59%`，压力也改善，新增 7 笔空合计净 PnL 为正，但 prefit 无优势、额外延迟和 `12h` 相位均弱于 V1，约 `93%` 的新增空收益集中于已揭示的 2026-07-11 后一笔。保留为可独立前瞻观察的 post-reveal 候选，不并入 V1、不登记 V2、不改变状态。证据：[冻结合同](specs/hype-1d-ma7-abt-trailing-stop-short-reversal-contract-2026-08-06.md) · [诊断](diagnostics/hype-1d-v1-trailing-stop-short-reversal-2026-08-06.md)。

## 2026-08-06 — 登记 V2

决定：按用户明确要求，将“V1 + 多头 trailing stop 后在下一根真实 `1h` open 反手空、反手后沿用原空头退出”的机制登记为 `HYPE-1D-MA7-Asymmetric-Body-Trend-V2`，默认仓位保持 `1x`。登记只冻结版本身份；post-reveal、增量集中、无独立 prospective 和执行审计缺口全部保留，状态为 `registered / not promoted / not live-ready`。证据：[V2 规格](specs/hype-1d-ma7-abt-v2-spec.md) · [家族主账](hype-1d-ma7-abt-core-ledger.md)。

## 2026-08-06 — V2 3x 杠杆观察

决定：按首次运行前冻结的合同，仅把 V2 每次自然/反手入场目标改为约 `3x`；主相位全期为 `+3,203.85%`、MDD `-57.55%`，实际杠杆最高 `4.11x`，但 `12h` 相位为 `-33.13%`、MDD `-90.92%`、最高 `4.28x`，且未建模 Binance maintenance margin 和 liquidation fee。3x 只记为 official observation，不改变已登记 V2 的 `1x` 身份，不创建 live spec 或推进 runner。证据：[3x 合同](specs/hype-1d-ma7-abt-v2-3x-leverage-contract-2026-08-06.md) · [3x 诊断](diagnostics/hype-1d-v2-3x-leverage-2026-08-06.md)。

## 2026-08-06 — V2 全参数与斜率专项消融

决定：27 个 active-parameter OAT、32 组斜率网格及分期/压力/延迟/滚动/相位检查显示，多头入场 slope 完全移除后为 `-45.82%`，空头入场 slope 完全移除后仅 `+64.22%`，全部 slope 移除为 `+26.99%`、MDD `-57.94%`；short slope exit 移除主相位仍有 `+300.49%`，但 `12h` 翻为 `-8.50%`。保留 V2 三层 slope 逻辑和 `0.02×ATR7` 阈值，不根据已揭示网格改参、不登记新版本。证据：[冻结合同](specs/hype-1d-ma7-abt-v2-full-parameter-ablation-contract-2026-08-06.md) · [消融报告](ablations/hype-1d-ma7-abt-v2-full-parameter-ablation-2026-08-06.md)。

## 2026-08-07 — 二元/三状态 MA7 迟滞诊断

决定：固定 `±0.75×ATR7` 的连续多空反转虽消除了 slope/reclaim 导致的“越界仍不开仓”，但全期仅 `+23.45%`、MDD `-55.12%`、23 个有效相位仅 1 正；增加 `±0.25×ATR7` 连续 3 日震荡空仓后为 `+20.79%`、MDD不变、相位仅 2 正，且暴露率仍达 `92.94%`。两种机制均不登记 V3，不修改 V2，也不在已揭示结果后追加容错参数搜索。证据：[冻结合同](specs/hype-1d-ma7-abt-three-state-hysteresis-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-three-state-hysteresis-2026-08-07.md) · [交易路径](artifacts/hype_1d_ma7_three_state_hysteresis_trade_path_2026-08-07.html)。

## 2026-08-07 — 状态边界 × V2斜率混合诊断

决定：persistent regime 零调参结合 V2 slope/非对称边界后，CORE 为 `-38.33%`、MDD `-70.95%`；加回V2保护、max-hold和cooldown后为 `-43.19%`、MDD `-61.08%`。CORE 39笔入场仅8笔满足原V2 reclaim，21笔short全部不满足reclaim且合计亏损，证明slope只过滤方向、reclaim还过滤趋势事件新鲜度。两种混合均不采纳、不登记，不修改V2。证据：[冻结合同](specs/hype-1d-ma7-abt-state-slope-hybrid-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-state-slope-hybrid-2026-08-07.md) · [交易路径](artifacts/hype_1d_ma7_state_slope_hybrid_core_trade_path_2026-08-07.html)。

## 2026-08-07 — V2空头迟滞放宽至0.75诊断

决定：只把short迟滞退出从`0.25×ATR7`放宽至`0.75×ATR7`后，全期从`+322.59%`提高至`+350.85%`、MDD不变、23个有效相位由19正改善为22正；但增量只来自prefit两笔空单延后2日，额外延迟一天反而从`+135.36%`降至`+104.25%`，故不改写V2，留作冻结后观察候选。登记V2与`0.75`变体主路径的short hard stop和trailing stop均为`0次`。证据：[冻结合同](specs/hype-1d-ma7-abt-v2-short-hysteresis-075-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v2-short-hysteresis-075-2026-08-07.md)。

## 2026-08-07 — 登记V3

决定：按用户明确要求，将“V2全部机制 + short `exit_buffer_atr=0.75`”登记为`HYPE-1D-MA7-Asymmetric-Body-Trend-V3`，默认仓位保持`1x`。登记只冻结版本身份；post-reveal、实际只改变两笔退出、延迟恶化和无独立prospective等缺口全部保留，状态为`registered / not promoted / not live-ready`。证据：[V3规格](specs/hype-1d-ma7-abt-v3-spec.md) · [家族主账](hype-1d-ma7-abt-core-ledger.md)。

## 2026-08-07 — V3全参数消融

决定：28个OAT、32组斜率网格及分期/压力/延迟/滚动/24相位检查显示，移除long/short入场斜率后分别为`-45.00% / +52.25%`，移除short斜率退出为`+211.69%`，全部斜率移除为`-68.57%`、MDD`-81.45%`；reclaim、short entry buffer、两侧迟滞、long trailing与强制反手同样有历史贡献。short保护、max hold及long cooldown虽历史未咬合仍保留；不追逐网格赢家，不修改V3、不登记V4。证据：[冻结合同](specs/hype-1d-ma7-abt-v3-full-parameter-ablation-contract-2026-08-07.md) · [消融报告](ablations/hype-1d-ma7-abt-v3-full-parameter-ablation-2026-08-07.md)。

## 2026-08-07 — V3 3x杠杆观察

决定：只把V3每次自然/反手入场目标改为约`3x`后，主相位为`+3,795.79%`、MDD`-57.55%`、实际杠杆最高`4.11x`；延迟一天MDD达`-72.33%`，`12h`仅`+8.25%`、MDD`-86.39%`、最高`4.28x`，且未建模真实maintenance margin与liquidation fee。3x只记为official observation，不改变V3的`1x`身份，不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v3-3x-leverage-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-v3-3x-leverage-2026-08-07.md)。

## 2026-08-07 — V3日线跌破MA7次日反手

决定：将long trailing改为只平仓，并只在前收仍位于MA7上、当收跌到MA7下时于次日open反手short后，主相位由V3的`+350.85%`降至`+20.81%`、MDD扩大至`-37.23%`、延迟为`-16.83%`；6笔反手全部不满足V3自然short的向下slope门槛。该候选不采纳、不登记、不修改V3；若只删除trailing反手，控制仍为`+306.41%`、MDD`-26.44%`。证据：[冻结合同](specs/hype-1d-ma7-abt-v3-daily-ma7-cross-reversal-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v3-daily-ma7-cross-reversal-2026-08-07.md) · [交易路径](artifacts/hype_1d_ma7_abt_v3_daily_ma7_cross_reversal_trade_path_2026-08-07.html)。

## 2026-08-07 — V3强制反手入场缺陷

决定：复核登记V3的7笔trailing强制反手，确认R-S02与R-S12在反手时最近完整日MA7上方开空且均亏损，5/7只持有1日、其中4笔亏损；“绕过short slope入场、建仓后立即启用slope exit”构成结构性live-readiness blocker。该发现不追溯改写V3身份或历史指标，但修复前不得推进promotion。证据：[强制反手入场审计](diagnostics/hype-1d-ma7-abt-v3-forced-reversal-entry-audit-2026-08-07.md)。

## 2026-08-07 — V3强制反手确认修正

决定：`MA_ONLY`只允许拟反手`1h` open低于上一完整日MA7时开空，拒绝R-S02/R-S12后主路径为`+411.23%`、MDD`-26.81%`，但仍有3笔一日反手；再要求V3 short slope的控制只保留1笔反手，为`+335.18%`、MDD`-26.44%`。`MA_ONLY`作为post-reveal候选保留，不登记V4、不修改V3；后续若继续，只隔离检验反手short的slope exit。证据：[冻结合同](specs/hype-1d-ma7-abt-v3-forced-reversal-confirmation-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v3-forced-reversal-confirmation-2026-08-07.md) · [交易路径](artifacts/hype_1d_ma7_abt_v3_ma_only_reversal_trade_path_2026-08-07.html)。

## 2026-08-07 — 登记V4

决定：按用户明确要求，将`MA_ONLY`登记为`HYPE-1D-MA7-Asymmetric-Body-Trend-V4`：保留V3全部参数，但只有拟反手真实`1h` open低于上一完整日MA7时才做空，否则flat并进入2日cooldown，且不保留pending反手。登记只固定post-reveal版本身份，状态为`registered / not promoted / not live-ready`；2025-06-17自然short cross因slope未通过、随后reclaim freshness消失而漏空，作为已知缺口保留。证据：[V4规格](specs/hype-1d-ma7-abt-v4-spec.md) · [形成诊断](diagnostics/hype-1d-ma7-abt-v3-forced-reversal-confirmation-2026-08-07.md) · [V4交易路径](artifacts/hype_1d_ma7_abt_v4_trade_path_2026-08-07.html)。

## 2026-08-07 — V4自然short入场时序

决定：`1d`入场slope与“fresh cross持续armed至`2d` slope确认”均抓到2025-06下跌，分别于6月18/19日开空并盈利`+8.41%/+7.23%`；但全期分别由V4的`+411.23%`降至`+297.11%/+70.27%`，后者MDD扩大到`-34.63%`、`12h`转为`-22.15%`。两种机制都会因新增short与cooldown错过后续高收益long，因此不修改V4、不登记V5。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-short-entry-timing-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-short-entry-timing-2026-08-07.md)。

## 2026-08-07 — V4多空持续regime入场

决定：按用户澄清，将“穿越不失效”重定义为flat时只要当前close仍在MA7对应一侧且方向slope通过就可次日入场，多空对称、不要求前一日reclaim；结果为`-42.91%`、MDD`-73.01%`、40笔，23个有效相位全部亏损。该规则在6月16日先重新做多，至6月19日trailing反手，说明若希望short条件出现时直接平多反手，必须另行定义target-side reversal；本轮不修改V4、不登记新版本。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-flat-regime-entry-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-flat-regime-entry-2026-08-07.md)。

## 2026-08-07 — V4目标侧regime直接反手

决定：按用户明确选择，当相反方向MA7侧别+slope确认时，于下一日open平原仓并立即反手；6月19日00:00成功平多开空，该short赚`+7.23%`。但全期为`-44.31%`、MDD`-73.55%`、49笔、17次直接反手，仅4/23有效相位为正，说明持续MA7侧别+slope会在震荡期频繁翻转，不能替代V4 reclaim freshness；不修改V4、不登记新版本。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-target-side-regime-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-target-side-regime-2026-08-07.md)。

## 2026-08-07 — V4 cooldown消融

决定：long `2d` cooldown改0在UTC主路径、压力、延迟、`12h`、近期、滚动与最新延伸逐笔零影响，但24相位中位由`+38.35%`降至`+34.75%`，删除没有收益；short `5d` cooldown改0后由`+411.23%`降至`+303.19%`、新增5笔，`12h`由`+35.33%`转为`-0.98%`且尾部显著恶化。V4继续保留long 2日与short 5日，不登记新版本。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-cooldown-ablation-contract-2026-08-07.md) · [消融](ablations/hype-1d-ma7-abt-v4-cooldown-ablation-2026-08-07.md)。

## 2026-08-07 — V4 ATR容错趋势状态机

决定：按用户确认实现`±0.75×ATR7+slope`完整target、保护退出只转flat及cooldown后同趋势重入；候选虽在6月20日补开short，但该笔亏`-7.83%`，全期`-26.40%`、MDD`-55.19%`、28笔，20笔保护退出且23个有效相位全部亏损。不修改V4、不登记V5。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-band-state-machine-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-band-state-machine-2026-08-07.md) · [交易路径HTML](artifacts/hype_1d_ma7_abt_v4_band_state_machine_trade_path_2026-08-07.html)。

## 2026-08-07 — V4有限reclaim pending逐步诊断

决定：在完全保留V4入场/退出/保护/cooldown的前提下，short等待1/2日分别为`+110.73%/+70.27%`，long等待1/2日为`+216.12%/+164.91%`，四个多空组合仅`+26.68%`至`+58.85%`；有限等待能补6月short，但无质量约束时仍因追单、仓位占用和cooldown显著降低精度。不修改V4、不登记新版本。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-finite-reclaim-pending-contract-2026-08-07.md) · [逐步诊断](diagnostics/hype-1d-ma7-abt-v4-local-repair-ladder-2026-08-07.md)。

## 2026-08-07 — V4 short pending质量与handoff候选

决定：第二轮只增加延迟short距MA7不超过`0.75×ATR7`的anti-chase，并只允许delayed仓位退出时由原V4 opposite reclaim同open交接；候选同时保留6月19日short和6月28日long，全期`+426.21%`、MDD`-29.25%`、20笔、23相位21正，通过冻结底线，但PF、延迟和相位中位弱于V4且机制来自二次post-reveal。保留为可冻结前瞻观察候选，不登记V5。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-pending-quality-handoff-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-local-repair-ladder-2026-08-07.md) · [交易路径HTML](artifacts/hype_1d_ma7_abt_v4_pending_quality_handoff_trade_path_2026-08-07.html)。

## 2026-08-07 — V4对称MA7 cross × 持仓迟滞

决定：按用户澄清，flat入场只看fresh MA7 cross，持仓后才使用双侧`0.75×ATR7`容错；行为正确抓到6月17日cross并于6月18日开short，但全期仅`+44.12%`、MDD`-53.32%`且`12h=-69.64%`，不替代V4、不登记V5。证据：[冻结合同](specs/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-2026-08-07.md) · [交易路径HTML](artifacts/hype_1d_ma7_abt_v4_symmetric_cross_d075_trade_path_2026-08-07.html)。

## 2026-08-09 — 原始 MA7 趋势状态机与 RSI6 分臂

决定：按用户“都按建议”冻结fresh cross直入、持仓armed `0.75×ATR7`、strict日线slope、short连续3日`RSI6<30`盈利止盈及3日`RSI6>70`后fresh down-cross提前反空。A核心为`-33.52%`、MDD`-57.28%`；B止盈改善至`-8.54%`、MDD`-50.27%`并把short腿转正，但`8bps=-12.54%`且MC3亏损概率`56.40%`；C无一次合格事件并与A逐笔相同，D与B相同；`1.5ATR`保护恶化。该分支保持`explore`，不登记V5、不修改V1–V4、不推进runner；若继续，只能按独立前瞻协议平行观察A–D，下一机制问题转向单日slope exit的过度抖动。证据：[冻结合同](specs/hype-1d-ma7-original-trend-state-machine-contract-2026-08-09.md) · [诊断](diagnostics/hype-1d-ma7-original-trend-state-machine-2026-08-09.md) · [消融](ablations/hype-1d-ma7-original-trend-ablation-2026-08-09.md) · [前瞻协议](specs/hype-1d-ma7-original-trend-prospective-observation-protocol-2026-08-09.md) · [交易路径](artifacts/hype_1d_ma7_original_trend_trade_path_2026-08-09.html)。

## 2026-08-09 — 原始意图优化 Development 硬门失败

决定：按预注册完成 structure OAT 与 174 个 Development trial；第一名 `C001` 及全部 final pool 均未在 D-full/WFO 同时实现相对 exact V4 的更高收益、更小 MDD，且 `8 bps` 压力失败，因此 development hard-gate `FAIL`、本轮不晋级，不替补 champion、不揭 V/H、不登记 V5、不改 V1–V4、不推进 runner。分支保持 `explore / not promoted / not live-ready`，本轮结果仅作诊断证据。证据：[预注册合同](specs/hype-1d-ma7-intent-optimization-preregistration-2026-08-09.md) · [Development 诊断](diagnostics/hype-1d-ma7-intent-optimization-development-2026-08-09.md) · [消融](ablations/hype-1d-ma7-intent-optimization-development-ablation-2026-08-09.md) · [机器裁决](artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development.json) · [失败首位交易路径](artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.html)。

## 2026-08-09 — V4-PFT修复 Development 硬门失败

决定：以exact V4为唯一control，预注册并完成P（short pending/handoff）、F（forced reversal slope确认）、T（盈利short的RSI6 `25×2`止盈）2×2×2共8臂。0个臂同时通过D-full与D-WFO收益更高、MDD更小的硬门，因此无champion、V/H未揭示、不登记V5、不改V4、不推进runner。`A001_T`在D-full由`+160.02%/-22.34%`改善到`+199.93%/-19.67%`，WFO收益由`+62.34%`提高到`+86.29%`，但WFO最差MDD仍为`-19.67%`；最差折只有一笔long，三个short侧修复模块均无法触及。P在D有2次delayed confirm但WFO F1新增亏损，F则删掉重要盈利forced short。证据：[预注册合同](specs/hype-1d-ma7-abt-v4-pft-repair-preregistration-2026-08-09.md) · [Development归因](diagnostics/hype-1d-ma7-abt-v4-pft-repair-development-2026-08-09.md) · [机器裁决](artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development.json) · [A001_T交易路径](artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development_failed_A001_T_trade_path.html)。

## 2026-08-10 — TPR一次性Validation失败

决定：以exact V4为唯一`1x` control，预注册真实`1h`顺序MDD、signed ER7入场过滤Q、盈利long slope decay E、固定RSI6 `25×2` short止盈T和V通过后才允许的`<=3x`杠杆层。`QOFF_EOFF_T25X2`是唯一D champion：D `+199.93%/-16.42%` vs V4 `+160.02%/-21.66%`，WFO `+86.29%/-13.14%` vs `+62.34%/-14.25%`，T在D触发4次且OAT PASS；Q会删掉高价值fresh reclaim，E在49个long held-day中0次合格。一次性V中T为0次触发，候选与V4逐笔相同，均为`+12.21%/-18.82%`、3笔，故严格双重支配失败。按合同停止，不运行固定/动态杠杆，不揭H，不登记V5，不修改V4，不推进runner。证据：[预注册合同](specs/hype-1d-ma7-trend-phase-risk-preregistration-2026-08-09.md) · [Validation裁决](diagnostics/hype-1d-ma7-trend-phase-risk-validation-2026-08-09.md) · [Development机器裁决](artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development.json) · [Validation机器裁决](artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_validation.json) · [D路径HTML](artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development_QOFF_EOFF_T25X2_trade_path.html)。

## 2026-08-10 — WTL广域搜索因冻结样本门失败

决定：在D+V均已暴露、H保持未触碰的边界下，以exact V4为唯一1x control，完成Stage A `555/555`、Stage B `32/32`与Stage C `624/624`，0 error。Stage C有440个组合同时在D与V实现收益更高、真实`1h` MDD更小并满足materiality、路径变化和V退出激活，但long盈利保护会提前结束一笔21日盈利多单并避免其后的坏forced short，使V候选只剩1–2笔，全部触发冻结的`candidate>=3`硬门。门禁不得事后放松，因此无champion、无杠杆、H未揭示、不登记V5、不改V4、不推进runner。失败后对162条独立经济路径做全上下文leave-one-out：long MFE是唯一D/V稳定双优模块，short RSI在D稳定为正但V休眠，entry在D不稳且压缩样本，short MFE在V休眠。后继只能另立机会感知合同，用eligible trend episode、独立fold/path和leave-one-trade-out代替单纯候选平仓数。证据：[预注册合同](specs/hype-1d-ma7-wide-trend-lifecycle-preregistration-2026-08-10.md) · [失败裁决](diagnostics/hype-1d-ma7-wide-trend-lifecycle-failure-2026-08-10.md) · [多轮消融](ablations/hype-1d-ma7-wide-trend-lifecycle-post-fail-ablation-2026-08-10.md) · [Stage C机器证据](artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_stage_c.json)。

## 2026-08-10 — OAPP一次性H失败

决定：另立机会感知合同，仅宽搜long MFE与short RSI，完成957个单模块、32条稳健路径、64个组合及11组完整OAT。唯一Development champion `C_2AA556432E9E`为fraction trail `0.5ATR/10%/2d` + RSI6 `20×2`；D、V、rolling分别为`+263.04%/-16.42%`、`+17.49%/-15.00%`、`+134.42%/-13.14%`，均严格优于exact V4，并通过8bps、funding-off、相邻参数和最大增量episode剔除。H一次性揭示后，候选`+16.70%/-17.94%`，V4`+22.43%/-17.94%`，hard-gate FAIL。原因是提前锁利虽把一笔long由`-1.20%`改为`+3.16%`，但同时切断V4随后`+16.87%`的forced short；RSI在H 0次触发。全部9个杠杆臂只作审计，不用杠杆救援1x失败；不登记V5、不改V4、不promotion、不推进runner。H已耗尽，任何后继只能把现有432日视为exposed并等待新增前瞻证据。证据：[预注册合同](specs/hype-1d-ma7-opportunity-aware-profit-protection-preregistration-2026-08-10.md) · [最终裁决](diagnostics/hype-1d-ma7-opportunity-aware-profit-protection-final-2026-08-10.md) · [多轮消融](ablations/hype-1d-ma7-opportunity-aware-profit-protection-ablation-2026-08-10.md) · [最终机器报告](artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_final.json) · [完整逐笔HTML](artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_full_trade_path.html)。

## 2026-08-10 — 启动PEHC shadow与新增前瞻任务

决定：OAPP H FAIL显示盈利退出与forced-reversal资格是同一状态链，另立PEHC materially new合同。现有432日及旧H全部标记exposed；固定OAPP long `0.5ATR/10%/2d`与RSI20×2，不继续救援参数，改为宽搜490个shadow原long/handoff组合（expiry、short slope、anti-chase、同小时/次日执行）。历史搜索只能冻结一个shadow候选，不能登记或promotion；最终资格必须来自合同冻结后新增至少90日HYPE数据并满足交易/多空/handoff事件门。1x前瞻PASS前禁止研究杠杆，旧H不得再次用于选择后宣称验证。证据：[PEHC预注册合同](specs/hype-1d-ma7-profit-exit-handoff-continuity-preregistration-2026-08-10.md)。

## 2026-08-10 — 冻结PEHC_294作shadow，等待clean prospective

决定：490臂、8个flat-start block、8bps、funding-off、12h相位及多轮逐事件消融均完成，13条经济路径中3条通过shadow门，冻结最低复杂度`PEHC_294`（8日shadow、slope OFF、MA-only、下一UTC日复核）。已暴露全窗`+617.11%/-18.39%`优于exact V4 `+398.84%/-25.09%`，删除最大赢家后仍优于fixed OAPP，但5次接受中有1次负贡献且没有新前瞻数据；因此不登记V5、不promotion、不研究杠杆，从`2026-08-11`起等待至少90日及事件样本门。证据：[冻结裁决](diagnostics/hype-1d-ma7-profit-exit-handoff-continuity-shadow-freeze-2026-08-10.md) · [消融](ablations/hype-1d-ma7-profit-exit-handoff-continuity-ablation-2026-08-10.md) · [机器shadow](artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_shadow_candidate.json) · [逐笔HTML](artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_full_trade_path.html)。

## 2026-08-10 — 冻结PEHC前瞻observer执行链

决定：不改PEHC/V4/OAPP任何已冻结文件，新增outcome-locked observer；以cold-flat、requested start后首个可执行open、排除terminal强平样本、最早样本合格terminal和一次性access lock消除运行日选择。observer manifest通过97项联合测试并逐字节复现冻结候选/V4 anchor；初始观察为0个新增完整日且`performance_disclosed=false`，目标继续活跃、杠杆继续锁定。证据：[observer补充协议](specs/hype-1d-ma7-profit-exit-handoff-continuity-prospective-observer-v1-2026-08-10.md) · [observer manifest](artifacts/hype_1d_ma7_profit_exit_handoff_continuity_prospective_observer_v1_2026-08-10_manifest.json) · [初始观察](artifacts/hype_1d_ma7_profit_exit_handoff_continuity_prospective_observer_v1_2026-08-10_observation_through_2026-08-05.json)。

## 2026-08-10 — 登记V5与V6

决定：按用户明确要求，将固定OAPP `C_2AA556432E9E`登记为`HYPE-1D-MA7-Asymmetric-Body-Trend-V5`，将其上的`PEHC_294`登记为V6；两者主状态均为`registered / not promoted / not live-ready`，V5的H失败与V6的shadow-only、至少90日新增前瞻及杠杆锁定事实不变。证据：[V5规格](specs/hype-1d-ma7-abt-v5-spec.md) · [V6规格](specs/hype-1d-ma7-abt-v6-spec.md) · [家族主账](hype-1d-ma7-abt-core-ledger.md)。

## 2026-08-10 — 启动CTLS持续趋势生命周期研究

决定：另立CTLS分支，将趋势方向状态与真实仓位解耦，预注册慢涨、阴跌、加速、减速、反转和震荡的因果状态、324项识别网格、最多3,888项生命周期与864项风险搜索；现有432日只作已暴露诊断和一次性LES拒绝门，clean资格只能来自冻结后至少90日新增数据，1x通过前禁止杠杆。证据：[CTLS预注册合同](specs/hype-1d-ma7-continuous-trend-lifecycle-preregistration-2026-08-10.md)。

## 2026-08-10 — CTLS R1–R6最终方向门失败

决定：按预注册顺序完成规则十状态、连续强度、严格walk-forward监督学习、稳定趋势段、持续期解码及日内/量/funding/BTC上下文六轮，共`13,056`个状态/方向配置，全部0项通过。R6最接近的稳定路径balanced accuracy `0.5729`、三类recall与5/5折均通过，但flip `0.1767`失败；把flip压至`0.1124`的路径仅2/5折通过。状态识别门未过，本轮裁决为`HARD-GATE-FAILED`，主状态保持`explore / not promoted / not live-ready`。因此未运行PnL、未访问LES、未研究杠杆、无交易候选或HTML；不登记V7、不promotion、不推进runner。同一432日停止继续调参，后继只能依赖至少90日新增clean prospective或新的跨资产/长历史合同。证据：[最终失败复盘](diagnostics/hype-1d-ma7-ctls-final-failure-2026-08-10.md) · [R6机器裁决](artifacts/hype_1d_ma7_ctls_r6_2026-08-10_direction.json)。

## 2026-08-10 — V6-DTEC延迟趋势episode Development失败

决定：按用户纠正后的口径，以已登记V6 `PEHC_294`为唯一control，只研究raw MA7 cross未触发V6入场后、价格继续同侧时的延迟确认，不使用ML。完成`576 long-only + 576 short-only + 16 combined`且0 error。long-only最优把D收益从`+316.58%`提高到`+339.54%`但MDD同为`-17.77%`且只有1个确认样本；short-only虽有`7/9`的5日趋势标签命中，却降至`+130.10%/-26.40%`，因为14笔short把V6 long从8笔挤到4笔并减少PEHC handoff。16个组合仅一条经济路径，均为`+177.57%/-26.40%`，0项通过冻结的D/WFO/8bps双重支配门。裁决`HARD-GATE-FAILED`，评估`[324,432)`未访问；不登记V7、不运行杠杆、不生成HTML、不推进runner。证据：[预注册合同](specs/hype-1d-ma7-delayed-trend-episode-confirmation-preregistration-2026-08-10.md) · [失败复盘](diagnostics/hype-1d-ma7-v6-delayed-trend-episode-confirmation-failure-2026-08-10.md) · [Stage A](artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_a.json) · [Stage B](artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_b.json) · [最终裁决](artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_final.json)。

## 2026-08-10 — V6-DTEC全432日同窗post-reveal比较

决定：按用户明确要求打开原封存后108日，以连续`[0,432)`、相同成本/funding/真实`1h` MDD比较exact V6与`DTEC_L189`。V6为累计`+617.11%`、折算年化`+428.31%`、MDD`-18.39%`；DTEC为`+623.48%/+432.27%/-20.97%`。候选只多`6.37pp`累计收益和`3.96pp`折算年化，却多`2.58pp`回撤，收益/MDD与年化/MDD均下降。冷启动后108日候选又为`+12.87%/-21.58%`，双劣于V6 `+72.14%/-12.66%`。上游hard-gate失败不变；本次只作post-reveal diagnostic，不登记V7、不研究杠杆、不promotion。证据：[诊断](diagnostics/hype-1d-ma7-v6-dtec-l189-full-history-post-reveal-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_v6_dtec_l189_full_history_post_reveal_2026-08-10.json)。

## 2026-08-10 — V6七项转换链修复全部失败

决定：在exact V6上冻结并完成移除全局cooldown、方向性1/2日cooldown、有限raw-cross episode、buffer/slope晚成熟、recross取消、RSI6止盈后重观察及anti-chase七项消融，共14个逐项arm和108个低复杂度组合。目标截图中的`2025-10-24 long +8.28%`与`2025-11-03 short +2.31%`确实补到，但同时释放更多假信号；108项中收益更高、MDD更小、双改善均为0，最佳组合也仅`+449.40%/-24.13%`，低于V6 `+617.11%/-18.39%`。裁决`HARD-GATE-FAILED`；不登记V7、不研究杠杆、不生成HTML、不改变V6。证据：[冻结合同](specs/hype-1d-ma7-v6-transition-repair-ablation-contract-2026-08-10.md) · [完整消融](ablations/hype-1d-ma7-v6-transition-repair-ablation-2026-08-10.md) · [机器证据v2](artifacts/hype_1d_ma7_v6_transition_repair_ablation_2026-08-10_v2.json)。

## 2026-08-10 — V6 RSI6记忆cross对称规则失败

决定：在exact V6上新增“cross前5个完整日有3日RSI6极值”的替代入场。对称主规则由`+617.11%/-18.39%`变为`+662.27%/-21.97%`，增收但扩大回撤；long-only为`+670.19%/-18.39%`却只替换1个已暴露多头episode，short-only为`+609.74%/-21.97%`双劣。裁决`FAIL / diagnostic-only`，不写回V6、不登记V7、不研究杠杆。证据：[冻结合同](specs/hype-1d-ma7-v6-rsi6-memory-cross-entry-contract-2026-08-10.md) · [消融结论](ablations/hype-1d-ma7-v6-rsi6-memory-cross-entry-2026-08-10.md) · [可缩放路径](artifacts/hype_1d_ma7_v6_rsi6_memory_cross_2026-08-10_primary_trade_path.html)。

## 2026-08-10 — V6 short cooldown 5日改2日失败

决定：严格只把exact V6的`short_config.cooldown_days`从5改为2；因底层是全局cooldown，该锁同时影响后续自然long/short。候选由`+617.11%/-18.39%`降至`+528.10%/-22.24%`，新增两笔short均亏损，8bps与8×54日也双劣；叠加RSI6记忆cross后又由`+662.27%`降至`+516.54%`。保留V6的5日参数，不登记V7、不继续搜索天数。证据：[冻结合同](specs/hype-1d-ma7-v6-short-cooldown-2d-contract-2026-08-10.md) · [消融结论](ablations/hype-1d-ma7-v6-short-cooldown-2d-2026-08-10.md) · [可缩放路径](artifacts/hype_1d_ma7_v6_short_cooldown_2d_2026-08-10_trade_path.html)。

## 2026-08-10 — V6固定3x诊断为高尾部风险

决定：用户明确授权偏离“1x前瞻PASS前不运行杠杆”的原门禁，只在已暴露432日上观察exact V6固定3x；主相位为`+14,164.73%/-45.35%`，但额外延迟为`+532.64%/-70.50%`，24相位最差收益`-59.97%`、MDD`-94.19%`且marked leverage最高`7.65x`。裁决`HIGH_TAIL_RISK / diagnostic-only`，不修改V6的1x身份、shadow-only状态、前瞻observer或杠杆锁，不登记V7、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v6-3x-leverage-contract-2026-08-10.md) · [诊断](diagnostics/hype-1d-ma7-abt-v6-3x-leverage-2026-08-10.md) · [完整路径](artifacts/hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10.html)。

## 2026-08-10 — V6连续趋势Overlay机会成本门失败

决定：按用户选择的“V6辅助overlay”方向，冻结四个代表性连续趋势候选并审计方向命中与完整经济路径。`CTO_L189`仅凭1个long确认把收益小幅提高至`+623.48%`但MDD恶化到`-20.97%`；`CTO_S005`与`CTO_L189_S005`方向命中率较高却破坏V6 long/OAPP/PEHC链条；`CTO_C001`降至`+449.40%/-24.13%`。四个候选均未同时提高收益并降低真实`1h` MDD，裁决`HARD-GATE-FAILED`；不修改V6、不登记V7、不研究杠杆、不生成HTML。证据：[冻结合同](specs/hype-1d-ma7-v6-continuous-trend-overlay-contract-2026-08-10.md) · [失败复盘](diagnostics/hype-1d-ma7-v6-continuous-trend-overlay-failure-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_v6_continuous_trend_overlay_2026-08-10.json)。

## 2026-08-10 — V6结构性probe、方向冷却与ATR降仓全部未达双优

决定：按预注册在exact V6上完成9个候选臂。memory-only long `0.5x/2d`把收益提高到`+643.64%`但MDD仍为`-18.39%`，且完整432日只激活1个独立episode；方向性short cooldown覆盖为`+639.79%/-24.00%`，新增两笔赢家同时释放一笔亏损long；memory-only short `0.5x/0.25x`均收益/MDD双劣；固定5% ATR cap虽把MDD降至`-13.81%`，但收益降至`+335.34%`。三个组合也全部失败。裁决`FAIL / diagnostic-only`，V6保持不变、不登记V7；long probe只保留为等待至少5个新增独立episode的observer假设。证据：[预注册合同](specs/hype-1d-ma7-v6-structural-sizing-contract-2026-08-10.md) · [完整消融](ablations/hype-1d-ma7-v6-structural-sizing-ablation-2026-08-10.md) · [机器证据v2](artifacts/hype_1d_ma7_v6_structural_sizing_2026-08-10_v2.json) · [可缩放路径v2](artifacts/hype_1d_ma7_v6_structural_sizing_2026-08-10_v2_best_trade_path.html)。

## 2026-08-10 — V6漏趋势归因确认存在漏段但全量隔离probe不经济

决定：CTLS-R4事后稳定标签共识别29段，V6仅在15段有同向暴露、按时长加权覆盖`39.51%`；14个完全漏段中10个来自freshness失效、3个cooldown、1个仓位占用，且9段主root在固定5日成本后为正，确认漏段并非全是视觉错觉。但不读取事后标签的`0.25x`隔离probe共34笔，只把V6从`+617.11%/-18.39%`变为`+496.39%/-21.72%`，8bps、funding-off及延迟也双劣；关闭该overlay，不改V6、不登记V7。证据：[冻结合同](specs/hype-1d-ma7-v6-missed-trend-attribution-contract-2026-08-10.md) · [归因诊断](diagnostics/hype-1d-ma7-v6-missed-trend-attribution-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_v6_missed_trend_attribution_2026-08-10.json)。

## 2026-08-10 — V6严格三门连续趋势Overlay失败

决定：按用户要求把“非ML event-conditioned / hazard overlay”落实成唯一固定规则，不做阈值搜索：raw MA7 cross后必须同时通过3日同侧、MA7斜率、MA7距离、ER5、MAE预算与机会成本门。该规则确认10次（long 1、short 9），但把V6从`+617.11%/-18.39%`降至`+255.26%/-32.65%`，并减少`handoff_accept` 2次、`long_trail_exit` 3次、`shadow_start` 3次；8bps、funding-off、lag和分块均未过门。裁决`HARD-GATE-FAILED`，不改V6、不登记V7、不研究杠杆、不生成HTML。证据：[冻结合同](specs/hype-1d-ma7-v6-strict-continuation-overlay-contract-2026-08-10.md) · [失败复盘](diagnostics/hype-1d-ma7-v6-strict-continuation-overlay-failure-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_v6_strict_continuation_overlay_2026-08-10.json)。

## 2026-08-10 — V6固定2x杠杆历史诊断

决定：用户明确要求查看当前V6固定`2x`表现，因此在已暴露432日上按每次实际入场目标`2x`执行一次diagnostic-only审计。主相位为`+3,532.97%/-31.51%`，`8 bps`为`+3,432.50%/-31.72%`，funding-off为`+3,584.23%/-31.59%`；主相位未触发简化maintenance筛查，但24个日界相位最差MDD达`-81.31%`。裁决`HISTORICAL_SCREEN_ONLY`，不修改V6、不解锁杠杆、不登记V7、不生成HTML、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v6-2x-leverage-contract-2026-08-10.md) · [诊断](diagnostics/hype-1d-ma7-abt-v6-2x-leverage-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_abt_v6_2x_leverage_2026-08-10.json)。

## 2026-08-10 — V6 EMA7替换失败

决定：按用户要求只把已登记V6 `PEHC_294` 的 `features.ma7` 从SMA7替换为 `EMA(span=7, adjust=False, min_periods=7)`，其余OAPP、PEHC、退出、成本、funding与执行顺序全部不变。EMA7版全窗为`-24.54%/-62.30%`，交易数从19增至35，8bps、funding-off、lag、分块、90日滚动和24相位均失败；24相位仅6/24为正，22个相位双劣。裁决`FAIL / diagnostic-only`，V6继续固定SMA7，不登记V7、不搜索EMA span、不生成HTML。证据：[冻结合同](specs/hype-1d-ma7-abt-v6-ema7-substitution-contract-2026-08-10.md) · [诊断](diagnostics/hype-1d-ma7-abt-v6-ema7-substitution-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_abt_v6_ema7_substitution_2026-08-10.json)。

## 2026-08-10 — V6执行层优化诊断失败

决定：按用户提出的“信号后优化入场成本、出场信号后争取更好退出”方向，冻结18个限价改善+超时市价兜底候选，仅测 exact V6 `1x`。entry-only 和 entry+exit 均双劣；唯一主窗双优为 exit-only `X_K10_T24`，逐小时重放为`+641.76%/-17.77%` vs V6 `+617.09%/-18.40%`，但额外一日lag双劣、cold-flat block门失败，并使`long_trail_exit -1`、`protective_stop +1`。裁决`FAIL / diagnostic-only`，不改V6、不登记V7、不生成HTML；`X_K10_T24`最多作为新增前瞻观察假设。证据：[冻结合同](specs/hype-1d-ma7-abt-v6-execution-improvement-contract-2026-08-10.md) · [诊断](diagnostics/hype-1d-ma7-abt-v6-execution-improvement-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_abt_v6_execution_improvement_2026-08-10.json)。

## 2026-08-10 — 原漏趋势终局裁决（后续撤回）

决定：在 HYPE outcome 继续锁定的前提下，跨资产 flow/quantile 盲测与21资产全新时间窗复制均失败；ALTA `take_all` 1,341笔 mean `-0.1207%`、PF `0.829`、bootstrap正概率仅`0.16%`且95%区间全负，固定asset-local policy更差。结合既有机制、状态、价格与衍生品信息路线，裁决“当前信息与MA7 maturity机制类下真漏趋势不可稳定辨识”；关闭同一substrate上的selector/threshold/model/late-entry/cooldown/overlay搜索，不改V6、不登记V7。仅保留冻结prospective observer，或未来另立非MA7-root且先在非HYPE验证的全新机制。证据：[终局复盘](diagnostics/hype-1d-ma7-v6-missed-trend-identifiability-final-2026-08-10.md) · [QUML失败](../../asset-portfolios/1d-ma7-quantile-utility-meta-label/diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md) · [ALTA未见时间窗失败](../../asset-portfolios/1d-ma7-asset-local-temporal-audit/diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md)。

## 2026-08-10 — 撤回“全部当前信息不可辨识”的终局归因

决定：DSTO、TFML/P1E 与 QUML 的 market aggregates 均未在 fold 内排除 held source history，故撤回其增量裁决及“当前 OI/flow/quantile 均无法辨识”的总括结论。ALTA 未见时间 `take_all` 负 edge、HYPE 同窗补丁未双优、V6 不变且不登记V7仍有效；已揭示历史调参关闭，但独立信息可辨识性只能由修正实现后的新 holdout 裁决。证据：[复盘更正](diagnostics/hype-1d-ma7-v6-missed-trend-identifiability-final-2026-08-10.md) · [DSTO更正](../../asset-portfolios/1d-derivatives-structure-trend-opportunity/diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md) · [TFML更正](../../asset-portfolios/1d-ma7-taker-flow-meta-label/diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md) · [QUML更正](../../asset-portfolios/1d-ma7-quantile-utility-meta-label/diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)。

## 2026-08-11 — V6盘中ATR阈值入场失败

决定：按用户提出的“不等日K收盘，只要盘中超过MA7距离阈值就入场”方向，在exact V6上测试上一完整日 `SMA7/ATR7` 的 `0.25/0.50/0.65/0.80/1.00 ATR` fresh intraday threshold entry。最佳 `1.00 ATR` 仅`+60.08%/-41.80%`，远低于V6 `+617.09%/-18.40%`；其余阈值收益接近归零或亏损且回撤显著扩大。裁决`FAIL / diagnostic-only`，不改V6、不登记V7、不生成HTML、不推进runner。证据：[诊断](diagnostics/hype-1d-ma7-v6-intraday-threshold-entry-failure-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_v6_intraday_threshold_entry_2026-08-11.json)。

## 2026-08-11 — V6全参数消融只保留前瞻观察线索

决定：按用户要求对exact V6做224项 active-parameter OAT与每个参数的单参数邻域扫描。`short_cooldown_days_3`最佳为`+711.04%/-18.40%`，`short_cooldown_days_8/10`为`+672.81%/-18.40%`，`short_rsi_threshold_25`为`+621.22%/-18.40%`，均通过8bps、1日lag与8个block正收益筛选；但全部来自已揭示432日，且同一substrate已反复调参，当时仅列为clean prospective observer假设。入场reclaim/slope/buffer、PEHC、OAPP等核心层多数消融显著变差；当时不改V6、不登记V7、不生成HTML、不推进runner。证据：[全参数消融](ablations/hype-1d-ma7-abt-v6-full-parameter-ablation-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v6_full_parameter_ablation_2026-08-11.json)。

## 2026-08-11 — 用户明确登记 V7：V6 short cooldown 5日改3日

决定：按用户明确要求，将全参数邻域扫描最佳候选 `n_short_cooldown_days_3` 登记为 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7`。V7完整继承V6，只把 `short_config.cooldown_days` 从 `5` 改为 `3`；已揭示全窗为`+711.04%/-18.40%`、20笔，8bps为`+698.75%/-18.53%`，额外1日lag为`+267.61%/-26.45%`，8/8个54日block为正。登记只冻结身份和参数，不代表promotion、live spec、runner授权或杠杆解锁；仍需clean prospective。证据：[V7规格](specs/hype-1d-ma7-abt-v7-spec.md) · [V7机器证据](artifacts/hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json) · [V7交互式交易路径](artifacts/hype_1d_ma7_abt_v7_trade_path_2026-08-11.html)。

## 2026-08-11 — V7固定2x杠杆历史诊断

决定：用户明确要求查看V7固定`2x`表现，因此在已暴露432日上按每次实际入场目标`2x`执行一次diagnostic-only审计。主相位为`+4,550.71%/-31.51%`，`8 bps`为`+4,415.88%/-31.72%`，funding-off为`+4,597.27%/-31.59%`；主相位未触发简化maintenance筛查，但24个日界相位最差收益`-47.45%`、最差MDD达`-87.02%`。裁决`HISTORICAL_SCREEN_ONLY`，不修改V7的`1x`身份、不解锁杠杆、不生成HTML、不创建live spec、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v7-2x-leverage-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-2x-leverage-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_2x_leverage_2026-08-11.json)。

## 2026-08-11 — V7四机制补漏消融失败

决定：按用户要求把 pending reclaim maturity、short RSI放宽、overbought exhaustion short、post-exit cooldown override 固定成诊断合同并在V7上逐项 ablation。四个单项均未优于V7：M1为`+106.61%/-52.30%`且交易增至34笔，M2为`+496.98%/-18.40%`，M3为`+465.29%/-24.01%`，M4为`+495.48%/-24.01%`；组合臂为`+159.98%/-45.33%`、44笔且8个block仅6个盈利。裁决`FAIL / diagnostic-only`，这些机制不写入V7、不登记V8、不生成HTML、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v7-four-mechanism-ablation-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-four-mechanism-ablation-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_four_mechanism_ablation_2026-08-11.json)。

## 2026-08-11 — V7四机制组合搜索只得到short RSI小候选

决定：按用户要求在四机制上再跑240个固定组合参数搜索。只有`P0__R25x2__CG__O0`一类全窗双优，即不启用pending、不改cooldown、不靠overbought，只把short RSI止盈从`20×2`放宽到`25×2`：全窗`+715.71%/-18.40%`、20笔、8bps`+703.35%`、lag`+276.83%`、8个block全正；收益仅比V7多`+4.67pp`，来自2025-09-20空头提前在2025-09-24以short RSI止盈退出。裁决`POST_REVEAL_CANDIDATE_ONLY`，不修改V7、不登记V8、不生成HTML、不推进runner。证据：[组合搜索合同](specs/hype-1d-ma7-abt-v7-four-mechanism-combo-search-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-four-mechanism-combo-search-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_four_mechanism_combo_search_2026-08-11.json)。

## 2026-08-11 — V7 stale reclaim maturity probe 失败

决定：按用户要求针对 `2025-08-07`、`2026-02-09/10`、`2026-04-07` 这类 raw reclaim 后成熟行情，冻结并回测144个 stale reclaim maturity probe 候选。无全窗双优；最佳 `S_long_only_MIN2_MAX3_D1p25_L0p25` 为`+572.40%/-20.90%`、26笔、stale confirm 5次，仍比V7少`-138.64pp`且MDD更差。能覆盖三段的宽候选 `S_both_MIN1_MAX4_D1p50_L0p25` 为`+161.13%/-37.12%`、35笔，说明补到目标行情的同时释放大量同型噪声。裁决`FAIL / noise-releasing / diagnostic-only`，不修改V7、不登记V8、不生成HTML、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v7-stale-reclaim-probe-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-stale-reclaim-probe-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_stale_reclaim_probe_2026-08-11.json)。

## 2026-08-11 — V7反向K+RSI极值reclaim失败

决定：按用户提出的“MA7突破/跌破当天，前10天反向K占比达到50%或60%，且过去10天RSI6出现过30/70极值则允许开单”冻结并回测54个候选。该条件能命中 `2025-08-07` long、`2026-02-06` short、`2026-04-04` long 的raw cross，但无全窗双优；最佳 `RK_short_only_R0p50_D1p00_L1p00` 仅`+351.06%/-23.72%`、23笔、触发11次，8个block仅7个为正。both版本虽然能覆盖目标三段，但如 `RK_both_R0p50_D1p50_L0p25` 仅`+68.68%/-33.81%`、31笔、触发21次，说明该条件释放大量同型噪声。裁决`FAIL / diagnostic-only`，不修改V7、不登记V8、不生成HTML、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v7-reverse-rsi-reclaim-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-reverse-rsi-reclaim-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_reverse_rsi_reclaim_2026-08-11.json)。

## 2026-08-11 — V7反向K+RSI后续确认出现post-reveal小候选

决定：按用户要求把反向K+RSI极值降为背景标签，再等待后续 `1-4d` follow-through 确认后入场，冻结并回测324个候选。`FT_long_only_R0p50_A2_P0p25_D1p25_L0p50` 与60%反向K等价版本全窗双优并通过压力包：`+728.96%/-17.87%`、23笔、tag/confirm `10/2`，8bps`+715.06%/-18.11%`、lag`+284.07%/-26.45%`、8个block全正。该候选主要补到 `2026-04-04/05` 和样本末端一次long，未补到 `2025-08-07` 或 `2026-02-06/09/10`；放宽距离到`1.5ATR`会跌至`+569.02%/-21.56%`。裁决`POST_REVEAL_CANDIDATE_ONLY`，只作为未来clean prospective观察假设，不修改V7、不登记V8、不生成HTML、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v7-reverse-rsi-followthrough-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-reverse-rsi-followthrough-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_reverse_rsi_followthrough_2026-08-11.json)。

## 2026-08-11 — V7空头MA7斜率退出放松失败

决定：按用户要求测试三类空头 `ma7_slope_exit` 替代口径：`lookback=2/3`、`MA7上拐+close>MA7`、`MA7上拐+close>MA7+0.25/0.50/0.75ATR`。全部低于V7：最佳收益变体 `SHORT_SLOPE_UP_AND_CLOSE_ABOVE_MA` 为`+574.59%/-18.40%`，最低收益 `0.75ATR` 为`+432.55%/-19.98%`。这些规则没有修复`2025-11-03`空头，而是先让`2025-10-15`空头拖到`2025-10-24`亏损退出，错过原始路径的`2025-10-24→2025-11-01`多头，导致`2025-11-03`空头不再以同样路径出现。裁决`FAIL / path-disruption`，不修改V7、不登记V8、不生成HTML、不推进runner。证据：[冻结合同](specs/hype-1d-ma7-abt-v7-short-slope-exit-variants-contract-2026-08-11.md) · [诊断](diagnostics/hype-1d-ma7-abt-v7-short-slope-exit-variants-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_short_slope_exit_variants_2026-08-11.json)。

## 2026-08-11 — V7问题与优化方向综合诊断未产生替代版本

决定：按用户要求把V7主要问题和优化方向全部落到回测：144个 delayed impulse confirmation 补票候选、4个空头 max_hold 趋势延长候选、禁用 PEHC entry 贡献测试，并整合空头斜率退出独立证据。没有候选全窗双优：delayed impulse 最佳为`+718.20%/-20.98%`、22笔、tag/confirm `14/1`，裁决`FAIL / higher-return-higher-risk`；max_hold延长为`+697.06%/-18.40%`，`2026-07-12`空头从`+21.15%`降至`+19.06%`；禁用PEHC为`+512.12%/-21.57%`，说明PEHC总体净贡献为正但有局部噪声。综合裁决：V7继续保持`registered / not promoted / not live-ready`，不修改V7、不登记V8、不生成HTML、不推进runner；后续只可做clean prospective observer。证据：[综合合同](specs/hype-1d-ma7-abt-v7-issue-optimization-omnibus-contract-2026-08-11.md) · [综合诊断](diagnostics/hype-1d-ma7-abt-v7-issue-optimization-omnibus-2026-08-11.md) · [delayed impulse机器证据](artifacts/hype_1d_ma7_abt_v7_delayed_impulse_confirmation_2026-08-11.json) · [state-control机器证据](artifacts/hype_1d_ma7_abt_v7_state_control_variants_2026-08-11.json)。

## 2026-08-11 — V7.1登记为功能等价参数面精简版本

决定：按用户要求在V7上重新运行224项全参数消融，并移除当前`reclaim`/`off`模式下的dormant/schema-only字段后登记为`HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`。V7.1与V7同路径同指标：`+711.04%/-18.40%`、20笔；仅从规格中移除pullback/breakout专用字段、OAPP off子字段和空的PEHC origin列表。`short_rsi_threshold_25`/`n_short_rsi_threshold_25`为post-reveal行为候选`+715.71%/-18.40%`，不纳入V7.1。V7.1状态为`registered / not promoted / not live-ready`，不生成HTML、不创建live spec、不推进runner。证据：[V7.1合同](specs/hype-1d-ma7-abt-v7-1-parameter-cleanup-contract-2026-08-11.md) · [V7.1规格](specs/hype-1d-ma7-abt-v7-1-spec.md) · [消融报告](ablations/hype-1d-ma7-abt-v7-full-parameter-cleanup-ablation-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json)。

## 2026-08-11 — V7.1导出Lab live spec草案但不授权实盘

决定：按用户“导出 live spec、小额资金跑三个月看看”的明确要求，创建`HYPE-1D-MA7-ABT-V7.1` Lab handoff草案，用于后续`quant-runner`实现、离线对拍和三个月观察计划。该草案标记为`live spec draft / not live-ready / approval_level_max=none`；runner kind尚未实现，offline parity、online open/close reconciliation、资金边界和launch decision均未完成，因此不改变V7.1的`registered / not promoted / not live-ready`研究状态，也不构成真实下单授权。随后按用户外发给同事复现的要求，另导出自包含外部复现规格，正文内嵌数据要求、公式、参数、执行模型、验收指标和20笔交易锚点，不依赖本地文件。证据：[V7.1 Lab live spec草案](live-specs/hype-1d-ma7-abt-v7-1-lab-live-spec.md) · [V7.1外部复现规格](live-specs/hype-1d-ma7-abt-v7-1-reproduction-spec-2026-08-11.md) · [V7.1规格](specs/hype-1d-ma7-abt-v7-1-spec.md) · [V7.1主账](hype-1d-ma7-abt-core-ledger.md)。

## 2026-08-11 — V7.1 Binance U本位Top15迁移失败

决定：按用户截图校正口径，对 Binance U本位 futures 全部交易中合约最近30个已闭合UTC日K `quote_volume` 做Top15排名，候选池包含普通`USDT`永续、`USDC`永续和`TRADIFI_PERPETUAL`。Top15进入`SNDKUSDT`、`SKHYNIXUSDT`、`SPCXUSDT`、`BTCUSDC`、`ETHUSDC`等App可见标的；15个标的全部有交易，但仅2个正收益，中位收益`-27.49%`，最佳`XAGUSDT` `+35.59%/-18.35%`，股票类高成交合约多数失败。裁决`TRANSFER_FAIL / diagnostic-only`，不修改V7.1、不登记新版本、不推进runner、不支持多币种迁移。证据：[Top15迁移诊断](diagnostics/hype-1d-ma7-abt-v7-1-top15-binance-perp-transfer-2026-08-11.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_1_top15_binance_perp_transfer_2026-08-11.json)。

## 2026-08-12 — V7.1 Binance USDT本位Top30迁移失败

决定：按用户要求过滤掉`USDC`本位合约，对 Binance U本位 futures 中`quoteAsset=USDT`的普通永续与`TRADIFI_PERPETUAL`按最近30个已闭合UTC日K `quote_volume` 取Top30并回测。Top30中`tradifi_perp`占`17/30`，`HYPEUSDT`成交额第17名且仍为最佳`+257.97%/-28.85%`；整体仅9个正收益、1个无交易，中位收益`-20.81%`，高成交股票类多数失败。裁决`TRANSFER_FAIL / diagnostic-only`，不修改V7.1、不登记新版本、不推进runner、不支持多币种迁移。证据：[USDT Top30迁移诊断](diagnostics/hype-1d-ma7-abt-v7-1-top30-binance-usdt-u-margin-transfer-2026-08-12.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_1_top30_binance_usdt_u_margin_transfer_2026-08-12.json)。

## 2026-08-12 — MA20替换Top20产生混合正向但不改V7.1

决定：按用户要求在USDT-only Top20上把V7.1的核心均线从`SMA7`替换为`SMA20`，其它ATR7、RSI6、OAPP、PEHC、冷却、成本与funding处理保持不变。MA20 Top20为11/20正收益、中位收益`+1.25%`，优于同Top20 MA7的6/20正收益与中位`-20.17%`；但`HYPEUSDT`从MA7的`+257.97%`降至MA20的`-2.65%`，说明这是新的机制线索而非V7.1等价优化。裁决`TRANSFER_MIXED_POSITIVE / diagnostic-only`，不修改V7.1、不登记新版本、不推进runner。证据：[MA20 Top20诊断](diagnostics/hype-1d-ma7-abt-v7-1-ma20-top20-binance-usdt-u-margin-transfer-2026-08-12.md) · [机器证据](artifacts/hype_1d_ma7_abt_v7_1_ma20_top20_binance_usdt_u_margin_transfer_2026-08-12.json)。
