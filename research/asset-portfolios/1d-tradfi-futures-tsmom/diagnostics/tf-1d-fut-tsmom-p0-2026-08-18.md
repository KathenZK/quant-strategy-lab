# TF-1D-FUT-TSMOM P0 多资产期货回测（2026-08-18）

- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 资产池：24 个连续期货，股票指数/债券/外汇/商品四类各 25% raw risk budget
- 主窗口：`2022-01-03T00:00:00+00:00` → `2026-07-31T00:00:00+00:00`
- 信号：月末 `sign(1M/3M/12M)`；下一交易日生效；Composite 等权
- 风险：资产与组合两层 60-day COM EWMA；组合目标 10%；gross cap 3x
- 成本：0 bps 对照 + 2 bps 单边目标权重换手；未单列 roll cost

## 结论

Composite 含成本 CAGR `2.25%`、Sharpe `0.286`、最大回撤 `-19.18%`、净总收益 `10.70%`。
Long-only risk parity 同口径 CAGR `0.96%`、Sharpe `0.145`、最大回撤 `-22.57%`。

## 四分支与基准（2 bps）

| 分支 | CAGR | 年化收益 | 年化波动 | Sharpe | Sortino | MDD | Calmar | 正收益月 | 年换手 | 毛总收益 | 净总收益 | 平均gross |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1M` | -0.72% | -0.24% | 9.84% | -0.025 | -0.035 | -17.58% | -0.041 | 47.27% | 31.798 | -0.41% | -3.26% | 2.544 |
| `3M` | -0.32% | 0.15% | 9.67% | 0.015 | 0.021 | -24.39% | -0.013 | 50.91% | 18.909 | 0.27% | -1.45% | 2.547 |
| `12M` | 5.14% | 5.39% | 8.73% | 0.618 | 0.876 | -14.30% | 0.359 | 61.82% | 11.960 | 27.11% | 25.73% | 2.595 |
| `Composite` | 2.25% | 2.66% | 9.27% | 0.286 | 0.405 | -19.18% | 0.117 | 54.55% | 22.853 | 13.04% | 10.70% | 2.194 |
| `Long-only RP` | 0.96% | 1.47% | 10.16% | 0.145 | 0.204 | -22.57% | 0.042 | 60.00% | 2.484 | 4.70% | 4.46% | 2.164 |

## Composite 类别累计净贡献（return points）

| 类别 | 净贡献 |
| --- | ---: |
| `equity_index` | 5.00% |
| `commodity` | 3.40% |
| `bond` | 2.79% |
| `fx` | 0.93% |

## Composite 市场累计净贡献（return points）

| 市场 | 类别 | 净贡献 | 换手 |
| --- | --- | ---: | ---: |
| `GC=F` | `commodity` | 3.79% | 1.525 |
| `ZT=F` | `bond` | 2.97% | 25.404 |
| `NKD=F` | `equity_index` | 2.92% | 2.334 |
| `NQ=F` | `equity_index` | 2.77% | 1.561 |
| `ES=F` | `equity_index` | 2.24% | 2.530 |
| `SI=F` | `commodity` | 1.76% | 0.871 |
| `6J=F` | `fx` | 1.52% | 3.418 |
| `6S=F` | `fx` | 0.92% | 4.743 |
| `ZC=F` | `commodity` | 0.69% | 1.188 |
| `UB=F` | `bond` | 0.57% | 2.812 |
| `HG=F` | `commodity` | 0.47% | 1.159 |
| `YM=F` | `equity_index` | 0.45% | 3.014 |
| `6B=F` | `fx` | 0.20% | 5.781 |
| `ZF=F` | `bond` | 0.08% | 12.387 |
| `BZ=F` | `commodity` | 0.03% | 0.798 |
| `6E=F` | `fx` | -0.09% | 5.445 |
| `ZN=F` | `bond` | -0.31% | 8.159 |
| `ZS=F` | `commodity` | -0.45% | 1.505 |
| `ZB=F` | `bond` | -0.52% | 3.643 |
| `6A=F` | `fx` | -0.57% | 4.235 |
| `6C=F` | `fx` | -1.05% | 8.179 |
| `NG=F` | `commodity` | -1.35% | 0.340 |
| `ZW=F` | `commodity` | -1.54% | 0.989 |
| `RTY=F` | `equity_index` | -3.37% | 2.466 |

## Composite vs Long-only 分年

| 年 | Composite | Long-only RP |
| --- | ---: | ---: |
| `2022` | 15.85% | -19.09% |
| `2023` | -5.76% | 7.63% |
| `2024` | -4.45% | -0.13% |
| `2025` | 6.63% | 17.68% |
| `2026` | -0.47% | 2.07% |

## 数据与结论边界

Yahoo 连续代码未披露逐合约 roll mapping；本轮没有官方结算价、合约乘数和显式换月成本。因此 P0 只能判断 2022–2026 公开连续序列上的组合形态，不能登记版本或声称严格复刻期货总收益。

## 证据

- [数据审计](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-data-audit.json)
- [固定配置](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-config.json)
- [完整指标](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-metrics.csv)
- [组合日路径](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-portfolio-paths.csv)
- [市场贡献](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-market-contributions.csv)
- [类别年度贡献](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-class-year-contributions.csv)
- [交互图](../artifacts/tf-1d-fut-tsmom-p0-2026-08-18-interactive.html)
