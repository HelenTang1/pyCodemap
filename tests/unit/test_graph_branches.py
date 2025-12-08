from pathlib import Path
import textwrap

from pycodemap.graph import (
    GraphConfig,
    GraphEdge,
    GraphNode,
    CallGraph,
    _prune_transitive_edges,
    _symbol_to_node_id,
    _make_node_for_symbol,
    build_call_graph,
)
from pycodemap.resolver import Symbol


def test_graph_edge_add_call_initializes_line_numbers() -> None:
    edge = GraphEdge(src="a", dst="b")
    edge.add_call(5)
    assert edge.call_count == 1
    assert edge.line_numbers == [5]


def test_build_call_graph_prunes_when_enabled(tmp_path: Path) -> None:
    src = tmp_path / "chain.py"
    src.write_text(
        textwrap.dedent(
            """
            def a():
                b()
                c()

            def b():
                c()

            def c():
                pass
            """
        ),
        encoding="utf-8",
    )
    from pycodemap.resolver import resolve_project
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="function", prune_transitive=True)
    graph = build_call_graph(project, cfg)
    # a->c should be pruned transitively
    assert ("chain.a", "chain.c") not in graph.edges


def test_build_call_graph_invalid_granularity_raises() -> None:
    from types import SimpleNamespace
    project = SimpleNamespace(symbols={}, calls=[])
    cfg = GraphConfig(node_granularity="invalid")
    try:
        build_call_graph(project, cfg)
    except ValueError:
        pass
    else:
        raise AssertionError("ValueError not raised for invalid granularity")
