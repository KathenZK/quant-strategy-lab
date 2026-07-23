# HYPE-15M-MMTF-V1 原始基线规格

## 身份与状态

- Family：`HYPE-15M-Multi-Mechanism-Trend-Following`
- Version：`HYPE-15M-MMTF-V1`
- 状态：`registered / not promoted / not live-ready`
- 角色：锁定 OOS 之前的原始基线，用于后续全接线消融；不代表达到最终目标。
- Config SHA256：`c5cb54034739eafc245afff052eb4337eba6168ab38aa19d192f93c9acdab70f`

## 冻结参数

| 字段 | 值 |
| --- | ---: |
| mechanism | `keltner_breakout` |
| direction | `both` |
| EMA fast / slow | `24 / 384` |
| ATR | `14` |
| ADX14 min | `26` |
| RVOL96 min | `1.0` |
| Keltner distance | `1.25 ATR14` from EMA384 |
| hard stop | `6.0 ATR14` |
| take profit | `0.75 ATR14` |
| trailing activation / distance | `1.0 / 2.0 ATR14` |
| breakeven trigger | `1.0 ATR14` |
| max hold | `24` bars |
| cooldown | `0` bars |
| trend exit | `false` |
| leverage | `2.0x` |

`entry_window=144`、`exit_window=16`、`breakout_atr=0.2` 仍保留在原始搜索表面，但按 Keltner/trend-exit-off 接线预计为 dormant；必须由 V1 消融的 trade signature 验证后才能删除。

## 信号与执行

1. 在闭合 bar `t` 计算 EMA24、EMA384、ATR14、ADX14 和 RVOL96；所有 rolling 指标只使用 `t` 及以前数据。
2. Long：close 从下向上穿过 `EMA384 + 1.25*ATR14`，且 `EMA24>EMA384`、`ADX14>=26`、`RVOL96>=1.0`。
3. Short：close 从上向下穿过 `EMA384 - 1.25*ATR14`，且 `EMA24<EMA384`、`ADX14>=26`、`RVOL96>=1.0`。
4. 无持仓时在下一根 bar `t+1` open 以 `4 bps` 不利滑点成交；每次 fill 收取成交名义价值 `0.001` fee。
5. 入场 ATR 固定 hard stop 与 TP；同 K 同时触及时 stop-first。gap 穿 stop 使用该 bar open，stop 不使用陈旧价格。
6. favorable excursion 到 `1 ATR` 后启用 trailing 候选并把 stop 推至 breakeven；因 trailing distance `2 ATR`，breakeven 可能先成为更紧保护线。
7. 持仓达到 `24` bars 后，下一根 open timeout 平仓；持仓期间按方向和实际 funding timestamp 计费。
8. 单净仓、不重叠；退出后没有额外 cooldown。

## 冻结证据

- [V1 广搜报告](../diagnostics/hype-15m-mmtf-v1-broad-search-2026-07-22.md)
- [V1 machine freeze](../artifacts/hype_15m_mmtf_v1_search_2026-07-22.json)

