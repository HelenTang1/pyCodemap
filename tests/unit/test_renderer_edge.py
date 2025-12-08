from pycodemap.resolver import resolve_project, ResolvedProject
from pycodemap.graph import GraphConfig, GraphNode, GraphEdge, CallGraph
from pycodemap.renderer import RendererConfig, build_dot
from pathlib import Path


def test_renderer_code_label_max_snippet_zero(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("def f():\n    x = 1\n    return x\n", encoding="utf-8")
    project = resolve_project(tmp_path)
    graph_cfg = GraphConfig(node_granularity="function")
    renderer_cfg = RendererConfig(label_mode="code", max_snippet_lines=0)
    dot = build_dot(project, graph_cfg, renderer_cfg)
    # Qualname header should still appear
    assert "m.f" in dot


def test_renderer_label_when_symbol_missing(monkeypatch) -> None:
    # Build a tiny call graph with a node lacking symbol_id to hit sym None path.
    node = GraphNode(id="n1", label="orphan", kind="function", module="mod")
    cg = CallGraph(nodes={"n1": node}, edges={})
    project = ResolvedProject(root=Path("."), symbols={}, calls=[])

    def fake_build_call_graph(project, cfg):  # pragma: no cover - monkeypatched use
        return cg

    monkeypatch.setattr("pycodemap.renderer.build_call_graph", fake_build_call_graph)
    dot = build_dot(project=project, graph_config=GraphConfig(), renderer_config=RendererConfig(show_module=True))
    assert "orphan" in dot


def test_renderer_edge_label_no_line_numbers(monkeypatch) -> None:
    nodes = {
        "n1": GraphNode(id="n1", label="a", kind="function"),
        "n2": GraphNode(id="n2", label="b", kind="function"),
    }
    edge = GraphEdge(src="n1", dst="n2", call_count=3, line_numbers=[])
    cg = CallGraph(nodes=nodes, edges={("n1", "n2"): edge})
    project = ResolvedProject(root=Path("."), symbols={}, calls=[])

    def fake_build_call_graph(project, cfg):  # pragma: no cover
        return cg

    monkeypatch.setattr("pycodemap.renderer.build_call_graph", fake_build_call_graph)
    dot = build_dot(project=project, graph_config=GraphConfig(), renderer_config=RendererConfig(show_line_numbers=True))
    assert 'label="3"' in dot