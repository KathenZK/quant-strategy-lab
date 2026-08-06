# HYPE-5M-PBTR runner 执行安全加固 2026-08-03

## 范围与结论

- Runner kind / mode：`hype_pullback`；直接受影响实例为 `hype-pullback-live`（tiny-live-pilot），平台层改动同时惠及 `hype-pullback-dry-run` 与其他 dry-run 实例。
- 来源：2026-08-02 全仓库风险审计（P1 执行安全项）与后续修复，分两个批次落地：
  - 2026-08-02 最小热修：CLI live 授权强制、protection deadline 先平仓再暂停、smoke/risk-resume 进程互斥。
  - 2026-08-03 剩余 P1：REST 部分成交对账、入场终态等待、marginType 严格校验、`engine_state.json` 耐久性、密钥隔离。
- **结论：全部改动为平台执行安全语义加固，策略信号/出场/参数口径不变；live spec（V6.2.1）无需修订。状态保持 `live / tiny-live-pilot / forward-test required`，keep，不改变 2026-09-24 授权复核门禁。**
- 当前所有改动均未部署、未提交（本地工作区）；线上事实仍以最近一次部署的 artifact 为准。

## 2026-08-02 批次（最小热修）

- `run-once` 等手工 CLI 路径对 live 实例强制校验 Lab 授权（manifest lock），不再依赖 systemd 才有的 `QUANT_RUNNER_REQUIRE_MANIFEST_LOCK`；`run-once`/`smoke-test` 同时加载平台上下文（平台风控闸、通知、超时）。
- `smoke-test`/`risk-resume` 获取实例进程锁，与运行中的服务互斥。
- kernel 维护保护的持仓缺失保护单超过 deadline 时，先按 stable emergency client ID 撤敞口（确认 flat），再以 `protection_failed_recovered_flat` 保持暂停，不再让裸仓长期无保护。
- 测试：`live_cli_authorization_is_enforced_against_lock_file`、`run_once_refuses_live_without_manifest_lock`、`smoke_test_requires_exclusive_process_lock`、`protection_deadline_flattens_exposed_position_before_pausing`、`partial_protection_fill_cancels_legs_and_rearms_residual_position`（替代原假阳性集成测试）。

## 2026-08-03 批次（剩余 P1）

### REST 对账识别保护单部分成交

- 修复前：REST fallback（`live_bracket_fill_reason`）只认 `FILLED`；保护单 `PARTIALLY_FILLED` 在 user-stream 中断期间不会被收敛，敞口/保护量可能长期不一致。
- 修复后：TP/SL 任一侧 REST 状态为 `PARTIALLY_FILLED` 且累计量 > 0 时，走与 user-stream 相同的处理原语（撤对侧+撤自身+按 venue 剩余仓位重挂）。幂等键为 tracked order 累计成交量：user-stream 已消化或上一轮 REST 已处理的累积量不重复撤挂。
- 测试：`rest_partial_protection_fill_rearms_residual_and_is_idempotent`（生产路径 + 幂等重放）。

### 入场等待终态成交

- 修复前：入场市价单按 `executedQty>0` 即挂保护；`NEW`/`PARTIALLY_FILLED` 状态下订单仍可能继续成交，实际敞口会超过保护量。
- 修复后：短预算（6×500ms）内补查订单至终态再按实际成交量挂保护；超预算仍不终态则保留 `pending_entry` 交给既有恢复路径（下一周期补挂或撤单/平仓），发 `execution_v2_entry_unconfirmed` ledger 事件与告警，不当作成功继续。
- 测试：`entry_terminal_classification_only_waits_for_resting_states`；既有入场/恢复回归全绿。

### marginType 严格校验

- 修复前：`setup_market` 用 `let _ =` 吞掉 marginType 全部错误（含权限不足、持仓冲突），账户实际保证金模式可能与配置不符仍启动。
- 修复后：除 Binance `-4046`（已是目标模式）外一律启动失败，并以 `positionRisk` 回读实际模式做最终确认，与配置不一致即拒绝启动。
- 测试：`margin_type_error_classification_only_accepts_idempotent_hit`、`margin_type_matches_normalizes_exchange_reported_case`。

