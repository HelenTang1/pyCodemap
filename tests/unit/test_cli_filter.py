"""TDD tests for --filter and --link-by-filter CLI arguments."""
from pathlib import Path
import textwrap
import json
import pytest
from pycodemap.cli import main


def test_filter_basic_single_keyword(tmp_path: Path) -> None:
    """Test --filter with a single keyword filters nodes by name."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                return 1
            
            def calculate_total():
                return 2
            
            def show_result():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing "process"
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process"])
    assert exit_code == 0
    # The implementation should filter the JSON output or graph nodes


def test_filter_multiple_keywords_comma_separated(tmp_path: Path, capsys) -> None:
    """Test --filter with comma-separated keywords matches any keyword."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                return 1
            
            def calculate_total():
                return 2
            
            def show_result():
                return 3
            
            def helper():
                return 4
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing "process" OR "calculate"
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process,calculate"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # Should include process_data and calculate_total, but not show_result or helper
    symbol_names = [s["name"] for s in data["symbols"]]
    assert "process_data" in symbol_names
    assert "calculate_total" in symbol_names
    assert "show_result" not in symbol_names
    assert "helper" not in symbol_names


def test_filter_with_no_matches(tmp_path: Path, capsys) -> None:
    """Test --filter with keyword that matches no nodes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            
            def bar():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing "nonexistent"
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "nonexistent"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # Should have no symbols (except possibly module)
    function_symbols = [s for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert len(function_symbols) == 0


def test_filter_partial_match(tmp_path: Path, capsys) -> None:
    """Test --filter matches partial names (contains, not exact match)."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                return 1
            
            def preprocess_input():
                return 2
            
            def calculate():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing "process" - should match both process_data and preprocess_input
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process_data" in symbol_names
    assert "preprocess_input" in symbol_names
    assert "calculate" not in symbol_names


def test_filter_case_sensitivity(tmp_path: Path, capsys) -> None:
    """Test --filter keyword matching is case-sensitive by default."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def ProcessData():
                return 1
            
            def process_data():
                return 2
            
            def PROCESS_DATA():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing lowercase "process"
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    # Should only match process_data (lowercase)
    assert "process_data" in symbol_names
    # Should not match ProcessData or PROCESS_DATA
    assert "ProcessData" not in symbol_names
    assert "PROCESS_DATA" not in symbol_names


def test_filter_with_methods_in_classes(tmp_path: Path, capsys) -> None:
    """Test --filter works with methods in classes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            class DataProcessor:
                def process(self):
                    return 1
                
                def validate(self):
                    return 2
            
            def process_input():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing "process"
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names  # method
    assert "process_input" in symbol_names  # function
    assert "validate" not in symbol_names


def test_filter_with_attributes(tmp_path: Path, capsys) -> None:
    """Test --filter works with class attributes node."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            class Person:
                name: str
                age: int
                
                def greet(self):
                    return "Hello"
            
            def process():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for nodes containing "attributes" - should match the <attributes> node
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "attributes"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"]]
    assert "<attributes>" in symbol_names
    assert "greet" not in symbol_names
    assert "process" not in symbol_names


def test_filter_with_dot_output(tmp_path: Path) -> None:
    """Test --filter works with DOT format output."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                calculate()
            
            def calculate():
                return 1
            
            def unrelated():
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
        "-o", str(output)
    ])
    
    assert exit_code == 0
    assert output.exists()
    
    content = output.read_text(encoding="utf-8")
    assert "process" in content
    assert "unrelated" not in content


def test_filter_with_svg_output(tmp_path: Path, monkeypatch) -> None:
    """Test --filter works with SVG format output."""
    # Mock Graphviz to avoid dependency in tests
    def mock_write_svg(dot_content: str, output_path: Path) -> None:
        output_path.write_text(f"<svg>{dot_content}</svg>", encoding="utf-8")
    
    import pycodemap.renderer
    monkeypatch.setattr(pycodemap.renderer, "write_svg", mock_write_svg)
    
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
    
    output = tmp_path / "filtered.svg"
    exit_code = main([
        str(tmp_path),
        "--format", "svg",
        "--filter", "process",
        "-o", str(output)
    ])
    
    assert exit_code == 0
    assert output.exists()
    
    content = output.read_text(encoding="utf-8")
    assert "process" in content
    assert "calculate" not in content


