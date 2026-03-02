"""应用级 package: 暂存 runner/cli/registrar 的导出，便于兼容导入。
"""
from .runner import run_batch  # re-export
from .cli import main as main

__all__ = ["run_batch", "main"]
