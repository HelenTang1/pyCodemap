# pycodemap/cli.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .resolver import ResolverConfig, resolve_project
from .graph import GraphConfig
from .renderer import RendererConfig, build_dot, write_svg


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pycodemap",
        description=(
            "Scan a Python project and visualize call relations. "
            "Week 4: summary, JSON, DOT, or SVG output."
        ),
    )
    parser.add_argument(
        "root",
        type=str,
        help="Path to the project root directory to scan.",
    )
    parser.add_argument(
        "--format",
        choices=("summary", "json", "dot", "svg"),
        default="summary",
        help=(
            "Output format: 'summary' (human-readable), 'json' (resolver output), "
            "'dot' (Graphviz DOT), or 'svg' (rendered SVG). Default: summary."
        ),
    )

    # Graph / layout options
    parser.add_argument(
        "--node-type",
        choices=("function", "file"),
        default="function",
        help="Node granularity: function-level or file-level nodes (default: function).",
    )
    parser.add_argument(
        "--no-cluster",
        action="store_true",
        help="Disable module-based clusters for nodes.",
    )
    parser.add_argument(
        "--prune-transitive",
        action="store_true",
        help="Remove transitive edges to simplify the call graph.",
    )

    # Rendering options
    parser.add_argument(
        "--label",
        choices=("name", "qualname", "code"),
        default="name",
        help="Node label mode: short name, fully qualified name, or code snippet.",
    )
    parser.add_argument(
        "--show-module",
        action="store_true",
        help="Append module names to node labels.",
    )
    parser.add_argument(
        "--show-line-numbers",
        action="store_true",
        help="Show line numbers in node labels where applicable.",
    )
    parser.add_argument(
        "--max-snippet-lines",
        type=int,
        default=-1,
        help="Maximum lines of code to include when --label=code (default: 6).",
    )

    # Filtering options
    parser.add_argument(
        "--filter",
        type=str,
        help="Comma-separated keywords to filter nodes. Keeps nodes whose names contain any keyword.",
    )
    parser.add_argument(
        "--link-by-filter",
        action="store_true",
        help="When --filter is used, also keep nodes called by filtered nodes (has no effect without --filter).",
    )

    # Output file for DOT/SVG
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path for DOT/SVG formats. Defaults to callgraph.dot/svg.",
    )

    return parser


def main(argv: Any | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.root)
    project = resolve_project(root, config=ResolverConfig())

    # Parse filter keywords for all formats
    filter_keywords = []
    if args.filter is not None:
        filter_keywords = [kw.strip() for kw in args.filter.split(",") if kw.strip()]
        # If filter was provided but resulted in no keywords (e.g., empty string or whitespace only),
        # treat it as wanting to filter everything out (match nothing)
        if not filter_keywords and args.filter is not None:
            filter_keywords = ["__MATCH_NOTHING__"]

    # Simple modes do not need graph/renderer
    if args.format == "summary":
        if filter_keywords:
            project = _filter_project(project, filter_keywords, args.link_by_filter)
        _print_summary(project)
        return 0

    if args.format == "json":
        if filter_keywords:
            project = _filter_project(project, filter_keywords, args.link_by_filter)
        data = _resolved_project_to_jsonable(project)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    # Graph-based modes: DOT or SVG
    graph_cfg = GraphConfig(
        node_granularity=args.node_type,
        cluster_by_module=not args.no_cluster,
        prune_transitive=args.prune_transitive,
        filter_keywords=filter_keywords,
        link_by_filter=args.link_by_filter,
    )
    renderer_cfg = RendererConfig(
        label_mode=args.label,
        show_module=args.show_module,
        show_line_numbers=args.show_line_numbers,
        max_snippet_lines=args.max_snippet_lines,
    )

    dot = build_dot(project, graph_cfg, renderer_cfg)

    if args.format == "dot":
        output = Path(args.output) if args.output else Path("callgraph.dot")
        output.write_text(dot, encoding="utf-8")
        print(f"Wrote DOT to {output}")
        return 0

    # args.format == "svg"
    output = Path(args.output) if args.output else Path("callgraph.svg")
    write_svg(dot, output)
    print(f"Wrote SVG to {output}")
    return 0


def _resolved_project_to_jsonable(project) -> Dict[str, Any]:
    return {
        "root": str(project.root),
        "symbols": [
            {
                "id": s.id,
                "kind": s.kind,
                "name": s.name,
                "qualname": s.qualname,
                "module": s.module,
                "file": str(s.file),
                "start_line": s.start_line,
                "end_line": s.end_line,
            }
            for s in sorted(project.symbols.values(), key=lambda s: s.id)
        ],
        "calls": [
            {
                "caller_id": c.caller_id,
                "raw_callee": c.raw_callee,
                "callee_id": c.callee_id,
                "file": str(c.location.file),
                "lineno": c.location.lineno,
                "col_offset": c.location.col_offset,
            }
            for c in project.calls
        ],
    }


def _filter_project(project, filter_keywords, link_by_filter):
    """
    Filter a ResolvedProject based on keywords.
    
    Returns a new ResolvedProject with filtered symbols and calls.
    """
    from .graph import GraphConfig, build_call_graph
    
    # Build a graph with filtering enabled
    graph_cfg = GraphConfig(
        node_granularity="function",
        filter_keywords=filter_keywords,
        link_by_filter=link_by_filter,
    )
    graph = build_call_graph(project, graph_cfg)
    
    # Extract kept symbol IDs from the graph
    kept_symbol_ids = set()
    for node in graph.nodes.values():
        if node.symbol_id:
            kept_symbol_ids.add(node.symbol_id)
    
    # Also keep module symbols for kept functions
    kept_modules = set()
    for sym_id in kept_symbol_ids:
        sym = project.symbols.get(sym_id)
        if sym:
            kept_modules.add(sym.module)
    
    # Filter symbols
    filtered_symbols = {}
    for sym_id, sym in project.symbols.items():
        if sym_id in kept_symbol_ids or (sym.kind == "module" and sym.id in kept_modules):
            filtered_symbols[sym_id] = sym
    
    # Filter calls to only include calls between kept symbols
    filtered_calls = []
    for call in project.calls:
        if call.caller_id in kept_symbol_ids:
            if call.callee_id is None or call.callee_id in kept_symbol_ids:
                filtered_calls.append(call)
    
    # Create new ResolvedProject with filtered data
    from .resolver import ResolvedProject
    return ResolvedProject(
        root=project.root,
        symbols=filtered_symbols,
        calls=filtered_calls,
    )


def _print_summary(project) -> None:
    print(f"Project root: {project.root}")
    print(f"  Symbols   : {len(project.symbols)}")
    print(f"  Functions : {len(project.functions())}")
    print(f"  Calls     : {len(project.calls)}")
    modules = sorted({s.module for s in project.symbols.values()})
    print(f"  Modules   : {len(modules)}")
    for m in modules:
        print(f"    - {m}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
