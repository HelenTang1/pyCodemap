from pathlib import Path
import textwrap

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
