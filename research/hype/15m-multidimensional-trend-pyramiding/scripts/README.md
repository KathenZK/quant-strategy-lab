# Scripts

- [research_hype_15m_mdtp.py](research_hype_15m_mdtp.py)：V35 冻结对照、三组新框架、成本阶梯、滚动时间测试、消融、参数/窗口稳定性、趋势分数组与跨币种固定参数诊断的统一复现入口。
- [audit_hype_15m_mdtp_failure.py](audit_hype_15m_mdtp_failure.py)：不选参的失败复审；修复 legacy raw parity，运行六币同窗口 gross/net、禁止增仓、成本盈亏平衡、动作换手与趋势持续性诊断。
- [research_hype_15m_mdtp_campaign_successor.py](research_hype_15m_mdtp_campaign_successor.py)：未登记 campaign successor 的冻结 Train 搜索与一次性 Validation；使用显式 quantity/equity ledger、`1% R0`、`3x cap`、离散分层、open-risk、MFE 50% floor、独立 long/short、成本压力、消融与 trade bootstrap。

运行：

```bash
uv run python research/hype/15m-multidimensional-trend-pyramiding/scripts/research_hype_15m_mdtp.py
uv run python research/hype/15m-multidimensional-trend-pyramiding/scripts/audit_hype_15m_mdtp_failure.py
uv run python research/hype/15m-multidimensional-trend-pyramiding/scripts/research_hype_15m_mdtp_campaign_successor.py
```

脚本固定 shared V35 kernel 的 SHA256；主 HYPE 数据未通过 raw/normalized 对拍时直接停止。复审入口对 legacy raw 文件按 canonical 路径限定数据集，并显式派生 `ts`/`vwap` 后逐行对拍；任一币种不通过时直接停止。
