# HYPE-1D-MA7-SNC02 趋势优先发现与完整持有审计

> 日期：2026-08-20。状态：`diagnostic-only / trend-first / not promoted / not live-ready`。本轮不以MDD或额外1日lag淘汰趋势机制；全部结果仍是已揭示历史。

## 结论

exact `SNC02` 仍是目前唯一值得保留的纯趋势基准。它不是最早发现每一段事后上涨/下跌的规则，但它能过滤大量MA7附近的反复穿越，并让已经成立的趋势持续持有。2026-08-09 long在持有期经历两次raw MA7 recross仍未退出，从 `55.113`持有到terminal `69.787`，gross `+26.63%`，截面MFE `+31.87%`，capture ratio为 **83.53%**。

唯一预冻结补票机制 `CSM02` 失败。它把所有fresh cross作为seed，允许斜率随后在同一MA7侧成熟：确实补到13个control事后漏掉的major raw-cross机会，但同时产生38笔delayed trade，只有11笔gross为正；总campaign从25增至59，净收益从 `+32.56%`变成 `-66.03%`，major MFE加权capture从 `47.19%`降到 `39.26%`，并在08-12错误翻空，破坏最新趋势连续性。

核心判断是：`raw cross + 后续MA7 slope成熟`并不等于新趋势。它在趋势内部的普通回踩中同样频繁发生。被拒cross的未来MFE只能说明事后存在机会，不能证明当时可辨识；把这些机会直接升级为反手信号会摧毁趋势跟踪。

## 1. 全量cross机会

扩展窗 `2025-05-31 -> 2026-08-20 terminal` 共103个strict raw MA7 cross：

| 类型 | 数量 |
|---|---:|
| SNC02当日斜率合格 | 40 |
| 当日斜率被拒 | 63 |
| 被拒但未来30日MFE>=20% | 29 |
| 被拒、control当时方向相反且MFE>=20% | 19 |
| CSM02实际补票的上述major机会 | 13 |

这19个标签不是19段独立趋势。30日前瞻窗口会重叠，同一大行情里的多个raw recross都可能各自得到高MFE。例如2025-09至10月的下跌途中，09-14、09-20、10-06、10-30多个short cross均被标为major；它们不能被简单相加为四个“漏趋势”。

有代表性的被拒机会：

| Raw cross | 方向 | cross slope/ATR | MFE30 | 同侧成熟 | 剩余MFE30 |
|---|---|---:|---:|---:|---:|
| 2025-08-07 | long | +0.0032 | +25.32% | 1日 | +25.03% |
| 2025-09-20 | short | +0.0102 | +61.24% | 1日 | +58.68% |
| 2025-10-06 | short | -0.0459 | +55.46% | 2日 | +54.92% |
| 2026-01-16 | long | -0.0075 | +53.96% | 1日 | +51.40% |
| 2026-04-04 | long | -0.2469 | +25.82% | 3日 | +18.52% |
| 2026-08-03 | long | -0.1112 | +34.60% | 2日 | +27.61% |

这些案例证明“较晚成熟时仍可能剩下大行情”，但全量路径同时证明：同型成熟事件大量出现在假突破和趋势内回踩，单靠MA7自身无法区分。

## 2. 裸SNC02的趋势捕获

| 指标 | SNC02 |
|---|---:|
| Campaign | 25 |
| MFE>=10% | 17 |
| MFE>=20% major | 9 |
| MFE>=30% | 5 |
| Major最终gross仍为正 | 7/9 |
| Major capture>=60% | 2/9 |
| Major median capture | 36.94% |
| Major MFE加权capture | 47.19% |

逐笔major趋势：

