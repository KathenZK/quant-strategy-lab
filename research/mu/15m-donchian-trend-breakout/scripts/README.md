# MU-15M-DTB 研究脚本

- [`research_mu_15m_dtb.py`](research_mu_15m_dtb.py)：`search` 只读取 train/validation 并冻结候选，`reveal` 校验哈希后一次性运行 final audit。

脚本只服务本家族；长期结论写入上级 Markdown，保留的 JSON/CSV 写入 [`../artifacts/`](../artifacts/README.md)。
