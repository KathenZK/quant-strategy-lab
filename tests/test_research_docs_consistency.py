"""研究文档一致性检查。

把 research/ 的索引更新义务、家族目录骨架和状态词约定变成可执行检查，
防止路由表与目录结构漂移（历史上 6h-rs4-regime-switch 曾建目录但未登记索引）。
规则来源：.cursor/rules/research-report-storage.mdc 与 docs/research-governance/strategy-status-glossary.md。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
GOVERNANCE_DOCS = ROOT / "docs" / "research-governance"

# 资产/主题目录：其下一级子目录被视为策略家族目录。
ASSET_DIRS = ["hype", "btc", "eth", "sol", "trx", "bnb", "asset-portfolios"]

# 扁平结构的 grandfathered 目录，不按 <asset>/<timeframe>-<family> 检查。
FLAT_GRANDFATHERED = {"mu"}

# 非家族的基础设施目录。
NON_FAMILY_DIRS = {"_shared-kernels"}


def _frontmatter(md: Path) -> dict:
  lines = md.read_text(encoding="utf-8").splitlines()
  if not lines or lines[0].strip() != "---":
    return {}
  try:
    end = lines.index("---", 1)
  except ValueError:
    return {}
  parsed = yaml.safe_load("\n".join(lines[1:end]))
  return parsed if isinstance(parsed, dict) else {}


def _schema_problems(instance: object, schema_path: Path) -> list[str]:
  schema = json.loads(schema_path.read_text(encoding="utf-8"))
  validator = Draft202012Validator(schema, format_checker=FormatChecker())
  return [
    f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
  ]

# 尚无 <family-id>-core-ledger.md 的家族（grandfathered 债务清单）。
# 只允许收缩：给家族补建 core ledger 后从这里删除对应条目。
# 有版本登记的家族新增到此清单属于违规（见 research-report-storage.mdc）。
GRANDFATHERED_NO_CORE_LEDGER = {
  # 未登记版本、由 README 临时承载路由与诊断结论的 portfolio 研究线。
  "asset-portfolios/15m-ema-cross-lightgbm-event-selector",
  "asset-portfolios/15m-multi-asset-trend-state-machine",
  "asset-portfolios/15m-multi-indicator-intraday",
  "asset-portfolios/1d-turtle-breakout",
  "asset-portfolios/1d-ema-cross-lightgbm-event-selector",
  "asset-portfolios/1d-ewmac-universal-trend",
  "asset-portfolios/1d-multi-asset-tsmom-vol-target",
  "asset-portfolios/1h-ema-cross-lightgbm-event-selector",
  "asset-portfolios/4h-ema-cross-lightgbm-event-selector",
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
    candidates = []
    for md in sorted(RESEARCH.rglob("*.md")):
        frontmatter = _frontmatter(md)
        named = "reproduction-spec" in md.name.lower()
        declared = frontmatter.get("document_type") == "external_reproduction_spec"
        if named or declared:
            candidates.append((md, frontmatter, named, declared))
    for md, frontmatter, named, declared in candidates:
        rel = str(md.relative_to(RESEARCH))
        lines = md.read_text(encoding="utf-8").splitlines()
        metadata_violations = []
        if not declared:
            metadata_violations.append(
                "缺少 front matter: document_type: external_reproduction_spec"
            )
        if not isinstance(frontmatter.get("intended_audience"), str) or not frontmatter.get(
            "intended_audience", ""
        ).strip():
            metadata_violations.append("缺少非空 intended_audience")
        if declared and not named:
            metadata_violations.append("用途已声明但文件名缺少 reproduction-spec")
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
        all_violations = metadata_violations + violations
        if all_violations and rel not in GRANDFATHERED_REPRO_SPECS:
            problems.append(
                f"{rel}: 外部复现规格声明/自包含不合规:\n"
                + "\n".join(all_violations[:8])
            )
        if not all_violations and rel in GRANDFATHERED_REPRO_SPECS:
            problems.append(f"{rel}: 已整改，请从 GRANDFATHERED_REPRO_SPECS 移除")
    assert not problems, "对外复现规格自包含检查失败:\n" + "\n".join(problems)


# 状态词校验：路由表状态列必须使用 strategy-status-glossary.md 的主状态词表。
_ALLOWED_MAIN_STATUS = (
  "explore",
  "registered",
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
        problems.append(f"{rel}:L{lineno}: 已废弃状态短语 {hit_phrases}: {cell}")
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


OVERLONG_CORE_LEDGER_CAPS = {
  "hype/15m-multi-indicator-intraday/hype-15m-mii-core-ledger.md": 509,
  "hype/15m-ema-crossover/hype-ema-x-core-ledger.md": 457,
  "hype/5m-pullback-trail/hype-5m-pullback-trail-core-ledger.md": 1181,
  "hype/15m-ema-trend-breakout/hype-ema-tb-core-ledger.md": 481,
  "btc/1h-adaptive-regime/btc-1h-ar-core-ledger.md": 205,
  "hype/1h-adaptive-regime/hype-1h-ar-core-ledger.md": 176,
  "hype/5m-event-quality-scoring/hype-5m-event-quality-scoring-core-ledger.md": 153,
}


def test_core_ledgers_respect_length_budget_or_shrink_only_cap() -> None:
  problems = []
  seen_allowlisted = set()
  for ledger in sorted(RESEARCH.rglob("*core-ledger*.md")):
    rel = str(ledger.relative_to(RESEARCH))
    line_count = len(ledger.read_text(encoding="utf-8").splitlines())
    cap = OVERLONG_CORE_LEDGER_CAPS.get(rel)
    if line_count > 150 and cap is None:
      problems.append(f"{rel}: {line_count} 行，超过新主账 150 行阈值")
    if cap is not None:
      seen_allowlisted.add(rel)
      if line_count > cap:
        problems.append(f"{rel}: {line_count} 行，超过历史 shrink-only cap {cap}")
      elif line_count <= 150:
        problems.append(f"{rel}: 已缩至 {line_count} 行，请从超长 allowlist 移除")
      else:
        warnings.warn(
          f"历史超长 core ledger 待压缩: {rel} ({line_count}/{cap})",
          UserWarning,
          stacklevel=1,
        )
  stale = set(OVERLONG_CORE_LEDGER_CAPS) - seen_allowlisted
  problems.extend(f"{rel}: allowlist 文件不存在，请移除" for rel in sorted(stale))
  assert not problems, "core ledger 长度检查失败:\n" + "\n".join(problems)


def test_live_specs_directories_are_not_empty() -> None:
  problems = []
  for live_specs in sorted(path for path in RESEARCH.rglob("live-specs") if path.is_dir()):
    specs = [
      md
      for md in live_specs.rglob("*.md")
      if md.name.lower() != "readme.md"
    ]
    if not specs:
      problems.append(str(live_specs.relative_to(ROOT)))
  assert not problems, "以下 live-specs/ 只有 README 或为空:\n" + "\n".join(problems)


def test_status_combinations_are_not_self_contradictory() -> None:
  problems = []
  status_docs = [RESEARCH / "README.md"]
  status_docs.extend(RESEARCH / asset / "README.md" for asset in ASSET_DIRS)
  status_docs.extend(family_dir / "README.md" for _, family_dir in iter_family_dirs())
  status_docs.extend(RESEARCH.rglob("*core-ledger*.md"))
  for md in dict.fromkeys(status_docs):
    status_lines = {
      lineno: cell for lineno, cell in _iter_status_cells(md)
    }
    for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
      is_current_status = bool(
        re.match(
          r"^\s*(?:[-*>]\s*)*(?:\*{0,2})?(?:current status|当前状态|status)\s*[:：]",
          line,
          re.IGNORECASE,
        )
      )
      if lineno not in status_lines and not is_current_status:
        continue
      status_text = status_lines.get(lineno, line)
      code_spans = re.findall(r"`([^`]+)`", status_text)
      for fragment in code_spans or [status_text]:
        lowered = fragment.lower()
        if "dry-run" in lowered and "not promoted" in lowered:
          problems.append(f"{md.relative_to(ROOT)}:L{lineno}: dry-run 与 not promoted 并存")
        if "dry-run" in lowered and "no-go" in lowered:
          problems.append(f"{md.relative_to(ROOT)}:L{lineno}: dry-run 与 NO-GO 并存")
        if "no-go" in lowered and "not promoted" in lowered:
          problems.append(f"{md.relative_to(ROOT)}:L{lineno}: NO-GO 与 not promoted 并存")
        if "no-go" in lowered and "not live-ready" in lowered:
          problems.append(f"{md.relative_to(ROOT)}:L{lineno}: NO-GO 与 not live-ready 并存")
        if "archived" in lowered and "not promoted" in lowered:
          problems.append(f"{md.relative_to(ROOT)}:L{lineno}: archived 与 not promoted 并存")
        if "archived" in lowered and "not live-ready" in lowered:
          problems.append(f"{md.relative_to(ROOT)}:L{lineno}: archived 与 not live-ready 并存")
  assert not problems, "发现非法状态组合:\n" + "\n".join(problems)


def test_lab_does_not_define_runtime_authority() -> None:
  forbidden = [
    GOVERNANCE_DOCS / "machine" / "active-strategy-manifest.json",
    GOVERNANCE_DOCS / "schemas" / "active-strategy-manifest.schema.json",
    GOVERNANCE_DOCS / "machine" / "external-runner-grandfathers.json",
    GOVERNANCE_DOCS / "schemas" / "external-runner-grandfathers.schema.json",
    ROOT / "scripts" / "governance" / "validate_manifest.py",
  ]
  existing = [path.relative_to(ROOT) for path in forbidden if path.exists()]
  assert not existing, (
    "运行与授权真源只允许存在于 quant-runner，Lab 不得恢复 active manifest: "
    f"{existing}"
  )


def test_governance_schemas_accept_canonical_contracts(tmp_path: Path) -> None:
  live_spec_schema = (
    GOVERNANCE_DOCS / "schemas" / "lab-live-spec-frontmatter.schema.json"
  )
  joint_frontmatter = {
    "schema_version": "1.0",
    "spec_role": "lab_handoff",
    "family_id": "EXAMPLE",
    "main_status": "dry-run",
    "spec_status": "active",
    "approval_level_max": "dry_run",
    "overlays": ["handoff"],
    "implementations": [
      {
        "strategy_id": "EXAMPLE-V1-A",
        "runner_kind": "example_a",
        "peer_spec": "crates/quant-runner/src/runner/strategies/example_a/A-SPEC.md",
      },
      {
        "strategy_id": "EXAMPLE-V1-B",
        "runner_kind": "example_b",
        "peer_spec": "crates/quant-runner/src/runner/strategies/example_b/B-SPEC.md",
      },
    ],
  }
  assert not _schema_problems(joint_frontmatter, live_spec_schema)
  joint_frontmatter["strategy_id"] = "AMBIGUOUS"
  assert _schema_problems(joint_frontmatter, live_spec_schema)

  sys.path.insert(0, str(ROOT))
  try:
    from scripts.governance.check_parity_report import _validate_report
    from scripts.governance.validate_live_specs import validate as validate_live_specs
  finally:
    sys.path.pop(0)

  sentinel_schema = tmp_path / "sentinel.schema.json"
  sentinel_schema.write_text(
    json.dumps({"type": "object", "required": ["schema_was_loaded"]}),
    encoding="utf-8",
  )
  assert any(
    "schema_was_loaded" in error
    for error in validate_live_specs(sentinel_schema)
  )
  parity_artifact = tmp_path / "parity.json"
  parity_artifact.write_text("{}", encoding="utf-8")
  assert any(
    "schema_was_loaded" in error
    for error in _validate_report(parity_artifact, sentinel_schema, [])
  )


def test_shared_kernel_index_and_copy_boundaries() -> None:
  kernels_dir = RESEARCH / "_shared-kernels"
  shared_index = (kernels_dir / "README.md").read_text(encoding="utf-8")
  top_index = (RESEARCH / "README.md").read_text(encoding="utf-8")
  problems = []
  kernel_hashes: dict[str, Path] = {}
  for kernel_dir in sorted(path for path in kernels_dir.iterdir() if path.is_dir()):
    if kernel_dir.name not in shared_index:
      problems.append(f"{kernel_dir.name}: 未登记在 _shared-kernels/README.md")
    if kernel_dir.name not in top_index:
      problems.append(f"{kernel_dir.name}: 未登记在 research/README.md")
    readme = kernel_dir / "README.md"
    if not readme.is_file():
      continue
    text = readme.read_text(encoding="utf-8")
    for version_dir in sorted(kernel_dir.glob("v*")):
      if version_dir.is_dir() and version_dir.name not in text:
        problems.append(f"{kernel_dir.name}/{version_dir.name}: 未登记在 kernel README")
      for engine in version_dir.glob("*.py"):
        kernel_hashes[hashlib.sha256(engine.read_bytes()).hexdigest()] = engine
  for script in sorted(RESEARCH.rglob("*.py")):
    if "_shared-kernels" in script.parts:
      continue
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    if digest in kernel_hashes:
      problems.append(
        f"{script.relative_to(ROOT)}: 复制了共享内核 "
        f"{kernel_hashes[digest].relative_to(ROOT)}，应 SHA pin 引用"
      )
  assert not problems, "共享内核索引/复制边界失败:\n" + "\n".join(problems)