| Entry/方向 | Exit | MFE | Gross exit | Capture | 解读 |
|---|---|---:|---:|---:|---|
| 2025-06-18 short | 06-28 | +22.66% | +8.37% | 36.9% | 趋势盈利但转向确认回吐较多 |
| 2025-07-10 long | 07-24 | +22.75% | +7.46% | 32.8% | 同上 |
| 2025-08-27 long | 10-15 | +22.20% | -19.27% | -86.8% | 最大的赢家转亏案例 |
| 2025-10-24 long | 11-09 | +24.97% | -0.13% | -0.5% | 几乎回吐全部MFE |
| 2025-11-09 short | 12-25 | +44.74% | +37.34% | 83.5% | 完整度最高的成熟short之一 |
| 2026-01-27 long | 02-22 | +54.36% | +19.26% | 35.4% | 持有完整但转向确认慢 |
| 2026-03-01 long | 03-30 | +40.22% | +21.26% | 52.9% | 中等完整度 |
| 2026-05-18 long | 07-02 | +68.47% | +36.48% | 53.3% | 抓到大趋势主体 |
| 2026-08-09 long | terminal | +31.87% | +26.63% | **83.5%** | 未成熟、terminal-censored |

裸核的主要不足不是“太早退出”，而是趋势转向必须等新的qualified fresh cross，部分campaign会从大幅浮盈回吐到小赚甚至亏损。这是趋势跟踪的经典代价，不能用事后峰值直接判为错误退出。

## 3. CSM02为何破坏趋势

| 指标 | Control | CSM02 |
|---|---:|---:|
| 净收益 | +32.56% | -66.03% |
| 真实1h MDD | -50.79% | -81.68% |
| Campaign | 25 | 59 |
| 胜率 | 40.00% | 35.59% |
| Major趋势数 | 9 | 15 |
| Major正收益数 | 7 | 15 |
| Major加权capture | **47.19%** | 39.26% |
| 08-09 long连续到terminal | 是 | 否 |

CSM02新增38笔delayed trade，其中27笔gross亏损。典型失败包括：

- 2026-01-16 long seed成熟后，01-18入场，01-21反手，gross `-17.45%`；
- 2026-01-18 short seed成熟后，01-21入场，01-27反手，gross `-18.81%`；
- 2026-05-01 long虽然事后MFE30很高，但05-06补入后05-13即反手，gross `-7.89%`；
- 最新路径先在08-06补long，08-12错误翻short，08-14再翻long。最终虽然再次参与上涨，却不再是“连续持有趋势”。

CSM02的major正收益数量增加，是因为59笔交易把同一行情切成更多campaign；不能把15个major campaign误读为发现了15段独立趋势。其总权益、capture与最新连续性全部失败。

## 4. 趋势跟踪的真正约束

从全量证据看，MA7策略的权威事件必须保持稀缺：

- `fresh price cross`与`当日directional slope`同时成立，才足以推翻当前趋势方向；
- rejected cross可以作为机会观察，但后续斜率成熟不能自动获得“反手权”；
- active trend需要容忍raw MA7 recross。最新long已经证明，两次raw recross并不等于趋势结束；
- 事后MFE标签只能用于评估漏掉了什么，不能进入实时规则。

这也意味着，若要补回exact SNC02确实错过的趋势，下一信息必须与MA7价格/斜率不同源，例如独立成交量、跨周期结构或市场流，而不是继续在同一MA7序列上添加等待天数和阈值。

## 5. 裁决

- exact `SNC02`：`KEEP AS TREND-FIRST CONTROL`。它仍不是可上线策略，但保留了当前研究真正需要的持有连续性。
- `CSM02`：`TREND_FIRST_GATE_FAILED / STOP`。不搜索等待天数、slope或距离参数救援。
- 不运行额外1日lag筛选；8bps下control仍为 `+29.90%`，CSM02为 `-67.62%`，只作成本描述。
- 不登记版本、不改V7.1、不修改runner。

## 证据

- [冻结合同](../specs/hype-1d-ma7-snc02-trend-first-discovery-audit-contract-2026-08-20.md)
- [机器证据](../artifacts/hype_1d_ma7_snc02_trend_first_discovery_audit_2026-08-20.json)及其[SHA256](../artifacts/hype_1d_ma7_snc02_trend_first_discovery_audit_2026-08-20.json.sha256)
- [可执行脚本](../scripts/research_hype_1d_ma7_snc02_trend_first_discovery_audit.py)
- [裸核交易路径](../artifacts/hype_1d_ma7_symmetric_naked_cross_slope_trade_path_2026-08-20.html)
