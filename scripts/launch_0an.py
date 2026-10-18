#!/usr/bin/env python3
"""Launch the aid arms on the grid landscape (Blind condition, truthful re-ask), each as a separate grid.py process
and tag. Spends nothing without --run.

Arms: ledger (--ledger), menu (--menu), repeat cap (--repeat-cap), structure note (--structure), and a control with
no aid for Gemini 2.5 Flash and DeepSeek V3.1 (Opus 4.7's control is an earlier Blind run on the same seeds).
Campaigns use the seeds of the grid's own Blind campaigns, so each pairs by seed with one already run. The launch
refuses unless every planned (model, seed) has a Blind partner and the arm's tag holds no campaign yet.

Usage:
  python3 scripts/launch_0an.py --stage panel --arms f0_control,f1_ledger,f2_menu     # check and print
  set -a; . ./.env; set +a; python3 scripts/launch_0an.py --stage panel --arms f0_control,f1_ledger,f2_menu --run
  set -a; . ./.env; set +a; python3 scripts/launch_0an.py --stage resmoke_f3 --run
  python3 scripts/launch_0an.py --smoke-report [--stage resmoke_f3]
"""
import argparse, glob, gzip, json, os, statistics as st, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import replicate_decision_rule as RD                                 # noqa: E402

OPUS, GEMINI, DEEPSEEK = "anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1"
ARMS = (("f1_ledger", "--ledger"), ("f2_menu", "--menu"), ("f3_cap", "--repeat-cap"), ("f0_control", None),
        ("f5_structure", "--structure"))
# Which arms each stage runs.
STAGE_ARMS = {"smoke": ("f1_ledger", "f2_menu", "f3_cap", "f0_control"), "resmoke_f3": ("f3_cap",),
              "smoke_f5": ("f5_structure",), "panel": tuple(n for n, _f in ARMS), "topup_0an5": ("f2_menu",)}
GRID = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
SEED0 = {"panel": 300_000, "smoke": 15_000_000, "resmoke_f3": 15_000_000, "smoke_f5": 15_000_002,
         "topup_0an5": 300_030}
# Extra Opus 4.7 menu campaigns, seeds 300,030 to 300,059, added after the n = 30 result.
TOPUP_0AN5 = dict(tag="gen_0an5_f2_menu_opus", n=30, ceiling=25.0)
# Campaigns per model per arm in the panel.
N_BY_ARM = {"f1_ledger": {OPUS: 60, GEMINI: 120, DEEPSEEK: 120},
            "f2_menu": {OPUS: 30, GEMINI: 120, DEEPSEEK: 120},
            "f3_cap": {OPUS: 30, GEMINI: 120, DEEPSEEK: 120},
            "f0_control": {GEMINI: 120, DEEPSEEK: 120},
            "f5_structure": {OPUS: 30, GEMINI: 120, DEEPSEEK: 120}}
N = N_BY_ARM["f1_ledger"]                          # the original sizes, used by the first pilot report
# Panel spend ceilings in USD; the panel stage refuses an arm with no ceiling.
PANEL_CEILING = {"f1_ledger": 25.0, "f2_menu": 30.0, "f3_cap": None, "f0_control": 4.0, "f5_structure": 19.0}
CEILING = {"panel": 25.0, "smoke": 1.0, "resmoke_f3": 5.0, "smoke_f5": 1.0}
CONTROL_CEILING = 4.0                              # the control arm
SMOKE_TAG = {"smoke": "smoke0an_", "resmoke_f3": "smoke0an1_", "smoke_f5": "smoke0an3_"}
LOST_LIMIT = 10
# The repeat-cap arm is withdrawn as a causal arm; its panel is refused by name.
WITHDRAWN = {"f3_cap": "0an.2 withdrew F3 as a causal arm; its smokes are kept as a descriptive record"}
COMMON = ["--conditions", "Blind", "--max-tokens", "6000", "--max-reasks", "3", "--temperature", "0.0",
          "--noise", "multiplicative", "--credit-floor", "50", "--workers", "3", "--shuffle",
          "--order-seed", "20261004", "--truthful-reask"]


def arms(stage, only=None):
    out = []
    for name, flag in ARMS:
        if name not in STAGE_ARMS[stage]:
            continue
        if only is not None and name not in only:
            continue
        tag = ("gen_0an_" if stage == "panel" else SMOKE_TAG.get(stage, "")) + name
        if stage == "topup_0an5":
            tag, size, ceiling = TOPUP_0AN5["tag"], ["--campaigns", str(TOPUP_0AN5["n"])], TOPUP_0AN5["ceiling"]
            out.append((tag, name, ceiling, [flag, "--models", "frontier"] + size +
                        ["--seed0", str(SEED0[stage]), "--tag", tag, "--stage", "0an5_topup",
                         "--budget-usd", "%.2f" % ceiling] + COMMON))
            continue
        if stage == "panel":
            n = N_BY_ARM[name]
            size = ["--campaigns", "120"] + (["--campaigns-by-model", "frontier=%d" % n[OPUS]] if OPUS in n else [])
            ceiling = PANEL_CEILING[name]
        else:
            size, ceiling = ["--campaigns", "2"], CEILING[stage]
        # The control: no aid, and no Opus, whose control was run earlier.
        flag_args = ["--models", "mid-tier,open-weight"] if flag is None else [flag]
        out.append((tag, name, ceiling, flag_args + size + ["--seed0", str(SEED0[stage]), "--tag", tag,
                                                            "--stage", "0an_" + stage,
                                                            "--budget-usd", "%.2f" % (ceiling or 0.0)] + COMMON))
    return out


