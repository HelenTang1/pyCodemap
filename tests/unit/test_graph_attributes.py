from pathlib import Path
import textwrap

from pycodemap import resolve_project, ResolverConfig
from pycodemap import GraphConfig, build_call_graph


def test_graph_includes_class_attributes(tmp_path: Path) -> None:
    """Test that class attributes are included in function-level graph."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Person:
                name: str
                age: int
                
                def greet(self):
                    return f"Hello, {self.name}"
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="function", cluster_by_module=False)
    graph = build_call_graph(project, cfg)
    
    # Should have both method and attributes nodes
    node_ids = set(graph.nodes.keys())
    assert "test.Person.greet" in node_ids
    assert "test.Person.<attributes>" in node_ids
    
    # Verify the attributes node
    attr_node = graph.nodes["test.Person.<attributes>"]
    assert attr_node.kind == "attribute"
    assert attr_node.label == "<attributes>"


def test_graph_attributes_clustered_with_class(tmp_path: Path) -> None:
    """Test that attributes are clustered with their containing class."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Person:
                name: str
                age: int
                
                def greet(self):
                    return "Hello"
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    graph = build_call_graph(project, cfg)
    
    # Both method and attributes should be in the same cluster (the class)
    method_node = graph.nodes["test.Person.greet"]
    attr_node = graph.nodes["test.Person.<attributes>"]
    
    assert method_node.cluster == "test.Person"
    assert attr_node.cluster == "test.Person"


def test_graph_without_attributes(tmp_path: Path) -> None:
    """Test that classes without attributes don't get an attributes node in the graph."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class EmptyClass:
                def method(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="function", cluster_by_module=False)
    graph = build_call_graph(project, cfg)
    
    # Should have method but no attributes node
    node_ids = set(graph.nodes.keys())
    assert "test.EmptyClass.method" in node_ids
    assert "test.EmptyClass.<attributes>" not in node_ids


def test_graph_multiple_classes_with_attributes(tmp_path: Path) -> None:
    """Test that multiple classes each get their own attributes node."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Person:
                name: str
                age: int
            
            class Company:
                name: str
                employees: int
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="function", cluster_by_module=True)
    graph = build_call_graph(project, cfg)
    
    # Both classes should have their own attributes nodes
    node_ids = set(graph.nodes.keys())
    assert "test.Person.<attributes>" in node_ids
    assert "test.Company.<attributes>" in node_ids
    
    # They should be in different clusters
    person_attrs = graph.nodes["test.Person.<attributes>"]
    company_attrs = graph.nodes["test.Company.<attributes>"]
    assert person_attrs.cluster == "test.Person"
    assert company_attrs.cluster == "test.Company"


def test_graph_attributes_not_in_file_level(tmp_path: Path) -> None:
    """Test that attributes are not included in file-level graphs."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Person:
                name: str
                age: int
                
                def greet(self):
                    return "Hello"
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="file", cluster_by_module=False)
    graph = build_call_graph(project, cfg)
    
    # File-level graph should only have module nodes, no attributes
    node_ids = set(graph.nodes.keys())
    assert "test.Person.<attributes>" not in node_ids
    # Should have the module node
    assert "test" in node_ids or any("test" in nid for nid in node_ids)


def test_attributes_node_properties(tmp_path: Path) -> None:
    """Test that attributes node has correct properties."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Config:
                host: str
                port: int
                debug: bool
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    cfg = GraphConfig(node_granularity="function", cluster_by_module=False)
    graph = build_call_graph(project, cfg)
    
    attr_node = graph.nodes["test.Config.<attributes>"]
    
    # Verify node properties
    assert attr_node.id == "test.Config.<attributes>"
    assert attr_node.label == "<attributes>"
    assert attr_node.kind == "attribute"
    assert attr_node.module == "test"
    assert attr_node.symbol_id == "test.Config.<attributes>"
