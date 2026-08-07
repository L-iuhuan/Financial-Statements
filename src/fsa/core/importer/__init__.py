"""Excel 报表导入模块。

职责: 读取 Excel 文件 -> 输出 Report 对象。
禁止: 执行校验逻辑。
"""

from __future__ import annotations

from fsa.core.importer.importer import ImportService

__all__ = ["ImportService"]
