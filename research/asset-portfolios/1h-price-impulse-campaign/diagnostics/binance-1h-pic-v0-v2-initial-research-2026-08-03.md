# BIN-1H-PIC V0–V2 初始研究结论（2026-08-03）

## 结论先行

这轮已经从“趋势分析”落成了可逐笔复现的 quantity/lot 订单状态机，但还不能接线上 runner。

- **理论没有被完全否定**：ETH 上“先小仓试错、行情走出后分层加仓、回吐时先卸新增仓、保留原始 probe 吃右尾”产生了明确的历史正偏。V2 base `+47.93%`、Sharpe `0.82`、MDD `-11.05%`，PnL-R skew `3.67`；胜率只有 `30.4%`，但 5 个最大赢家贡献总净 PnL 的 `76.3%`，符合 trend campaign 的正偏结构。
- **未来延续不能被普适预测**：同一规则的 BTC base 只有 `+8.30%`，HYPE `-1.73%`，SOL `-7.09%`；ETH standalone short 也是 `-2.68%`。这不是四资产通用规律，更不是“发现任意大波动就能预测延续”。
- **动态加减仓得到了部分验证**：V1 full `+53.93% / Sharpe 0.82 / MDD -11.64%`，高于 probe-only `+19.60% / Sharpe 0.70 / MDD -5.34%`；相对一开始满仓的 `+94.62% / Sharpe 0.73 / MDD -19.39%`，动态确认牺牲绝对收益，换来更好的风险调整收益和更小回撤。
- **V1 的落地风险确实有缺口**：只在 add 时检查 stop-out 不够。ETH 有 62 个 campaign 因长持有期间累计 funding 穿透 `1%` 风险线，最坏 stop-out 损失 `2.06%`。V2 用 `0.9%` operational budget + funding 后 LIFO risk trim，把最坏值压到 `0.90%`、违规降为 0。
- **V2 仍未过冻结门禁**：最近 6m `-0.23%`，低于预先冻结的非负要求；最近 1y 为 `+11.32%`，120d rolling 正窗口为 `74.0%`。因此当前只能是 `explore / not promoted / not live-ready`，不能用“只差一点”绕过门禁。

## 1. 研究对象不是传统技术指标

Admission 只使用价格变化和历史价格波动：

```text
four_hour_move = log(close_UTC04 / close_UTC00)
past_rms = RMS(过去 720 个 1h log return)
scaled_impulse = abs(four_hour_move) / (past_rms * sqrt(4))
signal = scaled_impulse >= 1.0
direction = sign(four_hour_move)
```

没有 Donchian、均线、RSI、KDJ、MACD、布林带或 Keltner。它验证的问题很窄：**固定观察相位出现相对过去波动足够大的价格冲量后，能否通过真实试单和仓位生命周期拿到未来 3–14 天的右尾**。

## 2. 数据与执行口径

- ETH Binance USD-M perpetual `15m` closed bars：2019-11-27 07:45 UTC 至 2026-08-03 07:15 UTC，共 234,335 根。
- 15m 缺口 0、重复 0、critical null 0、OHLCV blocker 0；raw/normalized 数值差异 0。
- 聚合后完整 `1h` bar 58,583 根；信号在 closed bar 形成，下一根 open adverse fill。
- base：每次 fill fee `10bps` + slippage `4bps` + 实际 funding；stress 把 slippage 提高到 `8bps`。
- 每个 campaign 计划硬风险 `1%`，entry leverage cap `3x`；V2 实际最大有效杠杆只有 `0.41x`。

数据质量证据见 [ETH 刷新审计](../artifacts/eth_binance_15m_refresh_quality.json)，完整逐笔/metrics 见 [artifacts](../artifacts/README.md)。

## 3. 三个冻结候选分别证明了什么

| 候选 | 订单机制 | ETH base return | Sharpe | MDD | 主要失败 |
| --- | --- | ---: | ---: | ---: | --- |
| V0 | 首次信号即满额；`2R` 后回吐一半 MFE 则全平 | `+5.52%` | `0.13` | `-27.46%` | 6m、rolling、stress、MDD 全失败；过早全平右尾 |
| V1 | 25% probe；`0.5R/1R/2R` 加至 50%/75%/100%；回吐只减至 probe | `+53.93%` | `0.82` | `-11.64%` | 6m 失败；funding 令风险最坏漂至 `2.06%` |
| V2 | V1 + 0.9% operational budget + funding 后 LIFO risk trim | `+47.93%` | `0.82` | `-11.05%` | 风险已合格；6m `-0.23%` 仍失败 |

V0 → V1 的改善不是把 threshold 或传统指标调得更顺眼，而是改变了订单生命周期。V1 → V2 也不是收益优化，而是修复持仓期间风险预算没有持续维护的执行缺口。

## 4. V2 完整结果

### 4.1 资产与成本控制

| Asset | Gross | Base | Stress 8bps | Base Sharpe | Base MDD | Hard-risk violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ETH | `+86.72%` | `+47.93%` | `+43.54%` | `0.82` | `-11.05%` | 0 |
| BTC | `+30.28%` | `+8.30%` | `+4.10%` | `0.23` | `-11.01%` | 0 |
| HYPE | `+0.48%` | `-1.73%` | `-2.15%` | `-0.21` | `-5.56%` | 0 |
| SOL | `-1.46%` | `-7.09%` | `-8.49%` | `-0.64` | `-11.15%` | 0 |

HYPE 波动大并没有自动变成更稳定的趋势延续。当前证据支持 asset-specific 的 ETH campaign，不支持把同一参数扩到四币。

### 4.2 ETH 近期与滚动稳定性

