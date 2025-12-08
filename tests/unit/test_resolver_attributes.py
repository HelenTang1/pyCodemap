from pathlib import Path
import textwrap
import pytest
from pycodemap import resolve_project, ResolverConfig


def test_class_attributes_are_tracked(tmp_path: Path) -> None:
    """Test that class attributes with type hints are tracked as a single node."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Person:
                name: str
                age: int
                city: str
                
                def greet(self):
                    return f"Hello, {self.name}"
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Check that we have the class and method
    assert "test.Person" in project.symbols
    assert "test.Person.greet" in project.symbols
    
    # Check that we have a single attributes node
    assert "test.Person.<attributes>" in project.symbols
    
    # Verify the attributes node
    attr_sym = project.symbols["test.Person.<attributes>"]
    assert attr_sym.kind == "attribute"
    assert attr_sym.name == "<attributes>"
    assert "name" in attr_sym.snippet
    assert "age" in attr_sym.snippet
    assert "city" in attr_sym.snippet


def test_function_level_annotations_not_tracked(tmp_path: Path) -> None:
    """Test that annotated variables inside functions are not tracked as attributes."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            def process():
                result: int = 42
                name: str = "test"
                return result
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Should only have module and function symbols, no attributes
    assert "test.process" in project.symbols
    attribute_symbols = [s for s in project.symbols.values() if s.kind == "attribute"]
    assert len(attribute_symbols) == 0


def test_method_level_annotations_not_tracked(tmp_path: Path) -> None:
    """Test that annotated variables inside methods are not tracked as attributes."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Calculator:
                def compute(self):
                    result: int = 10
                    temp: float = 3.14
                    return result
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Should have class and method, but no attributes
    assert "test.Calculator" in project.symbols
    assert "test.Calculator.compute" in project.symbols
    attribute_symbols = [s for s in project.symbols.values() if s.kind == "attribute"]
    assert len(attribute_symbols) == 0


def test_class_without_attributes(tmp_path: Path) -> None:
    """Test that classes without attributes don't get an attributes node."""
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
    
    # Should have class and method, but no attributes node
    assert "test.EmptyClass" in project.symbols
    assert "test.EmptyClass.method" in project.symbols
    assert "test.EmptyClass.<attributes>" not in project.symbols


def test_multiple_classes_with_attributes(tmp_path: Path) -> None:
    """Test that each class gets its own attributes node."""
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
                revenue: float
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Both classes should have their own attributes nodes
    assert "test.Person.<attributes>" in project.symbols
    assert "test.Company.<attributes>" in project.symbols
    
    # Verify Person attributes
    person_attrs = project.symbols["test.Person.<attributes>"]
    assert "name" in person_attrs.snippet
    assert "age" in person_attrs.snippet
    
    # Verify Company attributes
    company_attrs = project.symbols["test.Company.<attributes>"]
    assert "name" in company_attrs.snippet
    assert "employees" in company_attrs.snippet
    assert "revenue" in company_attrs.snippet


def test_nested_class_attributes(tmp_path: Path) -> None:
    """Test that nested classes with attributes are tracked correctly."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Outer:
                outer_attr: str
                
                class Inner:
                    inner_attr: int
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Both outer and inner classes should have attributes nodes
    assert "test.Outer.<attributes>" in project.symbols
    assert "test.Outer.Inner.<attributes>" in project.symbols
    
    # Verify the attributes are separate
    outer_attrs = project.symbols["test.Outer.<attributes>"]
    assert "outer_attr" in outer_attrs.snippet
    
    inner_attrs = project.symbols["test.Outer.Inner.<attributes>"]
    assert "inner_attr" in inner_attrs.snippet


def test_attributes_line_range(tmp_path: Path) -> None:
    """Test that the attributes node has correct line range."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class Config:
                host: str
                port: int
                timeout: float
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    attr_sym = project.symbols["test.Config.<attributes>"]
    
    # Should span from first to last attribute
    # Note: textwrap.dedent preserves the first blank line, so line numbers start at 3
    assert attr_sym.start_line == 3  # "host: str"
    assert attr_sym.end_line == 5    # "timeout: float"
    
    # Snippet should contain all three attributes
    lines = attr_sym.snippet.strip().split("\n")
    assert len(lines) == 3
    assert "host" in attr_sym.snippet
    assert "port" in attr_sym.snippet
    assert "timeout" in attr_sym.snippet


def test_mixed_class_with_methods_and_attributes(tmp_path: Path) -> None:
    """Test a class with both attributes and methods."""
    src = tmp_path / "test.py"
    src.write_text(
        textwrap.dedent(
            """
            class User:
                username: str
                email: str
                
                def __init__(self, username: str, email: str):
                    self.username = username
                    self.email = email
                
                def display(self):
                    return f"{self.username} <{self.email}>"
            """
        ),
        encoding="utf-8",
    )
    
    project = resolve_project(src)
    
    # Should have class, attributes node, and methods
    assert "test.User" in project.symbols
    assert "test.User.<attributes>" in project.symbols
    assert "test.User.__init__" in project.symbols
    assert "test.User.display" in project.symbols
    
    # Attributes node should only contain the class-level attributes
    attr_sym = project.symbols["test.User.<attributes>"]
    assert "username: str" in attr_sym.snippet or "username:str" in attr_sym.snippet.replace(" ", "")
    assert "email: str" in attr_sym.snippet or "email:str" in attr_sym.snippet.replace(" ", "")
    # Should not contain method code
    assert "def __init__" not in attr_sym.snippet
    assert "def display" not in attr_sym.snippet
