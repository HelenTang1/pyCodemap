import textwrap
from pathlib import Path
import pytest

from pycodemap.cli import main


def _run_cli(args):
    """Helper to normalize return code vs SystemExit."""
    try:
        return main(args)
    except SystemExit as exc:  # argparse error path
        return exc.code


def test_cli_missing_target_shows_usage(capsys) -> None:
    code = _run_cli([])
    captured = capsys.readouterr()
    assert code != 0
    assert "usage:" in captured.out or "usage:" in captured.err


def test_cli_nonexistent_target(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "nope.py"
    with pytest.raises(ValueError, match="does not exist"):
        _run_cli([str(missing)])


def test_cli_invalid_format_option(tmp_path: Path, capsys) -> None:
    script = tmp_path / "script.py"
    script.write_text("def hello():\n    pass\nhello()\n", encoding="utf-8")
    code = _run_cli([str(script), "--format", "pdf"])
    captured = capsys.readouterr()
    assert code != 0
    assert "invalid choice" in captured.out.lower() or "invalid choice" in captured.err.lower()


def test_cli_invalid_node_type_option(tmp_path: Path, capsys) -> None:
    script = tmp_path / "script.py"
    script.write_text(
        textwrap.dedent(
            """
            def hello():
                pass

            hello()
            """
        ),
        encoding="utf-8",
    )
    code = _run_cli([str(script), "--node-type", "invalid"])
    captured = capsys.readouterr()
    assert code != 0
    assert "invalid choice" in captured.out.lower() or "invalid choice" in captured.err.lower()