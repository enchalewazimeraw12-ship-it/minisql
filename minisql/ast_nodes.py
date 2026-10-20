"""AST node definitions."""
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass(eq=False)
class Node:
    line: int = 0
    col: int = 0


# ---- expressions ----
@dataclass(eq=False)
class Literal(Node):
    value: Any = None
    type: Optional[str] = None          # INT / FLOAT / TEXT


@dataclass(eq=False)
class Column(Node):
    table: Optional[str] = None
    name: str = ""
    type: Optional[str] = None          # filled by semantic analysis
    alias: Optional[str] = None         # resolved table alias


@dataclass(eq=False)
class Binary(Node):
    op: str = ""
    left: Node = None
    right: Node = None
    type: Optional[str] = None


@dataclass(eq=False)
class Unary(Node):
    op: str = ""
    operand: Node = None
    type: Optional[str] = None


# ---- query structure ----
@dataclass(eq=False)
class TableRef(Node):
    name: str = ""
    alias: str = ""


@dataclass(eq=False)
class JoinClause(Node):
    kind: str = "INNER"
    table: TableRef = None
    on: Node = None


@dataclass(eq=False)
class SelectItem(Node):
    expr: Node = None
    alias: Optional[str] = None


@dataclass(eq=False)
class OrderItem(Node):
    expr: Node = None
    ascending: bool = True


@dataclass(eq=False)
class Select(Node):
    star: bool = False
    items: List[SelectItem] = field(default_factory=list)
    source: TableRef = None
    joins: List[JoinClause] = field(default_factory=list)
    where: Optional[Node] = None
    order_by: List[OrderItem] = field(default_factory=list)
    limit: Optional[int] = None


def expr_to_str(e):
    if isinstance(e, Literal):
        return repr(e.value)
    if isinstance(e, Column):
        return f"{e.table}.{e.name}" if e.table else e.name
    if isinstance(e, Binary):
        return f"({expr_to_str(e.left)} {e.op} {expr_to_str(e.right)})"
    if isinstance(e, Unary):
        return f"({e.op} {expr_to_str(e.operand)})"
    return "?"


def dump_ast(n, indent=0):
    """Pretty tree for the AST (used by --ast)."""
    p = "  " * indent
    out = []
    if isinstance(n, Select):
        out.append(f"{p}Select{' *' if n.star else ''}")
        for it in n.items:
            out.append(f"{p}  Item" + (f" AS {it.alias}" if it.alias else ""))
            out.append(dump_ast(it.expr, indent + 2))
        out.append(f"{p}  From {n.source.name} AS {n.source.alias}")
        for j in n.joins:
            out.append(f"{p}  {j.kind} Join {j.table.name} AS {j.table.alias}")
            out.append(f"{p}    On")
            out.append(dump_ast(j.on, indent + 3))
        if n.where:
            out.append(f"{p}  Where")
            out.append(dump_ast(n.where, indent + 2))
        for o in n.order_by:
            out.append(f"{p}  OrderBy {'ASC' if o.ascending else 'DESC'}")
            out.append(dump_ast(o.expr, indent + 2))
        if n.limit is not None:
            out.append(f"{p}  Limit {n.limit}")
    elif isinstance(n, Binary):
        out.append(f"{p}Binary({n.op})" + (f" : {n.type}" if n.type else ""))
        out.append(dump_ast(n.left, indent + 1))
        out.append(dump_ast(n.right, indent + 1))
    elif isinstance(n, Unary):
        out.append(f"{p}Unary({n.op})")
        out.append(dump_ast(n.operand, indent + 1))
    elif isinstance(n, Column):
        out.append(f"{p}Column({expr_to_str(n)})" + (f" : {n.type}" if n.type else ""))
    elif isinstance(n, Literal):
        out.append(f"{p}Literal({n.value!r}) : {n.type}")
    return "\n".join(out)
