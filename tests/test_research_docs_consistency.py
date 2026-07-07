"""研究文档一致性检查。

把 research/ 的索引更新义务、家族目录骨架和状态词约定变成可执行检查，
防止路由表与目录结构漂移（历史上 6h-rs4-regime-switch 曾建目录但未登记索引）。
规则来源：.cursor/rules/research-report-storage.mdc 与 research/strategy-status-glossary.md。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"

# 资产/主题目录：其下一级子目录被视为策略家族目录。
ASSET_DIRS = ["hype", "btc", "eth", "sol", "trx", "bnb", "asset-portfolios"]

# 扁平结构的 grandfathered 目录，不按 <asset>/<timeframe>-<family> 检查。
FLAT_GRANDFATHERED = {"mu"}

# 非家族的基础设施目录。
NON_FAMILY_DIRS = {"_shared-kernels"}

# 尚无 <family-id>-core-ledger.md 的家族（grandfathered 债务清单）。
# 只允许收缩：给家族补建 core ledger 后从这里删除对应条目。
# 有版本登记的家族新增到此清单属于违规（见 research-report-storage.mdc）。
GRANDFATHERED_NO_CORE_LEDGER = {
  "asset-portfolios/15m-multi-indicator-intraday",
  "asset-portfolios/1d-turtle-breakout",
  # 用 milestone-comparison 文件兼任主账。
  "hype/15m-candle-count-reversal",
  "hype/15m-pullback-trail",
  "hype/15m-riptide",
  "hype/1m-ema-crossover",
  "hype/1m-ma-pullback-scalp",
  "hype/5m-ma-pullback-scalp",
  # 诊断主题目录，非策略家族。
  "hype/cross-strategy-account",
}


def iter_family_dirs() -> list[tuple[str, Path]]:
  families: list[tuple[str, Path]] = []
  for asset in ASSET_DIRS:
    asset_dir = RESEARCH / asset
    assert asset_dir.is_dir(), f"缺少资产目录 research/{asset}/"
    for child in sorted(asset_dir.iterdir()):
      if not child.is_dir() or child.name.startswith(("__", ".")):
        continue
      families.append((f"{asset}/{child.name}", child))
  return families


def test_asset_dirs_have_readme() -> None:
  missing = [
    asset
    for asset in ASSET_DIRS + sorted(FLAT_GRANDFATHERED)
    if not (RESEARCH / asset / "README.md").is_file()
  ]
  assert not missing, f"资产目录缺少 README.md: {missing}"


def test_family_dirs_have_readme_and_decision_log() -> None:
  problems = []
  for key, family_dir in iter_family_dirs():
    if not (family_dir / "README.md").is_file():
      problems.append(f"{key}: 缺少 README.md")
    if not (family_dir / "decision-log.md").is_file():
      problems.append(f"{key}: 缺少 decision-log.md")
  assert not problems, "家族目录骨架不完整:\n" + "\n".join(problems)


def test_family_dirs_have_core_ledger_unless_grandfathered() -> None:
  problems = []
  for key, family_dir in iter_family_dirs():
    has_ledger = any(family_dir.glob("*core-ledger*.md"))
    if has_ledger and key in GRANDFATHERED_NO_CORE_LEDGER:
      problems.append(f"{key}: 已有 core ledger，请从 grandfathered 清单移除")
    if not has_ledger and key not in GRANDFATHERED_NO_CORE_LEDGER:
      problems.append(
        f"{key}: 缺少 <family-id>-core-ledger.md（若确属无版本登记的诊断线，"
        "在测试的 grandfathered 清单登记并说明）"
      )
  assert not problems, "core-ledger 覆盖检查失败:\n" + "\n".join(problems)


def test_families_registered_in_top_level_index() -> None:
  """索引更新义务：每个家族目录必须出现在 research/README.md 路由表中。"""
  index_text = (RESEARCH / "README.md").read_text(encoding="utf-8")
  missing = [
    key for key, _ in iter_family_dirs() if f"{key}/" not in index_text
  ]
  assert not missing, (
    "以下家族目录未登记进 research/README.md 路由表:\n" + "\n".join(missing)
  )


def test_families_registered_in_asset_index() -> None:
  problems = []
  for key, family_dir in iter_family_dirs():
    asset = key.split("/", 1)[0]
    asset_readme = (RESEARCH / asset / "README.md").read_text(encoding="utf-8")
    if family_dir.name not in asset_readme:
      problems.append(f"{key}: 未出现在 research/{asset}/README.md")
  assert not problems, "资产索引缺项:\n" + "\n".join(problems)


def test_top_level_index_links_resolve() -> None:
  """research/README.md 与 hype/README.md 中引用的仓库相对路径必须存在。"""
  problems = []
  for md, base in [
    (RESEARCH / "README.md", RESEARCH),
    (RESEARCH / "hype" / "README.md", RESEARCH / "hype"),
  ]:
    text = md.read_text(encoding="utf-8")
    for match in re.finditer(r"`([^`\s]+?\.md)`", text):
      rel = match.group(1)
      # 无目录成分的裸文件名（如泛指的 decision-log.md）不视为链接。
      if rel.startswith(("http", "/")) or "/" not in rel:
        continue
      if not (base / rel).resolve().exists():
        problems.append(f"{md.relative_to(ROOT)}: 引用不存在的文件 {rel}")
  assert not problems, "索引链接失效:\n" + "\n".join(problems)


def test_no_links_to_retired_reports_dir() -> None:
  """顶层 reports/ 已退役；research/ 文档不得再链接它（legacy-canvas 除外）。"""
  pattern = re.compile(r"\]\((?:\.\./)*reports/|\]\(/reports/")
  offenders = []
  for md in RESEARCH.rglob("*.md"):
    if "legacy-canvas" in md.parts:
      continue
    if pattern.search(md.read_text(encoding="utf-8")):
      offenders.append(str(md.relative_to(ROOT)))
  assert not offenders, "以下文档仍链接已退役的 reports/:\n" + "\n".join(offenders)


def test_shared_kernel_versions_are_frozen() -> None:
  """_shared-kernels 冻结版本目录的 SHA256 必须与 kernel README 登记值一致。"""
  import hashlib

  kernels_dir = RESEARCH / "_shared-kernels"
  assert (kernels_dir / "README.md").is_file()
  problems = []
  for kernel_dir in sorted(kernels_dir.iterdir()):
    if not kernel_dir.is_dir():
      continue
    readme = kernel_dir / "README.md"
    if not readme.is_file():
      problems.append(f"{kernel_dir.name}: 缺少 README.md")
      continue
    text = readme.read_text(encoding="utf-8")
    for version_dir in sorted(kernel_dir.glob("v*")):
      if not version_dir.is_dir():
        continue
      for engine in sorted(version_dir.glob("*.py")):
        digest = hashlib.sha256(engine.read_bytes()).hexdigest()
        if digest not in text:
          problems.append(
            f"{kernel_dir.name}/{version_dir.name}/{engine.name}: "
            f"实际 SHA256 {digest} 未在 kernel README 登记（冻结版本被改动或未登记）"
          )
  assert not problems, "共享内核冻结检查失败:\n" + "\n".join(problems)
