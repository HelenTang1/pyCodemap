from pathlib import Path
import pytest

from pycodemap.resolver import resolve_project


def test_resolver_syntax_error(tmp_path: Path) -> None:
    bad = tmp_path / "broken.py"
    bad.write_text("def oops(:\n    pass\n", encoding="utf-8")
    with pytest.raises(SyntaxError):
        resolve_project(bad)


def test_resolver_non_py_extension(tmp_path: Path) -> None:
    not_py = tmp_path / "data.txt"
    not_py.write_text("print('hi')", encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_project(not_py)


def test_resolver_directory_without_files(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    project = resolve_project(empty_dir)
    assert project.symbols == {}
    assert project.calls == []

def test_resolver_unknown_callee_lambda(tmp_path: Path) -> None:
    (tmp_path / "lam.py").write_text("(lambda x: x)(1)\n", encoding="utf-8")
    project = resolve_project(tmp_path)
    assert project.calls
    call = project.calls[0]
    assert call.raw_callee == "<unknown>"
    assert call.callee_id is None
