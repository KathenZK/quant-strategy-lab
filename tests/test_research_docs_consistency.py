"""研究文档一致性检查。

把 research/ 的索引更新义务、家族目录骨架和状态词约定变成可执行检查，
防止路由表与目录结构漂移（历史上 6h-rs4-regime-switch 曾建目录但未登记索引）。
规则来源：.cursor/rules/research-report-storage.mdc 与 docs/research-governance/strategy-status-glossary.md。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
GOVERNANCE_DOCS = ROOT / "docs" / "research-governance"

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
  "asset-portfolios/hype-cross-strategy-account",
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


def test_core_ledger_template_defines_required_sections() -> None:
  template = GOVERNANCE_DOCS / "core-ledger-template.md"
  assert template.is_file(), "缺少 docs/research-governance/core-ledger-template.md"
  text = template.read_text(encoding="utf-8")
  required_headings = [
    "## Family Identity",
    "## Current State",
    "## Version Rules",
    "## Version Table",
    "## Shared Assumptions",
    "## Evidence Map",
    "## What Not To Put Here",
  ]
  missing = [heading for heading in required_headings if heading not in text]
  assert not missing, "core-ledger-template.md 缺少标准章节:\n" + "\n".join(missing)


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
  """research/README.md 与 hype/README.md 中引用的仓库相对路径必须存在。

  同时校验反引号路径和 Markdown 链接（clickable-file-references.mdc 要求
  路由表使用可点击链接，链接失效同样属于索引漂移）。
  """
  problems = []
  index_files = [(RESEARCH / "README.md", RESEARCH)]
  for asset in ASSET_DIRS + sorted(FLAT_GRANDFATHERED):
    index_files.append((RESEARCH / asset / "README.md", RESEARCH / asset))
  for md, base in index_files:
    text = md.read_text(encoding="utf-8")
    refs = [m.group(1) for m in re.finditer(r"`([^`\s]+?\.md)`", text)]
    refs += [m.group(1) for m in re.finditer(r"\]\(([^)\s]+?\.md)\)", text)]
    for rel in refs:
      # 无目录成分的裸反引号文件名（如泛指的 decision-log.md）不视为链接；
      # Markdown 链接则总是校验。
      if rel.startswith(("http", "/")):
        continue
      if "/" not in rel and f"`{rel}`" in text and f"]({rel})" not in text:
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


# 对外复现规格的存量整改清单：这两份写于 external-reproduction-spec 规则之前。
# 只允许收缩：把仓库内部引用移入"非复现依赖"附录后，从这里删除对应条目。
GRANDFATHERED_REPRO_SPECS = {
    "asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/specs/"
    "binance-1h-ar-mae-v1-full-reproduction-spec-2026-07-07.md",
    "hype/15m-multi-indicator-intraday/live-specs/"
    "hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md",
}

# 附录标题必须含此标记，其后的仓库内部引用才被允许。
_REPRO_APPENDIX_MARKER = "非复现依赖"
_REPRO_INTERNAL_REF = re.compile(
    r"(?:research|scripts|artifacts)/[A-Za-z0-9_\-./]+\.(?:py|json|csv|md|html|parquet)"
    r"|/Users/ZK"
    r"|uv run"
)


def test_external_reproduction_specs_are_self_contained() -> None:
    """对外复现规格必须自包含：仓库内部引用只能出现在"非复现依赖"附录之后。

    规则来源：.cursor/rules/external-reproduction-spec.mdc。同事只会拿到这一个
    Markdown 文件，正文里引用仓库脚本/产物/绝对路径都会让复现在仓库外失败。
    """
    problems = []
    for md in sorted(RESEARCH.rglob("*reproduction-spec*.md")):
        rel = str(md.relative_to(RESEARCH))
        lines = md.read_text(encoding="utf-8").splitlines()
        appendix_start = next(
            (
                i
                for i, line in enumerate(lines)
                if line.startswith("#") and _REPRO_APPENDIX_MARKER in line
            ),
            len(lines),
        )
        violations = [
            f"  L{i + 1}: {line.strip()[:100]}"
            for i, line in enumerate(lines[:appendix_start])
            if _REPRO_INTERNAL_REF.search(line)
        ]
        if violations and rel not in GRANDFATHERED_REPRO_SPECS:
            problems.append(
                f"{rel}: 正文含仓库内部引用（应移入'{_REPRO_APPENDIX_MARKER}'附录）:\n"
                + "\n".join(violations[:8])
            )
        if not violations and rel in GRANDFATHERED_REPRO_SPECS:
            problems.append(f"{rel}: 已整改，请从 GRANDFATHERED_REPRO_SPECS 移除")
    assert not problems, "对外复现规格自包含检查失败:\n" + "\n".join(problems)


# 状态词校验：路由表状态列必须使用 strategy-status-glossary.md 的主状态词表。
_ALLOWED_MAIN_STATUS = (
  "explore",
  "registered",
  "audit",
  "live spec",
  "dry-run",
  "live",
  "NO-GO",
  "archived",
)
# 已废弃/禁止的状态词（见 glossary：paper-live 无此阶段，candidate 只能作研究角色词）。
_FORBIDDEN_STATUS_TOKENS = ("paper-live", "sim-paper", "blocked")
_FORBIDDEN_STATUS_PHRASES = (
  "audit / not promoted",
  "audit only",
  "live candidate",
  "dry-run candidate",
  "promotion candidate",
)


def _iter_status_cells(md: Path):
  """遍历 Markdown 表格中"状态"列的单元格，返回 (行号, 内容)。"""
  status_col = None
  for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
    stripped = line.strip()
    if not stripped.startswith("|"):
      status_col = None
      continue
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if "状态" in cells:
      status_col = cells.index("状态")
      continue
    if status_col is None or set(stripped) <= {"|", "-", " ", ":"}:
      continue
    if len(cells) > status_col:
      yield lineno, cells[status_col]


def test_routing_table_status_labels_use_glossary_vocabulary() -> None:
  """research/README.md 与 hype/README.md 路由表状态列只能用 glossary 主状态词。"""
  problems = []
  for md in [RESEARCH / "README.md", RESEARCH / "hype" / "README.md"]:
    for lineno, cell in _iter_status_cells(md):
      rel = md.relative_to(ROOT)
      lowered = cell.lower()
      hit_forbidden = [t for t in _FORBIDDEN_STATUS_TOKENS if t in lowered]
      if hit_forbidden:
        problems.append(f"{rel}:L{lineno}: 状态含已废弃词 {hit_forbidden}: {cell}")
      hit_phrases = [p for p in _FORBIDDEN_STATUS_PHRASES if p in lowered]
      if hit_phrases:
        problems.append(f"{rel}:L{lineno}: audit gate 失败后应回到 registered/explore: {hit_phrases}: {cell}")
      # "live-ready" 属于修饰词后缀，不算主状态 `live` 命中。
      cleaned = re.sub(r"live-ready", "", lowered)
      if not any(
        re.search(rf"\b{re.escape(s.lower())}\b", cleaned)
        for s in _ALLOWED_MAIN_STATUS
      ):
        problems.append(f"{rel}:L{lineno}: 状态未包含任何 glossary 主状态词: {cell}")
  assert not problems, "路由表状态词校验失败:\n" + "\n".join(problems)


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
