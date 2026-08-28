# Historical Nasdaq-100 Membership 来源与重建说明

## 结论

本次已建立 2010-01-04 至 2026-08-21 的 session-level point-in-time membership：4,184 个 XNAS sessions、252 个历史 ticker、247 个冻结 entity lineage。反向重建的最后快照与 revision-pinned 当前成分表完全一致，规则完整性 finding 为 0。

这份 membership 足以复现研究管线，但仍是 `provisional_point_in_time_reconstruction`：完整变更索引来自带行级引用的 revision-pinned Wikipedia 表，不是 Nasdaq 授权的 constituent-history feed。首次解析时研究期 200 条变更中有 7 条未附引用；P0 又逐条补入 Nasdaq 或 SEC 原始证据，因此最终为 `142 primary_official / 58 secondary_cited / 0 uncited_secondary_index`。source augmentation 只补 URL，不改变事件日期或成分集合。

## 冻结来源

- Historical change index：`Historical_components_of_the_Nasdaq-100`，revision `1368915149`，UTC `2026-08-11T20:50:52Z`。
- Current terminal snapshot：`List_of_NASDAQ-100_companies`，revision `1368915166`，UTC `2026-08-11T20:51:02Z`。
- 本地原文、revision、SHA256 与 CC BY-SA attribution 保存在 [`../artifacts/membership-sources/`](../artifacts/membership-sources/)。
- 变更表每行解析有效日期、added/removed ticker、原因、URL，并按官方域名分层。

## 重建算法

1. 从冻结的当前证券集合开始，按有效日倒序撤销 additions/deletions，得到每个变更日之前的集合。
2. 公司更名不建立新经济实体；`FB→META`、`PCLN→BKNG`、`HANS→MNST`、`KFT→MDLZ`、`CTRP→TCOM`、`WLTW→WTW`、`WFMI→WFM`、`NWSA→FOXA` 等由冻结 alias 映射延续 entity。
3. 相同 ticker 表示不同 share-class generation 时强制断开：`GOOG` 2014 class split、`FOX/FOXA` 2019 新旧公司边界。
4. 将变更有效日投影到 XNAS session；默认在公告有效日开盘前生效。若来源明确前一日收盘后停止交易，则在下一 session 移除。
5. 生成 snapshot、interval 与 session-level parquet；每日行数可超过 100，因为指数按 100 家非金融公司定义，多重合资格 share classes 可以同时存在。

## 手工公司行动修正

- 2014-12-22 官方 Nasdaq notice 加入的是 `CMCSK`，不是 secondary table 记录的 `CMCSA`。
- `CMCSK` 于 2015-12-11 收盘后停止交易并转为既有 `CMCSA`，因此 2015-12-14 起移除；这是转换，不是新增 CMCSA entity。
- 2015-11-11 旧 Broadcom 移除 ticker 应为 `BRCM`；`AVGO` 当时仍在指数。
- 2016-02-01 的 Broadcom Ltd 名称变更行不是一次 `+AVGO` membership addition，已作为纯公司行动丢弃。

全部修正规则、来源 URL 与原因位于 [`../configs/ndx100-membership-overrides.json`](../configs/ndx100-membership-overrides.json)，不会隐藏在代码中。

## Massive 执行前的最终标识门禁

membership ticker 不是最终 price join identity。价格运行时必须：

- 对每个 interval 首尾日期查询 Massive ticker details；
- 保存 composite/share-class FIGI、CIK、交易所、active 状态；
- 查询 ticker-events 并验证 rename lineage；
- 对 `GOOG`、`FOX`、`FOXA` 这类 same-symbol generations 验证 FIGI 不混用；
- 已退市或历史 ticker 查不到 point-in-time details 时阻塞，不得换成当前 ticker 或填零。

复现：

```bash
.venv/bin/python research/us-indexes/1d-nasdaq100-ma7-regime-continuation/scripts/reconstruct_ndx100_membership.py --build --force
```
