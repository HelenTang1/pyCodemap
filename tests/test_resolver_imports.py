from pathlib import Path
import textwrap

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
