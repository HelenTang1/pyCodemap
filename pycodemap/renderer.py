# pycodemap/renderer.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Literal

from .resolver import ResolvedProject, Symbol
from .graph import CallGraph, GraphConfig, GraphNode, build_call_graph

LabelMode = Literal["name", "qualname", "code"]


@dataclass
class RendererConfig:
    """
    Controls how nodes and edges are rendered into a DOT graph.

    label_mode:
        "name"     -> use symbol.name
        "qualname" -> use symbol.qualname
        "code"     -> use a code snippet (up to max_snippet_lines)
    show_module:
        If True, append the module name to the label.
    show_line_numbers:
        If True, line information is shown for code/labels when possible.
    max_snippet_lines:
        Maximum number of lines of code to include for label_mode="code".
    """

    label_mode: LabelMode = "name"
    show_module: bool = False
    show_line_numbers: bool = False
    max_snippet_lines: int = 6


def build_dot(
    project: ResolvedProject,
    graph_config: GraphConfig,
    renderer_config: RendererConfig,
) -> str:
    """
    Build a Graphviz DOT string from a resolved project.

    This is a pure function: it does not touch the filesystem or run Graphviz.
    """
    call_graph: CallGraph = build_call_graph(project, graph_config)

    lines: List[str] = []
    lines.append("digraph CallGraph {")
    lines.append('  rankdir=LR;')
    lines.append(
        '  node [shape=box, style=filled, fillcolor="#f6f6f6", '
        'fontname="Menlo,Consolas,monospace"];'
    )
    lines.append('  edge [fontname="Menlo,Consolas,monospace"];')

    # Group nodes by cluster so the renderer can draw module-based clusters.
    clusters: Dict[Optional[str], List[GraphNode]] = {}
    for node in call_graph.nodes.values():
        clusters.setdefault(node.cluster, []).append(node)

    # Nodes (optionally grouped into subgraphs for clusters)
    for cluster_id, nodes in sorted(clusters.items(), key=lambda kv: str(kv[0])):
        if cluster_id is not None:
            subgraph_name = f"cluster_{_sanitize_id(cluster_id)}"
            lines.append(f'  subgraph "{subgraph_name}" {{')
            lines.append(f'    label="{_escape_label(cluster_id)}";')
            lines.append("    style=rounded;")
            indent = "    "
        else:
            indent = "  "

        for node in sorted(nodes, key=lambda n: n.id):
            label = _node_label(node, project, renderer_config)
            lines.append(
                f'{indent}"{_sanitize_id(node.id)}" [label="{_escape_label(label)}"];'
            )

        if cluster_id is not None:
            lines.append("  }")

    # Edges
    for edge in sorted(call_graph.iter_edges(), key=lambda e: (e.src, e.dst)):
        src = _sanitize_id(edge.src)
        dst = _sanitize_id(edge.dst)

        if renderer_config.show_line_numbers:
            nums = sorted(set(edge.line_numbers or []))
            if nums:
                num_list = ", ".join(str(n) for n in nums)
                label = f"{edge.call_count}: [{num_list}]"
            else:
                label = str(edge.call_count)
            lines.append(f'  "{src}" -> "{dst}" [label="{label}"];')
        else:
            if edge.call_count > 1:
                lines.append(f'  "{src}" -> "{dst}" [label="{edge.call_count}"];')
            else:
                lines.append(f'  "{src}" -> "{dst}";')

    lines.append("}")
    return "\n".join(lines)


def write_svg(dot: str, output: Path) -> None:  # pragma: no cover
    """
    Render a DOT string to an SVG file using the `graphviz` package.

    This requires the Graphviz `dot` binary to be installed on the system.
    """
    from graphviz import Source

    src = Source(dot)
    svg_bytes = src.pipe(format="svg")
    output.write_bytes(svg_bytes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_label(node: GraphNode, project: ResolvedProject, cfg: RendererConfig) -> str:
    """
    Build the label text for a node based on the renderer configuration.
    """
    sym: Optional[Symbol] = (
        project.symbols.get(node.symbol_id) if node.symbol_id else None
    )

    # Code snippet label
    if cfg.label_mode == "code" and sym is not None and sym.snippet:
        lines = sym.snippet.splitlines()
        if cfg.max_snippet_lines > 0:
            lines = lines[: cfg.max_snippet_lines]

        if cfg.show_line_numbers:
            start = sym.start_line
            lines = [f"{start + i}: {line}" for i, line in enumerate(lines)]

        label = "\n".join(lines)
        return label

    # Name / qualname label
    if sym is not None:
        if cfg.label_mode == "qualname":
            return sym.qualname
        base = sym.name
    else:
        base = node.label

    extras: List[str] = []
    if cfg.show_module and node.module and getattr(node, "kind", None) == "file":
        # Avoid redundant module when it already equals the base or endswith base
        if node.module != base and not node.module.endswith(f".{base}"):
            extras.append(node.module)
    if cfg.show_line_numbers and sym is not None:
        extras.append(f"lines {sym.start_line}-{sym.end_line}")

    if extras:
        return base + "\\n" + " · ".join(extras)
    return base


def _escape_label(text: str) -> str:
    """
    Escape a label string for use in DOT.

    - backslashes and quotes are escaped
    - newlines become `\\l` (Graphviz left-justified line break)
    """
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\n", "\\l")
    return text


def _sanitize_id(s: str) -> str:
    """
    Sanitize an identifier for use in DOT.

    Since we always quote IDs, this only needs to escape quotes.
    """
    return s.replace('"', '\\"')
