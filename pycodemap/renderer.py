# pycodemap/renderer.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Literal

from .resolver import ResolvedProject, Symbol
from .graph import CallGraph, GraphConfig, GraphNode, build_call_graph

try:
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.token import Token
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

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
        'fontname="Menlo,Consolas,monospace", margin="0.2,0.1"];'
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
            label_result = _node_label(node, project, renderer_config)
            
            if isinstance(label_result, tuple):  # HTML label
                html_label, _ = label_result
                lines.append(
                    f'{indent}"{_sanitize_id(node.id)}" [label=<{html_label}>];'
                )
            else:  # Plain text label
                lines.append(
                    f'{indent}"{_sanitize_id(node.id)}" [label="{_escape_label(label_result)}"];'
                )

        if cluster_id is not None:
            lines.append("  }")



    # Edges (original call graph)
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

def _build_html_label(header: str, code: str, start_line: Optional[int] = None) -> str:
    """
    Build an HTML-like label for Graphviz with syntax highlighting.
    Uses Pygments to tokenize Python code and applies colors.
    """
    lexer = PythonLexer()
    tokens = list(lexer.get_tokens(code))
    
    # Color mapping for Python tokens
    token_colors = {
        Token.Keyword: "#0000FF",           # Blue for keywords
        Token.Keyword.Namespace: "#0000FF",
        Token.Keyword.Type: "#0000FF",
        Token.Name.Builtin: "#0000FF",
        Token.Name.Function: "#000000",
        Token.Name.Class: "#267F99",        # Teal for classes
        Token.String: "#A31515",            # Red for strings
        Token.String.Doc: "#008000",        # Green for docstrings
        Token.Comment: "#008000",           # Green for comments
        Token.Comment.Single: "#008000",
        Token.Comment.Multiline: "#008000",
        Token.Number: "#098658",            # Dark green for numbers
        Token.Operator: "#000000",
        Token.Punctuation: "#000000",
    }
    
    # Build HTML table with header and code rows
    rows = [f'<TR><TD ALIGN="LEFT" VALIGN="MIDDLE"><B>{_escape_html(header)}</B></TD></TR>']
    
    # Process tokens line by line
    current_line = []
    line_num = start_line if start_line is not None else 1
    
    for token_type, value in tokens:
        if '\n' in value:
            parts = value.split('\n')
            for i, part in enumerate(parts):
                if part:
                    color = _get_token_color(token_type, token_colors)
                    if color:
                        current_line.append(f'<FONT COLOR="{color}">{_escape_html(part)}</FONT>')
                    else:
                        current_line.append(_escape_html(part))
                
                if i < len(parts) - 1:  # Not the last part (there's a newline)
                    line_text = ''.join(current_line) if current_line else '&#160;'
                    if start_line is not None:
                        line_text = f'{line_num}: {line_text}'
                        line_num += 1
                    rows.append(f'<TR><TD ALIGN="LEFT" VALIGN="MIDDLE">{line_text}</TD></TR>')
                    current_line = []
        else:
            if value:
                color = _get_token_color(token_type, token_colors)
                if color:
                    current_line.append(f'<FONT COLOR="{color}">{_escape_html(value)}</FONT>')
                else:
                    current_line.append(_escape_html(value))
    
    # Flush any remaining content
    if current_line:
        line_text = ''.join(current_line)
        if start_line is not None:
            line_text = f'{line_num}: {line_text}'
        rows.append(f'<TR><TD ALIGN="LEFT" VALIGN="MIDDLE">{line_text}</TD></TR>')
    
    return '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2" FIXEDSIZE="FALSE">' + ''.join(rows) + '</TABLE>'


def _get_token_color(token_type, color_map: dict) -> Optional[str]:
    """Get color for a token type, checking parent types if exact match not found."""
    if token_type in color_map:
        return color_map[token_type]
    # Check parent token types
    while token_type.parent:
        token_type = token_type.parent
        if token_type in color_map:
            return color_map[token_type]
    return None


def _escape_html(text: str) -> str:
    """Escape HTML special characters for use in Graphviz HTML-like labels."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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

def _node_label(node: GraphNode, project: ResolvedProject, cfg: RendererConfig):
    """
    Build the label for a node based on the renderer configuration.
    Returns either a string (plain text) or tuple (HTML label, is_html=True).
    """
    sym: Optional[Symbol] = (
        project.symbols.get(node.symbol_id) if node.symbol_id else None
    )

    # Code snippet label with syntax highlighting
    if cfg.label_mode == "code" and sym is not None and sym.snippet:
        lines = sym.snippet.splitlines()
        if cfg.max_snippet_lines > 0:
            lines = lines[: cfg.max_snippet_lines]

        snippet_text = "\n".join(lines)
        
        # Use Pygments HTML-like labels for syntax highlighting
        if PYGMENTS_AVAILABLE:
            try:
                html_label = _build_html_label(sym.qualname, snippet_text, sym.start_line if cfg.show_line_numbers else None)
                return (html_label, True)
            except Exception:
                pass  # Fall through to plain text
        
        # Fallback to plain text
        if cfg.show_line_numbers:
            start = sym.start_line
            lines = [f"{start + i}: {line}" for i, line in enumerate(lines)]
        label = sym.qualname + "\n" + "\n".join(lines)
        if not label.endswith("\n"):
            label += "\n"
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
