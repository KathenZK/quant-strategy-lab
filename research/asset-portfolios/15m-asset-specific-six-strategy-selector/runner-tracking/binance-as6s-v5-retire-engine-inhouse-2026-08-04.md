# AS6S V5 退役与 V6 引擎内聚记录（2026-08-04）

## 决定

用户决定 AS6S 家族只保留 V6 双路线（`v6_mark_joint_np` /
`v6_mark_joint_preemptive`，均为已授权 dry-run），V5
（`BIN-15M-AS6S-V5-JOINT-NP`）整体退役。

## Runner 侧变更（quant-runner 工作区，未提交时点快照）

- manifest：`bin-15m-as6s-v5-joint-np-dry-run` 条目移除；`configs/dryrun.toml`
  同名 disabled 实例移除；`configs/active-strategy.lock.json` 重新生成并通过
  `validate_manifest_lock.py` / `check_live_enabled_gate.py`。
- 删除目录 `crates/quant-runner/src/runner/strategies/asset_specific_six_selector_v5_joint_state/`
  （含 `BIN-15M-AS6S-V5-JOINT-NP-SPEC.md`）。
- V6 依赖迁移：原 V5 引擎四个文件原样迁入 V6 目录并改名——
  - `config.rs` → `engine_config.rs`（移除 V5 `STRATEGY_ID`/`KIND` 常量与
    test-only `allocation()`）
  - `signals.rs` → `engine_signals.rs`
  - `router.rs` → `engine_router.rs`
  - `mod.rs` → `engine.rs`（`AssetSpecificSixSelectorV5Driver` 改名
    `AssetSpecificSixSelectorDriver`，剔除 inventory 注册、
    `build_registered_driver`、`replay_handler`、V5 parity 常量与测试）
- V5 专属 strict replay（fixture 驱动）与 `AS6S_V5_PARITY_FIXTURE` 环境变量
  支持一并移除；`docs/ARCHITECTURE.md` 与 `README.md` 同步更新。

## 行为不变性验证

- 迁入代码与 V5 原文件 diff 审计：除上述显式剔除项外逐位一致。
- `cargo fmt --all`、`cargo clippy --workspace --all-targets -- -D warnings` 零告警。
- `cargo test --workspace`：232 passed / 0 failed / 2 ignored（ignored 为
  AS6S fixture 本地审计与另一项显式本地审计）。
- V6 两个实例的 driver 构造、frozen config 常量、路由行为均来自同一份迁移
  代码，V6 `config.rs` 的 profile 覆盖逻辑未改。

## 跟进项（2026-08-06 关闭）

- ~~V6 parity fixture 重新落盘~~ **已取消**：2026-08-04 artifacts 磁盘清理
  删除了导出脚本输入（冻结候选 JSON 与 trades CSV），2026-08-05 本家族在
  研究分支正式封存为 `archived`（不再从数据湖重建、取消原定最终 OOS）。
  fixture 重导出与全量对拍随家族归档一并终止；runner 侧遗留的 ignored
  parity 测试与 SHA 常量将作为死代码另行清理。封存记录见研究分支
  `cursor/pkc-campaign-and-mtf-research` 的家族 README 与
  `artifacts/README.md`（合并入 main 前以研究分支为准）。
- V5 历史证据（45 信号 / 15 退出 / 553 路由 PASS）保留于
  [V5 Runner 对拍](binance-as6s-v5-joint-runner-2026-07-15.md)，仅作历史记录。

## 边界

- 本次为 runner 代码结构退役，不改变 V6 双路线的授权状态（dry-run 维持）、
  参数、冻结规格或未来 OOS 禁改禁看边界。
