# HYPE-1D-MA7-Asymmetric-Body-Trend-V6 规格

## 身份与状态

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V6`
- Alias：`HYPE-1D-MA7-ABT-V6`
- 研究身份：`PEHC_294`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；保护与handoff审计使用真实`1h`
- 默认仓位：固定目标`1x`、单仓、非加仓
- 状态：`registered / shadow-only / not promoted / not live-ready`
- 来源：用户于2026-08-10明确将`PEHC_294`登记为V6

登记固定PEHC状态机身份，不把已暴露全窗当作clean OOS。V6继续执行冻结的前瞻observer门禁；达到门禁前不得promotion或采纳杠杆。用户于2026-08-10另行明确授权的一次固定3x已暴露历史诊断不解锁杠杆，也不改变本规格的默认1x身份。

## V5继承

V6完整继承[V5规格](hype-1d-ma7-abt-v5-spec.md)：exact V4全部入场、退出、保护、成本与`MA_ONLY`反手合同，加上固定OAPP的long `0.5ATR/10%/2d`利润保护、short `RSI6 20×2`盈利止盈及`0.28%`roundtrip guard。V6不修改任何V5实际交易参数。

## PEHC_294 增量

```json
{
  "arm_id": "PEHC_294",
  "enabled": true,
  "entry_enabled": true,
  "expiry_days": 8,
  "slope_threshold": null,
  "chase_cap_atr": "INF",
  "execution": "next_utc_open",
  "allowed_origin_indices": [],
  "blocked_origin_indices": []
}
```

状态机冻结为：

1. 只有V5因OAPP long MFE规则早于exact V4平多，且虚拟exact V4原long仍应继续持有时，才创建一个隔离shadow；
2. shadow复制当时虚拟V4 long的保护状态，但没有真实仓位、手续费、funding或PnL，也不得叠加或刷新；
3. shadow在`age=0..8`有效，`age>8`过期；虚拟V4自然退出、实际账户重新开long、数据非有限或已消费都会取消；
4. 只有虚拟V4原long随后命中其protective/trailing stop，才产生一次handoff short机会；普通MA7自然退出不产生；
5. 机会等待到下一UTC日open重新检查，open必须严格低于上一完整日`SMA7`；`slope_threshold=null`表示不增加short slope门，`chase_cap_atr=INF`表示没有额外ATR追价上限；
6. 条件通过后开short并继承V5/V4的short管理；每个shadow最多消费一次；
7. `allowed_origin_indices=[]`且`blocked_origin_indices=[]`，不得事后挑选或删除历史episode。

配置SHA256：`b155a35133224e77266ba0c22fb84ba1657ab89212a700e9f551b3fa3431af00`。

## 冻结结果与前瞻门禁

- 全部已暴露`432d`：`+617.11%`，真实`1h`顺序MDD `-18.39%`，19笔；exact V4为`+398.84%/-25.09%`。
- 历史共有6次handoff机会、5次接受，5次中有1次负贡献；这些只是shadow选择证据。
- clean prospective从`2026-08-11`起计算，至少需要90个新增完整UTC日，并满足冻结的交易、多空及handoff事件样本门；初始observer为0个新增完整日且不披露绩效。
- V6无live spec、无quant-runner implementation、无dry-run/live授权；`1x`前瞻门通过前杠杆继续锁定。

## 固定3x诊断观察

- 只把每次实际入场目标改为`3x`、持仓数量固定后，已暴露全窗为`+14,164.73%`、真实`1h` MDD `-45.35%`；19笔交易行为与1x逐笔相同。
- 24相位仅19个盈利，最差收益`-59.97%`、MDD`-94.19%`，最大marked leverage `7.65x`；额外延迟一天为`+532.64%/-70.50%`。
- 该结果为用户明确授权的`diagnostic-only`治理偏差，不修改V6、前瞻observer或杠杆锁；见[固定3x诊断](../diagnostics/hype-1d-ma7-abt-v6-3x-leverage-2026-08-10.md)与[交易路径](../artifacts/hype_1d_ma7_abt_v6_3x_leverage_trade_path_2026-08-10.html)。

## 证据

- [PEHC预注册合同](hype-1d-ma7-profit-exit-handoff-continuity-preregistration-2026-08-10.md)
- [V6前瞻observer协议](hype-1d-ma7-profit-exit-handoff-continuity-prospective-observer-v1-2026-08-10.md)
- [Shadow冻结裁决](../diagnostics/hype-1d-ma7-profit-exit-handoff-continuity-shadow-freeze-2026-08-10.md)
- [多轮消融](../ablations/hype-1d-ma7-profit-exit-handoff-continuity-ablation-2026-08-10.md)
- [冻结shadow机器证据](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_shadow_candidate.json)
- [初始前瞻观察](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_prospective_observer_v1_2026-08-10_observation_through_2026-08-05.json)
- [可缩放完整交易路径](../artifacts/hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_full_trade_path_zoomable_v2.html)
- [固定3x杠杆诊断](../diagnostics/hype-1d-ma7-abt-v6-3x-leverage-2026-08-10.md)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
