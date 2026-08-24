# HYPE 1D MA7 PEHC Shadow 冻结与前瞻等待裁决

## 结论

PEHC在全部已暴露历史上找到了一个满足预注册开发门的`1x shadow candidate`，但没有获得新版本、promotion或live-ready资格。冻结候选为`PEHC_294`：固定OAPP long `0.5ATR7 / 10% MFE giveback / 2d`与short Wilder RSI6 `<20 × 2d`，利润退出后保留最长8个calendar day的无资金原long shadow；shadow只有在原exact V4 protective/trailing stop本来会尝试forced short时才生成机会，不加short slope，不加anti-chase cap，下一UTC日open重新检查价格严格低于上一完整日MA7后入空。

全历史`[0,432)`仍是researcher-exposed Development。`PEHC_294`相对exact V4实现了更高收益和更小真实`1h` MDD，也通过8bps、funding-off、12h相位、相邻路径和最大赢家剔除；但这些都不能替代冻结后新增数据。当前最终状态是`INSUFFICIENT_FUTURE_DATA / shadow-only / not registered / not promoted / not live-ready`。

## 数据、成本与执行

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 完整日K：`2025-05-31`至`2026-08-05 UTC`，432日；terminal open为`2026-08-06T00:00:00Z`。
- 日内审计：10,390根连续closed `1h`，0 missing、0 duplicate、0 invalid OHLC；2,597个funding事件。
- Base成本：每次fill手续费`0.10%`、不利滑点`4bps`，双边约`28bps`，计真实funding；stress把滑点提高至`8bps`。
- 所有信号只读上一完整日或已发生的closed `1h`；次日open handoff会重新检查MA7/ATR/slope/actual flat，失效即取消。
- shadow不持有qty、不写equity、不产生PnL、cost或funding；87项冻结测试包含OAPP parity、资金隔离、expiry、同小时/次日边界、strict filter、terminal suppression与逐笔路径连接。

## 完整搜索

预注册的`7 expiry × 5 slope × 7 chase cap × 2 execution = 490`臂全部完成，0 error。每臂同时运行全历史与8个54日flat-start block，按全窗+分块完整交易经济路径去重后只有13条独立路径；13条全部进入8bps、funding-off与12h phase深审，最后3条通过全套shadow资格，确定性低复杂度排序冻结`PEHC_294`。

旧H`[356,432)`没有被重新包装成OOS，也没有单独进入排序键。选择只使用全历史、8个预注册block的最差差值、机会覆盖、复杂度和arm ID；`[0,356)`仅作为“剔除已知OAPP失败案例后是否仍双优”的因果门。

## 主结果

以下都是`1x`、成本后、真实顺序`1h` MDD；收益为初始权益百分比。

| 暴露历史场景 | PEHC_294 | exact V4 | 差值 |
| --- | ---: | ---: | ---: |
| 全窗收益 | `+617.11%` | `+398.84%` | `+218.27pp` |
| 全窗MDD | `-18.39%` | `-25.09%` | 改善`6.70pp` |
| 全窗平仓 | `19` | `17` | `+2` |
| `[0,356)`收益 | `+452.26%` | `+286.81%` | `+165.46pp` |
| `[0,356)`MDD | `-18.39%` | `-25.09%` | 改善`6.70pp` |
| 8bps收益 | `+606.77%` | `+392.35%` | `+214.42pp` |
| 8bps MDD | `-18.52%` | `-25.27%` | 改善`6.74pp` |
| 12h phase收益 | `+49.34%` | `+34.38%` | `+14.96pp` |
| 12h phase MDD | `-37.68%` | `-39.93%` | 改善`2.24pp` |

funding-off下候选为`+621.62% / -18.44%`且不破产。全窗最大实际marked leverage为`1.195x`，来自价格相对固定qty的日内漂移，不是策略主动加杠杆。

8个flat-start block中，候选5个收益和MDD同时改善、2个与V4经济路径相同、1个收益低`8.31pp`但MDD改善`5.27pp`；8/8均不双劣。分块独立复利为`+689.87%`，V4为`+350.16%`。因此路径不是每段都提高收益，shadow资格不应被误写为逐段全胜。

## Shadow与handoff实际激活

完整路径有8次shadow start、6次handoff opportunity、5次next-day接受、1次因机会open仍在MA7上方拒绝；5次接受跨5个54日block。两个shadow在actual新long出现时按合同取消。

旧OAPP失败案例被按因果链复现：2026-07-08 long盈利退出后，shadow在2026-07-11 06:00以原V4 stop `66.465`触发机会；候选不在同小时追单，而在2026-07-12 00:00以`66.743`重新通过MA-only条件后入空。该空头持有至2026-08-01 `max_hold`。这解释了为何OAPP能锁住long利润却失去后续forced-short收益。

冻结参数的含义不是“8、OFF、INF在未来最优”：

- `8d`是已暴露历史中保留第6个机会、同时不必延长到13/21日的最小路径；
- slope OFF说明额外MA7下行斜率不是这些机会的必要因果条件；
- cap `INF`仍保留价格严格低于MA7的底线，只表示`>=1ATR`的cap在这条经济路径上没有新增作用；
- `next_utc_open`是真正改变结果的执行层：它避免同小时反手并强制次日复核。

## 为什么现在不能称为完成目标

`+617.11% / -18.39%`来自用于设计、搜索和OAPP失败归因的同一432日历史，不是新的validation或OOS。blocked、相位和消融降低了“纯单笔偶然”的可能性，但不能消除多轮研究后对这段短历史的选择偏差。尤其逐事件审计确认5个接受中origin 213是负贡献，删除它后全窗反而提高到`+689.19%`；这正是不能继续在旧历史上删坏事件、再宣称更优的原因。

因此从`2026-08-11T00:00:00Z`起只观察冻结的`PEHC_294`与exact V4。最早裁决必须同时有连续至少90个新增完整UTC日、双方各至少5笔闭合交易、多空各至少2笔、至少2次handoff opportunity和1次接受，并在base下收益严格更高、真实`1h` MDD严格更小，且收益差至少`5pp`或MDD改善至少`2pp`；还要通过8bps、funding-off、账本与路径门。样本不足只记`INSUFFICIENT`并继续等，不判PASS或FAIL。

## 杠杆决定

没有运行PEHC杠杆搜索。预注册规则要求`1x` clean prospective PASS后才能冻结fixed/dynamic `<=3x`网格并按20/25/30/35/40/50% MDD预算报告。当前任何杠杆收益推演都会把已暴露alpha和风险缩放混在一起，不能用于救援或宣传候选。

## 证据

- [预注册合同](../specs/hype-1d-ma7-profit-exit-handoff-continuity-preregistration-2026-08-10.md)
- [多轮消融与因果归因](../ablations/hype-1d-ma7-profit-exit-handoff-continuity-ablation-2026-08-10.md)
- [冻结shadow candidate](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_shadow_candidate.json)
- [完整逐笔与shadow交互HTML](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_full_trade_path.html)
- [Prospective协议机器件](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_prospective_protocol.json)
- [Post-freeze逐事件消融](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_post_freeze_ablation.json)

