from pathlib import Path
import textwrap
import json
import pytest
from pycodemap.cli import main


def test_cli_summary_runs(tmp_path: Path, capsys) -> None:
    # Create a tiny project
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def hello():
                return 42
            """
        ),
        encoding="utf-8",
    )

    # Run CLI with summary format
    exit_code = main([str(tmp_path), "--format", "summary"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Project root:" in captured.out
    assert "Symbols" in captured.out
    assert "Functions" in captured.out


def test_cli_json_output(tmp_path, capsys):
    # small project
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def hello():
                return 42
            """
        ),
        encoding="utf-8",
    )

    exit_code = main([str(tmp_path), "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    # sanity checks
    assert data["root"].endswith(str(tmp_path))
    assert any(s["name"] == "hello" for s in data["symbols"])


def test_cli_invalid_root_raises(tmp_path):
    # Point to a *file*, not a directory, to exercise the error path in resolve_project
    file_path = tmp_path / "not_a_dir.py"
    file_path.write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(ValueError):
        main([str(file_path), "--format", "summary"])

def test_cli_dot_output(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def hello():
                return 42
            """
        ),
        encoding="utf-8",
    )

    output = tmp_path / "graph.dot"
    exit_code = main([str(tmp_path), "--format", "dot", "-o", str(output)])
    assert exit_code == 0
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "digraph CallGraph" in content
    assert "hello" in content