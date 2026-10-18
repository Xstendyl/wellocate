#!/usr/bin/env python3
"""Run the Menu on scrambled GB1, Blind condition with the truthful re-ask. Spends nothing without --run.

Two arms:
  gb1_menu     (--menu)  Opus 4.7 n = 30 on seeds 11,000,000 to 11,000,029; Gemini 2.5 Flash and DeepSeek V3.1
               n = 60 on 11,000,000 to 11,000,059
  gb1_control  (no tool) Gemini and DeepSeek n = 60 on the same seeds, concurrent
Opus's control is its earlier scrambled-GB1 Blind campaigns on the same seeds, labelled non-concurrent. A short
trial of 2 campaigns per model per arm runs first, and the panel stage refuses until its spending ceiling is set.

Usage:
  set -a; . ./.env; set +a; python3 scripts/launch_0an6.py --stage smoke --run
  python3 scripts/launch_0an6.py --smoke-report
"""
import argparse, json, os, statistics as st, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import launch_0an as L                                                  # noqa: E402
import replicate_decision_rule as RD                                    # noqa: E402

OPUS, GEMINI, DEEPSEEK = L.OPUS, L.GEMINI, L.DEEPSEEK
ARMS = (("gb1_menu", ["--menu"]), ("gb1_control", ["--models", "mid-tier,open-weight"]))
N = {"gb1_menu": {OPUS: 30, GEMINI: 60, DEEPSEEK: 60}, "gb1_control": {GEMINI: 60, DEEPSEEK: 60}}
SEED0 = {"smoke": 15_000_004, "panel": 11_000_000}
SMOKE_CEILING = 1.0
PANEL_CEILING = {"gb1_menu": 27.0, "gb1_control": 3.0}     # $30 in all
OAM = ("gen_r_gb1scr", "gen_r_gb1scr_top")


def arms(stage):
    out = []
    for name, flag in ARMS:
        tag = ("smoke0an6_" if stage == "smoke" else "gen_0an6_") + name
        if stage == "smoke":
            size, ceiling = ["--campaigns", "2"], SMOKE_CEILING
        else:
            size = ["--campaigns", "60"] + (["--campaigns-by-model", "frontier=30"] if OPUS in N[name] else [])
            ceiling = PANEL_CEILING[name]
        out.append((tag, name, ceiling, ["--landscape", "gb1_scrambled"] + flag + size +
                    ["--seed0", str(SEED0[stage]), "--tag", tag, "--stage", "0an6_" + stage,
                     "--budget-usd", "%.2f" % (ceiling or 0.0)] + L.COMMON))
    return out


def check(stage):
    for tag, name, ceiling, _a in arms(stage):
        if ceiling is None:
            raise SystemExit("REFUSED: %s has no ceiling; the operator sets it from the smoke" % name)
        if os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)):
            raise SystemExit("REFUSED: %s already holds campaigns" % tag)
    if stage == "smoke":
        lo, hi = SEED0["smoke"], SEED0["smoke"] + 2
        if set(range(lo, hi)) & RD.seeds_in_results():
            raise SystemExit("REFUSED: smoke seeds %d..%d are already used in results" % (lo, hi - 1))
        for base, src in RD.bases_in_code():
            if "launch_0an" not in src and base < hi and lo < base + RD.SPAN:
                raise SystemExit("REFUSED: smoke seeds fall within %d of the seed base %d at %s" % (RD.SPAN, base, src))
        print("smoke seeds %d..%d are new" % (lo, hi - 1))
    else:
        oam = {(r["model"], r["seed"]) for t in OAM for r in (json.loads(l) for l in open(os.path.join(
            ROOT, "results", "grid_%s_campaigns.jsonl" % t)) if l.strip()) if r["condition"] == "Blind"}
        missing = [(OPUS, SEED0["panel"] + i) for i in range(N["gb1_menu"][OPUS]) if (OPUS, SEED0["panel"] + i) not in oam]
        if missing:
            raise SystemExit("REFUSED: Opus seeds with no 0am GB1 Blind control: %s" % missing[:5])
        print("pairing: every Opus seed has its 0am GB1-scrambled Blind control")


def smoke_report():
    """Trial checks: every campaign complete, no empty or truncated reply, no genuine parser disagreement, no
    campaign losing more than 10 slots; plus per-campaign cost and the projected panel cost."""
    import analyse_0al as A0
    bad, total = [], 0.0
    for tag, name, _c, _a in arms("smoke"):
        p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
        h = os.path.join(ROOT, "results", "grid_%s_health.json" % tag)
        rows = [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
        health = json.load(open(h)) if os.path.exists(h) else {}
        calls = list(A0.calls(tag))
        genuine = sum(1 for c in calls if not c.get("parsers_agree", True) and c.get("parsed"))
        print("%s: %d campaigns, %d calls, %d genuine parser disagreements" % (tag, len(rows), len(calls), genuine))
        proj = 0.0
        for m, n in N[name].items():
            v = [r for r in rows if r["model"] == m]
            if not v:
                bad.append((tag, m, "no campaigns"))
                continue
            hh = health.get(m, {})
            spend = st.mean(r["spend"] for r in v)
            proj += n * spend
            print("   %-30s n=%d $/campaign %.4f share %s lost %s (rounds %s) rejections %s distinct %s empty %s trunc %s"
                  % (m, len(v), spend, ["%.0f%%" % (100 * r["replication_fraction"]) for r in v],
                     [r["lost_slots"] for r in v], [r["rounds_lost_slots"] for r in v], [r["n_rejected"] for r in v],
                     [r["n_distinct_measured"] for r in v], hh.get("empty"), hh.get("truncated")))
            if hh.get("empty") or hh.get("truncated"):
                bad.append((tag, m, "empty or truncated"))
            for r in v:
                if r["lost_slots"] > L.LOST_LIMIT:
                    bad.append((tag, m, "seed %d lost %d slots" % (r["seed"], r["lost_slots"])))
            if len(v) != 2:
                bad.append((tag, m, "%d of 2 campaigns" % len(v)))
        if genuine:
            bad.append((tag, "%d genuine parser disagreements" % genuine))
        print("   projected panel cost at the registered n: $%.2f" % proj)
        total += proj
    print("projected 0an.6 panel in all: $%.2f" % total)
    print("SMOKE GATE: %s" % ("PASS" if not bad else "FAIL %s" % bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("smoke", "panel"))
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--smoke-report", action="store_true")
    a = ap.parse_args()
    if a.smoke_report:
        return smoke_report()
    if not a.stage:
        raise SystemExit("--stage is required")
    check(a.stage)
    cmds = [(tag, [sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args)
            for tag, _n, _c, args in arms(a.stage)]
    for tag, c in cmds:
        print("launch %s: %s" % (tag, " ".join(c[2:]).replace(ROOT + "/", "")))
    if not a.run:
        print("dry: nothing launched. Re-run with --run.")
        return 0
    procs = []
    for tag, c in cmds:
        log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a")
        procs.append((tag, subprocess.Popen(c, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)))
        print("started %s (pid %d)" % (tag, procs[-1][1].pid))
    codes = {tag: p.wait() for tag, p in procs}
    print("exit codes: %s" % codes)
    return max(codes.values())


if __name__ == "__main__":
    sys.exit(main())
