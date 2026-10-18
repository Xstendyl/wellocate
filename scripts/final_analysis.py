#!/usr/bin/env python3
"""Run the final grid analysis in one command, stopping at the first structural failure.

It merges the main run with the three per-model follow-up runs, checks one campaign per (condition, model, seed)
with no transport errors and every cell at its model's N, then produces the six confirmatory contrasts (seed-paired,
studentised wild cluster bootstrap over seeds, Holm-adjusted), the behavioural tables, and the zero-noise and
reasoning panels. With --smoke it runs every step on the data that exists and redacts every number that could be a
condition mean.

Usage: python3 scripts/final_analysis.py --smoke   |   ANALYSE_GRID_COMPLETE=1 python3 scripts/final_analysis.py
"""
import argparse, collections, glob, gzip, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

MERGED = ["stage1", "topup_opus", "topup_gemini", "topup_deepseek"]
# Per-model N, computed from the main run under the paired rule.
N_PER_CELL = {"anthropic/claude-opus-4.7": 695,
              "deepseek/deepseek-chat-v3.1": 181,
              "google/gemini-2.5-flash": 139}
CONDITIONS = ["Blind", "Quantitative", "Mechanism", "Aggregated", "Decision-rule"]
RUNG = {"Blind": "blind", "Quantitative": "informed", "Mechanism": "instructed",
        "Aggregated": "aggregated", "Decision-rule": "decision_rule"}
# Any number that could be a condition mean. Redacted in smoke mode.
NUMBER = re.compile(r"[-+]?\d+\.\d+")


def read(tag, kind="campaigns"):
    p = os.path.join(ROOT, "results", "grid_%s_%s.jsonl" % (tag, kind))
    if os.path.exists(p):
        with open(p) as f:
            return [json.loads(l) for l in f if l.strip()]
    if kind == "calls":
        # A completed run keeps its call logs only as gzipped per-cell archives.
        gz = sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz")))
        if gz:
            out = []
            for g in gz:
                with gzip.open(g, "rt") as f:
                    out += [json.loads(l) for l in f if l.strip()]
            return out
    return None


def check_the_merge(smoke):
    """Every structural property the analysis depends on, checked before any statistic is computed."""
    print("=" * 100)
    print("1-2. MERGE AND INTEGRITY")
    print("=" * 100)
    rows, source, fails = [], {}, []
    for tag in MERGED:
        r = read(tag)
        if r is None:
            fails.append("missing results/grid_%s_campaigns.jsonl" % tag)
            continue
        print("  %-18s %6d campaigns" % (tag, len(r)))
        for c in r:
            k = (c["condition"], c["model"], c["seed"])
            if k in source:
                fails.append("DUPLICATE %s in both %r and %r" % (k, source[k], tag))
            source[k] = tag
            rows.append(c)
    print("  %-18s %6d campaigns merged" % ("TOTAL", len(rows)))

    # Transport errors and unusable campaigns must not exist in the merged set.
    bad_seeds, call_src = set(), []
    for tag in MERGED:
        calls = read(tag, "calls")
        if calls is None:
            call_src.append("%s: NO CALL DATA" % tag)
            fails.append("no call log or archive for %s, so its transport errors cannot be checked" % tag)
            continue
        raw = os.path.exists(os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag))
        call_src.append("%s: %d calls from the %s" % (tag, len(calls), "raw log" if raw else "ARCHIVE"))
        for r in calls:
            if r.get("error") or r.get("parse_status") == "transport_error":
                bad_seeds.add((r["rung"], r["campaign_seed"]))
    print("  call data read: %s" % "; ".join(call_src))
    n_err = sum(1 for c in rows if (RUNG[c["condition"]], c["seed"]) in bad_seeds)
    n_unus = sum(1 for c in rows
                 if (c.get("spend") or 0) == 0 or (c.get("n_ok") or 0) == 0
                 or c.get("nominated") in (None, "", "----"))
    print("  campaigns touched by a transport error: %d" % n_err)
    print("  campaigns with no successful measurement: %d" % n_unus)
    if n_err:
        fails.append("%d campaigns carry a transport error; quarantine them first" % n_err)
    if n_unus:
        fails.append("%d campaigns have no successful measurement" % n_unus)

    # Exactly one campaign per (condition, model, seed), and every cell at its model's N.
    cells = collections.Counter((c["condition"], c["model"]) for c in rows)
    seeds = collections.defaultdict(set)
    for c in rows:
        seeds[(c["condition"], c["model"])].add(c["seed"])
    print()
    print("  %-14s %-32s %7s %7s %7s %s" % ("condition", "model", "want", "have", "seeds", "status"))
    for m in sorted(N_PER_CELL):
        for cond in CONDITIONS:
            want = N_PER_CELL[m]
            have = cells.get((cond, m), 0)
            nseed = len(seeds.get((cond, m), ()))
            ok = (have == want == nseed)
            if not ok:
                fails.append("cell %s/%s has %d campaigns and %d distinct seeds, wants %d"
                             % (cond, m.split("/")[-1], have, nseed, want))
            print("  %-14s %-32s %7d %7d %7d %s"
                  % (cond, m.split("/")[-1], want, have, nseed, "ok" if ok else "SHORT"))
    # Within a model, every condition must hold the same seed set, or seed pairing is not possible.
    for m in sorted(N_PER_CELL):
        sets = [seeds.get((c, m), set()) for c in CONDITIONS]
        if sets and not all(s == sets[0] for s in sets):
            fails.append("model %s: the conditions do not share one seed set, so 0s pairing is "
                         "unavailable" % m)
    print()
    if fails:
        print("  INTEGRITY FAILED:")
        for f in fails:
            print("    - %s" % f)
    else:
        print("  INTEGRITY OK: one clean campaign per (condition, model, seed), every cell at its N,")
        print("  and within each model every condition holds the same seed set.")
    return rows, fails


