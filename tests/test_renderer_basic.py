# tests/test_renderer_basic.py
from pathlib import Path
import textwrap

from pycodemap.resolver import resolve_project, ResolverConfig
from pycodemap.graph import GraphConfig
from pycodemap.renderer import RendererConfig, build_dot


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
