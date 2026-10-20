# MiniSQL — Relational Query Compiler
**Compiler Design Semester Project · Track H · Group 8**
Mekdela Amba University · College of Computing & Informatics · Department of Computer Science

Group members: 1. ____ (Scanner) 2. ____ (Parser) 3. ____ (Semantic) 4. ____ (Code Gen) 5. ____ (Testing & Docs)

---
## 1. Introduction
MiniSQL translates a core subset of SQL (`SELECT`, `WHERE`, `JOIN`) into an **execution plan written in Three-Address Code (TAC)**. A small executor runs the plan against an in-memory database so correctness can be demonstrated. Implemented in Python 3 (no external libraries), written from scratch.

## 2. Language supported
- `SELECT *` or a list of expressions with optional `AS alias`
- `FROM table [AS] alias`, `[INNER | LEFT] JOIN table [alias] ON condition` (any number of joins)
- `WHERE` with `AND`, `OR`, `NOT`, `= <> != < <= > >=`, `+ - * /`, parentheses
- `ORDER BY expr [ASC|DESC], ...` (may use a SELECT alias), `LIMIT n`
- Types: `INT`, `FLOAT`, `TEXT`; literals `10`, `3.5`, `'text'` (`''` escapes a quote); `-- comments`

## 3. Compiler phases (architecture)
```
SQL text → Scanner → tokens → Parser → AST → Semantic Analyzer (+Symbol Table) → typed AST
        → Code Generator → TAC execution plan → Executor → result table
```
| Phase | File | Role |
|---|---|---|
| Scanner | `minisql/lexer.py` | Master regex; keywords case-insensitive; tracks line/column; reports illegal chars and unterminated strings and keeps scanning |
| Parser | `minisql/parser.py`, `ast_nodes.py` | Recursive descent; builds AST; panic-mode recovery at `;` so several syntax errors are reported in one run |
| Semantic | `minisql/semantic.py` | Symbol table (alias → table → columns/types), scope & ambiguity checking, type rules |
| Code gen | `minisql/codegen.py` | AST → relational operators (SCAN, JOIN, FILTER, SORT, PROJECT, LIMIT, EMIT) with per-row TAC blocks |
| Executor | `minisql/executor.py` | Runs the plan (nested-loop join, stable multi-key sort) |

## 4. Part 1 — Scanner: tokens
| Class | Pattern |
|---|---|
| Keywords | SELECT FROM WHERE JOIN INNER LEFT ON AS AND OR NOT ORDER BY ASC DESC LIMIT |
| IDENT | `[A-Za-z_][A-Za-z0-9_]*` |
| INT / FLOAT | `\d+` / `\d+\.\d+` |
| STRING | `'(?:[^'\n]|'')*'` |
| Operators | `= <> != < <= > >=` and `( ) , . * ; + - /` |

## 5. Part 2 — Grammar (CFG, EBNF)
```
program     := { select_stmt [';'] }
select_stmt := 'SELECT' ( '*' | item {',' item} ) 'FROM' table_ref { join }
               [ 'WHERE' expr ] [ 'ORDER' 'BY' order {',' order} ] [ 'LIMIT' INT ]
item        := expr [ 'AS' IDENT ]
table_ref   := IDENT [ ['AS'] IDENT ]
join        := [ 'INNER' | 'LEFT' ] 'JOIN' table_ref 'ON' expr
order       := expr [ 'ASC' | 'DESC' ]
expr        := and_expr { 'OR' and_expr }
and_expr    := not_expr { 'AND' not_expr }
not_expr    := 'NOT' not_expr | comparison
comparison  := additive [ cmp_op additive ]
additive    := term { ('+'|'-') term }
term        := unary { ('*'|'/') unary }
unary       := '-' unary | primary
primary     := INT | FLOAT | STRING | IDENT ['.' IDENT] | '(' expr ')'
```
Precedence (low→high): `OR`, `AND`, `NOT`, comparison, `+ -`, `* /`, unary minus. Each rule is one parser method, so the grammar is LL(1).

## 6. Part 3 — Semantic analysis
Symbol table: `alias → table → {column: type}`, built from `FROM`/`JOIN`, checked against the catalog (schema).

| Rule | Error example |
|---|---|
| Table must exist | `unknown table 'employee'` |
| Alias must be unique | `duplicate table alias 'e'` |
| Column must exist in scope | `unknown column 'nam'` |
| Unqualified column must not match 2+ tables | `ambiguous column 'name' (found in: e, d)` |
| Qualifier must be a declared alias | `unknown table or alias 'x'` |
| Arithmetic needs numbers; result FLOAT if any operand FLOAT | `operator '+' needs numeric operands` |
| Comparison: number↔number or TEXT↔TEXT | `cannot compare FLOAT with TEXT using '>'` |
| `AND/OR/NOT` need BOOL; `WHERE`/`ON` must be BOOL | `WHERE condition must be a boolean expression, got INT` |

All errors are collected and shown with line/column; an unknown table does not cascade into extra errors.

## 7. Part 4 — Code generation
Relational operators are emitted as TAC-style plan lines; expressions inside them are compiled to `dest = a op b` blocks evaluated per row.

Example:
```sql
SELECT e.name, d.name AS department, e.salary * 12 AS yearly
FROM employees e JOIN departments d ON e.dept_id = d.id
WHERE d.city = 'Addis Ababa' AND e.age < 40
ORDER BY yearly DESC LIMIT 3;
```
```
t1 = SCAN employees AS e
t2 = SCAN departments AS d
t3 = INNER JOIN t1, t2
      [JOIN:ON]        r1 = e.dept_id == d.id        => r1
t4 = FILTER t3
      [FILTER:WHERE]   r1 = d.city == 'Addis Ababa'
                       r2 = e.age < 40
                       r3 = r1 AND r2                 => r3
t5 = SORT t4           (key: r1 = e.salary * 12, DESC)
t6 = PROJECT t5        (name, department, yearly)
t7 = LIMIT t6, 3
EMIT t7
```
Result:
```
| name   | department  | yearly |
| Tigist | Finance     | 216000 |
| Abebe  | Engineering | 144000 |
```

## 8. Testing
`python -m unittest discover -s tests -v` → **25 tests, all pass**: scanner (tokens, positions, errors), parser (missing FROM/ON/paren, recovery, precedence), semantic (all rules in §6), execution (WHERE, JOIN, LEFT JOIN, ORDER BY alias, multi-key sort, LIMIT, `*`, NOT/OR, division by zero).
Sample inputs: `examples/valid.sql`, `examples/errors.sql`.

## 9. User guide
```
python main.py examples/valid.sql --plan            # compile + run, show plan
python main.py -e "SELECT * FROM departments;"      # inline query
python main.py query.sql --tokens --ast --symtab --plan   # show every phase
python main.py --db mydb.json query.sql             # use another database
python main.py                                      # interactive shell
```
Database format (`data/sample_db.json`): `{ "table": { "columns": {"id":"INT",...}, "rows": [[1,...], ...] } }` (`null` = NULL).

## 10. Limitations / future work
No GROUP BY/aggregates, subqueries, or INSERT/UPDATE; joins are nested-loop (no optimizer); a possible extension is predicate push-down before joins.

## 11. Work division
Member 1 Scanner · Member 2 Parser/AST · Member 3 Semantic/Symbol table · Member 4 Code generation/Executor · Member 5 Testing & Documentation.
