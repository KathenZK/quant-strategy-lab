# HYPE-EMA-TB-V35.1 Dry-run Promotion Review

日期：2026-07-20  
目标迁移：`registered -> live spec -> dry-run`  
结论：`未通过`；保持 `registered / not promoted / not live-ready`

## 结论

`HYPE-EMA-TB-V35.1` 的 quant-runner 实现与离线逐笔对拍已经完成，但研究 promotion review 不满足现行准入条件。本次不创建 `dry-run` 状态、不建立 `runner-tracking/`，runner 配置与 manifest 都保持 fail-closed：`enabled=false`、`enabled_allowed=false`、`approval_level=none`。

直接 blocker 是 Gate 3：既有 V35 全参数消融已将 `adx_window=28`、`long_adx_min=28`、`adx_exit=22`、`hard_stop_atr=7`、`atr_window=672`、`disable_after_mfe_atr=1.5` 等多数核心参数判为尖峰。V35.1 与 V35 逐笔等价，删除的空头 1h EMA 条件是死条件，不能把等价精简解释为新增稳健性证据。

此外，Gate 0 正式超额收益报告、Gate 2 OOS/CPCV、Gate 4 执行压力、Gate 5 真实 1m 相位，以及 live-executable promotion review 仍未完成。按状态机，任一项未通过或数据不足都不能先启用 dry-run 再补证据。

## 数据与成本

- 市场：Binance USD-M perpetual
- Symbol / timeframe：`HYPE/USDT:USDT` / `15m`
- 数据源：标准数据湖 Binance futures raw/normalized
- UTC 范围：`2025-05-30T10:30:00Z` 至 `2026-07-17T08:45:00Z`
- 数据质量：`39,642` 根闭合 K；缺口、重复、关键空值、非法 OHLC、raw/normalized 差异均为 0
- 成本：每 fill `0.00085`，表示手续费与 4 bps adverse slippage 合并
- Funding：Python 冻结基准包含；Rust public-kline replay 未计
- 最近分片：`1d/7d/1m/3m/6m/1y` 仅作审计，不用于本次选参

## Runner 实现结果

- Kind：`hype_ema_tb`
- Strategy ID：`HYPE-EMA-TB-V35.1`
- Capability：`DryRunOnly`
- 实现方式：从已对拍的 EMA-TB 趋势腿抽取独立单腿 Driver/replay；不实例化 ensemble，不包含 MII 状态
- 冻结差异：`long_vol_min=0.25`、`short_target_atr_pct=0.018`、`short_use_h1_ema=false`、cooldown0
- Runtime：K0 close 信号、K1 完整等待、K2 open 目标入场；entry ATR 取 K1；TP5/SL7；ADX22 delayed3；MFE1.5 后关闭指标退出；384 根 timeout
- 配置：实例已加入 `configs/dryrun.toml`，但保持 `enabled=false`

## 连续 Driver 修复复核

部署前检查发现离线 replay 未覆盖四项连续 runtime 偏差：持仓 `entry_i` 未从 ledger entry time 同步、ADX pending exit 多等待一个 cycle、`BracketAfterEntry` 跳过 K2 入场 K 的 TP/SL、ledger 把 K1 而非 K0 记为 signal timestamp。Runner 已在本地修复为：

- 每个持仓 cycle 从 `position.entry_ts` 重建并同步 `entry_i`，避免首根持仓 K 误触发 384-bar timeout；
- ADX 第三根弱势 K 确认后立即返回 `NextOpen` flat target，由同一 cycle 安排下一根 open 退出；
- descriptor 改为 `Bracket + BarPriceSource::Trade`，K2 入场 K 纳入 stop-first bracket；
- entry evidence 明确携带 K0 `signal_ts` 与 K2 `entry_ts`，公共 Driver runtime 校验二者因果顺序后写入 ledger。

新增定向回归均通过（含 384-bar timeout 精确边界与旧 Driver evidence fallback），Runner 全套结果为 `218 passed / 5 ignored`；刷新 Rust replay 后仍为 `111/111`、路径 mismatch `0`。这关闭了实现层缺陷，但不构成 Gate 0–5 的研究证据，也不改变本报告的 promotion 结论。

## Python / Rust parity

同一 Binance 公共 K 线窗口的 replay 与数据湖 Python 冻结逐笔比较：

- Python 平仓：`111`
- Rust 平仓：`111`
- 路径 mismatch：`0`
- 比较字段：entry time、exit time、side、entry price、exit price、allocation、exit reason

Rust replay 未计 funding，因此 Rust cumulative return `78.751157` 与 Python 含 funding的最终权益不作为 parity 字段；交易路径零偏差仍成立。

## Promotion 门禁

| Gate | 结果 | 说明 |
| --- | --- | --- |
| 0 超额收益 | 未完成 | 有高收益回测，但未形成现行口径的 benchmark / excess-return 报告 |
| 1 消融 | 可继承 | V35 完整消融；V35.1 删除项经逐笔证明为冗余 |
| 2 OOS/CPCV | 未完成 | recent slices 不能替代结构化 OOS/CPCV |
| 3 MC / 参数邻域 | 未通过 | 既有全参数消融明确显示多数核心参数为尖峰 |
| 4 压力测试 | 未完成 | 拒单、断流、gap、保护失败与恢复未形成执行完整性报告 |
| 5 相位 | 未完成 | 未用真实 1m 重聚合扫描 15m `{0,5,10}` 相位 |
| live-executable | 未完成 | workingType、funding、真实滑点、重启、missing-bar、kill switch、账本对账仍有缺口 |

## 执行差异与风险

- 研究 TP/SL 使用 trade-price OHLC；quant-runner 当前条件保护单使用 `MARK_PRICE`。这对 dry-run candle replay 不构成逐笔差异，但对未来 live 是硬 blocker。
- Python 基准计入 funding，Rust replay 未计；进入 live spec 前必须定义 runtime funding 记账与验收方式。
- 旧 Python 人工退出归因与成交分片聚合曾出现账本偏差；旧 SQLite 只读归档，不导入 quant-runner 原生 ledger。
- 当前为空仓；不存在 open-position adoption，但这不降低 promotion 研究门禁。

## 决定与重开条件

本次只保留实现和 parity 证据，不执行状态晋升。重开 dry-run promotion 至少需要：

1. 用冻结参数完成结构化 OOS/CPCV；
2. 以预先声明的邻域完成 `mc3 + mc4`，并解决“多数核心参数尖峰”的判定；
3. 完成执行完整性压力测试和真实 1m 相位扫描；
4. 完成 live-executable review，并明确 `MARK_PRICE` 与 trade-price 保护口径；
5. 全部门禁通过后，将 handoff draft 升为 active `live spec`，再授权 manifest 与配置进入 dry-run。

## 证据

- [V35.1 冻结规格](../specs/hype-trend-strategy-v35-1-spec.md)
- [V35 全参数消融](../notes/hype-ema-tb-v35-full-ablation-recent-tune-2026-07-08.md)
- [Runner handoff draft](../live-specs/hype-ema-tb-v35-1-runner-draft.md)
- [Python/Rust parity](../artifacts/HYPE-EMA-TB-V35.1_parity_2026-07-20.json)
- [Rust replay](../artifacts/HYPE-EMA-TB-V35.1_runner_replay_2026-07-20.json)
- [Python 冻结汇总](../artifacts/hype_ema_tb_v35_1_2026-07-20.json)
- [Parity 脚本](../scripts/check_hype_ema_tb_v35_1_runner_parity.py)
