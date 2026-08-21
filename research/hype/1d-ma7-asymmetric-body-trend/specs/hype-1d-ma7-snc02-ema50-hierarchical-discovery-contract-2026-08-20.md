# HYPE-1D-MA7-SNC02 EMA50分层趋势发现合同

> 冻结日期：2026-08-20。状态：`post-reveal successor diagnostic / trend-first / not promoted / not live-ready`。本合同在首次运行本候选结果前写入；其设计已看过SNC02/CSM02同窗结果，不能称为clean OOS或预注册验证。

## 1. 已知问题与研究假设

趋势优先审计已揭示：

- exact SNC02在最新08-09 long中容忍两次raw MA7 recross并持续持有，截面capture ratio为83.5%；
- 无慢趋势约束的CSM02虽补到13个事后major raw-cross机会，却产生38笔delayed trade、仅11笔gross为正，并在08-12错误翻空，破坏最新趋势连续性。

因此本轮不再搜索等待天数或MA7 slope阈值，只测试一个分层趋势假设：`MA7`负责快发现，`EMA50`只负责判断延迟补票是否与更慢的主趋势一致。

## 2. 唯一候选：HCSM50

`Hierarchical Cross-Seeded Maturation with EMA50`：

1. exact SNC02 qualified fresh cross保持最高优先级，完全不受EMA50过滤；
2. raw fresh MA7 cross若当日directional slope不足0.02，建立pending seed；
3. seed期间close必须持续严格位于该方向SMA7一侧，否则取消；
4. delayed signal只有在以下条件同时成立时才成熟：
   - directional `SMA7 slope / ATR7 >= 0.02`；
   - close位于目标方向EMA50一侧：`side * (close - EMA50) > 0`；
   - EMA50单日斜率同向：`side * (EMA50[t] - EMA50[t-1]) > 0`；
5. 若MA7 slope先成熟但EMA50尚未对齐，seed继续等待，只要close仍在目标方向SMA7一侧；
6. 成熟后下一UTC open入场或反手；持仓仍只被exact opposite SNC02或满足上述条件的opposite delayed signal反转；无止盈止损。

EMA50固定为daily close的 `EMA(span=50, adjust=False, min_periods=50)`；不得搜索span、EMA斜率幅度、价格距离或方向特例。EMA不足50个样本时只允许exact SNC02，不允许delayed signal。

## 3. 趋势优先评估

沿用[趋势优先审计合同](hype-1d-ma7-snc02-trend-first-discovery-audit-contract-2026-08-20.md)的同一口径：

- 全量raw cross机会和`MFE30>=20%` major标签不变；
- campaign报告MFE、MAE、gross capture、giveback、raw recross与MFE `10/20/30%`数量；
- `major_mfe_weighted_capture = sum(max(gross,0))/sum(MFE)`；
- 检查08-09 UTC时为long且连续持有至terminal，候选允许更早进入同一long趋势。

候选仅在以下条件全满足时得到 `CONTINUATION_WORTHY`：

1. 至少补回一个control漏掉的major raw-cross机会；
2. major trend正收益数量不低于control；
3. major MFE加权capture不低于control；
4. 保留08-09 long连续持有至terminal；
5. delayed trade中至少一笔gross为正，且总交易数不超过无慢趋势约束CSM02的59笔。

净收益、真实1h MDD与8bps只作第二层描述；不运行1d lag，不设MDD淘汰门。

## 4. 产物与边界

- 脚本：`scripts/research_hype_1d_ma7_snc02_ema50_hierarchical_discovery.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_ema50_hierarchical_discovery_2026-08-20.json`
- 报告：`diagnostics/hype-1d-ma7-snc02-ema50-hierarchical-discovery-2026-08-20.md`

本轮同样只作已揭示历史机制诊断，不登记版本、不promotion、不修改V7.1、不授权runner。
