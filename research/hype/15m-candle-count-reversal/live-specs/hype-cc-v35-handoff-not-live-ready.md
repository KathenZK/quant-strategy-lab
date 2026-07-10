---
spec_role: lab_handoff
strategy_id: HYPE-CANDLE-COUNT-V35
family_id: HYPE-CC
runner_kind: hype_candle_count
spec_status: active
peer_spec: crates/quant-runner/src/runner/strategies/hype_candle_count/HYPE-CANDLE-COUNT-V35-SPEC.md
manifest_instance_ids:
  - hype-candle-count-v35-dry-run
approval_level_max: dry_run
---

# HYPE-CANDLE-COUNT-V35 Runner Handoff

状态：`dry-run / forward-test required / not live-ready`。历史 live
underperformance 不因当前 dry-run 重新观察而失效。

- Exchange / market：Binance USD-M Futures。
- Symbol / timeframe：`HYPE/USDT:USDT` / `15m`。
- Runner kind：`hype_candle_count`。
- Closed-bar rule：信号只用闭合 K，下一根 open 执行；mark K、funding 和
  protection order 行为必须单独对账。
- Runner 实现规格：
  [`HYPE-CANDLE-COUNT-V35-SPEC.md`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/hype_candle_count/HYPE-CANDLE-COUNT-V35-SPEC.md)。
- 研究参数规格：
  [`specs/hype-v35-reproducible-params.md`](../specs/hype-v35-reproducible-params.md)。
- Live blockers：标准 parity、dated runner report、历史 underperformance
  复核、保护单/重启恢复、费用/滑点/funding 和平台安全闸验收。

```toml
name = "hype-candle-count-v35-dry-run"
kind = "hype_candle_count"
mode = "dry_run"
symbol = "HYPE/USDT:USDT"
timeframe = "15m"
state_dir = "/home/admin/quant-runner/state/hype-candle-count-v35-dry-run"
warmup_bars = 5000
dry_run_notional_usdt = 10.0
```
