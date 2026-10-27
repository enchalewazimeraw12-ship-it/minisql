#!/usr/bin/env python3
"""MiniSQL compiler CLI.
usage: python main.py query.sql [--db data/sample_db.json] [--tokens] [--ast] [--symtab] [--plan] [--no-run]
       python main.py -e "SELECT * FROM employees" ...
       python main.py            (interactive shell)
"""
import argparse
import sys
from minisql.compiler import compile_source, load_catalog
from minisql.executor import execute, format_table
from minisql.codegen import format_plan
from minisql.ast_nodes import dump_ast


def process(src, catalog, args):
    res = compile_source(src, catalog)
    if args.tokens:
        print("== TOKENS ==")
        for t in res.tokens:
            print("  ", t)
    if res.errors:
        print("== ERRORS ==")
        for e in res.errors:
            print("  ", e)
    for i, s in enumerate(res.valid_statements):
        print(f"\n######## Statement {i + 1} ########")
        if args.ast:
            print("== AST (annotated with types) ==")
            print(dump_ast(s))
        if args.symtab:
            print("== SYMBOL TABLE ==")
            print(res.valid_symtabs[i].dump())
        if args.plan:
            print("== THREE-ADDRESS CODE / EXECUTION PLAN ==")
            print(format_plan(res.plans[i]))
        if not args.no_run:
            print("== RESULT ==")
            h, rows = execute(res.plans[i], catalog)
            print(format_table(h, rows))
    return 1 if res.errors else 0


def main():
    ap = argparse.ArgumentParser(description="MiniSQL compiler")
    ap.add_argument("file", nargs="?")
    ap.add_argument("-e", "--execute", help="SQL text instead of a file")
    ap.add_argument("--db", default="data/sample_db.json")
    ap.add_argument("--tokens", action="store_true")
    ap.add_argument("--ast", action="store_true")
    ap.add_argument("--symtab", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--no-run", action="store_true")
    args = ap.parse_args()
    catalog = load_catalog(args.db)
    if args.execute or args.file:
        src = args.execute if args.execute else open(args.file, encoding="utf-8").read()
        sys.exit(process(src, catalog, args))
    print("MiniSQL shell. End statements with ';'. Type 'exit' to quit. (plan is shown by default)")
    args.plan = True
    buf = ""
    while True:
        try:
            line = input("sql> " if not buf else "...> ")
        except EOFError:
            break
        if line.strip().lower() in ("exit", "quit"):
            break
        buf += line + "\n"
        if ";" in line:
            process(buf, catalog, args)
            buf = ""


if __name__ == "__main__":
    main()
