"""Executes the TAC execution plan against the in-memory catalog (so we can demonstrate 'successful test execution')."""
from .errors import ExecError


def run_block(block, env):
    tmp = {}

    def val(o):
        k, v = o
        return v if k == "const" else (env[v] if k == "col" else tmp[v])

    for ins in block.code:
        x = val(ins.a)
        if ins.b is None:
            if ins.op == "NOT":
                tmp[ins.dest] = None if x is None else (not x)
            else:  # NEG
                tmp[ins.dest] = None if x is None else -x
            continue
        y = val(ins.b)
        op = ins.op
        if op == "AND":
            r = bool(x) and bool(y)
        elif op == "OR":
            r = bool(x) or bool(y)
        elif x is None or y is None:           # SQL-ish NULL: arithmetic -> NULL, comparison -> false
            r = None if op in "+-*/" else False
        elif op == "+": r = x + y
        elif op == "-": r = x - y
        elif op == "*": r = x * y
        elif op == "/":
            if y == 0:
                raise ExecError("division by zero")
            r = x / y
        elif op == "==": r = x == y
        elif op == "!=": r = x != y
        elif op == "<": r = x < y
        elif op == "<=": r = x <= y
        elif op == ">": r = x > y
        elif op == ">=": r = x >= y
        else:
            raise ExecError(f"unknown operator {op}")
        tmp[ins.dest] = r
    return val(block.result)


def execute(plan, catalog):
    """Returns (header, rows)."""
    store = {}
    header = []
    for p in plan:
        if p.op == "SCAN":
            cols = list(catalog.columns(p.args["table"]))
            a = p.args["alias"]
            store[p.dest] = [{f"{a}.{c}": v for c, v in zip(cols, row)}
                             for row in catalog.tables[p.args["table"]]["rows"]]
        elif p.op == "JOIN":
            left, right = store[p.inputs[0]], store[p.inputs[1]]
            blk = p.blocks[0]
            rcols = list(right[0].keys()) if right else []
            out = []
            for l in left:
                hit = False
                for r in right:
                    env = {**l, **r}
                    if run_block(blk, env):
                        out.append(env)
                        hit = True
                if not hit and p.args["kind"] == "LEFT":
                    out.append({**l, **{c: None for c in rcols}})
            store[p.dest] = out
        elif p.op == "FILTER":
            store[p.dest] = [r for r in store[p.inputs[0]] if run_block(p.blocks[0], r)]
        elif p.op == "SORT":
            rows = list(store[p.inputs[0]])
            for blk in reversed(p.blocks):     # stable multi-key sort, last key first
                rows.sort(key=lambda r, b=blk: (lambda v: (v is None, v))(run_block(b, r)),
                          reverse=not blk.ascending)
            store[p.dest] = rows
        elif p.op == "PROJECT":
            header = [b.label for b in p.blocks]
            store[p.dest] = [tuple(run_block(b, r) for b in p.blocks) for r in store[p.inputs[0]]]
        elif p.op == "LIMIT":
            store[p.dest] = store[p.inputs[0]][: p.args["n"]]
        elif p.op == "EMIT":
            return header, store[p.inputs[0]]
    return header, []


def format_table(header, rows):
    cells = [[("NULL" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))) for v in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(header)]
    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    def row(vals): return "| " + " | ".join(v.ljust(w) for v, w in zip(vals, widths)) + " |"
    out = [line, row(header), line] + [row(r) for r in cells] + [line, f"({len(rows)} row{'s' if len(rows) != 1 else ''})"]
    return "\n".join(out)
