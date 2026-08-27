# Decision Log

- 2026-08-27：建立全新独立 `HYPE-1D-MA7-Machine-Learning-Trend` P0 实验；冻结前 365 个完整 UTC 日为训练集、其后 81 日为一次性验证集，同时比较 ML、train-only MA 参数搜索、buy-and-hold，并将 exact V7.1 仅列为已揭示历史参考，不修改 V7.1。[冻结合同](specs/hype-1d-ma7-mlt-p0-365d-train-validation-contract-2026-08-27.md)
- 2026-08-27：P0 裁决 `ML_NO_EDGE`；训练内 `+204.34%` 的 `LGBM_B/H7/edge>0` 在锁定验证为 `-38.64%/-52.87%/PF 0.285`，弱于 train-only 规则 `-2.64%` 和买持 `+0.62%`。验证后不重选、不登记版本、不 promotion。[结果](diagnostics/hype-1d-ma7-mlt-p0-365d-train-validation-2026-08-27.md)
