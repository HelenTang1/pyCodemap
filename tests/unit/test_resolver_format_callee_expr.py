import ast

from pycodemap import resolver as r


def _parse_expr(src: str) -> ast.expr:
    # Parse "src" as an expression, e.g. "mod.f" or "x"
    module = ast.parse(src, mode="eval")
    return module.body


def test_format_callee_expr_simple_name_and_alias():
    expr = _parse_expr("f")
    assert r._format_callee_expr(expr, import_aliases={}) == "f"

    expr = _parse_expr("alias")
    aliases = {"alias": "pkg.a.f"}
    assert r._format_callee_expr(expr, import_aliases=aliases) == "pkg.a.f"


def test_format_callee_expr_attribute_on_alias():
    expr = _parse_expr("m.g")
    aliases = {"m": "pkg.mod"}
    # expect base alias + attribute
    assert r._format_callee_expr(expr, import_aliases=aliases) == "pkg.mod.g"


def test_format_callee_expr_dynamic_returns_none():
    # Call target is subscript, e.g., funcs[0]
    expr = _parse_expr("funcs[0]")
    assert r._format_callee_expr(expr, import_aliases={}) is None
