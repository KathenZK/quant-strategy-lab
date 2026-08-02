# Scripts

- [research_hype_15m_mdtp.py](research_hype_15m_mdtp.py)：V35 冻结对照、三组新框架、成本阶梯、滚动时间测试、消融、参数/窗口稳定性、趋势分数组与跨币种固定参数诊断的统一复现入口。

运行：

```bash
uv run python research/hype/15m-multidimensional-trend-pyramiding/scripts/research_hype_15m_mdtp.py
```

脚本固定 shared V35 kernel 的 SHA256；主 HYPE 数据未通过 raw/normalized 对拍时直接停止。跨币种 raw schema 不可审计的结果只标为 `explore / untrusted`。

