# Artifacts

本目录保存 V0/V1/V2 冻结脚本生成的机器可读数据质量、metrics、campaign、action、equity、rolling、slice、ablation 与风险审计证据。禁止手工修改生成文件。

- `binance_1h_pic_v0_*`：首次满额 + 半 MFE 全平基线及 shadow add。
- `binance_1h_pic_v1_*`：25% probe、真实分层 add、半回吐减至 probe；包含 funding 风险漂移失败证据。
- `binance_1h_pic_v2_*`：0.9% operational budget、funding 后 LIFO risk trim 与 1% hard-risk 审计。
- `eth_binance_15m_*`：ETH 官方 Binance closed-bar 刷新与数据质量证据。

叙事结论见 [V0–V2 初始研究报告](../diagnostics/binance-1h-pic-v0-v2-initial-research-2026-08-03.md)。
