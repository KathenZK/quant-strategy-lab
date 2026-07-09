# HYPE-15M-TB-MII-ENS V2 Live-Executable 静态检查摘要 2026-07-09

Strategy：`HYPE-15M-TB-MII-ENS-V2`

Result：`FAIL`

Decision：`NO-GO for dry-run/live until runner implementation and live-executable gates are completed`

## 检查来源

- [`/Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/runtime/config.rs`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/runtime/config.rs)
- [`/Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/mod.rs`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/mod.rs)
- [`/Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/hype_mii/mod.rs`](file:///Users/ZK/OpenCode/quant-runner/crates/quant-runner/src/runner/strategies/hype_mii/mod.rs)
- [`/Users/ZK/OpenCode/quant-runner/configs/live.toml`](file:///Users/ZK/OpenCode/quant-runner/configs/live.toml)
- [`/Users/ZK/OpenCode/hype-trend`](file:///Users/ZK/OpenCode/hype-trend)

## 计数

| Status | Count |
| --- | ---: |
| `PASS` | `3` |
| `PARTIAL` | `1` |
| `FAIL` | `12` |
| `UNKNOWN` | `0` |

## 关键检查

| Check | Status | Evidence |
| --- | --- | --- |
| `runner_kind_hype_tb_mii_ensemble` | `FAIL` | `quant-runner` 的 `StrategyKindName` 未发现 `HypeTbMii` / `hype_tb_mii_ensemble`。 |
| `runner_kind_hype_ema_tb_v39` | `FAIL` | `quant-runner` 未发现 `hype_ema_tb` / `HypeEmaTb`；现有 `HypeEmaX` 不是 V39 trend-breakout。 |
| `runner_hype_mii_present` | `PASS` | `quant-runner` 有 `hype_mii` strategy module。 |
| `runner_hype_mii_version` | `FAIL` | `hype_mii` 默认 `strategy_id` 是 `HYPE-15M-MII-V1.3`，未发现 V1.4 默认配置。 |
| `runner_hype_mii_min_rvol` | `FAIL` | `hype_mii` 默认 `min_rvol96=1.0`；V2 要求 V1.4 的 `0.85`。 |
| `runner_live_hype_mii_enabled` | `FAIL` | `quant-runner/configs/live.toml` 中 `hype-mii-live` 为 `enabled=false` / `live_confirm=false`。 |
| `runner_preempt_support` | `FAIL` | 检查文件中未发现 V2 所需的 preempt / global arbitration 实现。 |
| `runner_global_single_position` | `FAIL` | 检查文件中未发现 `global_position_limit` 或组合级全局单仓状态。 |
| `hype_trend_v35_single_leg` | `FAIL` | [`hype-trend`](file:///Users/ZK/OpenCode/hype-trend) 是 `V35Engine` 单腿 runner，未发现 MII/preempt/ensemble 证据。 |
| `generic_bracket_protection_quant_runner` | `PARTIAL` | `quant-runner` 单策略 bracket 路径有 TP/SL 与 emergency flatten 能力，但不覆盖 V2 组合层。 |
| `research_data_quality_gate` | `PASS` | V2 组合报告记录标准数据湖质量 gate 全 `0`。 |
| `research_replay_gate_python` | `PASS` | Python 组合循环门禁通过：V39 canonical 零差、V1.4 链路一致、V2 主口径 `291` 笔 / preempt `3`。 |
| `mii_funding_live_gap` | `FAIL` | 研究 V1.4/MII 腿 funding 未计，组合 live funding 记账未验证。 |
| `order_timing_live_gap` | `FAIL` | 研究使用 K+1/K+2 open 代理成交，缺 runner fill-vs-open 与交易所订单时序报告。 |
| `restart_recovery_live_gap` | `FAIL` | 未发现 V2 `active_leg`、`preempt_in_progress`、保护单 id 等状态恢复实现。 |
| `kill_switch_live_gap` | `FAIL` | 未发现 V2 专属 kill switch、日亏损、单笔 notional cap 证据。 |