### `engine_state.json` 耐久性

- 修复前：`StateStore::save` 直接 write+rename，无 fsync；掉电/杀机时可能丢最后一笔 persist-before-submit 记录。
- 修复后：tmp 写入 + 文件 fsync + rename + 目录 fsync（与 simulated venue 同一范式）；文件新增 `schema_version`（当前=1，serde default 兼容历史文件），高于二进制支持版本时拒绝加载而不是静默丢字段。
- 测试：`save_stamps_current_schema_version`、`load_refuses_newer_schema_version`、`legacy_file_without_version_loads_as_current`。

### 密钥隔离

- dry-run systemd unit 改为只读 `.secrets/dryrun.env`（通知密钥），不再加载含交易所凭据的 `.secrets/live.env`；`ExecStopPost` 同步切换。
- `.secrets/*.env` 权限强制 0600（本机已收紧；`install-release-and-units.sh` 每次部署强制执行）。
- 配置加载只为 `enabled` 策略解析账户凭据；disabled 实例（3 个待晋升 live 策略）不再把交易所密钥读进进程内存，CLI `--name` 点名时按需注入。disabled 实例的 `account_id` 引用仍在加载期校验。
- 测试：`disabled_strategy_credentials_are_resolved_on_demand_only`、`disabled_strategy_with_unknown_account_fails_fast`。

## 2026-08-03 批次（P2 运维硬化）

- `validate-config` 现在对每个 enabled 实例跑完整 `validate()`（与 run 启动路径一致），部署脚本能在重启前拦截坏配置，而不是只解析 TOML。
- dispatcher 启动时向 ledger 注册**全部**实例（含 disabled），被禁用策略在 `strategy_instances.enabled` 正确写回 0，不再保留过期的 enabled=1。
- CI 供应链硬化：`build-linux-release.yml` 新增 guard job，只允许 `refs/heads/main` 触发 release 构建；三个 workflow 的第三方 Actions 全部固定到 commit SHA（checkout v4.2.2 / setup-python v5.6.0 / upload-artifact v4.6.2）；`rust-quality.yml` 新增 `rustsec/audit-check` 门禁，本地 `cargo audit` 对当前 Cargo.lock（236 crate）零 advisory 确认通过。
- 仍保持冻结的两个架构性 P2（与稳定性优先原则一致，不在本次扩大改动面）：V6 复用 V5 Driver 的版本间耦合、多市场策略统一 REST 权重限流。后续若要动，单独立项并配套 replay/parity 验证。

## 部署前置（下次发布必须执行）

1. 无需手工创建 `.secrets/dryrun.env`：`install-release-and-units.sh` 每次部署从
   `live.env` 自动派生（仅 dryrun.toml 声明的通知变量，0600），服务器只维护
   `live.env` 一个密钥文件。若 live.env 缺少通知变量，脚本会保留旧 dryrun.env
   并打印 warning（不会静默失效）。
2. 首次带新二进制重启 live 时，`setup_market` 会实际校验保证金模式：若 subaccount 的 `HYPEUSDT` 当前不是 isolated 且无法切换（有持仓/挂单），启动会失败——届时按报错人工核对账户设置，属预期 fail-fast。
3. 标准发布流程不变（Actions artifact → scp → install-release-and-units.sh）。

## 验证记录

- `cargo test --workspace`：234 passed / 0 failed / 5 ignored（ignored 为大体量 parity fixture 测试）。
- `cargo clippy --workspace --all-targets` 无告警；`cargo fmt --all --check` 通过。
- governance：`validate_manifest_lock.py` 与 `sync_manifest_lock.py --check` 均通过，lock 与 Lab main `06e484f` 一致（本批次无策略启停，lock 无变化）。
- 运行事实核对：本次无线上开平仓/运行事件统计提取，无需对齐数据；改动对线上历史成交口径无影响。
