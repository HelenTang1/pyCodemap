from pathlib import Path
import textwrap

from pycodemap import resolve_project, ResolverConfig
from pycodemap import GraphConfig, build_call_graph


def _make_simple_project(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                return 1

            def g():
                return f()
            """
        ),
        encoding="utf-8",
    )


def test_build_function_level_graph(tmp_path: Path) -> None:
    _make_simple_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    graph = build_call_graph(project, cfg)

    node_ids = set(graph.nodes.keys())
    assert "pkg.a.f" in node_ids
    assert "pkg.a.g" in node_ids

    # g -> f edge should exist
    edges = {(e.src, e.dst) for e in graph.iter_edges()}
    assert ("pkg.a.g", "pkg.a.f") in edges

    # clustering by module
    assert graph.nodes["pkg.a.f"].cluster == "pkg.a"


def test_build_file_level_graph(tmp_path: Path) -> None:
    _make_simple_project(tmp_path)
    project = resolve_project(tmp_path, ResolverConfig())

    cfg = GraphConfig(node_granularity="file", cluster_by_module=True)
    graph = build_call_graph(project, cfg)

    node_ids = set(graph.nodes.keys())
    assert "pkg.a" in node_ids

    # Self-loop edges are dropped; file-level aggregation should not emit pkg.a -> pkg.a
    edges = {(e.src, e.dst) for e in graph.iter_edges()}
    assert ("pkg.a", "pkg.a") not in edges

    node = graph.nodes["pkg.a"]
    assert node.kind == "file"
    # top-level cluster should be "pkg"
    assert node.cluster == "pkg"


def test_transitive_pruning(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text(
        textwrap.dedent(
            """
            def f():
                return 1

            def g():
                return f()

            def h():
                f()
                g()
            """
        ),
        encoding="utf-8",
    )

    project = resolve_project(tmp_path, ResolverConfig())

    cfg_full = GraphConfig(node_granularity="function", prune_transitive=False)
    cfg_pruned = GraphConfig(node_granularity="function", prune_transitive=True)

    graph_full = build_call_graph(project, cfg_full)
    graph_pruned = build_call_graph(project, cfg_pruned)

    edges_full = {(e.src, e.dst) for e in graph_full.iter_edges()}
    edges_pruned = {(e.src, e.dst) for e in graph_pruned.iter_edges()}

    # All three direct edges should exist in the full graph:
    # g -> f, h -> f, h -> g
    assert ("pkg.a.g", "pkg.a.f") in edges_full
    assert ("pkg.a.h", "pkg.a.f") in edges_full
    assert ("pkg.a.h", "pkg.a.g") in edges_full

    # After transitive reduction, edge h -> f should be removed
    assert ("pkg.a.h", "pkg.a.f") not in edges_pruned
    assert ("pkg.a.h", "pkg.a.g") in edges_pruned
    assert ("pkg.a.g", "pkg.a.f") in edges_pruned
