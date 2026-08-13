# BIN-1D-MA7-DSML P0 官方 Archive 容量诊断

## 结论

P0 在下载与建模前即被官方历史覆盖范围否决。Binance Vision 只有 BTC metrics 回溯到 `2020-09-01`；ETH/BNB/SOL/TRX 均从 `2021-12-01` 才开始。加入合同冻结的 30 日因果上下文和至少三个 leave-target-out peers 后，全部资产最早可用日都是 `2021-12-31`，LMML 的 1,448 个冻结事件最多只剩 967 个。

状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。未下载 metrics ZIP、未拟合模型、未读取 HYPE。

## 最大理论容量

- Usable events：`967/1,448 = 66.78%`，低于 `>=1,300` 与 `>=90%` 双门；
- BTC `202`、ETH `207`、BNB `178`、SOL `181`、TRX `199`，每资产 `>=200` 门失败；
- Long `502`、Short `465`，每方向 `>=550` 门失败；
- 四项 P0 容量门全部失败。

这不是本地同步遗漏：审计直接查询 Binance Vision 公共 S3 object listing，保留了每个 symbol 的首个 archive key、时间、ETag 与大小。继续下载约六千个日包不能增加不存在的 2021-12 前 altcoin metrics，也不能修复事件有效样本量。

## 决定

- 按合同停止 P1；不事后把 `1,300/200/550/90%` 降到能通过的数字。
- 不生成 source archive corpus、feature panel、OOF predictions 或 frozen model。
- 独立 derivatives information 本身尚未被证伪；被否决的是“把它附加到稀疏 LMML maturity events”这一采样设计。
- 下一机制改用同一信息源覆盖期内的**每日全锚点**，把可用样本从稀疏 maturity event 提升到约 `1,200d × 5 assets`；root/label/模型须另立合同，不能继承 DSML P1 门。

## 证据

- [P0/P1 数据与模型合同](../specs/binance-1d-ma7-dsml-p0-p1-contract-2026-08-10.md)
- [官方 archive 容量 JSON](../artifacts/p0_capacity_2026-08-10/p0_archive_capacity.json)
- [SHA256](../artifacts/p0_capacity_2026-08-10/p0_archive_capacity.sha256)
- [容量审计脚本](../scripts/audit_binance_1d_ma7_dsml_p0_capacity.py)
- [冻结 LMML 事件诊断](../../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
