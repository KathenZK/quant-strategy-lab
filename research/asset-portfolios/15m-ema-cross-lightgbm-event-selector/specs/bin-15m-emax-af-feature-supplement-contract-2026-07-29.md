# BIN-15M-EMAX A/F 特征增补契约：持仓数据 + 现有数据新表达 → 15m 极限终判

> 跑数前冻结。动机：a2 证明补真实缺口有效但收益递减；用户决定把剩余两族可行特征（A 衍生品持仓、F 现有数据新表达）补满，作为 15m 刻度的极限测试；若仍不过门，则把同一选择器框架移植到 1h/4h。家族维持 `archived`，2026H1 不使用。

## 不变项

- 事件、标签、成本、trading pool、权重、LightGBM 超参、2022–2025 扩窗 purged 年度 OOF：与主消融/a2 完全一致；标签 `b4_2_net_atr` 回归。
- 判定沿用 Gate A（十分位 Spearman > 0.8）+ Gate B（顶桶合并净 ATR > 0 且 ≥3/4 年为正）。

## F 族（现有 15m K 线新表达，5 个，信号 K 收盘可知）

| 特征 | 定义 | 对齐 |
|---|---|---|
| `ret_8640` | 过去 90 天收益 ÷ `atr_frac`（不足 90 天缺失） | 是 |
| `donchian_pos_90d` | 收盘在 90 天高低区间位置（0–1，min 45 天） | 否 |
| `vwap_dist_30d` | 收盘 − 30 天滚动 VWAP（`hlc3` 按 `volume` 加权）÷ ATR | 是 |
| `vp_pos_30d` | 过去 30 天成交量中，成交在当前价下方的占比（量价分布位置，0–1，min 15 天） | 否 |
| `vp_hvn_dist_30d` | 收盘 − 30 天量价分布最大密集区中心（50 bins）÷ ATR | 是 |

## A 族（Binance Vision USDM daily metrics，5m 粒度，8 个）

- 数据：`data/futures/um/daily/metrics/<SYMBOL>/`，2020-09 起；范围化同步 pool 内 570 币 × 上市日 ≤ 2025-12-31，落 `data/normalized/derivatives_metrics/`。本轮为 **explore 级**接入：保留 raw 值与同步质检计数，未做全量湖审计前 A 特征结论不得单独引用为策略证据。
- 取值口径：信号 K 收盘时点 as-of 最近一条 metrics（陈旧容忍 6h，超时缺失）；全部 raw，不做方向对齐（模型自行与 `side` 交互）。
- 特征：`oi_chg_24h` / `oi_chg_3d` / `oi_chg_7d`（`sum_open_interest` 百分比变化）、`oi_value_to_adv`（OI 名义 ÷ `adv_30d`）、`ls_top_pos`（大户持仓多空比）、`ls_top_acct`（大户账户多空比）、`ls_global_acct`（全体账户多空比）、`taker_ls_vol`（taker 买卖量比）。
- 覆盖披露义务：报告 A 特征逐特征缺失率与按年覆盖率（metrics 历史晚于部分事件属预期）。

## 预注册判定与后续路径

1. 两步跑：`local+trend+F`（F 单独增量）→ `local+trend+F+A`（15m 极限）。
2. 任一变体过双门 → 15m 结论修订，重开研究线评估。
3. 均不过 → 15m 极限终判成立：局部信息 + 持仓信息合计仍低于成本墙，15m 关闭；按用户指令把同一选择器框架移植到 1h/4h（各自新开契约）。

产物落 `artifacts/af_supplement/`。
