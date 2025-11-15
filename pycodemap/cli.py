from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .resolver import ResolverConfig, resolve_project


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyCodemap",
        description=(
            "Scan a Python project and build an intermediate call-graph model. "
        ),
    )
    parser.add_argument(
        "root",
        type=str,
        help="Path to the project root directory to scan.",
    )
    parser.add_argument(
        "--format",
        choices=("summary", "json"),
        default="summary",
        help="How to display the resolver result (default: summary).",
    )
    return parser


def main(argv: Any | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.root)
    project = resolve_project(root, config=ResolverConfig())

    if args.format == "json":
        data = _resolved_project_to_jsonable(project)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_summary(project)

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
