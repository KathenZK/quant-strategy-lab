# HYPE-1D-MA7-Asymmetric-Body-Trend

- Alias：`HYPE-1D-MA7-ABT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`
- 机制：固定 `SMA7` 的非对称日线趋势状态机；先审计原始“前收/开盘/实体”规则，再研究多空独立 reclaim、斜率确认、迟滞退出和 ATR 保护。
- 当前状态：`V1–V7.1 registered / not promoted / not live-ready`；V5固定OAPP但一次性H失败，V6固定`PEHC_294`且当前仅作shadow，V7只把V6的short cooldown从5日改为3日，V7.1为V7功能等价参数面精简；V7.1已有Lab handoff草案但`approval_level_max=none`，Binance U本位Top15与USDT-only Top30迁移均为`TRANSFER_FAIL`；MA20替换Top20为混合偏正但破坏HYPE本体，不改变V7.1身份，各版本均不构成promotion或runner授权。
- 原始趋势状态机分支：`explore / not promoted / not live-ready`；A 核心为 `-33.52%`，B 的 RSI6 空头止盈改善至 `-8.54%`但成本压力失败，C overbought 反空无成交；不登记 V5。
- 原始意图优化分支：`explore / not promoted / not live-ready`；预注册的 174-row Development 搜索未产生 champion，V/H 保持封存，仅作诊断证据，不登记 V5。
- V4-PFT修复分支：`explore / not promoted / not live-ready`；8臂Development无champion。RSI6 `25×2` short止盈在D-full与WFO均提高收益，但WFO最差MDD来自未被P/F/T触及的long路径，故V/H保持封存，不登记V5。
- TPR趋势阶段与风险效率分支：`Validation hard-gate FAIL / explore / not promoted / not live-ready`；按真实`1h`顺序MDD，固定RSI6 `25×2` short止盈在D/WFO同时提高收益、降低回撤并成为唯一D champion，但V中0次触发、与exact V4逐笔相同。未研究杠杆，H继续封存，不登记V5。
- WTL广域趋势生命周期分支：`Development hard-gate FAIL / explore / not promoted / not live-ready`；完成555个单模块、32个rolling筛选与624个组合。440个组合在D/V收益和真实`1h` MDD上均严格优于exact V4，但盈利保护使V平仓数降至1–2笔，未通过冻结的`candidate>=3`门；无champion、无杠杆，H继续未触碰，不登记V5。
- V5固定OAPP：`registered / not promoted / not live-ready`；冻结`0.5ATR/10% giveback/2d + RSI20×2`，但一次性H低于exact V4，登记不改变H失败与杠杆无资格。
- V6 `PEHC_294`：`registered / shadow-only / not promoted / not live-ready`；8日虚拟原long handoff仅有已暴露历史证据，仍须从`2026-08-11`起至少90日clean prospective。用户授权的V6固定2x诊断为`+3,532.97%/-31.51%`、相位最差MDD`-81.31%`，固定3x诊断为`+14,164.73%/-45.35%`、相位最差MDD`-94.19%`；二者均只作diagnostic且杠杆继续锁定。
- V6漏趋势/EMA7/执行层复盘：`diagnostic-only / not promoted / not live-ready`；34笔隔离probe未双优，ALTA未见时间 `take_all` 1,341笔 mean `-0.1207%`、PF`0.829`、bootstrap正概率`0.16%`；EMA7为`-24.54%/-62.30%`；执行层最佳 `X_K10_T24` 主窗`+641.76%/-17.77%`但lag、block和核心链条门失败；盘中ATR阈值入场最佳仅`+60.08%/-41.80%`；224项全参数邻域扫描中 `short_cooldown_days_3` 已按用户要求登记为V7。V7.1经224项V7全参数清理消融登记为功能等价精简规格；`short_rsi_threshold_25`仅为post-reveal小候选。V7固定2x主相位`+4,550.71%/-31.51%`但24相位最差MDD`-87.02%`；V7补漏/退出/综合优化均未产生替代版本。均为post-reveal diagnostic、不promotion、不解锁杠杆。TFML/QUML/DSTO增量裁决因aggregate isolation违规撤回；已揭示历史继续禁止自动promotion。
- CTLS持续趋势生命周期分支：`explore / not promoted / not live-ready`；本轮`HARD-GATE-FAILED`。R1–R6共完成`13,056`个状态/方向配置，加入日内、量、funding和BTC上下文后仍没有路径同时通过准确率、跨折稳定和低flip门；未运行PnL、LES或杠杆，不登记V7。

