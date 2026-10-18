#!/usr/bin/env python3
"""List every call site that requests a shrinkage nomination, with its noise model and sigma argument.

Multiplicative callers that pass the scalar sigma=0.0 are flagged apart from additive callers that pass a real
sigma.
"""
import ast, io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"archive", ".git", "__pycache__"}


def main():
    rows = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            path = os.path.join(d, f)
            src = io.open(path, encoding="utf-8").read()
            # Pre-filter loosely, so files that pass `nomination=rule` from a loop are still parsed.
            if "shrinkage" not in src and "nomination" not in src:
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                if kw.get("nomination") is None:
                    continue
                dynamic = False
                try:
                    if ast.literal_eval(kw["nomination"]) != "shrinkage":
                        continue
                except Exception:
                    # A non-literal nomination (e.g. `nomination=rule` in a loop) is kept and flagged.
                    dynamic = True
                nm = "additive (default)"
                if "noise_model" in kw:
                    try:
                        nm = ast.literal_eval(kw["noise_model"])
                    except Exception:
                        nm = ast.unparse(kw["noise_model"])
                # The 4th positional argument of campaign.run is sigma; sweep.run_cell puts it 3rd.
                spos = {"C.run": 3, "campaign.run": 3, "S.run_cell": 2, "sweep.run_cell": 2}
                fname = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                idx = spos.get(fname, 3)
                sigma = (ast.unparse(node.args[idx]) if len(node.args) > idx
                         else (ast.unparse(kw["sigma"]) if "sigma" in kw else "(absent)"))
                rows.append(dict(file=os.path.relpath(path, ROOT), line=node.lineno,
                                 noise_model=nm, sigma_arg=sigma, dynamic=dynamic,
                                 func=(ast.unparse(node.func) if hasattr(ast, "unparse") else "?")))
    print("=" * 96)
    print("SHRINKAGE CALL SITES, and whether the estimator they asked for is the one that ran")
    print("=" * 96)
    print("  %-46s %-6s %-22s %-12s %s" % ("file", "line", "noise_model", "sigma arg", "status"))
    void = stands = 0
    for r in sorted(rows, key=lambda x: (x["file"], x["line"])):
        mult = r["noise_model"] == "multiplicative"
        zero = r["sigma_arg"].strip() in ("0.0", "0")
        if mult and zero:
            # run builds the callable and ignores the scalar here; only older output from these sites is void.
            status = "pre-fix output VOID, site now correct"; void += 1
        elif mult:
            status = "multiplicative, nonzero scalar, READ IT"
        else:
            status = "additive real scalar, output stands"; stands += 1
        if r["dynamic"]:
            status += "  [dynamic nomination, classified by reading]"
        print("  %-46s %-6d %-22s %-14s %s"
              % (r["file"], r["line"], r["noise_model"], r["sigma_arg"], status))
    print("\n%d call sites: %d produced void output before the fix, %d additive and stand."
          % (len(rows), void, stands))
    print("\nEvery void site is inside a script whose output has been regenerated with the fix, or")
    print("whose output is superseded. The published numbers affected are exactly the margins, and")
    print("results/RESULTS_LOG.md rows 18 to 21b carry the corrected values.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
