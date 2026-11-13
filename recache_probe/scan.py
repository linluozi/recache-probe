"""Statically find ``re.<func>("literal", ...)`` call sites (the ones that pay the tax)."""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

__all__ = ["CallSite", "scan_source", "scan_paths", "RE_FUNCTIONS"]

RE_FUNCTIONS = frozenset(
    {"match", "fullmatch", "search", "sub", "subn", "findall", "finditer", "split"}
)
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", "build", "dist"}


@dataclass(frozen=True)
class CallSite:
    path: str
    line: int
    column: int
    function: str
    pattern: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: re.{self.function}({self.pattern!r})"


def _aliases(tree: ast.AST) -> tuple[set[str], dict[str, str]]:
    modules: set[str] = set()
    functions: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re":
                    modules.add(alias.asname or "re")
        elif isinstance(node, ast.ImportFrom) and node.module == "re":
            for alias in node.names:
                if alias.name in RE_FUNCTIONS:
                    functions[alias.asname or alias.name] = alias.name
    return modules, functions


def scan_source(source: str, filename: str = "<string>") -> list[CallSite]:
    """Return literal-pattern ``re`` calls in ``source`` (sorted by position)."""
    tree = ast.parse(source)
    modules, functions = _aliases(tree)
    sites: list[CallSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        function: str | None = None
        if isinstance(node.func, ast.Attribute):
            if (
                node.func.attr in RE_FUNCTIONS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in modules
            ):
                function = node.func.attr
        elif isinstance(node.func, ast.Name):
            function = functions.get(node.func.id)
        if function is None:
            continue
        sites.append(
            CallSite(filename, node.lineno, node.col_offset, function, first.value)
        )
    sites.sort(key=lambda s: (s.line, s.column))
    return sites


def scan_paths(paths: list[str], limit: int = 2000) -> list[CallSite]:
    """Recursively scan ``*.py`` files under each path."""
    sites: list[CallSite] = []
    for raw in paths:
        root = pathlib.Path(raw)
        candidates = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in candidates:
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
                sites.extend(scan_source(text, str(path)))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            if len(sites) >= limit:
                return sites
    return sites
