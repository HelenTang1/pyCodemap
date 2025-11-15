from pathlib import Path
import textwrap
from dataclasses import dataclass
from unittest.mock import call
from pycodemap import resolver
from pycodemap import resolve_project, ResolverConfig


def test_resolver_resolves_imported_function_calls(tmp_path: Path) -> None:
    # pkg/a.py: defines f
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                return 123
            """
        ),
        encoding="utf-8",
    )

    # pkg/b.py: imports f as foo and calls it
    (pkg / "b.py").write_text(
        textwrap.dedent(
            """
            from pkg.a import f as foo

            def g():
                return foo()
            """
        ),
        encoding="utf-8",
    )

    project = resolve_project(tmp_path, ResolverConfig())

    # Ensure the core symbols exist
    assert "pkg.a.f" in project.symbols
    assert "pkg.b.g" in project.symbols

    # There should be exactly one call in b.g
    calls = [c for c in project.calls if c.caller_id == "pkg.b.g"]
    assert len(calls) == 1

    call = calls[0]
    # Raw callee should be fully qualified from alias resolution
    assert call.raw_callee == "pkg.a.f"
    assert call.callee_id == "pkg.a.f"

def test_resolver_records_unknown_callee(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                return 123

            def g():
                funcs = [f]
                # Call target is a list element -> dynamic, not statically resolvable
                return funcs[0]()
            """
        ),
        encoding="utf-8",
    )

    project = resolve_project(tmp_path, ResolverConfig())

    unknown_calls = [c for c in project.calls if c.raw_callee == "<unknown>"]
    assert len(unknown_calls) == 1
    call = unknown_calls[0]
    assert call.callee_id is None
    # caller is g()
    assert call.caller_id.endswith(".g")

def test_resolver_importfrom_module_none(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                return 1
            """
        ),
        encoding="utf-8",
    )

    (pkg / "b.py").write_text(
        textwrap.dedent(
            """
            from . import a

            def g():
                # callee is a.f(), but base `a` came from `from . import a`
                return a.f()
            """
        ),
        encoding="utf-8",
    )

    project = resolve_project(tmp_path, ResolverConfig())
    calls = [c for c in project.calls if c.caller_id.endswith(".g")]

    assert calls, "Expected at least one call from pkg.b.g"
    call = calls[0]

    assert call.raw_callee in ("a.f", "pkg.a.f")
    assert call.callee_id == "pkg.a.f"

@dataclass
class DummySym:
    id: str
    kind: resolver.SymbolKind
    name: str
    module: str


def test_resolve_callee_id_unique_global_match():
    # Build a fake symbol_index with a unique name across modules
    s1 = DummySym(id="pkg.a.f", kind="function", name="f", module="pkg.a")
    symbol_index = {
        ("pkg.a", "f"): [s1],
    }

    callee = resolver._resolve_callee_id("f", current_module="other.mod", symbol_index=symbol_index)
    assert callee == "pkg.a.f"


def test_resolve_callee_id_ambiguous_global_match_returns_none():
    s1 = DummySym(id="pkg.a.h", kind="function", name="h", module="pkg.a")
    s2 = DummySym(id="pkg.b.h", kind="function", name="h", module="pkg.b")
    symbol_index = {
        ("pkg.a", "h"): [s1],
        ("pkg.b", "h"): [s2],
    }

    # No local match in current_module, but 2 global matches -> should be None
    callee = resolver._resolve_callee_id("h", current_module="pkg.c", symbol_index=symbol_index)
    assert callee is None


def test_pick_best_symbol_prefers_function_over_class():
    func_sym = DummySym(id="pkg.a.f", kind="function", name="f", module="pkg.a")
    class_sym = DummySym(id="pkg.a.f", kind="class", name="f", module="pkg.a")

    best = resolver._pick_best_symbol([class_sym, func_sym])
    assert best is func_sym
