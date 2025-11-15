# pyCodemap
This project is a tool that automatically parses a Python project and generates a **visual call graph** as a single SVG file. The tool reads a project’s root directory, analyzes call relations between modules and functions, and outputs an SVG diagram that helps users understand the overall system structure.

Typical use cases:
- Quickly understanding an unfamiliar Python codebase
- Supporting code reading when studying research code or collaborating on large projects
- Visualizing how modules and functions depend on each other

# Dependencies
- Python == 3.10

# Install(development)
```
$ pip install -e .[dev]
```

# Run test
```
$ python -m pytest -q --cov="pycodemap"  --cov-report=term-missing tests/
```

# Key Features
The initial version of the tool is designed around the following requirements: 

- **Full-project call graph**
  - Generate a *single* diagram for the entire project, automatically connecting all call relations.
- **Configurable node granularity**
  - Choose between:
    - **Function-level** nodes, or  
    - **File-level** nodes.
- **Module-based clustering**
  - When using function-level nodes, optionally group nodes by **module**, so that logical boundaries are clearer.
- **Transitive edge reduction**
  - Optionally remove **redundant transitive edges** to make the graph more readable.
- **Flexible node labels**
  - Nodes can display either:
    - The **definition name** (for high-level architecture overview), or  
    - A **code snippet** (for tracing code more directly).
- **Syntax-highlighted snippets**
  - When showing code snippets, syntax highlighting improves readability.
- **Line number display**
  - Snippets include the **original file line numbers**, making it easy to jump back to the source.
