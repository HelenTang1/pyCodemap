"""
Tests for new features:
1. Code labels show qualname header
2. Class instantiation creates edges to __init__
"""
import tempfile
from pathlib import Path
import pytest

from pycodemap.resolver import resolve_project, ResolverConfig
from pycodemap.graph import GraphConfig, build_call_graph
from pycodemap.renderer import RendererConfig, build_dot


def test_code_label_shows_qualname_header(tmp_path: Path) -> None:
    """When using --label code, the qualname should appear at the top of the node."""
    
    src = tmp_path / "mod.py"
    src.write_text(
        "def foo():\n"
        "    return 42\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(
        label_mode="code",
        show_line_numbers=False,
        max_snippet_lines=10,
    )
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # The label should contain the qualname "mod.foo" followed by the code
    assert "mod.foo" in dot
    # Code content may be wrapped in FONT tags for syntax highlighting
    assert "return" in dot and "42" in dot
    
    # Verify HTML table structure for code labels
    assert "<TABLE" in dot and "</TABLE>" in dot


def test_code_label_with_line_numbers_shows_qualname(tmp_path: Path) -> None:
    """Code labels with line numbers should still show qualname header."""
    
    src = tmp_path / "pkg" / "util.py"
    src.parent.mkdir(parents=True)
    (src.parent / "__init__.py").write_text("", encoding="utf-8")
    src.write_text(
        "def helper():\n"
        "    x = 1\n"
        "    return x\n",
        encoding="utf-8",
    )
    
    project = resolve_project(tmp_path)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(
        label_mode="code",
        show_line_numbers=True,
        max_snippet_lines=5,
    )
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # Should contain qualname
    assert "pkg.util.helper" in dot
    # Should contain line numbers
    assert "1:" in dot or "2:" in dot


def test_class_instantiation_creates_edge_to_init(tmp_path: Path) -> None:
    """When a class is instantiated, an edge to Class.__init__ should be created."""
    
    src = tmp_path / "classes.py"
    src.write_text(
        "class MyClass:\n"
        "    def __init__(self):\n"
        "        self.value = 42\n"
        "\n"
        "def create_instance():\n"
        "    obj = MyClass()\n"
        "    return obj\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Check that __init__ symbol exists
    assert "classes.MyClass.__init__" in project.symbols
    
    # Check calls: should have create_instance -> MyClass and create_instance -> MyClass.__init__
    calls_from_create = [c for c in project.calls if c.caller_id == "classes.create_instance"]
    
    # Should have at least 2 calls: one to MyClass (class), one to __init__
    assert len(calls_from_create) >= 2
    
    # Find the call to __init__
    init_calls = [c for c in calls_from_create if c.callee_id == "classes.MyClass.__init__"]
    assert len(init_calls) == 1
    
    init_call = init_calls[0]
    assert init_call.raw_callee == "MyClass.__init__"


def test_class_instantiation_without_init(tmp_path: Path) -> None:
    """Class instantiation without explicit __init__ should not crash."""
    
    src = tmp_path / "simple.py"
    src.write_text(
        "class SimpleClass:\n"
        "    pass\n"
        "\n"
        "def make_it():\n"
        "    return SimpleClass()\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Should not have __init__ symbol
    assert "simple.SimpleClass.__init__" not in project.symbols
    
    # Should have call to SimpleClass
    calls = [c for c in project.calls if c.caller_id == "simple.make_it"]
    class_calls = [c for c in calls if "SimpleClass" in (c.raw_callee or "")]
    
    # Should only have one call (to the class itself, not __init__)
    assert len(class_calls) == 1
    assert class_calls[0].callee_id == "simple.SimpleClass"


def test_nested_class_init_edge(tmp_path: Path) -> None:
    """Nested class instantiation should create edge to nested __init__."""
    
    src = tmp_path / "nested.py"
    src.write_text(
        "class Outer:\n"
        "    class Inner:\n"
        "        def __init__(self, val):\n"
        "            self.val = val\n"
        "\n"
        "def factory():\n"
        "    return Outer.Inner(10)\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Check nested __init__ exists
    assert "nested.Outer.Inner.__init__" in project.symbols
    
    # Check calls from factory
    calls = [c for c in project.calls if c.caller_id == "nested.factory"]
    
    # Should have calls to Inner and Inner.__init__
    init_calls = [c for c in calls if c.callee_id == "nested.Outer.Inner.__init__"]
    assert len(init_calls) == 1


def test_graph_rendering_with_init_edges(tmp_path: Path) -> None:
    """Integration test: class instantiation edges appear in DOT output."""
    
    src = tmp_path / "app.py"
    src.write_text(
        "class Service:\n"
        "    def __init__(self, config):\n"
        "        self.config = config\n"
        "\n"
        "def setup():\n"
        "    svc = Service('prod')\n"
        "    return svc\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="name")
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # Should have edge from setup to __init__
    # The exact format depends on sanitization, but __init__ should appear
    assert "__init__" in dot
    assert "setup" in dot
    # Check there's an edge (-> symbol)
    assert "->" in dot
