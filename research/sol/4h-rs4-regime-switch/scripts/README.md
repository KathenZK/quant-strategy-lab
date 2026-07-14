# Scripts

- `research_sol_4h_rs4_search.py`：读取 SOL 最新两年 `1h` 标准数据并聚合为完整 `4h` K；运行 RS4 压缩 MACD v10 + 扩张 Donchian melt 小矩阵搜索、近期分片及 K+2/成本压力。

复现：

```bash
uv run python research/sol/4h-rs4-regime-switch/scripts/research_sol_4h_rs4_search.py
```

