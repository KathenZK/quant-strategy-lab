"""HYPE 1h adaptive-regime 搜索入口。

真实实现冻结在共享 kernel v1；本文件只负责 SHA256 pin、动态加载和兼容性导出，
避免家族目录继续保存整文件副本。
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ENGINE_PATH = (
    ROOT / "research/_shared-kernels/1h-adaptive-regime-search/v1/engine.py"
)
ENGINE_SHA256 = "0420ea44854201e17d4bf5b9142fb8335d143e78772656473a1dcf4594a5f04c"
_MODULE_NAME = "_hype_1h_adaptive_regime_search_kernel_v1"


def _load_engine():
    actual = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if actual != ENGINE_SHA256:
        raise RuntimeError(
            "1h-adaptive-regime-search v1 SHA mismatch: "
            f"expected {ENGINE_SHA256}, got {actual}"
        )
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_ENGINE = _load_engine()

# 兼容历史消费者：继续从本模块导入共享引擎的公开/内部研究符号。
for _name in dir(_ENGINE):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_ENGINE, _name)


if __name__ == "__main__":
    _ENGINE.main()
