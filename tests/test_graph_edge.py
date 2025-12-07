# tests/test_graph_extra.py
from pathlib import Path
from dataclasses import dataclass

import pytest

from pycodemap.resolver import Symbol, ResolverConfig, resolve_project
import pycodemap.graph as graph


def _make_symbol(
    id_: str,
    kind: str,
    module: str,
    file: Path | None = None,
) -> Symbol:
    """
    Helper to build a Symbol with just enough fields for the graph helpers.
    """
    if file is None:
        file = Path("dummy.py")
    name = id_.split(".")[-1]
    return Symbol(
        id=id_,
        kind=kind,
        name=name,
        qualname=id_,
        module=module,
        file=file,
        start_line=1,
        end_line=1,
        snippet=None,
    )


def test_build_call_graph_invalid_granularity_raises(tmp_path: Path) -> None:
    """
    Hit the 'unsupported node granularity' ValueError in build_call_graph.
    """
    (tmp_path / "mod.py").write_text(
        "def f():\n    return 1\n",
        encoding="utf-8",
    )
    project = resolve_project(tmp_path, ResolverConfig())

    cfg = graph.GraphConfig(node_granularity="weird")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        graph.build_call_graph(project, cfg)


def test_symbol_to_node_id_branches() -> None:
    """
    Exercise all branches in _symbol_to_node_id:
    - function granularity (function vs non-function)
    - file granularity (module vs other kinds)
    """
    cfg_fun = graph.GraphConfig(node_granularity="function")
    cfg_file = graph.GraphConfig(node_granularity="file")

    func_sym = _make_symbol("pkg.mod.f", "function", "pkg.mod")
    class_sym = _make_symbol("pkg.mod.C", "class", "pkg.mod")
    module_sym = _make_symbol("pkg.mod", "module", "pkg.mod")

    # function-level
    assert graph._symbol_to_node_id(func_sym, cfg_fun) == "pkg.mod.f"
    assert graph._symbol_to_node_id(class_sym, cfg_fun) is None  # non-function ignored

    # file-level
    assert graph._symbol_to_node_id(module_sym, cfg_file) == "pkg.mod"
    # non-module symbols map back to their module
    assert graph._symbol_to_node_id(func_sym, cfg_file) == "pkg.mod"
    assert graph._symbol_to_node_id(class_sym, cfg_file) == "pkg.mod"


def test_make_node_for_symbol_function_and_file() -> None:
    """
    Exercise _make_node_for_symbol for:
    - function-level nodes
    - file-level nodes; cluster_by_module True/False
    """
    func_sym = _make_symbol("pkg.mod.f", "function", "pkg.mod")
    module_sym = _make_symbol("pkg.mod", "module", "pkg.mod")

    # function-level
    cfg_fun = graph.GraphConfig(node_granularity="function", cluster_by_module=True)
    node_f = graph._make_node_for_symbol(func_sym, cfg_fun)
    assert node_f.kind == "function"
    assert node_f.cluster == "pkg.mod"
    assert node_f.label == "f"

    # file-level with clustering
    cfg_file_cluster = graph.GraphConfig(node_granularity="file", cluster_by_module=True)
    node_mod = graph._make_node_for_symbol(module_sym, cfg_file_cluster)
    assert node_mod.kind == "file"
    assert node_mod.module == "pkg.mod"
    # top-level package "pkg"
    assert node_mod.cluster == "pkg"

    # file-level without clustering
    cfg_file_no_cluster = graph.GraphConfig(node_granularity="file", cluster_by_module=False)
    node_mod2 = graph._make_node_for_symbol(module_sym, cfg_file_no_cluster)
    assert node_mod2.cluster is None


def test_prune_transitive_edges_removes_redundant_edge() -> None:
    """
    Build a tiny hand-crafted graph:
        a -> b -> c
         ------> c

    The direct edge a->c is redundant and should be pruned.
    """
    nodes = {
        "a": graph.GraphNode(id="a", label="a", kind="function"),
        "b": graph.GraphNode(id="b", label="b", kind="function"),
        "c": graph.GraphNode(id="c", label="c", kind="function"),
    }
    edges = {
        ("a", "b"): graph.GraphEdge(src="a", dst="b", call_count=1),
        ("b", "c"): graph.GraphEdge(src="b", dst="c", call_count=1),
        ("a", "c"): graph.GraphEdge(src="a", dst="c", call_count=1),
    }
    cg = graph.CallGraph(nodes=nodes, edges=edges)

    graph._prune_transitive_edges(cg)

    remaining = set(cg.edges.keys())
    # a->c must be removed; the others stay
    assert ("a", "c") not in remaining
    assert ("a", "b") in remaining
    assert ("b", "c") in remaining


def test_edge_labels_include_line_numbers_when_enabled(tmp_path: Path) -> None:
    """
    When --show-line-numbers is enabled, edges should show
    "<count>: [l1, l2, ...]" for the aggregated call sites.
    """

    src = tmp_path / "mod.py"
    src.write_text(
        "def foo():\n"
        "    bar()\n"      # line 2
        "    bar()\n"      # line 3
        "\n"
        "def bar():\n"
        "    return 1\n"   # line 6
        "\n"
        "foo()\n",        # line 8 (module-level call, not part of foo->bar edge)
        encoding="utf-8",
    )

    from pycodemap.resolver import resolve_project
    from pycodemap.graph import GraphConfig
    from pycodemap.renderer import RendererConfig, build_dot

    project = resolve_project(src)

    graph_cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    renderer_cfg = RendererConfig(
        label_mode="name",
        show_module=False,
        show_line_numbers=True,
        max_snippet_lines=6,
    )

    dot = build_dot(project, graph_cfg, renderer_cfg)

    # Expect the aggregated edge foo->bar to show count 2 and lines [2, 3]
    # Node IDs are fully-qualified (mod.foo -> mod.bar)
    assert '"mod.foo" -> "mod.bar" [label="2: [2, 3]"]' in dot
