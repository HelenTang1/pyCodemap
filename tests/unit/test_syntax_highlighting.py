"""
Tests for Pygments syntax highlighting in code labels.
"""
import textwrap
from pathlib import Path

from pycodemap.resolver import resolve_project
from pycodemap.graph import GraphConfig
from pycodemap.renderer import RendererConfig, build_dot


def test_code_label_with_syntax_highlighting(tmp_path: Path) -> None:
    """Code labels should use Pygments syntax highlighting when available."""
    
    src = tmp_path / "sample.py"
    src.write_text(
        textwrap.dedent(
            """
            def calculate(x, y):
                result = x + y
                return result
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(
        label_mode="code",
        show_line_numbers=False,
        max_snippet_lines=5,
    )
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # Should contain qualname header
    assert "sample.calculate" in dot
    
    # Should contain syntax-highlighted code (Pygments HTML tags)
    # Look for common Pygments spans like keyword (def, return)
    assert "def" in dot
    assert "return" in dot
    
    # When Pygments is available, should have HTML table with FONT COLOR tags for highlighting
    # Check for the HTML table structure and color formatting
    has_highlighting = (
        "<TABLE" in dot and
        "</TABLE>" in dot and
        '<FONT COLOR=' in dot  # Our HTML-like labels use FONT COLOR for syntax highlighting
    )
    
    # If Pygments is not installed, highlighting won't be present but code should still work
    assert "calculate" in dot
    # At minimum, we should have the HTML table for code labels
    assert "<TABLE" in dot
    # Most importantly, assert that highlighting is actually present
    assert has_highlighting, "Syntax highlighting with FONT COLOR tags should be present"


def test_code_label_with_line_numbers_and_highlighting(tmp_path: Path) -> None:
    """Syntax highlighting should work with line numbers enabled."""
    
    src = tmp_path / "module.py"
    src.write_text(
        textwrap.dedent(
            """
            class Widget:
                def render(self):
                    print("rendering")
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(
        label_mode="code",
        show_line_numbers=True,
        max_snippet_lines=3,
    )
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # Should have qualname
    assert "module.Widget.render" in dot
    
    # Should have line numbers (method starts at line 2)
    assert "2:" in dot or "3:" in dot
    
    # Should have code content
    assert "render" in dot


def test_code_label_truncation_with_highlighting(tmp_path: Path) -> None:
    """max_snippet_lines should truncate before highlighting."""
    
    src = tmp_path / "long.py"
    src.write_text(
        textwrap.dedent(
            """
            def process():
                step1 = 1
                step2 = 2
                step3 = 3
                step4 = 4
                return step4
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(
        label_mode="code",
        show_line_numbers=False,
        max_snippet_lines=2,  # Only first 2 lines
    )
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # Should contain first lines
    assert "step1" in dot
    
    # Should NOT contain later lines (truncated)
    assert "step4" not in dot
    assert "return step4" not in dot
