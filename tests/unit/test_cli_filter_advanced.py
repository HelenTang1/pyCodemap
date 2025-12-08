"""Additional integration and edge case tests for filter feature."""
from pathlib import Path
import textwrap
import json
import pytest
from pycodemap.cli import main


def test_filter_combined_with_node_options(tmp_path: Path, capsys) -> None:
    """Test --filter works with various node display options."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                return 1
            
            def calculate():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter with --label qualname
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--label", "qualname"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process_data" in symbol_names
    assert "calculate" not in symbol_names


def test_filter_combined_with_cluster_options(tmp_path: Path) -> None:
    """Test --filter works with clustering options."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                return 1
            
            def calculate():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    output = tmp_path / "filtered.dot"
    exit_code = main([
        str(tmp_path),
        "--format", "dot",
        "--filter", "process",
        "--no-cluster",
        "-o", str(output)
    ])
    
    assert exit_code == 0
    assert output.exists()


def test_filter_combined_with_prune_transitive(tmp_path: Path, capsys) -> None:
    """Test --filter works with --prune-transitive."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                helper()
                bar()
            
            def helper():
                bar()
            
            def bar():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter",
        "--prune-transitive"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # All nodes should be present
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names
    assert "helper" in symbol_names
    assert "bar" in symbol_names


def test_filter_with_special_characters_in_keyword(tmp_path: Path, capsys) -> None:
    """Test --filter with special characters in keyword."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                return 1
            
            def __init__():
                return 2
            
            def _private_method():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for underscore patterns
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "_"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process_data" in symbol_names  # contains _
    assert "__init__" in symbol_names  # contains _
    assert "_private_method" in symbol_names  # contains _


def test_filter_matches_qualname_not_just_name(tmp_path: Path, capsys) -> None:
    """Test --filter matches against qualname (module.class.method)."""
    (tmp_path / "mymod.py").write_text(
        textwrap.dedent(
            """
            class Processor:
                def process(self):
                    return 1
            
            def helper():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "Processor" should match the class's methods too
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "Processor"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # Should match "Processor" class and its methods via qualname
    symbol_qualnames = [s["qualname"] for s in data["symbols"]]
    assert any("Processor" in qn for qn in symbol_qualnames)


def test_link_by_filter_does_not_include_callers(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter includes callees but NOT callers."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def caller():
                process()
            
            def process():
                helper()
            
            def helper():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" - should include process and helper (callee)
    # Should NOT include caller (even though it calls process)
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names  # matched
    assert "helper" in symbol_names  # callee
    assert "caller" not in symbol_names  # caller should NOT be included


def test_filter_with_module_names(tmp_path: Path, capsys) -> None:
    """Test --filter can match module names."""
    (tmp_path / "processor.py").write_text(
        textwrap.dedent(
            """
            def run():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    (tmp_path / "helper.py").write_text(
        textwrap.dedent(
            """
            def assist():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "processor" at file level
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--node-type", "file",
        "--filter", "processor"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    module_names = [s["module"] for s in data["symbols"] if s["kind"] == "module"]
    assert "processor" in module_names
    assert "helper" not in module_names


def test_link_by_filter_with_unresolved_calls(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter handles unresolved calls gracefully."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                unknown_function()  # unresolved call
                helper()
            
            def helper():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names
    assert "helper" in symbol_names


def test_filter_with_summary_format(tmp_path: Path, capsys) -> None:
    """Test --filter works with summary format output."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                return 1
            
            def calculate():
                return 2
            
            def helper():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    exit_code = main([str(tmp_path), "--format", "summary", "--filter", "process"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    # Summary should reflect filtered counts
    assert "Project root:" in captured.out
    # Should show filtered symbol count


def test_multiple_filter_keywords_with_overlapping_matches(tmp_path: Path, capsys) -> None:
    """Test multiple keywords that match overlapping sets of nodes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                return 1
            
            def data_processor():
                return 2
            
            def handler():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Both keywords match process_data and data_processor
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process,data"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process_data" in symbol_names
    assert "data_processor" in symbol_names
    assert "handler" not in symbol_names


def test_link_by_filter_with_diamond_dependency(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter with diamond-shaped call graph."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                left()
                right()
            
            def left():
                bottom()
            
            def right():
                bottom()
            
            def bottom():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    # Should include all nodes in the diamond
    assert "process" in symbol_names
    assert "left" in symbol_names
    assert "right" in symbol_names
    assert "bottom" in symbol_names


def test_filter_no_impact_on_non_graph_formats(tmp_path: Path, capsys) -> None:
    """Test that filter behavior is consistent across all output formats."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                return 1
            
            def calculate():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Test JSON format
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process"])
    captured_json = capsys.readouterr()
    assert exit_code == 0
    json_data = json.loads(captured_json.out)
    json_names = [s["name"] for s in json_data["symbols"] if s["kind"] in ("function", "method")]
    
    # Test DOT format
    output_dot = tmp_path / "test.dot"
    exit_code = main([str(tmp_path), "--format", "dot", "--filter", "process", "-o", str(output_dot)])
    assert exit_code == 0
    dot_content = output_dot.read_text(encoding="utf-8")
    
    # Both should filter the same way
    assert "process" in json_names
    assert "calculate" not in json_names
    assert "process" in dot_content
    assert "calculate" not in dot_content


def test_link_by_filter_with_self_calls(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter handles recursive/self-calls."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                helper()
                process()  # self-call
            
            def helper():
                return 1
            
            def other():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names
    assert "helper" in symbol_names
    assert "other" not in symbol_names


def test_filter_with_async_functions(tmp_path: Path, capsys) -> None:
    """Test --filter works with async functions."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            async def process_async():
                return 1
            
            async def calculate_async():
                return 2
            
            def sync_process():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process_async" in symbol_names
    assert "sync_process" in symbol_names
    assert "calculate_async" not in symbol_names


def test_filter_combined_with_all_label_modes(tmp_path: Path) -> None:
    """Test --filter works with all label modes (name, qualname, code)."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                return 1
            
            def calculate():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    for label_mode in ["name", "qualname", "code"]:
        output = tmp_path / f"test_{label_mode}.dot"
        exit_code = main([
            str(tmp_path),
            "--format", "dot",
            "--filter", "process",
            "--label", label_mode,
            "-o", str(output)
        ])
        
        assert exit_code == 0
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "process" in content
        assert "calculate" not in content


def test_link_by_filter_respects_filter_scope(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter only follows calls from filtered nodes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                shared()
            
            def calculate():
                shared()
            
            def shared():
                deep()
            
            def deep():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" only - should include shared and deep via process's calls
    # Should NOT include calculate even though it also calls shared
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names
    assert "shared" in symbol_names
    assert "deep" in symbol_names
    assert "calculate" not in symbol_names
