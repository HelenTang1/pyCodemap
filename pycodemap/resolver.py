from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Literal, Iterable, Tuple
import os

__all__ = [
    "SourceLocation",
    "SymbolKind",
    "Symbol",
    "Call",
    "ResolvedProject",
    "ResolverConfig",
    "resolve_project",
]

SymbolKind = Literal["function", "method", "class", "module", "file"]


@dataclass(frozen=True)
class SourceLocation:
    """
    Represents a concrete location in a source file.

    All paths are stored *relative to the project root* to keep the model portable.
    """

    file: Path
    lineno: int
    col_offset: int = 0

    def with_project_root(self, root: Path) -> Path:
        """Return the absolute path under a given project root."""
        return root / self.file


@dataclass
class Symbol:
    """A named thing in the project (function, method, class, module, or file)."""

    id: str
    kind: SymbolKind
    name: str
    qualname: str
    module: str
    file: Path  # path *relative* to project root
    start_line: int
    end_line: int
    snippet: Optional[str] = None


@dataclass
class Call:
    """
    Represents a call site in the code.
    """

    caller_id: str
    location: SourceLocation
    raw_callee: str
    callee_id: Optional[str] = None


@dataclass
class ResolvedProject:
    """
    The output of the resolver.

    It contains a flat list of symbols and call sites. The `graph` module will
    turn this into a more graph-oriented structure in a later milestone.
    """

    root: Path
    symbols: Dict[str, Symbol]
    calls: List[Call]

    def functions(self) -> List[Symbol]:
        """Convenience helper to get only functions + methods."""
        return [s for s in self.symbols.values() if s.kind in ("function", "method")]


@dataclass
class ResolverConfig:
    """
    Configuration for the resolver.
    """

    follow_symlinks: bool = False
    exclude: Sequence[str] = (
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "venv",
        "env",
    )


def resolve_project(root: Path, config: Optional[ResolverConfig] = None) -> ResolvedProject:
    """
    Resolve a Python project into a `ResolvedProject`.

    - Walk the directory tree from ``root``
    - Find all ``.py`` files
    - Extract function and method symbols via the `ast` module

    Parameters
    ----------
    root:
        Path to the project root directory.
    config:
        Optional :class:`ResolverConfig`. If omitted, defaults are used.

    Returns
    -------
    ResolvedProject
        A project model with discovered symbols and an empty list of calls.
    """
    root = root.resolve()
    if config is None:
        config = ResolverConfig()

    symbols: Dict[str, Symbol] = {}
    calls: List[Call] = []

    if not root.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {root}")

    for path in _iter_python_files(root, config):
        rel = path.relative_to(root)
        module = _module_name_from_path(rel)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(rel))

        for sym in _iter_symbols_from_ast(tree, module=module, rel_path=rel, source=source):
            # ID is fully qualified (module + nested qualname), so clashes are unlikely.
            symbols[sym.id] = sym

    return ResolvedProject(root=root, symbols=symbols, calls=calls)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def os_walk(root: Path) -> Iterable[Tuple[str, List[str], List[str]]]:
    """Small wrapper to keep typing happy."""
    return os.walk(root)


def _iter_python_files(root: Path, config: ResolverConfig) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os_walk(root):
        # mutate dirnames in-place to respect exclude list
        dirnames[:] = [d for d in dirnames if d not in config.exclude]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = Path(dirpath) / name
            if not config.follow_symlinks and path.is_symlink():
                continue
            yield path


def _module_name_from_path(rel_path: Path) -> str:
    """
    Convert a project-relative path to a dotted module name.

    Example
    -------
    >>> _module_name_from_path(Path("pkg/sub/mod.py"))
    'pkg.sub.mod'
    """
    parts = list(rel_path.with_suffix("").parts)
    return ".".join(parts)


class _SymbolVisitor(ast.NodeVisitor):
    """
    Traverses an AST and records functions / methods / classes as `Symbol`s.
    """

    def __init__(self, module: str, rel_path: Path, source_lines: List[str]):
        self.module = module
        self.rel_path = rel_path
        self.source_lines = source_lines
        self.symbols: List[Symbol] = []
        self._qualname_stack: List[str] = []

    # --- helpers ---------------------------------------------------------

    def _push(self, name: str) -> None:
        self._qualname_stack.append(name)

    def _pop(self) -> None:
        self._qualname_stack.pop()

    def _current_qualname(self, name: str) -> str:
        if self._qualname_stack:
            return ".".join([self.module, *self._qualname_stack, name])
        return ".".join([self.module, name])

    def _add_symbol(self, node: ast.AST, kind: SymbolKind, name: str) -> None:
        qualname = self._current_qualname(name)
        sym_id = qualname  # for now ID == qualname
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        # Python `end_lineno` is inclusive. Slicing uses exclusive end.
        snippet = self._extract_snippet(start_line, end_line)
        self.symbols.append(
            Symbol(
                id=sym_id,
                kind=kind,
                name=name,
                qualname=qualname,
                module=self.module,
                file=self.rel_path,
                start_line=start_line,
                end_line=end_line,
                snippet=snippet,
            )
        )

    def _extract_snippet(self, start: int, end: int) -> str:
        # Clamp to available lines
        start = max(1, start)
        end = min(len(self.source_lines), end)
        return "".join(self.source_lines[start - 1 : end])

    # --- visitors --------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind: SymbolKind = "function" if not self._qualname_stack else "method"
        self._add_symbol(node, kind=kind, name=node.name)
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind: SymbolKind = "function" if not self._qualname_stack else "method"
        self._add_symbol(node, kind=kind, name=node.name)
        self._push(node.name)
        self.generic_visit(node)
        self._pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node, kind="class", name=node.name)
        self._push(node.name)
        self.generic_visit(node)
        self._pop()


def _iter_symbols_from_ast(tree: ast.AST, module: str, rel_path: Path, source: str) -> List[Symbol]:
    visitor = _SymbolVisitor(
        module=module,
        rel_path=rel_path,
        source_lines=source.splitlines(keepends=True),
    )
    visitor.visit(tree)
    return visitor.symbols
