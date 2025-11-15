"""
py_callgraphviz package.

Week 1 – minimal subset:
- Public data structures for the resolver
- `resolve_project` convenience import

Later milestones will add the `graph` and `renderer` modules.
"""

from .resolver import (
    SourceLocation,
    SymbolKind,
    Symbol,
    Call,
    ResolvedProject,
    ResolverConfig,
    resolve_project,
)

__all__ = [
    "SourceLocation",
    "SymbolKind",
    "Symbol",
    "Call",
    "ResolvedProject",
    "ResolverConfig",
    "resolve_project",
]

__version__ = "0.1.0"
