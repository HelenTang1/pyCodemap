from pathlib import Path
import textwrap

from pycodemap import resolve_project, ResolverConfig


def test_resolver_discovers_functions_and_methods(tmp_path: Path) -> None:
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

    # Assert
    # We expect 1 function + 1 method + 1 class
    kinds = {s.kind for s in project.symbols.values()}
    assert {"function", "method", "class"} <= kinds

    ids = sorted(project.symbols.keys())
    assert "pkg.a.f" in ids
    assert "pkg.a.C" in ids
    assert any(id_.startswith("pkg.a.C.") for id_ in ids)  # method

    assert project.calls == []  # TODO: not implemented yet
