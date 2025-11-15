from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Literal, Iterable, Tuple, DefaultDict
import os
from collections import defaultdict

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

    `file` is stored *relative to the project root* to keep the model portable.
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

    - `caller_id`: ID of the calling symbol (a function / method / module).
    - `raw_callee`: textual representation from the source (e.g. `f`, `pkg.mod.g`).
    - `callee_id`: resolved symbol ID if we could match it, else None.
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

    Parameters can be expanded in later milestones as needed.
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

    1. Walk the directory tree from ``root`` and find all ``.py`` files.
    2. First pass:
       - Parse every file into an AST.
       - Create a *module symbol* per file.
       - Extract functions/methods/classes as `Symbol`s.
    3. Build an index over all symbols.
    4. Second pass:
       - Traverse ASTs again and record call sites.
       - Try to resolve each call to a `Symbol.id` using a simple static analysis.

    Parameters
    ----------
    root:
        Path to the project root directory.
    config:
        Optional :class:`ResolverConfig`. If omitted, defaults are used.

    Returns
    -------
    ResolvedProject
        A project model with discovered symbols and call sites.
    """
    root = root.resolve()
    if config is None:
        config = ResolverConfig()

    if not root.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {root}")

    # ------------------------------------------------------------------
    # First pass: collect ASTs + symbols
    # ------------------------------------------------------------------
    symbols: Dict[str, Symbol] = {}
    file_infos: List[Tuple[Path, str, str, ast.AST]] = []  # (rel_path, module, source, tree)

    for path in _iter_python_files(root, config):
        rel = path.relative_to(root)
        module = _module_name_from_path(rel)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(rel))

        source_lines = source.splitlines(keepends=True)
        # Module-level symbol for this file
        module_sym = _make_module_symbol(module, rel, source_lines)
        if module_sym.id not in symbols:
            symbols[module_sym.id] = module_sym

        # Function / method / class symbols
        for sym in _iter_symbols_from_ast(tree, module=module, rel_path=rel, source_lines=source_lines):
            symbols[sym.id] = sym

        file_infos.append((rel, module, source, tree))

    # Build an index over symbols for call resolution
    symbol_index = _build_symbol_index(symbols)

    # ------------------------------------------------------------------
    # Second pass: collect calls
    # ------------------------------------------------------------------
    calls: List[Call] = []
    for rel, module, source, tree in file_infos:
        source_lines = source.splitlines(keepends=True)
        visitor = _CallVisitor(
            module=module,
            rel_path=rel,
            symbol_index=symbol_index,
            source_lines=source_lines,
        )
        visitor.visit(tree)
        calls.extend(visitor.calls)

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


def _make_module_symbol(module: str, rel_path: Path, source_lines: List[str]) -> Symbol:
    """
    Create a `module`-kind symbol that represents the file as a whole.

    This gives module-level call sites a valid `caller_id`.
    """
    name = module.split(".")[-1] if module else ""
    start_line = 1
    end_line = len(source_lines) if source_lines else 1
    return Symbol(
        id=module,
        kind="module",
        name=name or module,
        qualname=module,
        module=module,
        file=rel_path,
        start_line=start_line,
        end_line=end_line,
        snippet=None,  # avoid embedding whole file by default
    )


# ---------------------------------------------------------------------------
# Symbol discovery
# ---------------------------------------------------------------------------

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


def _iter_symbols_from_ast(
    tree: ast.AST,
    module: str,
    rel_path: Path,
    source_lines: List[str],
) -> List[Symbol]:
    visitor = _SymbolVisitor(
        module=module,
        rel_path=rel_path,
        source_lines=source_lines,
    )
    visitor.visit(tree)
    return visitor.symbols


# ---------------------------------------------------------------------------
# Call discovery
# ---------------------------------------------------------------------------

class _CallVisitor(ast.NodeVisitor):
    """
    Traverses an AST and records call sites as `Call`s.

    It uses a simple static scheme to map callees to symbol IDs:
    - local functions/methods/classes in the same module
    - imported names via `import` / `from ... import ...`
    - attributes where the base is an imported module/alias
    """

    def __init__(
        self,
        module: str,
        rel_path: Path,
        symbol_index: Dict[Tuple[str, str], List[Symbol]],
        source_lines: List[str],
    ) -> None:
        self.module = module
        self.rel_path = rel_path
        self.symbol_index = symbol_index
        self.source_lines = source_lines

        self.calls: List[Call] = []
        self._ctx_stack: List[str] = []  # nested class / function names
        self._import_aliases: Dict[str, str] = {}  # local_name -> fully qualified target

    # --- context helpers -------------------------------------------------

    def _current_caller_id(self) -> str:
        """
        ID of the current caller.

        - If inside a function/method/class, use `module.qualname`.
        - Otherwise, use the module symbol ID (module name itself).
        """
        if self._ctx_stack:
            qual = ".".join([self.module, *self._ctx_stack])
            return qual
        return self.module  # module-level calls

    # --- import handling -------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname:
                local = alias.asname
                target = alias.name
            else:
                # e.g. `import pkg.sub` binds `pkg`
                first = alias.name.split(".", 1)[0]
                local = first
                target = first
            self._import_aliases[local] = target
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.asname:
                local = alias.asname
            else:
                local = alias.name
            if module:
                target = f"{module}.{alias.name}"
            else:
                # relative import without explicit module - we keep just the name
                target = alias.name
            self._import_aliases[local] = target
        self.generic_visit(node)

    # --- definition nesting ---------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._ctx_stack.append(node.name)
        self.generic_visit(node)
        self._ctx_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._ctx_stack.append(node.name)
        self.generic_visit(node)
        self._ctx_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._ctx_stack.append(node.name)
        self.generic_visit(node)
        self._ctx_stack.pop()

    # --- call sites ------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        caller_id = self._current_caller_id()
        location = SourceLocation(
            file=self.rel_path,
            lineno=getattr(node, "lineno", 1),
            col_offset=getattr(node, "col_offset", 0),
        )

        raw = _format_callee_expr(node.func, import_aliases=self._import_aliases)
        if raw is None:
            raw = "<unknown>"

        callee_id = _resolve_callee_id(
            raw_callee=raw,
            current_module=self.module,
            symbol_index=self.symbol_index,
        )

        self.calls.append(
            Call(
                caller_id=caller_id,
                location=location,
                raw_callee=raw,
                callee_id=callee_id,
            )
        )

        self.generic_visit(node)


def _build_symbol_index(symbols: Dict[str, Symbol]) -> Dict[Tuple[str, str], List[Symbol]]:
    """
    Build an index for call resolution:
    (module, name) -> [Symbol, ...]
    """
    index: DefaultDict[Tuple[str, str], List[Symbol]] = defaultdict(list)
    for sym in symbols.values():
        if sym.kind not in ("function", "method", "class"):
            continue
        index[(sym.module, sym.name)].append(sym)
    return dict(index)


def _format_callee_expr(
    expr: ast.AST,
    import_aliases: Dict[str, str],
) -> Optional[str]:
    """
    Turn the `func` part of a Call into a dotted string, using import/alias info.

    Examples:
        f           -> "f"
        foo         -> "pkg.mod.f"  (if `foo` imported as that function)
        m.g         -> "pkg.m.g"    (if `m` is an alias for `pkg.m`)
        pkg.mod.f   -> "pkg.mod.f"

    Returns None if the expression is too dynamic to represent.
    """
    if isinstance(expr, ast.Name):
        name = expr.id
        if name in import_aliases:
            return import_aliases[name]
        return name

    if isinstance(expr, ast.Attribute):
        base = _format_callee_expr(expr.value, import_aliases=import_aliases)
        if base is None:
            return None
        return f"{base}.{expr.attr}"

    # More dynamic / complex call target (e.g., indexing, lambda, etc.)
    return None


def _resolve_callee_id(
    raw_callee: str,
    current_module: str,
    symbol_index: Dict[Tuple[str, str], List[Symbol]],
) -> Optional[str]:
    """
    Heuristically resolve a raw callee name to a Symbol ID.

    Strategy:
    1. If it's a dotted path "pkg.mod.f", interpret module="pkg.mod", name="f".
    2. Otherwise, treat it as a bare name and look in the current module.
    3. As a last resort, if there's exactly one symbol with that name across all
       modules, use it.
    """
    if raw_callee == "<unknown>":
        return None

    module: Optional[str] = None
    name: str

    if "." in raw_callee:
        module, name = raw_callee.rsplit(".", 1)
        # Direct match on (module, name)
        candidates = symbol_index.get((module, name))
        if candidates:
            return _pick_best_symbol(candidates).id

    # Bare name or dotted path with no direct match
    # Try current module for bare names
    if module is None:
        name = raw_callee
        candidates = symbol_index.get((current_module, name))
        if candidates:
            return _pick_best_symbol(candidates).id

    # Last resort: global name match (only if unique)
    global_matches: List[Symbol] = []
    for (mod, n), syms in symbol_index.items():
        if n == name:
            global_matches.extend(syms)

    if len(global_matches) == 1:
        return global_matches[0].id

    return None


def _pick_best_symbol(candidates: List[Symbol]) -> Symbol:
    """
    Pick the "best" symbol if multiple share the same (module, name).

    For now:
    - prefer functions/methods over classes (slightly arbitrary, but reasonable)
    """
    func_kinds = ("function", "method")
    func_like = [s for s in candidates if s.kind in func_kinds]
    if func_like:
        return func_like[0]
    return candidates[0]
