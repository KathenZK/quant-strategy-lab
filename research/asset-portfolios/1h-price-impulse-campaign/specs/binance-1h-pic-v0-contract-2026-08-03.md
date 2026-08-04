# BIN-1H-PIC-V0 冻结合同（2026-08-03）

## 1. 身份与目标

- Family：`Binance-1H-Price-Impulse-Campaign`（`BIN-1H-PIC`）。
- Candidate id：`BIN-1H-PIC-V0`；冻结研究候选，不因命名自动 registered 或 promotion。
- 目标：把 ETH `4h` 价格冲量延续线索变成完整、可由 runner 复现的固定 quantity campaign；BTC/HYPE/SOL 原样运行作为控制。
- 状态：`explore / not promoted / not live-ready`。

## 2. 数据与可见性

- Binance USD-M `ETHUSDT/BTCUSDT/HYPEUSDT/SOLUSDT` perpetual。
- 标准数据湖闭合 `15m` OHLCV/funding；raw/normalized parity、连续性、重复、关键空值、OHLCV 合法性必须通过。
- 四根连续 `15m` 聚合为完整 `1h`；hour-open 数据只有在一小时结束后可见。
- 每日 UTC `00:00` 已知 close 为 anchor；UTC `04:00` 已知 close 形成 4h move。信号在该闭合时刻确认，下一根 `1h open` 成交。
- `past_rms` 只使用 anchor `00:00` 之前完整 `720h` hourly log return，不把 4h impulse 纳入尺度估计。

## 3. Admission

```text
impulse = log(close_04 / close_00)
scaled_impulse = abs(impulse) / (past_rms_720 × sqrt(4))
```

- `scaled_impulse >= 1.0` 时产生候选；方向为 impulse 符号。
- 每资产同一时刻最多一个 campaign；持仓中忽略新信号。
- Long/Short 对称，不增加 7d/28d、传统指标、方向白名单或资产特例。

## 4. Entry、quantity 与成本

- Entry：信号闭合后的下一根 `1h open`，adverse slippage `4bps`。
- `R_log = past_rms_720 × sqrt(24)`；初始 stop 为 `entry × exp(-side × R_log)`。
- 计划风险为 entry 前账户权益 `1%`。quantity 同时受下列上限约束：
  - stop distance + entry/exit fee/slippage 后的最坏计划损失不超过 `1%`；
  - entry notional 不超过权益 `3x`；
  - quantity 固定直至退出，不连续再平衡。
- 每 fill fee `10bps`；slippage `4bps`；持仓期间按实际 funding rate 计提。

## 5. 状态机与退出

- 初始 stop 从 entry 起有效；同一 `1h` bar 若 stop 与 MFE threshold 均可能触及，保守地先判 stop。
- 24h validation：入场后 24 个完整小时内若从未达到 `+1R`，在下一根 open 退出。
- MFE 只由已闭合/已完成的价格路径更新；保护更新从下一 bar 开始生效。
- MFE 达 `2R` 后，stop 至少保护 `entry + side × 0.5 × peak_mfe_price`；只能收紧。
- 无固定 take profit；持仓达到 `336h` 后下一根 open 退出。
- 数据末尾强制 mark close 只用于完整研究账本，不伪装成在线可成交退出。

## 6. Shadow add

- 首次达到 `0.5R/1R/2R` 时分别记录 shadow event，不改变 quantity、成本或收益。
- shadow event 用于估计未来真实 `25%→50%→75%→100%` layers 的到达率和路径，不构成 pyramiding 回测。
- 真实 add/reduce 需要 quant-runner 同方向 resize、保护替换、pending recovery 与 reconciliation 全部实现后另立版本。

## 7. 固定实验与门禁

- Arms：四资产 `full`、Long-only、Short-only；ETH 为唯一执行候选，其余是控制，不能因某控制更好临时换主角。
- Costs：gross、base cost+funding；另做 `8bps` slippage stress。
- Recent slices：最近 `1d/7d/1m/3m/6m/1y`，只审计，不选择。
- Rolling audit：固定 `120d` evaluation windows、`30d` step；报告净收益、MDD、campaign count 和正窗口比例。
- Ablation：no 24h failure exit、no MFE floor、72h timeout；只判断部件作用，不选择替代策略。

V0 进入登记讨论的最低条件：ETH base net return `>0`、Sharpe `>0`、MDD `>-20%`、至少 `30` 个闭合 campaign、最近 `6m` 非负、rolling 正窗口比例 `>=60%`、8bps stress 非负、无 leverage/risk/timing/data blocker。任一失败则保持 `explore / not promoted / not live-ready`，不得调阈值救援。

## 8. 已知证据边界

该规则源自已揭示的 FATHA ETH onset 诊断。即使历史门禁全部通过，仍需在冻结日之后收集 prospective OOS；历史结果不能单独授权 live spec、dry-run 或 live。

