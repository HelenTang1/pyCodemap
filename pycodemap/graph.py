from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple, List, Set

from .resolver import ResolvedProject, Symbol


NodeGranularity = Literal["function", "file"]
NodeKind = Literal["function", "file"]


@dataclass
class GraphNode:
    """
    A node in the call graph.

    - id        : unique identifier in the graph
    - label     : human-readable label (e.g., short name or module name)
    - kind      : either "function" or "file"
    - module    : dotted module path (e.g., "pkg.sub.mod"), if available
    - file      : relative path to the file under the project root
    - symbol_id : original symbol ID from the resolver (for function/file nodes)
    - cluster   : cluster key (typically module/package) for grouping in renderer
    """

    id: str
    label: str
    kind: NodeKind
    module: Optional[str] = None
    file: Optional[Path] = None
    symbol_id: Optional[str] = None
    cluster: Optional[str] = None


@dataclass
class GraphEdge:
    """
    A directed edge in the call graph.

    We aggregate multiple call sites between the same src/dst pair.  In addition to
    `call_count`, we keep track of the line numbers where the calls occur so the
    renderer can optionally show them when `--show-line-numbers` is enabled.
    """

    src: str
    dst: str
    call_count: int = 0
    line_numbers: List[int] = None

    def add_call(self, lineno: int) -> None:
        if self.line_numbers is None:
            self.line_numbers = []
        self.call_count += 1
        self.line_numbers.append(lineno)


@dataclass
class CallGraph:
    """
    Graph model derived from a `ResolvedProject`.

    The `graph` module does not know about rendering; it focuses on:
    - selecting nodes (function vs file)
    - aggregating call edges
    - optionally pruning transitive edges
    """

    nodes: Dict[str, GraphNode]
    edges: Dict[Tuple[str, str], GraphEdge]

    def iter_edges(self) -> List[GraphEdge]:
        return list(self.edges.values())


@dataclass
class GraphConfig:
    """
    Configuration controlling how a call graph is built from a `ResolvedProject`.

    Parameters
    ----------
    node_granularity:
        "function"  -> function/method-level nodes
        "file"      -> per-module/file nodes
    cluster_by_module:
        If True, each node's `cluster` field is filled in with a module-based key
        suitable for use as a cluster ID in the renderer.
    prune_transitive:
        If True, run a simple transitive-reduction pass to remove edges (u, v)
        whenever there exists an alternate path from u to v.
    """

    node_granularity: NodeGranularity = "function"
    cluster_by_module: bool = True
    prune_transitive: bool = False


def build_call_graph(project: ResolvedProject, config: Optional[GraphConfig] = None) -> CallGraph:
    """
    Build a `CallGraph` from a `ResolvedProject`.

    This function is deterministic and pure: it does not read the filesystem and
    does not mutate the input project.
    """
    if config is None:
        config = GraphConfig()

    # ------------------------------------------------------------------
    # Step 1: create all potential nodes
    # ------------------------------------------------------------------
    nodes: Dict[str, GraphNode] = {}

    if config.node_granularity == "function":
        for sym in project.symbols.values():
            if sym.kind not in ("function", "method"):
                continue
            node_id = sym.id
            label = sym.name
            cluster = sym.module if config.cluster_by_module else None
            nodes[node_id] = GraphNode(
                id=node_id,
                label=label,
                kind="function",
                module= sym.module,
                file=sym.file,
                symbol_id=sym.id,
                cluster=cluster,
            )
    elif config.node_granularity == "file":
        # Use module symbols as file-level nodes.
        for sym in project.symbols.values():
            if sym.kind != "module":
                continue
            node_id = sym.id  # module name
            label = sym.module
            if config.cluster_by_module:
                # Group by top-level package (text before first dot), if any
                if "." in sym.module:
                    cluster = sym.module.split(".", 1)[0]
                else:
                    cluster = sym.module
            else:
                cluster = None
            nodes[node_id] = GraphNode(
                id=node_id,
                label=label,
                kind="file",
                module=sym.module,
                file=sym.file,
                symbol_id=sym.id,
                cluster=cluster,
            )
    else:
        raise ValueError(f"Unsupported node granularity: {config.node_granularity}")

    # ------------------------------------------------------------------
    # Step 2: build edges from call sites
    # ------------------------------------------------------------------
    edges: Dict[Tuple[str, str], GraphEdge] = {}

    for call in project.calls:
        caller_sym = project.symbols.get(call.caller_id)
        callee_sym = project.symbols.get(call.callee_id) if call.callee_id else None

        caller_node_id = _symbol_to_node_id(caller_sym, config)
        callee_node_id = _symbol_to_node_id(callee_sym, config)

        # If either side can't be mapped to a node at this granularity, skip it.
        if caller_node_id is None or callee_node_id is None:
            continue

        # Drop self-loops (caller and callee map to same node)
        if caller_node_id == callee_node_id:
            continue

        # Ensure nodes exist for any symbol that participated in a call but was
        # not part of the initial set (defensive; normally not needed).
        if caller_node_id not in nodes and caller_sym is not None:
            nodes[caller_node_id] = _make_node_for_symbol(caller_sym, config)
        if callee_node_id not in nodes and callee_sym is not None:
            nodes[callee_node_id] = _make_node_for_symbol(callee_sym, config)

        key = (caller_node_id, callee_node_id)
        edge = edges.get(key)
        if edge is None:
            edge = GraphEdge(src=caller_node_id, dst=callee_node_id, call_count=0, line_numbers=[])
            edges[key] = edge
        edge.add_call(call.location.lineno)

    graph = CallGraph(nodes=nodes, edges=edges)

    # ------------------------------------------------------------------
    # Step 3: optional transitive reduction
    # ------------------------------------------------------------------
    if config.prune_transitive:
        _prune_transitive_edges(graph)

    return graph


