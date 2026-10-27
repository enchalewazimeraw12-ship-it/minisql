# MiniSQL

**A small SQL compiler and query workbench that turns a practical `SELECT` subset into an execution plan and runs it against a sample database.**

MiniSQL is an educational project written in Python. It demonstrates the stages of a relational query compiler, from scanning and parsing through semantic analysis and plan generation, with both a command-line interface and a graphical query workbench.

## Features

- Compile supported SQL into a typed abstract syntax tree and three-address-code-style execution plan.
- Run queries against a JSON-backed, in-memory catalog.
- Inspect compiler output from the command line: tokens, annotated AST, symbol table, and execution plan.
- Query using `SELECT`, expressions and aliases, `WHERE`, `INNER JOIN`, `LEFT JOIN`, `ORDER BY`, and `LIMIT`.
- Use arithmetic, comparisons, boolean operators, parentheses, and SQL string literals with escaped quotes.
- Get line- and column-aware lexical, syntax, and semantic diagnostics.
- Explore and run queries in a Tkinter GUI with tabular results.

MiniSQL implements a focused SQL subset; it is not a general-purpose database and does not support features such as `INSERT`, `UPDATE`, `DELETE`, aggregates, or subqueries.

## Prerequisites & Installation

- Python 3.10 or newer
- Tkinter, included with many Python installations, to use the GUI
- No third-party Python packages are required

Clone the repository and change into its directory:

```bash
git clone https://github.com/enchalewazimeraw12-ship-it/minisql.git
cd minisql
```

There is no package-install step. Run the scripts from the repository root so the default database path (`data/sample_db.json`) is available.

## Usage

### Command line

Run a SQL file:

```bash
python main.py examples/valid.sql
```

Run a query directly:

```bash
python main.py -e "SELECT name, salary FROM employees ORDER BY salary DESC LIMIT 3;"
```

When a script contains invalid statements, MiniSQL reports their errors and skips
them while continuing with valid statements. The command exits with a nonzero
status if any errors were reported, even when valid statements produced results.

Start the interactive shell:

```bash
python main.py
```

In the shell, end statements with a semicolon and enter `exit` or `quit` to leave. The execution plan is shown by default in interactive mode.

Optional flags expose compiler stages or change execution behavior:

```bash
python main.py examples/valid.sql --tokens --ast --symtab --plan
python main.py examples/valid.sql --no-run
python main.py --db data/sample_db.json examples/valid.sql
```

### Graphical query workbench

Launch the Tkinter interface from the repository root:

```bash
python gui.py
```

The workbench starts with an example query. Use **Run Query** to compile and execute it, **Load Example** to load `examples/valid.sql`, or **Clear** to reset the editor. You can also run a query with **Ctrl+Enter**.

## Directory Structure

```text
minisql/
|-- main.py                 # Command-line interface and interactive shell
|-- gui.py                  # Tkinter query workbench
|-- minisql/                # Compiler and execution engine
|   |-- lexer.py            # Scanner and tokenization
|   |-- parser.py           # Recursive-descent parser
|   |-- ast_nodes.py        # AST node definitions and display
|   |-- semantic.py         # Catalog checks, types, and symbol tables
|   |-- codegen.py          # Execution-plan generation
|   |-- executor.py         # Plan execution and result formatting
|   |-- compiler.py         # Compiler pipeline and catalog loading
|   `-- errors.py           # Compiler and execution errors
|-- data/
|   `-- sample_db.json      # Sample database catalog and rows
|-- examples/
|   |-- valid.sql           # Example supported query
|   `-- errors.sql          # Example queries with errors
|-- tests/
|   `-- test_minisql.py     # Unit tests
|-- EXPLANATION.pdf         # Project explanation
`-- REPORT.md               # Language, architecture, and project report
```

## Testing & Documentation

Run the test suite using Python's built-in `unittest`:

```bash
python -m unittest discover -s tests -v
```

For more detail on the supported grammar, compiler phases, database format, and design limitations, see [REPORT.md](REPORT.md) and [EXPLANATION.pdf](EXPLANATION.pdf). The SQL files in `examples/` provide runnable and error-case examples.