def test_link_by_filter_without_filter_is_noop(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter has no effect when --filter is not used."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def foo():
                bar()
            
            def bar():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    # Using --link-by-filter without --filter should show all nodes (no filtering)
    exit_code = main([str(tmp_path), "--format", "json", "--link-by-filter"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # Should include all functions since no filter is applied
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "foo" in symbol_names
    assert "bar" in symbol_names


def test_link_by_filter_includes_callees(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter keeps nodes that are called by filtered nodes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                helper()
                calculate()
            
            def helper():
                return 1
            
            def calculate():
                return 2
            
            def unrelated():
                return 3
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" with link-by-filter
    # Should include process, helper, and calculate (all called by process)
    # Should NOT include unrelated
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
    assert "process" in symbol_names  # matched by filter
    assert "helper" in symbol_names  # called by process
    assert "calculate" in symbol_names  # called by process
    assert "unrelated" not in symbol_names  # not called by process


def test_link_by_filter_transitive_calls(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter includes transitively called nodes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                level1()
            
            def level1():
                level2()
            
            def level2():
                level3()
            
            def level3():
                return 1
            
            def unrelated():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" with link-by-filter
    # Should include entire call chain: process -> level1 -> level2 -> level3
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
    assert "level1" in symbol_names
    assert "level2" in symbol_names
    assert "level3" in symbol_names
    assert "unrelated" not in symbol_names


def test_link_by_filter_multiple_filtered_nodes(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter with multiple nodes matching filter."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process_data():
                helper1()
            
            def process_input():
                helper2()
            
            def helper1():
                common()
            
            def helper2():
                common()
            
            def common():
                return 1
            
            def unrelated():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" - matches both process_data and process_input
    # With link-by-filter, should include helper1, helper2, and common
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
    assert "process_data" in symbol_names
    assert "process_input" in symbol_names
    assert "helper1" in symbol_names
    assert "helper2" in symbol_names
    assert "common" in symbol_names
    assert "unrelated" not in symbol_names


def test_link_by_filter_with_no_outgoing_calls(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter when filtered node has no outgoing calls."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                return 1
            
            def helper():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" which doesn't call anything
    # Should only include process itself
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
    assert "helper" not in symbol_names


def test_link_by_filter_with_circular_calls(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter handles circular call relationships."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                foo()
            
            def foo():
                bar()
            
            def bar():
                foo()  # circular: bar -> foo
            
            def unrelated():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" with circular calls
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
    assert "foo" in symbol_names
    assert "bar" in symbol_names
    assert "unrelated" not in symbol_names


def test_link_by_filter_with_file_granularity(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter works with --node-type file."""
    (tmp_path / "process.py").write_text(
        textwrap.dedent(
            """
            from helper import help_func
            
            def process():
                help_func()
            """
        ),
        encoding="utf-8",
    )
    
    (tmp_path / "helper.py").write_text(
        textwrap.dedent(
            """
            def help_func():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    (tmp_path / "unrelated.py").write_text(
        textwrap.dedent(
            """
            def other():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for files containing "process"
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--node-type", "file",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # Should include process.py (matched) and helper.py (called)
    # Should NOT include unrelated.py
    module_names = [s["module"] for s in data["symbols"] if s["kind"] == "module"]
    assert "process" in module_names
    assert "helper" in module_names
    assert "unrelated" not in module_names


def test_filter_with_whitespace_in_keywords(tmp_path: Path, capsys) -> None:
    """Test --filter handles whitespace around comma-separated keywords."""
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
    
    # Filter with whitespace: "process, calculate"
    exit_code = main([str(tmp_path), "--format", "json", "--filter", "process, calculate"])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    symbol_names = [s["name"] for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert "process" in symbol_names
    assert "calculate" in symbol_names
    assert "helper" not in symbol_names


def test_filter_empty_string_shows_nothing(tmp_path: Path, capsys) -> None:
    """Test --filter with empty string matches nothing."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def foo():
                return 1
            """
        ),
        encoding="utf-8",
    )
    
    # Empty filter string
    exit_code = main([str(tmp_path), "--format", "json", "--filter", ""])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    function_symbols = [s for s in data["symbols"] if s["kind"] in ("function", "method")]
    assert len(function_symbols) == 0


def test_link_by_filter_preserves_edges_between_kept_nodes(tmp_path: Path, capsys) -> None:
    """Test --link-by-filter preserves call edges between kept nodes."""
    (tmp_path / "mod.py").write_text(
        textwrap.dedent(
            """
            def process():
                foo()
            
            def foo():
                bar()
            
            def bar():
                return 1
            
            def unrelated():
                other()
            
            def other():
                return 2
            """
        ),
        encoding="utf-8",
    )
    
    # Filter for "process" with link-by-filter
    exit_code = main([
        str(tmp_path),
        "--format", "json",
        "--filter", "process",
        "--link-by-filter"
    ])
    captured = capsys.readouterr()
    
    assert exit_code == 0
    data = json.loads(captured.out)
    
    # Check that calls between kept nodes are preserved
    calls = data["calls"]
    caller_callee_pairs = [(c["caller_id"], c["callee_id"]) for c in calls if c["callee_id"]]
    
    # Should have process->foo and foo->bar
    assert any("process" in caller and "foo" in callee for caller, callee in caller_callee_pairs)
    assert any("foo" in caller and "bar" in callee for caller, callee in caller_callee_pairs)
    
    # Should NOT have unrelated->other
    assert not any("unrelated" in caller and "other" in callee for caller, callee in caller_callee_pairs)
