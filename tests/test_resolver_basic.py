from pathlib import Path
import textwrap
import pytest
import os
from pycodemap import resolve_project, ResolverConfig
from pycodemap.resolver import Symbol, _pick_best_symbol

def test_resolver_discovers_symbols_and_calls(tmp_path: Path) -> None:
    # Arrange: small fake project
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                x = 1
                return x

            class C:
                def m(self):
                    return f()
            """
        ),
        encoding="utf-8",
    )

    # Act
    project = resolve_project(tmp_path, ResolverConfig())

    # Assert symbols
    kinds = {s.kind for s in project.symbols.values()}
    # We should now have module + function + method + class symbols
    assert {"module", "function", "method", "class"} <= kinds

    ids = sorted(project.symbols.keys())
    assert "pkg.a.f" in ids
    assert "pkg.a.C" in ids
    assert any(id_.startswith("pkg.a.C.") for id_ in ids)  # method inside C

    # Assert calls
    calls = project.calls
    assert len(calls) == 1

    call = calls[0]
    assert call.caller_id.endswith(".C.m")  # method C.m
    assert call.raw_callee == "f"
    assert call.callee_id == "pkg.a.f"
    assert call.location.file == Path("pkg/a.py")
    assert call.location.lineno > 0

def test_pick_best_symbol_prefers_function_over_class() -> None:
    func = Symbol(
        id="m.foo",
        kind="function",
        name="foo",
        qualname="m.foo",
        module="m",
        file=Path("m.py"),
        start_line=1,
        end_line=1,
        snippet=None,
    )
    cls = Symbol(
        id="m.foo",
        kind="class",
        name="foo",
        qualname="m.foo",
        module="m",
        file=Path("m.py"),
        start_line=1,
        end_line=1,
        snippet=None,
    )
    best = _pick_best_symbol([cls, func])
    assert best.kind == "function"