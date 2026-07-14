# Scripts

- `fetch_sol_1h_vcb_data.py`：复用冻结抓取/归一化内核，刷新 Binance `SOLUSDT` perpetual 最近两年闭合 `1h` K、funding 和合约快照，并写入本 family 独立 artifacts。
- `research_sol_1h_vcb_search.py`：多 K 压缩区间 arm、突破确认、fixed/trailing exit、fixed/risk sizing 扩展搜索；选择只使用 train/validation/prefit。

从仓库根目录运行：

```bash
uv run python research/sol/1h-volatility-compression-breakout/scripts/fetch_sol_1h_vcb_data.py
uv run python research/sol/1h-volatility-compression-breakout/scripts/research_sol_1h_vcb_search.py --entry-configs 3000 --exits-per-entry 16 --keep 1000
```

