# HYPE-1D-MA7-Asymmetric-Body-Trend-V7 规格

## 身份与状态

- Full version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V7`
- Alias：`HYPE-1D-MA7-ABT-V7`
- 来源候选：V6全参数邻域扫描 `n_short_cooldown_days_3`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；风险回放使用真实 `1h`
- 默认仓位：固定目标 `1x`、单仓、非加仓
- 状态：`registered / not promoted / not live-ready`
- 登记日期：2026-08-11

登记只冻结版本身份、参数和证据链接；不表示 promotion，不创建 live spec，不授权 dry-run/live，不改变杠杆锁。V7 来自已揭示 `432d` 历史邻域扫描，必须视为 post-reveal registration。

## V7 定义

V7 完整继承 [V6规格](hype-1d-ma7-abt-v6-spec.md)，唯一实际交易参数改动为：

```json
{
  "short_config.cooldown_days": {
    "from_v6": 5,
    "to_v7": 3
  }
}
```

除上述字段外，V6 的 exact V4 基础、OAPP、PEHC、成本、执行时序和仓位规则全部不变。

## 冻结参数

```json
{
  "long_config": {
    "side": 1,
    "entry_mode": "reclaim",
    "slope_lookback": 1,
    "slope_min_atr": 0.02,
    "confirm_days": 1,
    "entry_buffer_atr": 0.0,
    "pullback_lookback": 5,
    "pullback_touch_atr": 0.0,
    "breakout_lookback": 2,
    "exit_confirm_days": 1,
    "exit_buffer_atr": 0.75,
    "slope_exit_lookback": 0,
    "hard_stop_atr": 0.0,
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
    "pullback_lookback": 10,
    "pullback_touch_atr": 0.0,
    "breakout_lookback": 5,
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
      "kind": "off",
      "lookback": 0,
      "scope": "both",
      "threshold": 0.0
    },
    "long_exit": {
      "mode": "fraction",
      "activation_atr": 0.5,
      "giveback": 0.1,
      "confirm_days": 2
    },
    "short_exit": {
      "mode": "off",
      "activation_atr": 0.0,
      "giveback": 0.0,
      "confirm_days": 0
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
    "execution": "next_utc_open",
    "allowed_origin_indices": [],
    "blocked_origin_indices": []
  }
}
```

配置 SHA256：`af41da106f8cf15cd433209e361d2c64c8ff5056e414a87ea021020838af8c5d`。

## 成本与执行

- 手续费：`0.001` / fill。
- 滑点：base `4 bps` / fill；压力检查 `8 bps` / fill。
- Funding：真实 Binance funding 事件，只在真实持仓区间结算。
- 日线信号：收盘条件最早在下一 UTC 日 open 成交。
- 空头开盘条件：先观察日 open，再在下一根 `1h` open 成交。
- PEHC handoff：沿用 V6 `next_utc_open` 复核；shadow 无仓位、无费用、无 funding、无 PnL。

## 冻结结果

- 已揭示全窗 `2025-05-31` 至 `2026-08-06 UTC`，`432d`：`+711.04%`，真实 `1h` 顺序 MDD `-18.40%`，20笔，PF `17.51`。
- exact V6 同窗：`+617.09%`，真实 `1h` 顺序 MDD `-18.40%`，19笔。
- `8 bps` 压力：`+698.75%`，真实 `1h` 顺序 MDD `-18.53%`。
- 额外 `1d` signal lag：`+267.61%`，真实 `1h` 顺序 MDD `-26.45%`。
- 8个54日block均为正收益：`+20.47%` 至 `+44.79%`。
- 近期切片：`1d/7d` 无新闭合交易，`1m +6.17%/-9.11%`，`3m +72.14%/-12.66%`，`6m +110.41%/-18.40%`，`1y +426.91%/-18.40%`。

## 证据

- [全参数邻域消融](../ablations/hype-1d-ma7-abt-v6-full-parameter-ablation-2026-08-11.md)
- [V7冻结机器证据](../artifacts/hype_1d_ma7_abt_v7_short_cooldown3_2026-08-11.json)
- [V7交互式交易路径](../artifacts/hype_1d_ma7_abt_v7_trade_path_2026-08-11.html)
- [V7交易路径渲染脚本](../scripts/render_hype_1d_ma7_abt_v7_trade_path.py)
- [家族主账](../hype-1d-ma7-abt-core-ledger.md)
