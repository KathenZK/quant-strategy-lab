# Spot CTA 回测诊断

> 迁移说明：本文由 legacy Cursor Canvas `spot-cta-diagnosis.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：Platform / generic experiment Canvas。

样本为 Binance spot 1h，本地数据区间 2026-01-30 至 2026-05-06，共 2,286 根小时 K。 本次重点不是单看最终收益，而是拆开信号、universe、换手和成本。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| trend 默认净收益 | -99.1% |
| pump 默认净收益 | -83.7% |
| 每 1.0 换手成本 | 0.4% |
| 默认全市场标的数 | 422 |

### 关键问题 >结论摘要

默认回测入口用了 422 个现货标的、空 strategy_params、min_dollar_volume=0 和 min_history_bars=1。 这不是配置文件里的“主流币趋势 CTA”，而是全市场小币追涨测试。

trend 的 gross equity 不计成本仍是 -31.4%，但净值跌到 -99.1% 的主要放大器是成本： 总换手 1,071.7，按 40bps 计，累计交易成本约 428.7%。

pump 的问题更偏信号本身：实际入场后 24h 平均收益 -3.59%，72h 平均收益 -4.96%，说明短线 pump 信号在当前样本里更像买到冲高回落。

## 默认回测拆解

| 策略 | 净收益 | 不计成本收益 | 累计成本 | 平均小时换手 | 交易事件 | 入场后表现 |
| --- | --- | --- | --- | --- | --- | --- |
| trend default / 422 symbols | -99.1% | -31.4% | 428.7% | 46.9% | 15,310 | Entry +24h avg -0.43% |
| pump default / 422 symbols | -83.7% | -73.4% | 48.9% | 5.35% | 1,019 | Entry +24h avg -3.59% |

## 信号是否真的捕捉上涨

| 事件 | +1h 均值 | +24h 均值 | +72h 均值 | +72h 胜率 |
| --- | --- | --- | --- | --- |
| trend positive signal | -0.03% | -0.26% | -0.92% | 36.0% |
| trend actual entry | -0.08% | -0.43% | -0.67% | 37.0% |
| pump positive signal | -0.23% | -1.52% | -2.35% | 31.8% |
| pump actual entry | -0.87% | -3.59% | -4.96% | 27.1% |

## 快速优化对照

| 变体 | 净收益 | Gross sum | 成本 | 平均换手 | 解读 |
| --- | --- | --- | --- | --- | --- |
| trend config / 10 symbols / signal-loss exit | -10.7% | +0.06% | 11.3% | 1.65% | Low exposure, cost dominates |
| trend config / 10 symbols / hold until risk exit | -36.3% | +0.85% | 45.2% | 6.58% | More exposure, more cost |
| trend config / 10 symbols / concentrated | -17.1% | -2.32% | 16.3% | 2.38% | Lower exposure helps but alpha weak |
| trend liquid filter / 5 symbols | -2.48% | +2.71% | 5.21% | 0.76% | Gross positive, net killed by cost |
| pump config / 11 symbols | -12.5% | -9.33% | 3.84% | 0.42% | Signal still negative |
| pump stricter / 11 symbols | -2.69% | -1.76% | 0.96% | 0.10% | Less damage, very low activity |
| pump liquid strict / 5 symbols | -0.95% | +1.03% | 1.97% | 0.22% | Closest to viable in this sample |

## 优先优化方向

先修评估入口：不要用空参数全市场回测代表策略，应默认用 workflow config，或至少要求流动性、历史长度和明确 strategy_params。

trend 应拆成“突破入场”和“趋势持有”两个状态。不要让 fresh breakout 缺失直接触发离场，否则趋势策略会变成高换手追涨。

pump 需要重新定义为短线 continuation，而不是单纯涨幅加放量。建议加入更严格的突破确认、过热过滤和 6-12h 快速退出。

### 下一步 >实验顺序

1. 补 4h/1d 数据，按 trend 原配置重跑，不要用 1h 代替中周期趋势。

2. 用 top liquid universe 做 walk-forward 参数扫描。

3. 对 trend 增加状态型持仓退出，对 pump 做更短持仓和更强过滤。

4. 单独输出 cost sensitivity：0bps、10bps、25bps、40bps。