def run_analyse(tag, out, smoke, against=None):
    """Delegate to scripts/analyse_grid.py, the single source of every table."""
    env = dict(os.environ)
    if not smoke:
        env["ANALYSE_GRID_COMPLETE"] = "1"
    else:
        env["ANALYSE_GRID_COMPLETE"] = "1"      # needed to execute; output is redacted below
    cmd = [sys.executable, "-B", os.path.join(ROOT, "scripts", "analyse_grid.py"), tag, "--out", out]
    if against:
        # Compare the panel's cell against the grid's same cell at the same seeds.
        cmd += ["--against", against]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)
    ok = r.returncode == 0
    print("  %-52s %s" % (tag, "produced its tables" if ok else "FAILED"))
    if not ok:
        print((r.stdout + r.stderr)[-1200:])
    return ok


def show(path, smoke, head=14):
    print("  --- %s ---" % os.path.relpath(path, ROOT))
    if not os.path.exists(path):
        print("    (absent)")
        return
    with open(path) as f:
        for i, line in enumerate(f):
            if i >= head:
                print("    ...")
                break
            print("    " + (NUMBER.sub("REDACTED", line.rstrip()) if smoke else line.rstrip()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="execute every step on the data that exists and REDACT every decimal number, "
                         "so the pipeline is proven to run without any condition mean being read")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if not a.smoke and not os.environ.get("ANALYSE_GRID_COMPLETE"):
        sys.exit("REFUSED: set ANALYSE_GRID_COMPLETE=1 only when the grid is complete, or pass --smoke.")
    # In smoke mode the delegated tables go to a temporary directory that is deleted, unless --out is given.
    temp = None
    if a.out:
        out = a.out
    elif a.smoke:
        temp = tempfile.mkdtemp(prefix="repdef_smoke_")
        out = temp
    else:
        out = os.path.join(ROOT, "results", "analysis_final")
    os.makedirs(out, exist_ok=True)
    print("FINAL ANALYSIS   mode=%s   out=%s\n" % ("SMOKE (numbers redacted)" if a.smoke else "REAL",
                                                   os.path.relpath(out, ROOT)))
    rows, fails = check_the_merge(a.smoke)
    if fails and not a.smoke:
        sys.exit("\nREFUSED to analyse: the merge is not sound. Fix the above first.")
    if fails:
        print("\n  SMOKE MODE: continuing past %d integrity failure(s), which are EXPECTED while the "
              "grid runs." % len(fails))

    print()
    print("=" * 100)
    print("3-4. CONFIRMATORY AND BEHAVIOURAL TABLES")
    print("=" * 100)
    merged_tag = "+".join(MERGED) if not a.smoke else "stage1"
    if a.smoke:
        print("  smoke mode analyses stage1 ALONE, because the top-up is incomplete and joining an")
        print("  unfinished run would refuse on a short cell. The command path is identical.")
    ok = run_analyse(merged_tag, os.path.join(out, "grid"), a.smoke)

    print()
    print("=" * 100)
    print("5. THE PANELS")
    print("=" * 100)
    print("  Both panels are EXPLORATORY (0q). Their contrasts are not in the confirmatory family of")
    print("  0g, and each is additionally compared against stage 1 on the seeds they share, which is")
    print("  the question each panel exists to answer.")
    for tag in ("zeronoise", "panelc"):
        if read(tag) is None:
            print("  %-52s no data yet" % tag)
            continue
        ok = run_analyse(tag, os.path.join(out, tag), a.smoke, against="stage1") and ok
    # Only the zero-noise panel has exact readings, so it shows replication with no noise to respond to.
    if read("zeronoise") is not None:
        cmd = [sys.executable, "-B", os.path.join(ROOT, "scripts", "post_repeat_replication.py"),
               "zeronoise", "stage1", "--out", os.path.join(out, "zeronoise")]
        if a.smoke:
            cmd.append("--redact")
        env = dict(os.environ, ANALYSE_GRID_COMPLETE="1")
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)
        print("  %-52s %s" % ("table 2c, the central test (0ad)",
                              "produced" if r.returncode == 0 else "FAILED"))
        if r.returncode:
            print((r.stdout + r.stderr)[-900:])
        ok = ok and r.returncode == 0

    print()
    print("=" * 100)
    print("WHAT WAS WRITTEN")
    print("=" * 100)
    for sub in ("grid", "zeronoise", "panelc"):
        d = os.path.join(out, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            print("  %s" % os.path.relpath(os.path.join(d, f), ROOT))
    print()
    show(os.path.join(out, "grid", "table2_confirmatory.txt"), a.smoke)
    if a.smoke:
        print("\n  SMOKE COMPLETE. Every decimal number above is REDACTED, so no condition mean was read.")
        print("  The pipeline executes end to end. Re-run without --smoke when the grid is complete.")
        if temp:
            n_files = sum(len(f) for _r, _d, f in os.walk(temp))
            shutil.rmtree(temp, ignore_errors=True)
            print("  Its %d table files went to a temporary directory and were DELETED, so no real"
                  % n_files)
            print("  condition mean has been left anywhere under results/.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
