# pyCodemap
This project is a tool that automatically parses a Python project and generates a **visual call graph** as a single SVG file. The tool reads a project’s root directory, analyzes call relations between modules and functions, and outputs an SVG diagram that helps users understand the overall system structure.

Typical use cases:
- Quickly understanding an unfamiliar Python codebase
- Supporting code reading when studying research code or collaborating on large projects
- Visualizing how modules and functions depend on each other

# Dependencies
- Python == 3.10

# Install

## For Users
From the project directory:
```bash
$ pip install .
```

## For Development
```bash
$ pip install -e .[dev]
```

# Usage
After installation, you can use `pycodemap` from the command line to generate a call graph for your Python project:
```bash
$ pycodemap <project_directory> [options]
```

## Basic Examples

### Generate a summary (default)
```bash
$ pycodemap ./my_project
```

### Generate an SVG call graph
```bash
$ pycodemap ./my_project --format svg -o callgraph.svg
```

### Generate DOT format
```bash
$ pycodemap ./my_project --format dot -o callgraph.dot
```

## Command-line Options

### Output Format
- **`--format <format>`**: Output format: `summary` (default, human-readable), `json` (resolver output), `dot` (Graphviz DOT), or `svg` (rendered SVG)
- **`-o, --output <file>`**: Output file path for DOT/SVG formats (default: `callgraph.dot` or `callgraph.svg`)

### Graph Structure
- **`--node-type <level>`**: Node granularity: `function` (default) or `file`
- **`--no-cluster`**: Disable module-based clustering for nodes
- **`--prune-transitive`**: Remove transitive edges to simplify the call graph

### Node Labels
- **`--label <style>`**: Node label mode: `name` (default, short name), `qualname` (fully qualified name), or `code` (code snippet)
- **`--show-module`**: Append module names to node labels
- **`--show-line-numbers`**: Show line numbers in node labels
- **`--max-snippet-lines <n>`**: Maximum lines of code when `--label=code` (default: 6)

## Advanced Example
```bash
$ pycodemap ./my_project \
    --format svg \
    -o graph.svg \
    --node-type function \
    --prune-transitive \
    --label code \
    --show-module \
    --show-line-numbers \
    --max-snippet-lines 10
```

# Run test
```bash
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
