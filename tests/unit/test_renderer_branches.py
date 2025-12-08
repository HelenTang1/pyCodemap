import importlib
from pathlib import Path
import builtins
import sys

import textwrap

import pycodemap.renderer as renderer
from pycodemap.resolver import resolve_project
from pycodemap.graph import GraphConfig, GraphNode, GraphEdge, CallGraph
from pycodemap.renderer import RendererConfig


def _make_project(tmp_path: Path) -> Path:
    src = tmp_path / "mod.py"
    src.write_text(
        textwrap.dedent(
            """
            def f():
                x = 1
                return x
            """
        ),
        encoding="utf-8",
    )
    return src


def test_fallback_when_highlight_raises(tmp_path: Path, monkeypatch) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path)
    monkeypatch.setattr(renderer, "PYGMENTS_AVAILABLE", True)
    monkeypatch.setattr(renderer, "_build_html_label", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    cfg = RendererConfig(label_mode="code", show_line_numbers=False, max_snippet_lines=2)
    dot = renderer.build_dot(project, GraphConfig(node_granularity="function"), cfg)
    # Should fall back to plain text (no HTML table)
    assert "<TABLE" not in dot
    assert "f" in dot


def test_import_guard_sets_pygments_unavailable(tmp_path: Path, monkeypatch) -> None:
    """Ensure ImportError during import sets PYGMENTS_AVAILABLE to False."""
    _make_project(tmp_path)
    project = resolve_project(tmp_path)

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("pygments"):
            raise ImportError("no pygments")
        return original_import(name, *args, **kwargs)

    # Force reload with ImportError
    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "pygments", raising=False)
    monkeypatch.delitem(sys.modules, "pygments.lexers", raising=False)
    monkeypatch.delitem(sys.modules, "pygments.token", raising=False)
    import importlib as _importlib  # local alias to avoid patched name confusion
    _importlib.reload(renderer)

    cfg = RendererConfig(label_mode="code", show_line_numbers=False, max_snippet_lines=1)
    dot = renderer.build_dot(project, GraphConfig(node_granularity="function"), cfg)
    # Should have fallen back to plain labels (no HTML)
    assert "<TABLE" not in dot
    assert renderer.PYGMENTS_AVAILABLE is False

    # Reset global to avoid leaking state into other tests
    renderer.PYGMENTS_AVAILABLE = True


def test_escape_label_handles_newlines_and_quotes() -> None:
    text = 'a\n"b" \\'
    escaped = renderer._escape_label(text)
    assert "\\l" in escaped  # newline becomes \l
    assert '\\"' in escaped  # quotes escaped
    assert "\\\\" in escaped  # backslash escaped


def test_html_label_without_line_numbers(tmp_path: Path, monkeypatch) -> None:
    _make_project(tmp_path)
    project = resolve_project(tmp_path)
    monkeypatch.setattr(renderer, "PYGMENTS_AVAILABLE", True)
    cfg = RendererConfig(label_mode="code", show_line_numbers=False, max_snippet_lines=2)
    dot = renderer.build_dot(project, GraphConfig(node_granularity="function"), cfg)
    assert "<TABLE" in dot and "</TABLE>" in dot
    # No explicit line numbers should be prefixed when show_line_numbers is False
    assert ": " not in dot


def test_edge_label_with_line_numbers(monkeypatch) -> None:
    from pycodemap.resolver import ResolvedProject
    nodes = {
        "n1": GraphNode(id="n1", label="a", kind="function"),
        "n2": GraphNode(id="n2", label="b", kind="function"),
    }
    edge = GraphEdge(src="n1", dst="n2", call_count=3, line_numbers=[5, 2, 5])
    cg = CallGraph(nodes=nodes, edges={("n1", "n2"): edge})
    project = ResolvedProject(root=Path("."), symbols={}, calls=[])

    def fake_build_call_graph(project, cfg):  # pragma: no cover
        return cg

    monkeypatch.setattr("pycodemap.renderer.build_call_graph", fake_build_call_graph)
    dot = renderer.build_dot(project=project, graph_config=GraphConfig(), renderer_config=RendererConfig(show_line_numbers=True))
    assert "3: [2, 5]" in dot


def test_edge_label_multiple_calls_plain(monkeypatch) -> None:
    from pycodemap.resolver import ResolvedProject
    nodes = {
        "n1": GraphNode(id="n1", label="a", kind="function"),
        "n2": GraphNode(id="n2", label="b", kind="function"),
    }
    edge = GraphEdge(src="n1", dst="n2", call_count=3, line_numbers=[1])
    cg = CallGraph(nodes=nodes, edges={("n1", "n2"): edge})
    project = ResolvedProject(root=Path("."), symbols={}, calls=[])

    def fake_build_call_graph(project, cfg):  # pragma: no cover
        return cg

    monkeypatch.setattr("pycodemap.renderer.build_call_graph", fake_build_call_graph)
    dot = renderer.build_dot(project=project, graph_config=GraphConfig(), renderer_config=RendererConfig(show_line_numbers=False))
    assert 'label="3"' in dot