def grid_blind():
    have = set()
    for t in GRID:
        for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)):
            if l.strip():
                r = json.loads(l)
                if r["condition"] == "Blind":
                    have.add((r["model"], r["seed"]))
    return have


def check(stage, only=None):
    planned = arms(stage, only)
    for tag, name, ceiling, _a in planned:
        if stage == "panel" and name in WITHDRAWN:
            raise SystemExit("REFUSED: %s" % WITHDRAWN[name])
        if ceiling is None:
            raise SystemExit("REFUSED: %s has no registered ceiling; F3's is set after its re-smoke is checked" % name)
        if os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)):
            raise SystemExit("REFUSED: %s already holds campaigns" % tag)
    if stage == "topup_0an5":
        have = grid_blind()
        a0 = {(r["model"], r["seed"]) for r in (json.loads(l) for l in open(os.path.join(
            ROOT, "results", "grid_panelA0_original_campaigns.jsonl")) if l.strip()) if r["condition"] == "Blind"}
        want = [(OPUS, SEED0[stage] + i) for i in range(TOPUP_0AN5["n"])]
        missing = [k for k in want if k not in have or k not in a0]
        if missing:
            raise SystemExit("REFUSED: top-up seeds with no grid Blind or A0 partner: %s" % missing[:5])
        print("pairing: all %d top-up seeds have a grid Blind and an A0 partner" % len(want))
    elif stage == "panel":
        have = grid_blind()
        a0 = {(r["model"], r["seed"]) for r in (json.loads(l) for l in open(os.path.join(
            ROOT, "results", "grid_panelA0_original_campaigns.jsonl")) if l.strip()) if r["condition"] == "Blind"}
        missing = []
        for _t, name, _c, _a in planned:
            for m, n in N_BY_ARM[name].items():
                for i in range(n):
                    k = (m, SEED0["panel"] + i)
                    if k not in have or (m == OPUS and k not in a0):
                        missing.append((name,) + k)
        if missing:
            raise SystemExit("REFUSED: planned campaigns with no grid Blind or A0 partner: %s" % missing[:5])
        print("pairing: every planned campaign has a grid Blind partner, and Opus an A0 partner: %s"
              % {name: sum(N_BY_ARM[name].values()) for _t, name, _c, _a in planned})
    elif stage == "resmoke_f3":
        lo, hi = SEED0[stage], SEED0[stage] + 2
        users = seed_users(range(lo, hi))
        if any(not os.path.basename(u).startswith("grid_" + SMOKE_TAG["smoke"]) for u in users):
            raise SystemExit("REFUSED: smoke seeds %d..%d are held outside the 0an smoke: %s" % (lo, hi - 1, users))
        print("re-smoke seeds %d..%d are held only by the 0an smoke (%d files)" % (lo, hi - 1, len(users)))
    else:
        lo, hi = SEED0[stage], SEED0[stage] + 2
        if set(range(lo, hi)) & RD.seeds_in_results():
            raise SystemExit("REFUSED: smoke seeds %d..%d are already used in results" % (lo, hi - 1))
        for base, src in RD.bases_in_code():
            if "launch_0an.py" not in src and base < hi and lo < base + RD.SPAN:
                raise SystemExit("REFUSED: smoke seeds fall within %d of the seed base %d at %s"
                                 % (RD.SPAN, base, src))
        print("smoke seeds %d..%d are new" % (lo, hi - 1))


def seed_users(seeds):
    """Every results file, campaign or call log, that records one of `seeds`, by the top-level results name."""
    want, out = set(seeds), set()
    for p in glob.glob(os.path.join(ROOT, "results", "**", "*.jsonl*"), recursive=True):
        fh = gzip.open(p, "rt", errors="replace") if p.endswith(".gz") else open(p, errors="replace")
        with fh:
            for line in fh:
                if '"seed"' in line or '"campaign_seed"' in line:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("seed") in want or r.get("campaign_seed") in want:
                        out.add(os.path.relpath(p, os.path.join(ROOT, "results")).split(os.sep)[0])
                        break
    return sorted(out)


