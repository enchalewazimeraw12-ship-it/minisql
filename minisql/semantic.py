"""Part 3 - Semantic analysis: symbol table, scope checking, type validation."""
from .ast_nodes import *
from .errors import SemanticError

NUMERIC = {"INT", "FLOAT"}


class Catalog:
    """Database schema + data: {table: {'columns': {name: TYPE}, 'rows': [[...]]}}."""

    def __init__(self, tables):
        self.tables = {}
        for name, t in tables.items():
            cols = {c.lower(): ty.upper() for c, ty in t["columns"].items()}
            self.tables[name.lower()] = {"columns": cols, "rows": t.get("rows", [])}

    def has(self, name):
        return name in self.tables

    def columns(self, name):
        return self.tables[name]["columns"]


class SymbolTable:
    """Query scope: alias -> table name. Column lookup goes through the catalog schema."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.aliases = {}          # alias -> table

    def declare(self, alias, table):
        self.aliases[alias] = table

    def lookup_column(self, table_alias, name):
        """returns list of (alias, type) matches"""
        if table_alias is not None:
            tbl = self.aliases.get(table_alias)
            if tbl is None:
                return None
            ty = self.catalog.columns(tbl).get(name)
            return [(table_alias, ty)] if ty else []
        return [(a, self.catalog.columns(t)[name]) for a, t in self.aliases.items()
                if name in self.catalog.columns(t)]

    def dump(self):
        lines = ["Alias   Table        Columns"]
        for a, t in self.aliases.items():
            cols = ", ".join(f"{c}:{ty}" for c, ty in self.catalog.columns(t).items())
            lines.append(f"{a:<7} {t:<12} {cols}")
        return "\n".join(lines)


class Analyzer:
    def __init__(self, catalog):
        self.catalog = catalog
        self.errors = []
        self.symtab = None

    def err(self, msg, node):
        self.errors.append(SemanticError(msg, node.line, node.col))

    def analyze(self, select):
        self.symtab = SymbolTable(self.catalog)
        self.bad_scope = False
        self.declare(select.source)
        for j in select.joins:
            self.declare(j.table)
        # ON conditions can see everything declared so far; to keep it simple we allow the whole query scope
        for j in select.joins:
            ty = self.expr(j.on)
            if ty not in (None, "BOOL"):
                self.err(f"JOIN condition must be a boolean expression, got {ty}", j.on)
        if select.star:
            select.items = []
            for a, t in self.symtab.aliases.items():
                for c, ty in self.catalog.columns(t).items():
                    col = Column(line=select.line, col=select.col, table=a, name=c, type=ty, alias=a)
                    select.items.append(SelectItem(line=select.line, col=select.col, expr=col, alias=c))
            select.star = False
        else:
            for it in select.items:
                ty = self.expr(it.expr)
                if ty == "BOOL":
                    pass  # allowed: boolean result column
        names = set()
        for it in select.items:
            if it.alias is None:
                it.alias = it.expr.name if isinstance(it.expr, Column) else expr_to_str(it.expr)
            names.add(it.alias)
        if select.where is not None:
            ty = self.expr(select.where)
            if ty not in (None, "BOOL"):
                self.err(f"WHERE condition must be a boolean expression, got {ty}", select.where)
        by_alias = {it.alias: it.expr for it in select.items}
        for o in select.order_by:
            # ORDER BY may refer to a SELECT alias (e.g. ORDER BY yearly)
            if isinstance(o.expr, Column) and o.expr.table is None and o.expr.name in by_alias:
                o.expr = by_alias[o.expr.name]
            else:
                self.expr(o.expr)
        return self.symtab

    def declare(self, ref):
        if not self.catalog.has(ref.name):
            self.err(f"unknown table '{ref.name}'", ref)
            self.bad_scope = True      # suppress cascading column errors
            return
        if ref.alias in self.symtab.aliases:
            self.err(f"duplicate table alias '{ref.alias}'", ref)
            return
        self.symtab.declare(ref.alias, ref.name)

    def expr(self, e):
        """Returns the type of e (INT, FLOAT, TEXT, BOOL) or None after an error."""
        if isinstance(e, Literal):
            return e.type
        if isinstance(e, Column):
            if self.bad_scope:
                return None
            matches = self.symtab.lookup_column(e.table, e.name)
            if matches is None:
                self.err(f"unknown table or alias '{e.table}'", e)
                return None
            if not matches:
                self.err(f"unknown column '{expr_to_str(e)}'", e)
                return None
            if len(matches) > 1:
                where = ", ".join(a for a, _ in matches)
                self.err(f"ambiguous column '{e.name}' (found in: {where}); qualify it with an alias", e)
                return None
            e.alias, e.type = matches[0]
            e.table = e.alias
            return e.type
        if isinstance(e, Unary):
            t = self.expr(e.operand)
            if t is None:
                return None
            if e.op == "NOT":
                if t != "BOOL":
                    self.err(f"NOT needs a boolean operand, got {t}", e)
                    return None
                e.type = "BOOL"
            else:
                if t not in NUMERIC:
                    self.err(f"unary minus needs a numeric operand, got {t}", e)
                    return None
                e.type = t
            return e.type
        if isinstance(e, Binary):
            lt, rt = self.expr(e.left), self.expr(e.right)
            if lt is None or rt is None:
                return None
            if e.op in ("AND", "OR"):
                if lt != "BOOL" or rt != "BOOL":
                    self.err(f"{e.op} needs boolean operands, got {lt} and {rt}", e)
                    return None
                e.type = "BOOL"
            elif e.op in ("+", "-", "*", "/"):
                if lt not in NUMERIC or rt not in NUMERIC:
                    self.err(f"operator '{e.op}' needs numeric operands, got {lt} and {rt}", e)
                    return None
                e.type = "FLOAT" if "FLOAT" in (lt, rt) or e.op == "/" and False else \
                         ("FLOAT" if lt == "FLOAT" or rt == "FLOAT" else "INT")
            else:  # comparison
                ok = (lt in NUMERIC and rt in NUMERIC) or (lt == rt == "TEXT")
                if not ok:
                    self.err(f"cannot compare {lt} with {rt} using '{e.op}'", e)
                    return None
                e.type = "BOOL"
            return e.type
        return None


def analyze(select, catalog):
    a = Analyzer(catalog)
    symtab = a.analyze(select)
    return symtab, a.errors
