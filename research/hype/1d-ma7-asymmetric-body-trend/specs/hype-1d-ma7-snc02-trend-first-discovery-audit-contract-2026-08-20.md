# HYPE-1D-MA7-SNC02 趋势优先发现与完整持有审计合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / trend-first / not promoted / not live-ready`。本合同在首次运行本审计结果前写入。第一目标是发现并尽可能完整持有趋势；收益回撤、仓位缩放与额外1日延迟不作为本轮候选首筛。

## 1. 研究顺序纠正

本轮恢复MA7趋势跟踪的核心顺序：

1. 先审计趋势是否被发现；
2. 再审计入场后是否持续持有到镜像趋势真正成立；
3. 最后才记录成本、收益与回撤，不用它们反向改写趋势路径。

Exact control为 `SNC02`：昨日close在SMA7反侧、今日close strict fresh cross、当日directional `SMA7 slope / ATR7 >= 0.02`，下一UTC open入场；多空镜像，仅在镜像合格信号时反手。不得叠加MA05、OAPP、stop、保本、部分止盈、确认加仓、权益节流或仓位优化。V7.1身份不变。

## 2. 全量fresh cross机会审计

对扩展窗内每个strict fresh SMA7 cross，不论其是否达到0.02 slope，都记录：

- cross日期、方向、`slope_atr`、是否被SNC02接受；
- 下一UTC open的可执行参考价；
- 未来 `3/7/14/30` 个完整日的方向性close return；
- 未来30日内基于日high/low的MFE与MAE；
- 在价格仍留在cross方向MA7一侧期间，directional slope首次达到0.02的日期、等待天数和剩余30日MFE。

`MFE30 >= 20%` 固定标记为 `major_cross_opportunity`，只作事后趋势机会标签，不进入实时信号。所有被拒cross按MFE30完整排序，不能只展示有利案例。

## 3. 唯一结构性补票机制：CSM02

本轮不扫参数，只测试 `Cross-Seeded Slope Maturation 0.02`：

1. 任一strict fresh cross都会在该方向建立一个pending seed；
2. 若cross当日directional slope已达到0.02，行为与SNC02相同；
3. 若未达到，只要每日close仍严格位于该方向SMA7一侧，seed持续有效；
4. 当directional slope首次达到0.02时，发出成熟信号，下一UTC open入场或反手；
5. 在成熟前若close重新cross到另一侧，旧seed取消，并由新方向fresh cross建立新seed；
6. 成熟后seed清空；持仓只在镜像CSM02成熟信号时反手，不因浮盈、回吐或普通回踩退出。

该机制没有最大等待天数、距离阈值、ATR buffer、盈利条件或方向特例。它只回答“cross当天斜率不够，但同一MA7侧趋势随后成熟时能否补上”。

## 4. 趋势持有与捕获指标

对control和CSM02每个campaign，从实际entry到镜像信号exit（末笔terminal-censored）记录：

- 基于日high/low的directional MFE、MAE；
- gross exit return；
- `capture_ratio = gross_exit_return / MFE`（MFE>0）；
- `giveback_ratio = (MFE - gross_exit_return) / MFE`；
- 持有天数、期间raw MA7 recross次数；
- MFE至少 `10%/20%/30%` 的campaign数；
- MFE>=20%的major trend中，exit仍为正及capture ratio>=60%的数量；
- `major_mfe_weighted_capture = sum(max(gross_exit_return, 0)) / sum(MFE)`，只在MFE>=20%的campaign上计算；
- 2026-08-09 UTC时是否为long并连续持有至terminal，以及该campaign截至统一截面的MFE/capture（候选允许更早进入同一long趋势，不强制entry恰好等于08-09）。

末笔terminal flatten仅用于统一截面估值，不算成熟趋势退出。

## 5. 趋势优先裁决

本轮不设MDD20或lag淘汰门。CSM02仅在以下趋势证据上获得 `CONTINUATION_WORTHY` 标签：

1. 至少补回一个SNC02拒绝的major cross opportunity；
2. control已捕获的major trend正收益数量不减少；
3. major trend的MFE加权capture ratio不低于control；
4. 保留2026-08-09 long至terminal；
5. 新增补票不是全部在成熟信号后立即反向亏损，逐笔路径必须完整披露。

净收益、真实1h MDD、8bps成本只作为第二层描述证据；不运行额外1日lag，不据此否定趋势发现机制。即使通过也仍是post-reveal diagnostic，不登记版本、不promotion、不授权runner。

## 6. 数据与产物

- 数据：Binance USDⓈ-M perpetual `HYPEUSDT`，UTC `1d`信号与`1h`风险路径，扩展窗 `2025-05-31 -> 2026-08-20 terminal`；canonical截止 `2026-08-06`只作同路径参考。
- 成本：`0.001/fill`手续费、4bps不利滑点、实际funding；另报告8bps，不做lag筛选。
- 脚本：`scripts/research_hype_1d_ma7_snc02_trend_first_discovery_audit.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_trend_first_discovery_audit_2026-08-20.json`
- 报告：`diagnostics/hype-1d-ma7-snc02-trend-first-discovery-audit-2026-08-20.md`