def _symbol_to_node_id(sym: Optional[Symbol], config: GraphConfig) -> Optional[str]:
    """
    Map a resolver `Symbol` to a graph node ID according to `GraphConfig`.
    """
    if sym is None:
        return None

    if config.node_granularity == "function":
        if sym.kind in ("function", "method"):
            return sym.id
        # Ignore other kinds at function-level granularity
        return None

    # file-level granularity: group by module
    if sym.kind == "module":
        return sym.id
    return sym.module


def _make_node_for_symbol(sym: Symbol, config: GraphConfig) -> GraphNode:
    """
    Fallback path: create a node for a symbol that wasn't in the initial node set.

    This is primarily defensive; for the normal flow, all needed nodes should be
    constructed in the first pass.
    """
    if config.node_granularity == "function":
        label = sym.name
        cluster = sym.module if config.cluster_by_module else None
        return GraphNode(
            id=sym.id,
            label=label,
            kind="function",
            module=sym.module,
            file=sym.file,
            symbol_id=sym.id,
            cluster=cluster,
        )
    else:
        module = sym.module if sym.kind != "module" else sym.id
        if config.cluster_by_module:
            if "." in module:
                cluster = module.split(".", 1)[0]
            else:
                cluster = module
        else:
            cluster = None
        return GraphNode(
            id=module,
            label=module,
            kind="file",
            module=module,
            file=sym.file,
            symbol_id=sym.id,
            cluster=cluster,
        )


def _prune_transitive_edges(graph: CallGraph) -> None:
    """
    Perform a simple transitive reduction on the graph's edges.

    For each edge (u, v), if there exists an alternate path from u to v using
    other edges, then (u, v) is removed.

    Complexity: O(|E| * (|V| + |E|)), which is fine for this project.
    """
    # Build adjacency lists
    adj: Dict[str, Set[str]] = {node_id: set() for node_id in graph.nodes.keys()}
    for edge in graph.edges.values():
        adj.setdefault(edge.src, set()).add(edge.dst)

    redundant: Set[Tuple[str, str]] = set()

    for key, edge in list(graph.edges.items()):
        u, v = edge.src, edge.dst
        if _has_alternate_path(adj, u, v, skip_edge=(u, v)):
            redundant.add((u, v))

    # Remove redundant edges
    for key in redundant:
        graph.edges.pop(key, None)


def _has_alternate_path(
    adj: Dict[str, Set[str]],
    start: str,
    target: str,
    skip_edge: Tuple[str, str],
) -> bool:
    """
    Return True if there exists a path from `start` to `target` that does NOT
    use the edge `skip_edge`.
    """
    from collections import deque

    visited: Set[str] = set()
    queue: "deque[str]" = deque()
    visited.add(start)
    queue.append(start)

    while queue:
        u = queue.popleft()
        for w in adj.get(u, ()):
            if (u, w) == skip_edge:
                continue
            if w == target:
                return True
            if w not in visited:
                visited.add(w)
                queue.append(w)

    return False
