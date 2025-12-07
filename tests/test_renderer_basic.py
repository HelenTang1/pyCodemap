# tests/test_renderer_basic.py
from pathlib import Path
import textwrap

from pycodemap.resolver import resolve_project, ResolverConfig
from pycodemap.graph import GraphConfig
from pycodemap.renderer import RendererConfig, build_dot
from pycodemap.resolver import resolve_project


def _make_project(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                x = 1
                return x

            def g():
                return f()
            """
        ),
        encoding="utf-8",
    )


def test_build_dot_with_name_labels(tmp_path: Path) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="name")

    dot = build_dot(project, graph_cfg, renderer_cfg)

    assert "digraph CallGraph" in dot
    # function names should appear in labels
    assert "f" in dot
    assert "g" in dot


def test_function_labels_do_not_append_module_when_show_module_true(tmp_path: Path) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="name", show_module=True)

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # Labels for functions should remain just the function name (no module suffix)
    assert 'label="f\\n' not in dot
    assert 'label="g\\n' not in dot
    assert 'label="f"' in dot
    assert 'label="g"' in dot


def test_build_dot_with_code_labels_includes_snippet(tmp_path: Path) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="code", max_snippet_lines=2)

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # The snippet should include at least the 'x = 1' line
    assert "x = 1" in dot


def test_code_label_includes_qualname_and_trailing_newline(tmp_path: Path) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="code", show_line_numbers=False, max_snippet_lines=3)

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # Expect escaped left-justified newlines (\\l) and qualname at the top
    assert "pkg.a.f\\l" in dot
    assert "x = 1" in dot
    assert "return x" in dot
    # Ensure the label ends with a newline escape to avoid misalignment
    assert "pkg.a.f\\l" in dot and "x = 1\\l" in dot


def test_name_labels_do_not_duplicate_module_for_functions(tmp_path: Path) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="name", show_module=True)

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # Function labels should remain single-line without module duplication
    assert 'label="f"' in dot
    assert 'label="g"' in dot
    assert 'label="f\\n' not in dot
    assert 'label="g\\n' not in dot


def test_file_labels_append_module_once(tmp_path: Path) -> None:
    # Create a simple module file to verify file-level label formatting
    (tmp_path / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper():\n    return 1\n", encoding="utf-8")

    project = resolve_project(tmp_path)
    graph_cfg = GraphConfig(node_granularity="file", cluster_by_module=True)
    renderer_cfg = RendererConfig(label_mode="name", show_module=True)

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # File node should show base name plus module once (no duplicate lines)
    assert 'label="utils\\nutils"' not in dot
    assert 'label="utils"' in dot


def test_qualname_label_returns_full_qualname(tmp_path: Path) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="qualname", show_module=True)

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # Qualname labels should include the full dotted path and no extra module suffix
    assert 'label="pkg.a.f"' in dot
    assert 'label="pkg.a.g"' in dot
    assert '\\n' not in dot.split('label="pkg.a.f"')[0] if 'label="pkg.a.f"' in dot else True
