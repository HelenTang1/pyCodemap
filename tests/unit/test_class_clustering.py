"""
Test for class-based clustering with --node-type function --show-module.
"""
import tempfile
from pathlib import Path

from pycodemap.resolver import resolve_project, ResolverConfig
from pycodemap.graph import GraphConfig, build_call_graph
from pycodemap.renderer import RendererConfig, build_dot


def test_methods_clustered_by_class(tmp_path: Path) -> None:
    """
    When using --node-type function with cluster_by_module=True,
    methods should be grouped within their containing class cluster.
    """
    
    src = tmp_path / "service.py"
    src.write_text(
        "class DataService:\n"
        "    def load(self):\n"
        "        return self.parse()\n"
        "\n"
        "    def parse(self):\n"
        "        return {}\n"
        "\n"
        "    def save(self, data):\n"
        "        pass\n"
        "\n"
        "def helper():\n"
        "    svc = DataService()\n"
        "    return svc.load()\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    call_graph = build_call_graph(project, graph_cfg)
    
    # Check that methods have the class as their cluster
    load_node = call_graph.nodes.get("service.DataService.load")
    parse_node = call_graph.nodes.get("service.DataService.parse")
    save_node = call_graph.nodes.get("service.DataService.save")
    
    assert load_node is not None
    assert parse_node is not None
    assert save_node is not None
    
    # All methods should be clustered under the class qualname
    assert load_node.cluster == "service.DataService"
    assert parse_node.cluster == "service.DataService"
    assert save_node.cluster == "service.DataService"
    
    # Top-level function should be clustered by module
    helper_node = call_graph.nodes.get("service.helper")
    assert helper_node is not None
    assert helper_node.cluster == "service"


def test_dot_output_contains_class_clusters(tmp_path: Path) -> None:
    """
    DOT output should contain subgraph clusters for classes when
    using function-level nodes with clustering enabled.
    """
    
    src = tmp_path / "calculator.py"
    src.write_text(
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "    def subtract(self, a, b):\n"
        "        return a - b\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    renderer_cfg = RendererConfig(label_mode="name")
    
    dot = build_dot(project, graph_cfg, renderer_cfg)
    
    # Should contain a subgraph cluster for the Calculator class
    assert "subgraph" in dot
    assert "calculator.Calculator" in dot or "Calculator" in dot
    
    # Should contain the method nodes
    assert "add" in dot
    assert "subtract" in dot


def test_nested_class_methods_clustered(tmp_path: Path) -> None:
    """Nested class methods should be clustered by their immediate class."""
    
    src = tmp_path / "nested.py"
    src.write_text(
        "class Outer:\n"
        "    class Inner:\n"
        "        def method_a(self):\n"
        "            return 1\n"
        "\n"
        "        def method_b(self):\n"
        "            return 2\n"
        "\n"
        "    def outer_method(self):\n"
        "        return 3\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    call_graph = build_call_graph(project, graph_cfg)
    
    # Inner class methods should be clustered under Inner
    method_a = call_graph.nodes.get("nested.Outer.Inner.method_a")
    method_b = call_graph.nodes.get("nested.Outer.Inner.method_b")
    
    assert method_a is not None
    assert method_b is not None
    assert method_a.cluster == "nested.Outer.Inner"
    assert method_b.cluster == "nested.Outer.Inner"
    
    # Outer class method should be clustered under Outer
    outer_method = call_graph.nodes.get("nested.Outer.outer_method")
    assert outer_method is not None
    assert outer_method.cluster == "nested.Outer"


def test_no_clustering_when_disabled(tmp_path: Path) -> None:
    """
    When cluster_by_module=False, methods should not be grouped into clusters.
    """
    
    src = tmp_path / "plain.py"
    src.write_text(
        "class Widget:\n"
        "    def render(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    graph_cfg = GraphConfig(node_granularity="function", cluster_by_module=False)
    call_graph = build_call_graph(project, graph_cfg)
    
    render_node = call_graph.nodes.get("plain.Widget.render")
    assert render_node is not None
    assert render_node.cluster is None
