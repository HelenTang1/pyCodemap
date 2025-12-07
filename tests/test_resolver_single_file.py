"""
Tests for pycodemap when the input is a single Python file.
"""
import tempfile
from pathlib import Path
import pytest

from pycodemap.resolver import resolve_project


def test_single_file_basic():
    """Test resolving a single Python file with a simple function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "script.py"
        test_file.write_text(
            "def hello():\n"
            "    print('Hello')\n"
            "\n"
            "hello()\n"
        )
        
        project = resolve_project(test_file)
        
        # Should have module symbol + function symbol
        assert len(project.symbols) == 2
        
        # Check module symbol
        module_sym = project.symbols.get("script")
        assert module_sym is not None
        assert module_sym.kind == "module"
        assert module_sym.name == "script"
        assert module_sym.qualname == "script"
        
        # Check function symbol
        func_sym = project.symbols.get("script.hello")
        assert func_sym is not None
        assert func_sym.kind == "function"
        assert func_sym.name == "hello"
        assert func_sym.qualname == "script.hello"
        assert func_sym.module == "script"
        
        # Should have two calls: hello() calling print(), and module-level calling hello()
        assert len(project.calls) == 2
        
        # Check module-level call to hello
        hello_call = [c for c in project.calls if c.caller_id == "script" and c.raw_callee == "hello"][0]
        assert hello_call.callee_id == "script.hello"
        
        # Check hello calling print (builtin, so callee_id may be None or "builtins.print")
        print_call = [c for c in project.calls if c.caller_id == "script.hello" and c.raw_callee == "print"][0]
        assert print_call.raw_callee == "print"
        # callee_id could be None for builtins depending on resolver configuration


def test_single_file_with_imports():
    """Test a single file that imports and calls external modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "main.py"
        test_file.write_text(
            "import os\n"
            "\n"
            "def check_file(path):\n"
            "    return os.path.exists(path)\n"
            "\n"
            "check_file('test.txt')\n"
        )
        
        project = resolve_project(test_file)
        
        # Should have module + function
        assert "main" in project.symbols
        assert "main.check_file" in project.symbols
        
        # Should have calls
        assert len(project.calls) >= 1
        
        # Check the module-level call
        module_call = [c for c in project.calls if c.caller_id == "main"][0]
        assert module_call.raw_callee == "check_file"
        assert module_call.callee_id == "main.check_file"


def test_single_file_with_class():
    """Test a single file containing a class with methods."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "calculator.py"
        test_file.write_text(
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
            "\n"
            "    def subtract(self, a, b):\n"
            "        return a - b\n"
            "\n"
            "calc = Calculator()\n"
            "result = calc.add(1, 2)\n"
        )
        
        project = resolve_project(test_file)
        
        # Check symbols
        assert "calculator" in project.symbols
        assert "calculator.Calculator" in project.symbols
        assert "calculator.Calculator.add" in project.symbols
        assert "calculator.Calculator.subtract" in project.symbols
        
        # Check symbol kinds
        assert project.symbols["calculator"].kind == "module"
        assert project.symbols["calculator.Calculator"].kind == "class"
        assert project.symbols["calculator.Calculator.add"].kind == "method"


def test_single_file_nested_functions():
    """Test a single file with nested function definitions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "nested.py"
        test_file.write_text(
            "def outer():\n"
            "    def inner():\n"
            "        return 42\n"
            "    return inner()\n"
            "\n"
            "outer()\n"
        )
        
        project = resolve_project(test_file)
        
        # Check nested function symbols
        assert "nested.outer" in project.symbols
        assert "nested.outer.inner" in project.symbols
        
        # Check calls
        calls = project.calls
        # Should have module-level call to outer, and outer calling inner
        assert any(c.caller_id == "nested" and c.raw_callee == "outer" for c in calls)
        assert any(c.caller_id == "nested.outer" and c.raw_callee == "inner" for c in calls)


def test_single_file_empty():
    """Test an empty Python file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "empty.py"
        test_file.write_text("")
        
        project = resolve_project(test_file)
        
        # Should only have module symbol
        assert len(project.symbols) == 1
        assert "empty" in project.symbols
        assert project.symbols["empty"].kind == "module"
        
        # No calls
        assert len(project.calls) == 0


def test_single_file_comments_only():
    """Test a file with only comments and docstrings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "comments.py"
        test_file.write_text(
            '"""Module docstring."""\n'
            "# This is a comment\n"
            "# Another comment\n"
        )
        
        project = resolve_project(test_file)
        
        # Should only have module symbol
        assert len(project.symbols) == 1
        assert "comments" in project.symbols
        assert len(project.calls) == 0


def test_single_file_invalid_extension():
    """Test that non-.py files raise an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "script.txt"
        test_file.write_text("print('hello')")
        
        with pytest.raises(ValueError, match="not a .py file"):
            resolve_project(test_file)


def test_single_file_nonexistent():
    """Test that nonexistent files raise an error."""
    with pytest.raises(ValueError, match="does not exist"):
        resolve_project(Path("/nonexistent/file.py"))


def test_single_file_with_graph_generation():
    """Integration test: single file through the entire pipeline to DOT."""
    from pycodemap.graph import GraphConfig, build_call_graph
    from pycodemap.renderer import RendererConfig, build_dot
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "simple.py"
        test_file.write_text(
            "def foo():\n"
            "    bar()\n"
            "\n"
            "def bar():\n"
            "    pass\n"
            "\n"
            "foo()\n"
        )
        
        project = resolve_project(test_file)
        graph_cfg = GraphConfig(
            node_granularity="function",
            cluster_by_module=True,
            prune_transitive=False,
        )
        renderer_cfg = RendererConfig(
            label_mode="name",
            show_module=False,
            show_line_numbers=False,
        )
        
        dot = build_dot(project, graph_cfg, renderer_cfg)
        
        # Verify DOT contains expected nodes
        assert "digraph CallGraph" in dot
        assert "foo" in dot
        assert "bar" in dot
        # Should have edge foo -> bar
        assert "->" in dot


def test_single_file_module_name_resolution():
    """Test that module name is correctly derived from single file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Test various file names
        test_cases = [
            ("script.py", "script"),
            ("my_module.py", "my_module"),
            ("test_file.py", "test_file"),
            ("__main__.py", "__main__"),
        ]
        
        for filename, expected_module in test_cases:
            test_file = tmpdir / filename
            test_file.write_text("def test(): pass")
            
            project = resolve_project(test_file)
            
            # Check module symbol
            assert expected_module in project.symbols
            assert project.symbols[expected_module].kind == "module"
            assert project.symbols[expected_module].module == expected_module
            
            # Check function symbol
            func_qualname = f"{expected_module}.test"
            assert func_qualname in project.symbols
            assert project.symbols[func_qualname].module == expected_module
            
            # Cleanup for next iteration
            test_file.unlink()