#!/usr/bin/env python3
"""Find every guard that answers bad input with a plausible default instead of raising.

Walks the AST and flags a function whose guard on a suspicious condition is followed immediately by a
`return` of a computed value rather than None, a constant or a raise. Findings are ranked for inspection;
some are correct behaviour.
"""
import ast, io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"archive", ".git", "__pycache__"}

# A condition that reads like "this input is missing, empty, zero or malformed".
SUSPICIOUS = ("not ", "<= 0", "< 0", "== 0", "is None", "== None", "not in", "len(", "== ''",
              '== ""', "<= 0.0", "is not None and not")


def cond_text(node):
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def returns_a_computed_value(ret):
    """True when the return value is neither None, nor a literal, nor a bare name."""
    if ret.value is None:
        return False
    v = ret.value
    if isinstance(v, ast.Constant):
        return False
    if isinstance(v, ast.Name):
        return False          # returning an existing variable is usually pass-through, not a default
    return True               # a Call, BinOp, Attribute, Dict, Tuple of calls, etc.


def scan(path):
    src = io.open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            c = cond_text(node.test)
            if not any(k in c for k in SUSPICIOUS):
                continue
            body = [b for b in node.body if not isinstance(b, ast.Pass)]
            if len(body) != 1 or not isinstance(body[0], ast.Return):
                continue
            if not returns_a_computed_value(body[0]):
                continue
            out.append(dict(file=os.path.relpath(path, ROOT), func=fn.name,
                            line=node.lineno, cond=c[:70],
                            ret=cond_text(body[0].value)[:70]))
    return out


def main():
    findings = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in sorted(files):
            if f.endswith(".py"):
                findings += scan(os.path.join(d, f))
    print("=" * 96)
    print("SILENT-FALLBACK AUDIT: a guard on bad input that returns a COMPUTED value")
    print("=" * 96)
    if not findings:
        print("  none found.")
    core = [f for f in findings if f["file"].startswith("repdef/")]
    other = [f for f in findings if not f["file"].startswith("repdef/")]
    for title, group in (("CORE LIBRARY, these matter", core), ("scripts and tests", other)):
        print("\n%s  (%d)" % (title, len(group)))
        for f in group:
            print("  %-34s %-26s line %-5d if %s:\n%s-> return %s"
                  % (f["file"], f["func"] + "()", f["line"], f["cond"], " " * 68, f["ret"]))
    print("\n%d findings, %d in the core library." % (len(findings), len(core)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
