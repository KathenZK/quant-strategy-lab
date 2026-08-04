# Scripts

本目录只保存 `BIN-MTF-DSTC` 当前 Goal 的一次性数据审计、双状态账户引擎、消融、搜索、滚动验证和导出脚本。

所有脚本必须遵守：完整 closed bar、高周期 causal visibility、下一根 `15m open` 成交、真实 lot/fee/slippage/funding、stop gap 更差成交、逐 15m 与 bar 内 MDD、3x effective leverage 审计。

不得导入旧 `BIN-MTF-PTC` 的候选选择结果或读取 `HYPE-15M-MTPP` prospective OOS；若机械复用旧数据加载代码，必须只复用已审计 schema/normalization，不得继承旧参数或结论。
