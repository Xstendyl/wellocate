#!/usr/bin/env python3
"""Every number the paper quotes that the yardstick's alphabet correction moves: old, new and change.

The paper's quoted figures are the verifier's own table, `verify_paper_numbers.computed()`, keyed by the string
the paper prints. This script evaluates that table twice:
  OLD  on the results as first published, read from git history for every file the correction rewrote;
  NEW  on the corrected results: the curves from reference_curve_alphabet.json, the risk-free yardstick from
       riskfree_reference_alphabet.json, and the regenerated loss, protocol, learnability, percentile and
       landscape files.
A row is listed when the value changes at all, and marked when the change reaches the printed precision. A claim
the verifier asserts in words is checked on both sides and reported by its message if the new results break it.

Usage: python3 scripts/yardstick_fix_table.py      (writes results/yardstick_fix_table.json and .txt)
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify_paper_numbers as V                                     # noqa: E402
import figstyle as FS                                                # noqa: E402
import make_table_cells as MTC                                       # noqa: E402

OLD_COMMIT = "e325069"
REWRITTEN = ("loss_vs_guessing.json", "lab_protocols.json", "learnability_fresh_n1500_rescored.json",
             "reference_percentile.json", "landscape_summary.json")
REDIRECT = {"fair_reference_curve.json": "reference_curve_alphabet.json",
            "riskfree_reference.json": "riskfree_reference_alphabet.json"}
OUT = os.path.join(ROOT, "results", "yardstick_fix_table")


def _lenient_computed():
    """`computed` with each `raise SystemExit(...)` turned into a recorded failure, built from the verifier's
    own source, so one broken claim does not hide the rest."""
    import inspect, textwrap
    src = textwrap.dedent(inspect.getsource(V.computed)).replace("raise SystemExit(", "_claim_failed(")
    ns = dict(V.__dict__)
    ns["_claim_failed"] = lambda msg: FAILED.append(str(msg))
    exec(compile(src, V.__file__, "exec"), ns)
    return ns["computed"]


FAILED = []


def evaluate(loader):
    real = V.load
    V.load = loader
    del FAILED[:]
    try:
        return _lenient_computed()(), list(FAILED)
    finally:
        V.load = real


def render_cells(loader):
    """The generated per-cell table, rendered from the given results without writing anything."""
    real = FS.results
    FS.results = loader
    try:
        return MTC.render()
    finally:
        FS.results = real


def decimals(s):
    t = s.replace(",", "").rstrip("%")
    return len(t.split(".")[1]) if "." in t else 0


def printed(s, value):
    d = decimals(s)
    out = "%.*f" % (d, value)
    if "," in s:
        whole, _dot, frac = out.partition(".")
        out = "{:,}".format(int(whole)) + ("." + frac if frac else "")
    return out + ("%" if s.endswith("%") else "")


def main():
    tmp = tempfile.mkdtemp(prefix="yardfix_")
    for f in REWRITTEN:
        blob = subprocess.run(["git", "show", "%s:results/%s" % (OLD_COMMIT, f)], cwd=ROOT,
                              capture_output=True, check=True).stdout
        open(os.path.join(tmp, f), "wb").write(blob)

    def old_load(p):
        if p in REWRITTEN:
            return json.load(open(os.path.join(tmp, p)))
        return json.load(open(os.path.join(ROOT, "results", p)))

    def new_load(p):
        return json.load(open(os.path.join(ROOT, "results", REDIRECT.get(p, p))))

    def old_fs(p):
        # figstyle reads the corrected curve by name; the original file is its old source.
        return old_load("fair_reference_curve.json" if p == "reference_curve_alphabet.json" else p)

    t_old = render_cells(old_fs).splitlines()
    t_new = render_cells(new_load).splitlines()
    if len(t_old) != len(t_new):
        raise SystemExit("REFUSED: the per-cell table changed shape, %d lines to %d" % (len(t_old), len(t_new)))
    table_rows = [dict(old=a, new=b) for a, b in zip(t_old, t_new) if a != b]

    old, old_err = evaluate(old_load)
    new, new_err = evaluate(new_load)
    if old_err:
        raise SystemExit("REFUSED: the verifier fails on the PUBLISHED results: %s" % old_err)
    if new is None:
        raise SystemExit("REFUSED: the lenient verifier returned nothing on the corrected results")
    rows = []
    if new is not None:
        for s, (label, ov) in old.items():
            nl, nv = new[s]
            if not isinstance(ov, (int, float)) or ov == nv:
                continue
            np_ = printed(s, nv)
            rows.append(dict(printed_old=s, label=label, old=ov, new=nv, change=nv - ov, printed_new=np_,
                             text_changes=(np_ != s)))
    rows.sort(key=lambda r: (not r["text_changes"], r["label"]))
    json.dump(dict(old_commit=OLD_COMMIT, redirect=REDIRECT, rewritten=list(REWRITTEN), rows=rows,
                   table_cells_changed_lines=table_rows, new_results_break_a_claim=new_err),
              open(OUT + ".json", "w"), indent=1)
    lines = ["%-10s %-10s %12s %12s %10s  %s" % ("paper now", "paper new", "old", "new", "change", "what")]
    for r in rows:
        lines.append("%-10s %-10s %12.4f %12.4f %+10.4f  %s%s" % (
            r["printed_old"], r["printed_new"], r["old"], r["new"], r["change"], r["label"],
            "" if r["text_changes"] else "   (no change at the printed precision)"))
    lines.append("\nGENERATED PER-CELL TABLE (paper/sections/table_cells.tex): %d lines change" % len(table_rows))
    for r in table_rows:
        lines.append("  old: %s\n  new: %s" % (r["old"], r["new"]))
    for e in new_err:
        lines.append("\nTHE CORRECTED RESULTS BREAK A CLAIM THE VERIFIER CHECKS: %s" % e)
    open(OUT + ".txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\n%d quoted numbers move, %d of them at the printed precision; wrote %s.json and .txt"
          % (len(rows), sum(r["text_changes"] for r in rows), os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
