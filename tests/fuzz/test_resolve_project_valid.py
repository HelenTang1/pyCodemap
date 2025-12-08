import tempfile
from pathlib import Path
import string
import keyword

from hypothesis import given, settings, strategies as st

from pycodemap import resolve_project, ResolverConfig


@st.composite
def simple_module_source(draw):
    """
    Generate a tiny Python module with a handful of functions that may call
    each other.

    Returns (source_text, function_names).
    """
    # Restrict to lowercase letters so everything is a valid identifier
    ident_alphabet = string.ascii_lowercase
    identifier = st.text(
        alphabet=ident_alphabet,
        min_size=1,
        max_size=8,
    )
    identifier = identifier.filter(
        lambda s: s.isidentifier() and not keyword.iskeyword(s)
    )

    # Choose 1–5 unique function names
    func_names = draw(
        st.lists(identifier, min_size=1, max_size=5, unique=True)
    )

    bodies = []
    for fname in func_names:
        # How many calls inside this function?
        n_calls = draw(st.integers(min_value=0, max_value=4))
        if n_calls == 0:
            body_lines = ["    pass"]
        else:
            # Each call is to one of the known functions (could be self)
            callees = draw(
                st.lists(
                    st.sampled_from(func_names),
                    min_size=n_calls,
                    max_size=n_calls,
                )
            )
            body_lines = [f"    {c}()" for c in callees]

        func_def_lines = [f"def {fname}():", *body_lines, ""]
        bodies.extend(func_def_lines)

    module_source = "\n".join(bodies) + "\n"
    return module_source, set(func_names)

@given(data=simple_module_source())
@settings(max_examples=100, deadline=None)
def test_resolver_never_crashes_and_locations_are_consistent(data):
    src, func_names = data  # func_names isn't used yet but may be handy later
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Build a tiny package under root
        pkg = root / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        mod_path = pkg / "mod.py"
        mod_path.write_text(src, encoding="utf-8")

        # Act: run the resolver
        project = resolve_project(root, ResolverConfig())

        # Root should match root (resolved)
        assert project.root == root.resolve()

        # --- Symbol invariants ---
        # 1) unique IDs; 2) keys == sym.id; 3) file paths are valid & in range
        assert len(project.symbols) == len(set(project.symbols.keys()))
        for sym_id, sym in project.symbols.items():
            assert sym_id == sym.id

            # file is stored *relative* to project root
            assert not sym.file.is_absolute()
            assert ".." not in sym.file.parts

            full_path = project.root / sym.file
            assert full_path.is_file()

            lines = full_path.read_text(encoding="utf-8").splitlines()
            # allow empty files -> len(lines) can be 0; clamp with max(...)
            assert 1 <= sym.start_line <= sym.end_line <= max(len(lines), 1)

        # --- Call invariants ---
        for call in project.calls:
            # caller must exist
            assert call.caller_id in project.symbols

            loc = call.location
            # location file is also relative & safe
            assert not loc.file.is_absolute()
            assert ".." not in loc.file.parts

            full_path = loc.with_project_root(project.root)
            assert full_path.is_file()

            lines = full_path.read_text(encoding="utf-8").splitlines()
            assert 1 <= loc.lineno <= max(len(lines), 1)

            # if we resolved a callee, that symbol must exist too
            if call.callee_id is not None:
                assert call.callee_id in project.symbols

@given(data=simple_module_source())
@settings(max_examples=100, deadline=None)
def test_resolver_discovers_all_generated_functions(data):
    src, expected_func_names = data

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        pkg = root / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        mod_path = pkg / "mod.py"
        mod_path.write_text(src, encoding="utf-8")

        project = resolve_project(root, ResolverConfig())

        # Collect names of function-like symbols in this module
        functions_in_mod = {
            s.name
            for s in project.functions()
            if s.module == "pkg.mod"
        }

        # Our generator only creates simple top-level functions in pkg.mod,
        # so all generated names should be present.
        assert expected_func_names.issubset(functions_in_mod)
