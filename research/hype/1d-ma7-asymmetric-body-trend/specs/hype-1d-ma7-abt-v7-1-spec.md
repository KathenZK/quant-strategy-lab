# HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1 规格

## 身份与状态

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`
- Alias：`HYPE-1D-MA7-ABT-V7.1`
- 来源：V7 全参数消融后的功能等价参数面精简
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；风险回放使用真实 `1h`
- 默认仓位：固定目标 `1x`、单仓、非加仓
- 状态：`registered / not promoted / not live-ready`
- 登记日期：2026-08-11

V7.1 只移除 V7 规格里的 dormant/schema-only 字段；不改变 V7 交易路径、成本、执行时序、OAPP/PEHC、short cooldown、风险保护或杠杆。登记只冻结精简规格身份，不表示 promotion，不创建 live spec，不授权 dry-run/live。

## V7.1 定义

V7.1 与 [V7规格](hype-1d-ma7-abt-v7-spec.md) 功能等价。移除字段：

- `long_config.pullback_lookback`、`long_config.pullback_touch_atr`、`long_config.breakout_lookback`
- `short_config.pullback_lookback`、`short_config.pullback_touch_atr`、`short_config.breakout_lookback`
- `oapp_config.entry.lookback`、`oapp_config.entry.scope`、`oapp_config.entry.threshold`
- `oapp_config.short_exit.activation_atr`、`oapp_config.short_exit.giveback`、`oapp_config.short_exit.confirm_days`
- `pehc_config.allowed_origin_indices`、`pehc_config.blocked_origin_indices`

风险保护参数即使历史未触发也保留为版本身份的一部分。

## 精简参数

```json
{
  "long_config": {
    "side": 1,
    "entry_mode": "reclaim",
    "slope_lookback": 1,
    "slope_min_atr": 0.02,
    "confirm_days": 1,
    "entry_buffer_atr": 0.0,
    "exit_confirm_days": 1,
    "exit_buffer_atr": 0.75,
    "trail_atr": 1.5,
    "max_hold_days": 90,
    "cooldown_days": 2
  },
  "short_config": {
    "side": -1,
    "entry_mode": "reclaim",
    "slope_lookback": 2,
    "slope_min_atr": 0.02,
    "confirm_days": 1,
    "entry_buffer_atr": 0.1,
    "exit_confirm_days": 1,
    "exit_buffer_atr": 0.75,
    "slope_exit_lookback": 1,
    "hard_stop_atr": 1.5,
    "trail_atr": 4.0,
    "max_hold_days": 20,
    "cooldown_days": 3
  },
  "oapp_config": {
    "arm_id": "V6_OAPP",
    "entry": {
      "kind": "off"
    },
    "long_exit": {
      "mode": "fraction",
      "activation_atr": 0.5,
      "giveback": 0.1,
      "confirm_days": 2
    },
    "short_exit": {
      "mode": "off"
    },
    "short_rsi": {
      "threshold": 20.0,
      "days": 2
    },
    "roundtrip_guard": 0.0028
  },
  "pehc_config": {
    "arm_id": "PEHC_294",
    "enabled": true,
    "entry_enabled": true,
    "expiry_days": 8,
    "slope_threshold": null,
    "chase_cap_atr": "INF",
    "execution": "next_utc_open"
  }
}
```

## 冻结结果

- exact V7/V7.1 同窗 `2025-05-31` 至 `2026-08-06 UTC`，`432d`：`+711.04%`，真实 `1h` 顺序 MDD `-18.40%`，20笔，PF `17.51`。
- 全参数消融：224个候选；仅 `short_rsi_threshold_25` / `n_short_rsi_threshold_25` 出现 post-reveal 小幅双优，但它改变策略行为，不属于 V7.1 参数清理。
- V7.1 与 V7 的关系：同路径、同指标、同风险；只是去除 dormant/schema-only 字段。

## 证据

- [V7.1参数清理合同](hype-1d-ma7-abt-v7-1-parameter-cleanup-contract-2026-08-11.md)
- [V7全参数清理消融诊断](../ablations/hype-1d-ma7-abt-v7-full-parameter-cleanup-ablation-2026-08-11.md)
- [V7全参数清理机器证据](../artifacts/hype_1d_ma7_abt_v7_full_parameter_cleanup_ablation_2026-08-11.json)
- [V7规格](hype-1d-ma7-abt-v7-spec.md)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