## 边界

- 本家族是固定 `SMA7`、`1x`、非加仓的非对称多空状态机；不是 `HYPE-1D-Pyramiding-Trend`、`HYPE-1D-Multi-Horizon-EMA-Forecast` 或无订单的 `Binance-1D-MA7-Deviation-Continuation`。
- “MA7 不穿过实体”按字面会让实体完全位于 MA7 下方的空单在次日开盘平仓并可能立即重开；该歧义不静默改写，研究同时保留字面版与方向性反转版。
- 多空分离分支是 materially new diagnostic mechanism，不继承初始规则的失败指标；其盈利候选来自 post-reveal 选择，不能当作 OOS 或 promotion 证据。

## 入口

- [主账](hype-1d-ma7-abt-core-ledger.md)
- [决策记录](decision-log.md)
- [原始趋势状态机冻结合同](specs/hype-1d-ma7-original-trend-state-machine-contract-2026-08-09.md) · [诊断](diagnostics/hype-1d-ma7-original-trend-state-machine-2026-08-09.md) · [消融](ablations/hype-1d-ma7-original-trend-ablation-2026-08-09.md) · [前瞻观察协议](specs/hype-1d-ma7-original-trend-prospective-observation-protocol-2026-08-09.md) · [完整交易路径 HTML](artifacts/hype_1d_ma7_original_trend_trade_path_2026-08-09.html)
- [原始意图优化预注册合同](specs/hype-1d-ma7-intent-optimization-preregistration-2026-08-09.md) · [Development 诊断](diagnostics/hype-1d-ma7-intent-optimization-development-2026-08-09.md) · [Development 消融](ablations/hype-1d-ma7-intent-optimization-development-ablation-2026-08-09.md) · [机器证据](artifacts/hype_1d_ma7_intent_optimization_2026-08-09_development.json) · [失败首位 D-only 交易路径](artifacts/hype_1d_ma7_intent_optimization_2026-08-09_failed_first_c001_development_trade_path.html)
- [V4-PFT修复预注册合同](specs/hype-1d-ma7-abt-v4-pft-repair-preregistration-2026-08-09.md) · [Development裁决与机制归因](diagnostics/hype-1d-ma7-abt-v4-pft-repair-development-2026-08-09.md) · [机器裁决](artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development.json) · [A001_T D-only交易路径](artifacts/hype_1d_ma7_v4_pft_repair_2026-08-09_development_failed_A001_T_trade_path.html)
- [TPR预注册合同](specs/hype-1d-ma7-trend-phase-risk-preregistration-2026-08-09.md) · [Validation裁决与机制归因](diagnostics/hype-1d-ma7-trend-phase-risk-validation-2026-08-09.md) · [Development机器裁决](artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development.json) · [一次性Validation](artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_validation.json) · [D champion完整路径](artifacts/hype_1d_ma7_trend_phase_risk_2026-08-09_development_QOFF_EOFF_T25X2_trade_path.html)
- [WTL预注册合同](specs/hype-1d-ma7-wide-trend-lifecycle-preregistration-2026-08-10.md) · [Development失败裁决](diagnostics/hype-1d-ma7-wide-trend-lifecycle-failure-2026-08-10.md) · [失败后多轮消融](ablations/hype-1d-ma7-wide-trend-lifecycle-post-fail-ablation-2026-08-10.md) · [Stage C完整组合](artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_stage_c.json) · [Post-fail机器证据](artifacts/hype_1d_ma7_wide_trend_lifecycle_2026-08-10_post_fail_ablation.json)
- [V5规格](specs/hype-1d-ma7-abt-v5-spec.md) · [OAPP预注册合同](specs/hype-1d-ma7-opportunity-aware-profit-protection-preregistration-2026-08-10.md) · [H最终裁决](diagnostics/hype-1d-ma7-opportunity-aware-profit-protection-final-2026-08-10.md) · [多轮消融](ablations/hype-1d-ma7-opportunity-aware-profit-protection-ablation-2026-08-10.md) · [可缩放逐笔HTML](artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_full_trade_path_zoomable_v2.html)
- [V6规格](specs/hype-1d-ma7-abt-v6-spec.md) · [PEHC预注册合同](specs/hype-1d-ma7-profit-exit-handoff-continuity-preregistration-2026-08-10.md) · [前瞻observer协议](specs/hype-1d-ma7-profit-exit-handoff-continuity-prospective-observer-v1-2026-08-10.md) · [Shadow冻结裁决](diagnostics/hype-1d-ma7-profit-exit-handoff-continuity-shadow-freeze-2026-08-10.md) · [1x可缩放逐笔HTML](artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_full_trade_path_zoomable_v2.html) · [固定2x诊断](diagnostics/hype-1d-ma7-abt-v6-2x-leverage-2026-08-10.md) · [固定3x诊断](diagnostics/hype-1d-ma7-abt-v6-3x-leverage-2026-08-10.md) · [EMA7替换失败](diagnostics/hype-1d-ma7-abt-v6-ema7-substitution-2026-08-10.md) · [3x路径](artifacts/hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10.html)
- [V6-DTEC预注册合同](specs/hype-1d-ma7-delayed-trend-episode-confirmation-preregistration-2026-08-10.md) · [Development失败复盘](diagnostics/hype-1d-ma7-v6-delayed-trend-episode-confirmation-failure-2026-08-10.md) · [Stage A单边搜索](artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_a.json) · [Stage B组合门禁](artifacts/hype_1d_ma7_v6_delayed_episode_2026-08-10_stage_b.json)
- [V6-DTEC全432日同窗post-reveal比较](diagnostics/hype-1d-ma7-v6-dtec-l189-full-history-post-reveal-2026-08-10.md) · [机器证据](artifacts/hype_1d_ma7_v6_dtec_l189_full_history_post_reveal_2026-08-10.json)
- [V6漏趋势归因合同](specs/hype-1d-ma7-v6-missed-trend-attribution-contract-2026-08-10.md) · [漏趋势归因诊断](diagnostics/hype-1d-ma7-v6-missed-trend-attribution-2026-08-10.md) · [漏趋势复盘与证据更正](diagnostics/hype-1d-ma7-v6-missed-trend-identifiability-final-2026-08-10.md) · [归因机器证据](artifacts/hype_1d_ma7_v6_missed_trend_attribution_2026-08-10.json) · [V6转换链消融](ablations/hype-1d-ma7-v6-transition-repair-ablation-2026-08-10.md) · [连续趋势Overlay失败复盘](diagnostics/hype-1d-ma7-v6-continuous-trend-overlay-failure-2026-08-10.md) · [严格三门Overlay失败复盘](diagnostics/hype-1d-ma7-v6-strict-continuation-overlay-failure-2026-08-10.md) · [执行层优化失败](diagnostics/hype-1d-ma7-abt-v6-execution-improvement-2026-08-10.md) · [盘中ATR阈值入场失败](diagnostics/hype-1d-ma7-v6-intraday-threshold-entry-failure-2026-08-11.md) · [全参数消融](ablations/hype-1d-ma7-abt-v6-full-parameter-ablation-2026-08-11.md) · [结构性仓位消融](ablations/hype-1d-ma7-v6-structural-sizing-ablation-2026-08-10.md)
- [V7规格](specs/hype-1d-ma7-abt-v7-spec.md) · [V7.1规格](specs/hype-1d-ma7-abt-v7-1-spec.md) · [V7.1 Lab live spec草案](live-specs/hype-1d-ma7-abt-v7-1-lab-live-spec.md) · [V7.1外部复现规格](live-specs/hype-1d-ma7-abt-v7-1-reproduction-spec-2026-08-11.md) · [V7.1全参数清理消融](ablations/hype-1d-ma7-abt-v7-full-parameter-cleanup-ablation-2026-08-11.md) · [V7.1 U本位Top15迁移诊断](diagnostics/hype-1d-ma7-abt-v7-1-top15-binance-perp-transfer-2026-08-11.md) · [V7.1 USDT本位Top30迁移诊断](diagnostics/hype-1d-ma7-abt-v7-1-top30-binance-usdt-u-margin-transfer-2026-08-12.md) · [V7.1 MA20替换Top20诊断](diagnostics/hype-1d-ma7-abt-v7-1-ma20-top20-binance-usdt-u-margin-transfer-2026-08-12.md) · [V7机器证据](artifacts/hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json) · [V7交互式交易路径](artifacts/hype_1d_ma7_abt_v7_trade_path_2026-08-11.html) · [V7固定2x诊断](diagnostics/hype-1d-ma7-abt-v7-2x-leverage-2026-08-11.md) · [V7组合搜索](diagnostics/hype-1d-ma7-abt-v7-four-mechanism-combo-search-2026-08-11.md) · [V7综合优化诊断](diagnostics/hype-1d-ma7-abt-v7-issue-optimization-omnibus-2026-08-11.md)
- [CTLS持续趋势生命周期预注册合同](specs/hype-1d-ma7-continuous-trend-lifecycle-preregistration-2026-08-10.md) · [R1–R6最终失败复盘](diagnostics/hype-1d-ma7-ctls-final-failure-2026-08-10.md) · [R6机器裁决](artifacts/hype_1d_ma7_ctls_r6_2026-08-10_direction.json)
- [初始研究合同](specs/hype-1d-ma7-abt-initial-contract-2026-08-04.md)
- [初始回测与稳健性报告](diagnostics/hype-1d-ma7-abt-initial-validation-2026-08-04.md)
- [V1 规格](specs/hype-1d-ma7-abt-v1-spec.md)
- [V2 规格](specs/hype-1d-ma7-abt-v2-spec.md)
- [V3 规格](specs/hype-1d-ma7-abt-v3-spec.md)
- [V4规格](specs/hype-1d-ma7-abt-v4-spec.md)
- [V4自然short入场时序合同](specs/hype-1d-ma7-abt-v4-short-entry-timing-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-short-entry-timing-2026-08-07.md)
- [V4多空持续regime入场合同](specs/hype-1d-ma7-abt-v4-flat-regime-entry-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-flat-regime-entry-2026-08-07.md)
- [V4目标侧regime直接反手合同](specs/hype-1d-ma7-abt-v4-target-side-regime-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-target-side-regime-2026-08-07.md)
- [V4 cooldown消融合同](specs/hype-1d-ma7-abt-v4-cooldown-ablation-contract-2026-08-07.md) · [消融](ablations/hype-1d-ma7-abt-v4-cooldown-ablation-2026-08-07.md)
- [V4 ATR容错趋势状态机合同](specs/hype-1d-ma7-abt-v4-band-state-machine-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-band-state-machine-2026-08-07.md) · [交易路径HTML](artifacts/hype_1d_ma7_abt_v4_band_state_machine_trade_path_2026-08-07.html)
- [V4局部修复第一轮合同](specs/hype-1d-ma7-abt-v4-finite-reclaim-pending-contract-2026-08-07.md) · [第二轮合同](specs/hype-1d-ma7-abt-v4-pending-quality-handoff-contract-2026-08-07.md) · [逐步诊断](diagnostics/hype-1d-ma7-abt-v4-local-repair-ladder-2026-08-07.md) · [最佳候选HTML](artifacts/hype_1d_ma7_abt_v4_pending_quality_handoff_trade_path_2026-08-07.html)
- [V4对称MA7 cross × 持仓迟滞合同](specs/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-contract-2026-08-07.md) · [诊断](diagnostics/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-2026-08-07.md) · [交易路径HTML](artifacts/hype_1d_ma7_abt_v4_symmetric_cross_d075_trade_path_2026-08-07.html)
- [V4 1x完整交易路径HTML](artifacts/hype_1d_ma7_abt_v4_trade_path_2026-08-07.html)
- [V3 1x完整交易路径HTML](artifacts/hype_1d_ma7_abt_v3_trade_path_2026-08-07.html)
- [V2 1x 完整交易路径 HTML](artifacts/hype_1d_ma7_abt_v2_trade_path_2026-08-06.html)
- [多空分离候选观察规格](specs/hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md)
- [多空分离搜索报告](diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md)
- [V1 EMA7 零调参替换诊断](diagnostics/hype-1d-v1-ema7-substitution-2026-08-05.md)
- [V1 3x 杠杆诊断](diagnostics/hype-1d-v1-3x-leverage-2026-08-05.md)
- [V2 3x 杠杆合同](specs/hype-1d-ma7-abt-v2-3x-leverage-contract-2026-08-06.md)与[诊断](diagnostics/hype-1d-v2-3x-leverage-2026-08-06.md)
- [V2 全参数消融合同](specs/hype-1d-ma7-abt-v2-full-parameter-ablation-contract-2026-08-06.md)与[消融报告](ablations/hype-1d-ma7-abt-v2-full-parameter-ablation-2026-08-06.md)
- [V2 空头迟滞 `0.75×ATR7` 合同](specs/hype-1d-ma7-abt-v2-short-hysteresis-075-contract-2026-08-07.md)与[诊断](diagnostics/hype-1d-ma7-abt-v2-short-hysteresis-075-2026-08-07.md)
- [V3全参数消融合同](specs/hype-1d-ma7-abt-v3-full-parameter-ablation-contract-2026-08-07.md)与[消融报告](ablations/hype-1d-ma7-abt-v3-full-parameter-ablation-2026-08-07.md)
- [V3 3x杠杆合同](specs/hype-1d-ma7-abt-v3-3x-leverage-contract-2026-08-07.md)与[诊断](diagnostics/hype-1d-v3-3x-leverage-2026-08-07.md)
- [V3强制反手入场审计](diagnostics/hype-1d-ma7-abt-v3-forced-reversal-entry-audit-2026-08-07.md)
- [V3强制反手确认修正合同](specs/hype-1d-ma7-abt-v3-forced-reversal-confirmation-contract-2026-08-07.md)、[诊断](diagnostics/hype-1d-ma7-abt-v3-forced-reversal-confirmation-2026-08-07.md)与[`MA_ONLY`交易路径](artifacts/hype_1d_ma7_abt_v3_ma_only_reversal_trade_path_2026-08-07.html)
- [V3日线跌破MA7反手合同](specs/hype-1d-ma7-abt-v3-daily-ma7-cross-reversal-contract-2026-08-07.md)、[诊断](diagnostics/hype-1d-ma7-abt-v3-daily-ma7-cross-reversal-2026-08-07.md)与[交易路径HTML](artifacts/hype_1d_ma7_abt_v3_daily_ma7_cross_reversal_trade_path_2026-08-07.html)
- [二元/三状态 MA7 迟滞合同](specs/hype-1d-ma7-abt-three-state-hysteresis-contract-2026-08-07.md)、[诊断](diagnostics/hype-1d-ma7-abt-three-state-hysteresis-2026-08-07.md)与[交易路径 HTML](artifacts/hype_1d_ma7_three_state_hysteresis_trade_path_2026-08-07.html)
- [状态边界 × V2斜率混合合同](specs/hype-1d-ma7-abt-state-slope-hybrid-contract-2026-08-07.md)、[诊断](diagnostics/hype-1d-ma7-abt-state-slope-hybrid-2026-08-07.md)与[CORE交易路径 HTML](artifacts/hype_1d_ma7_state_slope_hybrid_core_trade_path_2026-08-07.html)
- [V1 前瞻观察协议](specs/hype-1d-ma7-abt-v1-prospective-observation-protocol-2026-08-06.md)与[观察 #1](diagnostics/hype-1d-ma7-abt-v1-prospective-obs-2026-08-06.md)
- [V1 首日保护与相位/起跑点审计](diagnostics/hype-1d-ma7-abt-v1-protection-phase-audit-2026-08-06.md)
- [V1 平多即反手空跨资产诊断](../../asset-portfolios/1d-ma7-asset-specific-search/diagnostics/binance-ma7-long-exit-short-reversal-2026-08-06.md)
- [V1 trailing stop 后反手空合同](specs/hype-1d-ma7-abt-trailing-stop-short-reversal-contract-2026-08-06.md)与[诊断](diagnostics/hype-1d-v1-trailing-stop-short-reversal-2026-08-06.md)
- [初始规则脚本](scripts/research_hype_1d_ma7_asymmetric_body_trend.py) · [多空分离搜索脚本](scripts/search_hype_1d_ma7_separated_trend.py) · [原始趋势状态机](scripts/hype_1d_ma7_original_trend_engine.py) · [原始趋势研究器](scripts/research_hype_1d_ma7_original_trend.py)
- [产物说明](artifacts/README.md)
