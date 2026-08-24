# Scripts

- [`research_binance_1d_mcsm_long10.py`](research_binance_1d_mcsm_long10.py)：复用冻结的 Binance 日级缓存与月度横截面引擎，独立运行 Top10 long-only、Top3 control 和 BTC/ETH/全市场基准。
- [`research_binance_1d_mcsm_long_breadth.py`](research_binance_1d_mcsm_long_breadth.py)：在同一口径下运行全上市与 ADV 宇宙的 Top10/20/30/40/50 long-only，并输出动态共同窗口指标。
- [`research_binance_1d_mcsm_long10_risk_buffer.py`](research_binance_1d_mcsm_long10_risk_buffer.py)：按冻结合同运行 Top10 对照、20% 组合目标波动无杠杆版，以及 10/20 持仓缓冲版。
- [`research_binance_1d_mcsm_long10_positive_cash.py`](research_binance_1d_mcsm_long10_positive_cash.py)：只买 Top10 中形成收益严格大于0的名字，每槽10%，空缺持有现金，并与 target20 对照。
- [`research_binance_1d_mcsm_long10_liveability.py`](research_binance_1d_mcsm_long10_liveability.py)：冻结运行 BTC SMA200 市场风控、target12 风险预算、成本/延迟、时间 cohort、bootstrap、超额收益和容量诊断。
- [`research_binance_1d_mcsm_mh136_liveability.py`](research_binance_1d_mcsm_mh136_liveability.py)：冻结运行 1M/3M/6M 等资本袖套、逐袖消融、风险扰动、压力、bootstrap 和容量诊断。
- [`audit_binance_1d_mcsm_long10_target12_execution_timing.py`](audit_binance_1d_mcsm_long10_target12_execution_timing.py)：用真实 15m panel 审计 `00:15 UTC` 可成交入选、退出与持仓缺价；任一 blocker 存在即标记 `PERFORMANCE_INVALIDATED`。
- [`research_binance_1d_mcsm_money_effect_continuation.py`](research_binance_1d_mcsm_money_effect_continuation.py)：以真实 `00:15 UTC` 月度标签诊断 Binance 赚钱效应 breadth、市场中位数、leader spread、3M 延续、流动性/拥挤和冻结 2×2 状态，并输出收益捕获、衰减、cohort 与 post-reveal 消融。

```bash
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10.py --run-date 2026-08-18 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long_breadth.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long_breadth.py --run-date 2026-08-19 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_risk_buffer.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_risk_buffer.py --run-date 2026-08-19 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_positive_cash.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_positive_cash.py --run-date 2026-08-19 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_liveability.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_long10_liveability.py --run-date 2026-08-20 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_mh136_liveability.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_mh136_liveability.py --run-date 2026-08-20 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/audit_binance_1d_mcsm_long10_target12_execution_timing.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/audit_binance_1d_mcsm_long10_target12_execution_timing.py --run-date 2026-08-20 --force
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_money_effect_continuation.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-long10/scripts/research_binance_1d_mcsm_money_effect_continuation.py --run-date 2026-08-20 --force
```
