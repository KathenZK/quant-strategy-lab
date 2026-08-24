# Scripts

- `fetch_tradfi_futures_yahoo.py`：获取冻结 24 市场并写入统一 raw 数据湖。
- `run_tradfi_futures_tsmom.py`：运行四个 TSMOM 分支和 Long-only risk parity。
- `run_tradfi_tsmom_proxy_validation.py`：在冻结 30 个 ETF/FX 代理上运行同规则长期验证；
  只作机制诊断，不是期货证据。
- `render_tradfi_futures_tsmom.py`：生成自包含交互权益、年度收益和类别贡献图。
- `extract_aqr_tsmom_workbooks.py`：用 Codex bundled Python 从AQR官方工作簿提取冻结CSV并
  固化哈希；该脚本需要工作区 spreadsheet runtime。
- `run_mop2012_exact_replication.py`：审计作者/AQR月度因子，并在24期货与30代理上运行
  `12M sign × 40%/sigma × 全市场等权` 论文公式。
