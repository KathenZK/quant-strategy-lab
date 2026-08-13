# HYPE-1D-MA7-Asymmetric-Body-Trend-V5 规格

## 身份与状态

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V5`
- Alias：`HYPE-1D-MA7-ABT-V5`
- 研究身份：固定 OAPP，冻结 arm `C_2AA556432E9E`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；保护路径使用真实 `1h`
- 默认仓位：固定目标 `1x`、单仓、非加仓
- 状态：`registered / not promoted / not live-ready`
- 来源：用户于 2026-08-10 明确将固定 OAPP 登记为 V5

登记只固定版本身份。一次性 H hard-gate `FAIL`、全部历史已暴露、无 runner parity 与不得用杠杆救援等事实继续有效。

## Exact V4 继承

V5完整继承[V4规格](hype-1d-ma7-abt-v4-spec.md)的信号、成本、成交与风险合同；身份级参数如下。

| 方向 | 入场 | 退出/保护 | 最长持有/冷却 |
| --- | --- | --- | --- |
| long | `reclaim`；`slope_lookback=1`、`slope_min_atr=0.02`、`confirm_days=1`、`entry_buffer_atr=0`、`pullback_touch_atr=0` | `exit_confirm_days=1`、`exit_buffer_atr=0.75`、`slope_exit_lookback=0`、`hard_stop_atr=0`、`trail_atr=1.5` | `max_hold_days=90`、`cooldown_days=2` |
| short | `reclaim`；`slope_lookback=2`、`slope_min_atr=0.02`、`confirm_days=1`、`entry_buffer_atr=0.10`、`pullback_touch_atr=0` | `exit_confirm_days=1`、`exit_buffer_atr=0.75`、`slope_exit_lookback=1`、`hard_stop_atr=1.5`、`trail_atr=4` | `max_hold_days=20`、`cooldown_days=5` |

- `pullback_lookback=5/10`与`breakout_lookback=2/5`分别保留在long/short配置中，但在`entry_mode=reclaim`下休眠。
- V4 `MA_ONLY`强制反手保留：long保护/追踪止损后的拟反手真实`1h open`必须严格低于上一完整UTC日`SMA7`；不重新要求自然short的fresh cross、`0.10ATR`距离或两日slope。
- 指标为`SMA7`、`ATR7`与Wilder `RSI6`；手续费`0.001/fill`、基准不利滑点`4 bps/fill`并计实际event-time funding。

## V5 OAPP 增量

```json
{
  "entry": {"kind": "off", "lookback": 0, "scope": "both", "threshold": 0.0},
  "long_exit": {"mode": "fraction", "activation_atr": 0.5, "giveback": 0.1, "confirm_days": 2},
  "short_exit": {"mode": "off", "activation_atr": 0.0, "giveback": 0.0, "confirm_days": 0},
  "short_rsi": {"threshold": 20.0, "days": 2},
  "roundtrip_guard": 0.0028
}
```

- 入场过滤关闭，V5不改变V4的趋势开始识别。
- long历史最高收盘浮盈达到`0.5ATR7`后，当前毛利润仍严格大于`0.28%`且从峰值浮盈回吐至少`10%`，连续两个实际持仓日成立，则下一UTC日open平多。
- short MFE退出关闭；实际持有short且`RSI6<20`连续两个持仓日、当前毛利润严格大于`0.28%`时，下一UTC日open止盈。
- 配置SHA256：`4a7136f016d3258d371bc32ae558974ce47fb827a071111446c64d6d01e0a588`。

## 冻结结果与门禁

- 全部已暴露`432d`：`+509.26%`，真实`1h`顺序MDD `-21.56%`，17笔；同期exact V4为`+398.84%/-25.09%`。
- Development、Validation与rolling均曾严格优于V4，但一次性H为`+16.70%/-17.94%`，低于V4的`+22.43%/-17.94%`，hard-gate `FAIL`。
- H失败机制：提前平多把一笔long从亏损改为盈利，却切断随后一笔`+16.87%`的V4 forced short；H内RSI退出0次触发。
- V5不进入promotion、不生成live spec、不推进quant-runner；固定/动态杠杆臂不具采纳资格。

## 证据

- [OAPP预注册合同](hype-1d-ma7-opportunity-aware-profit-protection-preregistration-2026-08-10.md)
- [H最终裁决](../diagnostics/hype-1d-ma7-opportunity-aware-profit-protection-final-2026-08-10.md)
- [多轮消融](../ablations/hype-1d-ma7-opportunity-aware-profit-protection-ablation-2026-08-10.md)
- [冻结champion](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_champion.json)
- [最终机器报告](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_final.json)
- [可缩放完整交易路径](../artifacts/hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_full_trade_path_zoomable_v2.html)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
