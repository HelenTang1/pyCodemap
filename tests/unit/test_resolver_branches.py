import ast
import textwrap
from pathlib import Path

import pycodemap.resolver as resolver
from pycodemap.resolver import (
    ResolverConfig,
    resolve_project,
    _format_callee_expr,
    _resolve_callee_id,
    _pick_best_symbol,
    _CallVisitor,
    _SymbolVisitor,
    Symbol,
)


def test_iter_python_files_skips_symlinks_by_default(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "keep.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "skip.py").write_text("print('skip')", encoding="utf-8")

    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "skip.py")

    paths_default = list(resolver._iter_python_files(tmp_path, ResolverConfig()))
    assert any(p.name == "keep.py" for p in paths_default)
    assert all(p.name != "skip.py" for p in paths_default)

    paths_follow = list(resolver._iter_python_files(tmp_path, ResolverConfig(follow_symlinks=True)))
    assert any(p.name == "skip.py" for p in paths_follow)

    monkeypatch.setattr(Path, "is_symlink", real_is_symlink)


def test_module_name_from_path_handles_nested() -> None:
    # Test that nested paths are converted to dotted module names
    assert resolver._module_name_from_path(Path("pkg/sub/mod.py")) == "pkg.sub.mod"


def test_extract_snippet_clamps_bounds() -> None:
    visitor = _SymbolVisitor(module="m", rel_path=Path("m.py"), source_lines=["line1\n"])
    # start below 1 and end beyond length should be clamped
    assert visitor._extract_snippet(0, 10) == "line1\n"


def test_current_caller_id_inside_function(monkeypatch) -> None:
    visitor = _CallVisitor(
        module="m",
        rel_path=Path("m.py"),
        symbol_index={},
        symbol_index_flat={},
        source_lines=[],
    )
    visitor._ctx_stack = ["f"]
    assert visitor._current_caller_id() == "m.f"


def test_resolve_callee_id_dotted_direct_match() -> None:
    sym = Symbol(id="pkg.mod.f", kind="function", name="f", qualname="pkg.mod.f", module="pkg.mod", file=Path("m.py"), start_line=1, end_line=1)
    symbol_index = {("pkg.mod", "f"): [sym]}
    assert _resolve_callee_id("pkg.mod.f", current_module="pkg.mod", symbol_index=symbol_index) == "pkg.mod.f"


def test_resolve_callee_id_global_unique_match() -> None:
    sym = Symbol(id="m.f", kind="function", name="f", qualname="m.f", module="m", file=Path("m.py"), start_line=1, end_line=1)
    symbol_index = {("m", "f"): [sym]}
    assert _resolve_callee_id("f", current_module="other", symbol_index=symbol_index) == "m.f"


def test_resolve_callee_id_unknown_returns_none() -> None:
    sym = Symbol(id="m.f", kind="function", name="f", qualname="m.f", module="m", file=Path("m.py"), start_line=1, end_line=1)
    symbol_index = {("m", "f"): [sym]}
    assert _resolve_callee_id("<unknown>", current_module="m", symbol_index=symbol_index) is None


def test_call_visitor_records_unknown_calls(tmp_path: Path) -> None:
    src = tmp_path / "u.py"
    src.write_text(
        textwrap.dedent(
            """
            def f():
                (lambda x: x)(1)
            """
        ),
        encoding="utf-8",
    )
    project = resolve_project(src)
    # Should record a call with raw_callee "<unknown>" for the lambda call
    assert any(call.raw_callee == "<unknown>" and call.callee_id is None for call in project.calls)