def smoke_report(stage="smoke"):
    """Check a pilot run: every campaign complete and healthy, no genuine parser disagreement, no campaign losing
    more than 10 slots, and each arm's projected spend inside its ceiling. For the repeat-cap arm only lost rounds
    count toward the 10, and rejection losses are reported by channel."""
    import analyse_0al as A0
    bad = []
    for tag, name, _c, _a in arms(stage):
        p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
        h = os.path.join(ROOT, "results", "grid_%s_health.json" % tag)
        rows = [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
        health = json.load(open(h)) if os.path.exists(h) else {}
        calls = list(A0.calls(tag))
        genuine = sum(1 for c in calls if not c.get("parsers_agree", True) and c.get("parsed"))
        print("%s: %d campaigns, %d calls, %d genuine parser disagreements" % (tag, len(rows), len(calls), genuine))
        sizes = N if stage == "smoke" else N_BY_ARM[name]
        models = [m for m in sizes if not (name == "f0_control" and m == OPUS)]
        proj = 0.0
        for m in models:
            v = [r for r in rows if r["model"] == m]
            if not v:
                bad.append((tag, m, "no campaigns"))
                continue
            hh = health.get(m, {})
            spend = st.mean(r["spend"] for r in v)
            proj += sizes[m] * spend
            print("   %-30s n=%d $/campaign %.4f share %s lost %s capped %s rejections %s distinct %s empty %s trunc %s"
                  % (m, len(v), spend, ["%.0f%%" % (100 * r["replication_fraction"]) for r in v],
                     [r["lost_slots"] for r in v], [r.get("n_capped") for r in v], [r["n_rejected"] for r in v],
                     [r["n_distinct_measured"] for r in v], hh.get("empty"), hh.get("truncated")))
            if stage == "resmoke_f3":
                print("   %-30s lost rounds (slots) %s | rejection losses %s | cap-bound losses %s | pick %s"
                      % ("", [r["rounds_lost_slots"] for r in v],
                         [r["slots_abandoned"] - (r.get("repeat_cap_hits") or 0) for r in v],
                         [r.get("repeat_cap_hits") or 0 for r in v], ["%.3f" % r["nominated_true"] for r in v]))
            if hh.get("empty") or hh.get("truncated"):
                bad.append((tag, m, "empty or truncated"))
            for r in v:
                lost = r["rounds_lost_slots"] if stage == "resmoke_f3" else r["lost_slots"]
                if lost > LOST_LIMIT:
                    bad.append((tag, m, "seed %d lost %d slots%s" % (r["seed"], lost,
                                                                     " to lost rounds" if stage == "resmoke_f3" else "")))
        if genuine:
            bad.append((tag, "%d parser disagreements" % genuine))
        if len(rows) != 2 * len(models):
            bad.append((tag, "%d of %d campaigns" % (len(rows), 2 * len(models))))
        if stage == "resmoke_f3":
            print("   projected arm cost at %s: $%.2f (F3's ceiling is set by the operator after this report)"
                  % ({k.split("/")[1]: n for k, n in sizes.items()}, proj))
            continue
        ceiling = (CONTROL_CEILING if name == "f0_control" else
                   PANEL_CEILING[name] if stage == "smoke_f5" else CEILING["panel"])
        print("   projected arm cost $%.2f (ceiling $%.2f)" % (proj, ceiling))
        if proj > ceiling:
            bad.append((tag, "projected $%.2f over the ceiling" % proj))
    print("SMOKE GATE: %s" % ("PASS" if not bad else "FAIL %s" % bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("smoke", "panel", "resmoke_f3", "smoke_f5", "topup_0an5"))
    ap.add_argument("--arms", default="", help="panel only: comma-separated arm names, for example "
                                               "f0_control,f1_ledger,f2_menu")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--smoke-report", action="store_true")
    a = ap.parse_args()
    if a.smoke_report:
        return smoke_report(a.stage or "smoke")
    if not a.stage:
        raise SystemExit("--stage is required")
    only = None
    if a.stage == "panel":
        if not a.arms:
            raise SystemExit("--arms is required for the panel")
        only = set(a.arms.split(","))
        unknown = only - {n for n, _f in ARMS}
        if unknown:
            raise SystemExit("unknown arms %s" % sorted(unknown))
    check(a.stage, only)
    cmds = [(tag, [sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args)
            for tag, _n, _c, args in arms(a.stage, only)]
    for tag, c in cmds:
        print("launch %s: %s" % (tag, " ".join(c[2:]).replace(ROOT + "/", "")))
    if not a.run:
        print("dry: nothing launched. Re-run with --run.")
        return 0
    procs = []
    for tag, c in cmds:
        log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a")
        procs.append((tag, subprocess.Popen(c, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)))
        print("started %s (pid %d), log results/grid_%s.log" % (tag, procs[-1][1].pid, tag))
    codes = {tag: p.wait() for tag, p in procs}
    print("exit codes: %s" % codes)
    return max(codes.values())


if __name__ == "__main__":
    sys.exit(main())
