# HYPE 1D MA7 PEHC 多轮消融与因果归因

## 研究问题

OAPP不是因为long盈利保护本身无效而失败：它把旧H一笔long从亏损改成盈利，却在平仓时同时删除了原V4稍后触发forced short所需的持仓状态。PEHC检验的是能否把“资金仓位已经退出”和“原趋势状态继续观察”拆开，并只在原V4 stop真实出现时做一次空头handoff。

全部432日已经暴露。本报告只做机制归因与shadow选择，不把任何结果称为OOS。

## Round 1：490参数与13条经济路径

490臂全部执行且0 error，参数为expiry `{1,2,3,5,8,13,21}`、slope `{OFF,0,0.01,0.02,0.04}`、cap `{0.25,0.5,0.75,1,1.5,2,INF}`和execution `{same_1h,next_utc}`。全窗表现只有22种指标/激活组合；加入8个flat-start block的交易哈希后收敛为13条完整经济路径。

所有490臂在全窗都相对V4双优，原因不是490套过滤都有效，而是固定OAPP本身已从V4的`+398.84% / -25.09%`改善到`+509.26% / -21.56%`。因此全窗“490/490双优”不能证明handoff，后续必须看handoff-off parity、接受次数、路径变化与逐事件消融。

`PEHC_294`对应的13/21日expiry与cap 1/1.5/2/INF在历史上经济路径等价；冻结8日是产生同类完整机会路径的最短expiry，冻结INF是移除休眠cap的更简单表达。slope开启臂没有提供更好的独立经济路径，说明这里的收益来源不是再次调MA7 slope阈值。

## Round 2：控制组OAT

| 控制 | 全窗收益 | 真实1h MDD | 平仓 | 归因 |
| --- | ---: | ---: | ---: | --- |
| exact V4 | `+398.84%` | `-25.09%` | 17 | 唯一登记control |
| fixed OAPP | `+509.26%` | `-21.56%` | 17 | handoff-off |
| long-only | `+356.40%` | `-21.66%` | 16 | long保护降MDD，但单独牺牲收益 |
| RSI-only | `+472.07%` | `-25.09%` | 19 | RSI主要提高收益，不改变最差MDD |
| shadow without entry | `+509.26%` | `-21.56%` | 17 | 与OAPP逐笔/资金路径parity，证明shadow无资金副作用 |
| handoff without RSI | `+528.03%` | `-18.39%` | 17 | handoff是MDD改善的主要来源 |
| PEHC_294 | `+617.11%` | `-18.39%` | 19 | RSI与handoff叠加 |

结论：long保护、RSI和handoff作用不同。long保护主要改变long退出和回撤；RSI提高short利润回收；handoff恢复被利润退出切断的方向转换，并把最差回撤进一步从`-21.56%`降到`-18.39%`。完整收益不是某一个阈值单独制造的。

## Round 3：5个接受事件的keep-one / leave-one-out

`PEHC_294`接受origin `{46,213,294,362,403}`，跨5个预注册block。keep-one表示只有该origin可成交，其余handoff只观察；leave-one表示完整候选只禁用该origin。收益差会包含后续仓位占用和cooldown路径，不能当作可加总的独立交易PnL。

| Origin | keep-one收益 | keep-one相对OAPP | leave-one收益 | 删除后仍相对OAPP |
| ---: | ---: | ---: | ---: | ---: |
| 46 | `+529.40%` | `+20.13pp` | `+594.17%` | `+84.91pp` |
| 213 | `+453.61%` | `-55.65pp` | `+689.19%` | `+179.93pp` |
| 294 | `+533.90%` | `+24.64pp` | `+589.23%` | `+79.97pp` |
| 362 | `+543.39%` | `+34.13pp` | `+579.07%` | `+69.80pp` |
| 403 | `+595.31%` | `+86.04pp` | `+528.37%` | `+19.10pp` |

origin 213是明确负贡献，说明MA-only handoff不是每次都对；不能在已暴露历史上事后屏蔽它，因为那会直接把候选优化到`+689.19%`。origin 403是最大赢家，也是已知OAPP旧H失败链；删除它后仍为`+528.37% / -18.39%`，相对OAPP收益高`19.10pp`、MDD改善`3.17pp`，所以candidate不是只靠旧H一笔成立。

逐事件leave-one全部solvent。删除origin 294后MDD与OAPP只差约浮点噪声，报告按相等处理，不把`1e-14`级差异称为严格改善。

## Round 4：邻域、分块与反证

- 5个一参数相邻arm在全窗和`[0,356)`仍同时相对V4双优，满足相邻路径门。
- `[0,356)`候选为`+452.26% / -18.39%`，V4约`+286.81% / -25.09%`；剔除旧H案例后方向不变。
- 8个54日flat-start block为5个双优、2个path-equal、1个收益较低但MDD改善；最差收益差`-8.31pp`，最差MDD差`0pp`，8/8不双劣。
- 8bps候选`+606.77% / -18.52%`，V4约`+392.35% / -25.27%`。
- funding-off候选`+621.62% / -18.44%`，不破产。
- 12h phase候选`+49.34% / -37.68%`，V4约`+34.38% / -39.93%`；相位绝对MDD很大，仍是重要风险警告，不因相对双优而忽略。
- BTC/ETH没有冻结的同身份exact V4和同源handoff事件链，本轮标记`NOT_APPLICABLE`，未用跨资产收益补HYPE样本。

## 状态机审计

完整路径记录8次shadow start、22个shadow hold日、6次机会、5次接受、1次MA-only拒绝；HTML包含19笔候选、17笔V4完整连线和60个shadow/handoff事件。shadow事件无equity字段；关闭entry时与fixed OAPP metrics、trades、path逐项相同。

时序边界经真实案例和测试固定：expiry 1日在旧H于2026-07-10过期，无法使用7月11事件；expiry 3日可在7月11 06:00产生机会；same-hour arm在该小时`66.536`成交，next-day arm只在7月12 00:00以`66.743`重新检查并成交。到terminal才到期的pending只记抑制，不创建零未来信息的新仓。

## 研究复盘

PEHC修复了OAPP最具体的结构缺口：利润退出不再等于删除反手机会。它没有证明“更复杂的趋势判定全面更好”，反而显示简单MA-only + 次日复核足够覆盖历史机会，slope和anti-chase在冻结路径中没有新增贡献。

当前最大遗留不是继续扩大旧历史参数，而是样本与选择偏差：只有6次机会、5次接受，其中1次负贡献，且全部来自已反复研究的432日。继续在这段数据删除origin 213或选择更细cap会违反前瞻治理。唯一允许的下一步是从`2026-08-11T00:00:00Z`累计clean prospective；样本不足就继续等待，前瞻FAIL则以更晚起点另立materially new机制，不能重用同一未来窗。

## 机器证据

- [Stage A 490臂](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_stage_a.json)
- [Stage B stress/funding/phase](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_stage_b.json)
- [Stage C多轮消融](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_stage_c.json)
- [Post-freeze控制与逐事件消融](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_post_freeze_ablation.json)
- [Shadow candidate与近期切片](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_shadow_candidate.json)