| Slice | Return | Sharpe | MDD | Campaigns |
| --- | ---: | ---: | ---: | ---: |
| 1m | `-0.73%` | `-4.21` | `-0.92%` | 5 |
| 3m | `-0.80%` | `-0.89` | `-1.85%` | 14 |
| 6m | `-0.23%` | `-0.10` | `-3.73%` | 24 |
| 1y | `+11.32%` | `1.78` | `-3.91%` | 43 |

120d/30d rolling 有交易窗口的正收益比例为 `74.0%`。末端 3–6m 处在没有足够右尾覆盖试错成本的阶段，不能用调方向或放宽门禁事后修掉。

### 4.3 正偏与退出归因

- 273 个 closed campaigns，胜率 `30.4%`，profit factor `1.74`，平均 `+0.150R`，中位数 `-0.139R`，skew `3.67`。
- 53 个持有至 336h timeout 的 campaign 全部盈利，合计净 PnL `+1.087`；它们支付了其余失败试单的成本。
- 102 个 24h validation failure 合计 `-0.093`；118 个 stop exit 合计 `-0.515`。
- 最大 1/3/5 个赢家分别贡献总净 PnL 的 `18.9% / 52.1% / 76.3%`；前 10 个超过净总收益，说明大量小亏由少数大趋势覆盖。
- 独立 long arm base `+29.21%`，独立 short arm `-2.68%`。不能在已揭示历史后把 V2 改成 long-only；这是后续新证据需要回答的方向稳定性问题。

### 4.4 动态仓位与风险维护归因

| Variant | Return | Sharpe | MDD | Risk trims | Hard-risk violations | Worst stop-out loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V2 full | `+47.93%` | `0.82` | `-11.05%` | 718 | 0 | `0.90%` |
| probe-only | `+19.60%` | `0.70` | `-5.34%` | 0 | 0 | `0.66%` |
| maintenance, no 0.1% buffer | `+51.98%` | `0.82` | `-11.61%` | 701 | 0 | `1.00%` |
| 0.1% buffer, no maintenance | `+49.63%` | `0.82` | `-11.08%` | 0 | 1,309 bar-hours | `1.86%` |

所以 buffer 不能替代持续维护，持续维护也不能消除“下一次 funding 与执行误差”的运营缓冲。718 次 risk trim 是 6.7 年、273 个 campaign 内发生的细小风险维护动作，已经计入 fill fee；runner 若未来实现，必须支持同方向 partial resize、LIFO lot ledger、stop quantity 同步和重启恢复，不能用 flat-and-reopen 冒充。

## 5. V2 冻结门禁

| Gate | 实际 | 结果 |
| --- | ---: | --- |
| Base return > 0 | `+47.93%` | PASS |
| Sharpe > 0 | `0.82` | PASS |
| MDD > -20% | `-11.05%` | PASS |
| Campaigns >= 30 | 273 | PASS |
| 最近 6m >= 0 | `-0.23%` | **FAIL** |
| 120d rolling positive >= 60% | `74.0%` | PASS |
| Stress 8bps >= 0 | `+43.54%` | PASS |
| Hard risk violations = 0 | 0 | PASS |
| Effective leverage <= 3x | `0.41x` | PASS |
| Full return >= probe-only | `47.93% >= 19.60%` | PASS |

最低门禁不是多数票；任一硬项失败就不能进入 promotion review。

## 6. 理论问题与落地问题的最终拆分

1. **“用价格幅度和速度发现某种延续倾向”只在 ETH 的特定观察相位有历史证据，不是普适定律。** HYPE/SOL 失败、BTC 边际，说明标的和市场生态确实重要。
2. **“单点预测下一段趋势”仍未验证成高胜率问题。** 30% 胜率和负中位数意味着模型主要依赖廉价试错，而不是准确预言。
3. **“行情确认后加仓”得到真实 quantity 证据。** 它把 probe-only 的收益放大，同时保持优于一开始满仓的 Sharpe/MDD；这是本轮最实质的正结果。
4. **“尽量吃完整趋势”依赖保留 probe，而不是不断收紧 stop。** 盈利来自少数持满 14 天的 campaign；V0 的半 MFE 全平会破坏右尾。
5. **资金费和执行内核是策略本体，不是回测附注。** V1 在收益上看似成功，却因 funding 让 1% 变成 2.06%；V2 才把风险合同落到每根 bar。

## 7. 当前线上决定

- 不写 live spec，不接入或修改 quant-runner，不启动 dry-run/live。
- 原因不是“策略完全没用”，而是最近 6m 冻结门禁失败、V2 形成于 V1 全历史揭示之后，没有新的 prospective OOS；同时 runner 的同方向 partial resize、funding 后 risk trim 和 lot/stop parity 尚未完成。
- 禁止在当前已揭示历史上选择 long-only、改 6m 门禁、调 impulse threshold、减少 risk trim 或把 risk 提到 3%/10% 来救结果。
- 若继续推进，正确顺序是：用户明确登记冻结身份 → 锁定 2026-08-03 之后的新 prospective OOS → 到期一次性揭示 → 全部门禁通过后才写 live spec → runner 实现 resize/parity → dry-run。

## 8. 复现入口

- [V0 合同](../specs/binance-1h-pic-v0-contract-2026-08-03.md)
- [V1 合同](../specs/binance-1h-pic-v1-layered-contract-2026-08-03.md)
- [V2 风险不变量合同](../specs/binance-1h-pic-v2-risk-invariant-contract-2026-08-03.md)
- [脚本与命令](../scripts/README.md)
- [机器产物索引](../artifacts/README.md)
