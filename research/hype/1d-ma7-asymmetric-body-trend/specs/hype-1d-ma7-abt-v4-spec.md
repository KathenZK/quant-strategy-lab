# HYPE-1D-MA7-Asymmetric-Body-Trend-V4 规格

## 身份

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V4`
- Alias：`HYPE-1D-MA7-ABT-V4`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；保护与反手使用真实`1h`路径
- 状态：`registered / not promoted / not live-ready`
- 来源：V3强制反手确认修正中的`MA_ONLY`；由用户于2026-08-07明确登记

登记只冻结版本身份，不代表promotion、live spec或runner授权。V1、V2、V3继续保留。

## V3继承

V4完整继承V3的：

- long/short自然reclaim、slope、entry buffer；
- long `0.75×ATR7`迟滞与`1.5×ATR7` trailing；
- short `0.75×ATR7`迟滞、slope exit、`1.5×ATR7` hard stop、`4×ATR7` trailing和20日max hold；
- 单仓、非加仓、约`1x`目标与固定数量持仓；
- 手续费`0.001/fill`、基准不利滑点`4 bps/fill`和真实event-time funding。

完整参数见[V3规格](hype-1d-ma7-abt-v3-spec.md)；V4只改变下述强制反手确认。

## V4强制反手

1. long trailing stop先按V3的保护价/跳空规则平多；
2. 在拟反手的下一根真实`1h` open，只读取上一完整UTC日的`SMA7`；
3. 仅当该`1h open < SMA7`时建立short；
4. 若`1h open >= SMA7`，拒绝反手、保持flat，并执行long的2日cooldown；
5. 拒绝后不保留pending反手；后续只能由新的自然long/short信号入场；
6. 反手成功后仍立即启用V3 short的迟滞、slope exit、hard/trailing、max hold和cooldown；
7. 平多与成功开空分别计手续费与不利滑点；反手当日剩余`1h`路径和funding照常计入。

若trailing在UTC日最后一小时触发，则在下一日open用届时最近完整日MA7执行同一确认。

## 冻结历史观察

- `2025-05-31`至`2026-07-30 UTC`：成本后`+411.23%`，MDD`-26.81%`，Sharpe`2.669`，PF`13.516`，17笔；
- 7次反手尝试中5次获准、2次拒绝；R-S02与原R-S12两笔MA7上方亏损反手被过滤；
- 5笔获准反手中仍有3笔只持有1日；
- `8 bps`为`+404.59%`，额外延迟一天为`+109.85%`，`12h`日界为`+35.33%`；
- 12个90日滚动窗口全正；23个有效相位21正、中位`+38.35%`。
- 登记后short timing诊断：自然short入场改用`1d` slope为`+297.11%`；保持fresh cross armed直至`2d` slope确认为`+70.27%`、MDD`-34.63%`。两者都抓到2025-06下跌，但因新增short与cooldown错过后续高收益long，均不替代V4。
- 登记后flat regime诊断：取消前一日reclaim，多空均在flat时按当前MA7侧别+slope入场，结果为`-42.91%`、MDD`-73.01%`、40笔；28次自然入场中仅4次原V4 reclaim也会通过，23个有效相位全部亏损。
- 登记后target-side诊断：若当前持反侧仓，MA7侧别+slope确认后于下一日open直接反手；6月19日short正确建立并赚`+7.23%`，但全期为`-44.31%`、MDD`-73.55%`、49笔、17次直接反手。
- 登记后cooldown消融：long cooldown从2日改0在UTC主路径逐笔零影响；short cooldown从5日改0后收益降至`+303.19%`、交易增至22笔、`12h=-0.98%`，因此两侧均保留。
- 登记后ATR-band状态机诊断：用`±0.75×ATR7+slope`完整target决定flat入场/持仓反手，保护退出只转flat并允许cooldown后同趋势重入；2025-06 short于6月20日建立但亏`-7.83%`，全期`-26.40%`、MDD`-55.19%`、28笔，20笔保护退出、6笔重入，23个有效相位全部亏损。
- 登记后有限pending第一轮：short等待1/2日为`+110.73%/+70.27%`，long等待1/2日为`+216.12%/+164.91%`，多空组合仅`+26.68%`至`+58.85%`；不带质量约束的有限等待仍会追单并改写V4路径。
- 登记后局部修复第二轮：只允许short等待1日、延迟确认距MA7不超过`0.75×ATR7`，且只有该delayed仓位退出时可由原V4 opposite reclaim同open交接；6月short与后续long均保留，全期`+426.21%`、MDD`-29.25%`、20笔、23相位21正，但PF、延迟和相位中位弱于V4。只作post-reveal观察候选，不并入V4。
- 登记后对称cross × 持仓迟滞诊断：flat只按fresh MA7 cross入场，不用slope/entry buffer；持仓后才以双侧`0.75×ATR7`外边界反手，保护只转flat。6月17日cross于6月18日正确开short，但全期仅`+44.12%`、MDD`-53.32%`、29笔，`12h=-69.64%`、23相位仅6正；不替代V4。

以上全部是已揭示历史上的post-reveal观察，不是clean OOS。主路径相对V3的改善来自过滤两笔已知亏损，不能作为独立验证。

## 门禁缺口

- 无独立prospective OOS、CPCV、Monte Carlo、runner parity或线上对账；
- 反手样本只有5笔，且3笔一日退出，short slope入场/退出一致性仍未解决；
- 23相位中位数低于V3，历史改善集中于已揭示的R-S02/R-S12；
- 无限armed与无质量约束的有限pending均会增加低质量short；`1d + 0.75×ATR7 anti-chase + delayed-only handoff`仅在已揭示历史通过，尚无独立prospective；
- 纯flat regime、相反regime直接反手和ATR-band target状态机均已失败；更严格边界虽减少表面翻转，仍不能替代reclaim freshness与V4退出选择性；
- 多头首持仓日无hard stop；无live spec、无quant-runner implementation、无dry-run/live授权。

## 证据

- [形成合同](hype-1d-ma7-abt-v3-forced-reversal-confirmation-contract-2026-08-07.md)
- [形成诊断](../diagnostics/hype-1d-ma7-abt-v3-forced-reversal-confirmation-2026-08-07.md)
- [原V3反手缺陷审计](../diagnostics/hype-1d-ma7-abt-v3-forced-reversal-entry-audit-2026-08-07.md)
- [V4 short入场时序诊断](../diagnostics/hype-1d-ma7-abt-v4-short-entry-timing-2026-08-07.md)
- [V4 flat regime入场诊断](../diagnostics/hype-1d-ma7-abt-v4-flat-regime-entry-2026-08-07.md)
- [V4 target-side regime诊断](../diagnostics/hype-1d-ma7-abt-v4-target-side-regime-2026-08-07.md)
- [V4 cooldown消融](../ablations/hype-1d-ma7-abt-v4-cooldown-ablation-2026-08-07.md)
- [V4 ATR容错趋势状态机合同](hype-1d-ma7-abt-v4-band-state-machine-contract-2026-08-07.md) · [诊断](../diagnostics/hype-1d-ma7-abt-v4-band-state-machine-2026-08-07.md) · [交易路径HTML](../artifacts/hype_1d_ma7_abt_v4_band_state_machine_trade_path_2026-08-07.html)
- [V4局部修复第一轮合同](hype-1d-ma7-abt-v4-finite-reclaim-pending-contract-2026-08-07.md) · [第二轮合同](hype-1d-ma7-abt-v4-pending-quality-handoff-contract-2026-08-07.md) · [逐步诊断](../diagnostics/hype-1d-ma7-abt-v4-local-repair-ladder-2026-08-07.md) · [最佳候选HTML](../artifacts/hype_1d_ma7_abt_v4_pending_quality_handoff_trade_path_2026-08-07.html)
- [V4对称MA7 cross × 持仓迟滞合同](hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-contract-2026-08-07.md) · [诊断](../diagnostics/hype-1d-ma7-abt-v4-symmetric-cross-hysteresis-2026-08-07.md) · [交易路径HTML](../artifacts/hype_1d_ma7_abt_v4_symmetric_cross_d075_trade_path_2026-08-07.html)
- [V4完整交易路径HTML](../artifacts/hype_1d_ma7_abt_v4_trade_path_2026-08-07.html)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
