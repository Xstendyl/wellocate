#!/usr/bin/env python3
"""Trial and main runs for GPT-6.1 Sol and Gemini 3.1 Pro Preview at minimal reasoning effort.

Three arms, 2 trial campaigns per model each, one grid.py process per arm with both models:
  grid_blind  the grid's landscape, Blind, seeds 300,000 and 300,001
  gb1_blind   scrambled GB1, Blind, seeds 11,000,000 and 11,000,001
  gb1_menu    scrambled GB1, Blind with the Menu, seeds 11,000,000 and 11,000,001
The trial report gives, per model, empty answers and fallback-pattern calls, parse rate, refusals, slot loss,
median reasoning and visible tokens per call, cost per campaign, and the main run's projected cost.

Usage:
  set -a; . ./.env; set +a; python3 scripts/launch_0an7.py --run
  python3 scripts/launch_0an7.py --smoke-report
"""
import argparse, json, os, re, statistics as st, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import launch_0an as L                                                  # noqa: E402

MODELS = ("openai/gpt-6.1-sol", "google/gemini-3.1-pro-preview")
ARMS = (("grid_blind", [], 300_000, 60), ("gb1_blind", ["--landscape", "gb1_scrambled"], 11_000_000, 30),
        ("gb1_menu", ["--landscape", "gb1_scrambled", "--menu"], 11_000_000, 30))
PER_ARM = 1.30
COMMON = [a for a in L.COMMON if a not in ("--max-tokens", "6000")]
TRUTHFUL = "Your previous reply could not be used. These candidates contain letters that are not in the alphabet"
COMPARATORS = {
    "grid Blind": "0an F0 control (Gemini 2.5 Flash, DeepSeek V3.1): same prompt options, the clean comparator. "
                  "Panel A0 (Opus 4.7): prompt differs only by the truthful re-ask line. Panel c: prompt differs "
                  "only by the truthful re-ask line, and ran at medium effort",
    "GB1 Blind": "0am Panel R, GB1 scrambled Blind: same prompt options (the truthful re-ask on from 0am.2)",
    "GB1 Menu": "0an.6 GB1 Menu: same prompt options",
}
REFUSAL = re.compile(r"\b(?:I can't|I cannot|I won't|I'm sorry|I am sorry|unable to help|can't assist)\b", re.I)


def arms():
    out = []
    for name, extra, seed0, _n in ARMS:
        tag = "smoke0an7_" + name
        out.append((tag, extra + ["--models", ",".join(MODELS), "--campaigns", "2", "--seed0", str(seed0),
                                  "--tag", tag, "--stage", "0an7_smoke", "--budget-usd", "%.2f" % PER_ARM,
                                  "--reasoning-effort", "minimal", "--max-tokens", "16000"] + COMMON))
    return out


# Main run: one grid.py process per model per arm; output budget 16,000 for Sol and 32,000 for Gemini;
# each model's ceiling split across its arms in proportion to the trial's projected cost.
SHORT = {"openai/gpt-6.1-sol": "sol", "google/gemini-3.1-pro-preview": "gem"}
MAX_TOKENS = {"openai/gpt-6.1-sol": 16000, "google/gemini-3.1-pro-preview": 32000}
MODEL_CEILING = {"openai/gpt-6.1-sol": 22.0, "google/gemini-3.1-pro-preview": 76.0}
ABANDON_CEILING = {60: 3, 30: 1}               # at most 5% of a model's campaigns per arm


def arm_ceilings():
    rep = json.load(open(os.path.join(ROOT, "results", "smoke_0an7_report.json")))
    out = {}
    for m in MODELS:
        proj = {name: n * rep[m]["arms"][name]["cost_per_campaign"] for name, _e, _s, n in ARMS}
        tot = sum(proj.values())
        for name in proj:
            out[(m, name)] = round(MODEL_CEILING[m] * proj[name] / tot, 2)
    return out


def main_arms():
    ceil = arm_ceilings()
    out = []
    for m in MODELS:
        for name, extra, seed0, n in ARMS:
            tag = "gen_0an7_%s_%s" % (SHORT[m], name)
            out.append((tag, m, name, n, extra + ["--models", m, "--campaigns", str(n), "--seed0", str(seed0),
                                                  "--tag", tag, "--stage", "0an7_main",
                                                  "--budget-usd", "%.2f" % ceil[(m, name)], "--reasoning-effort",
                                                  "minimal", "--max-tokens", str(MAX_TOKENS[m])] + COMMON))
    return out


def failed_seeds(tag):
    p = os.path.join(ROOT, "results", "grid_%s.log" % tag)
    seeds = []
    for l in (open(p) if os.path.exists(p) else []):
        mm = re.search(r"seed\s+(\d+)\s+(?:FAILED|ABANDONED)", l)
        if mm:
            seeds.append(int(mm.group(1)))
    return seeds


def rerun(run):
    """Re-run each abandoned seed once at the same seed and settings, tag suffix _rerun, so pairing by seed holds;
    a seed abandoned twice is dropped from both sides and reported."""
    jobs = []
    for tag, m, name, n, args in main_arms():
        seeds = failed_seeds(tag)
        if len(seeds) > ABANDON_CEILING[n]:
            raise SystemExit("STOP: %s abandoned %d campaigns, above its ceiling of %d" % (tag, len(seeds), ABANDON_CEILING[n]))
        for sd in seeds:
            a = list(args)
            a[a.index("--campaigns") + 1] = "1"
            a[a.index("--seed0") + 1] = str(sd)
            a[a.index("--tag") + 1] = tag + "_rerun"
            jobs.append((tag + "_rerun", a))
    for tag, a in jobs:
        print("re-run %s: %s" % (tag, " ".join(a)))
        if run:
            log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a")
            subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + a, cwd=ROOT, stdout=log,
                           stderr=subprocess.STDOUT)
    return 0


def smoke_report():
    import analyse_0al as A0
    out, bad = {}, []
    for m in MODELS:
        d = dict(arms={}, calls=0, empty=0, fallback_pattern=0, parsed_ok=0, refusals=0, reasoning=[], visible=[],
                 failed_campaigns=0, truthful_reask_fired=0, started=0, written=0, abandoned=[])
        for (tag, _a), (name, _e, _s, n) in zip(arms(), ARMS):
            rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag))
                    if l.strip()] if os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)) else []
            v = [r for r in rows if r["model"] == m]
            log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag)).read()
            failed = [l for l in log.splitlines() if ("FAILED" in l or "ABANDONED" in l) and m in l]
            d["failed_campaigns"] += len(failed)
            d["started"] += 2
            d["written"] += len(v)
            d["abandoned"] += [dict(arm=name, line=l.strip()[:300]) for l in failed]
            d["empty"] += sum(1 for l in failed if "empty content" in l)
            for c in A0.calls(tag):
                if c["model"] != m:
                    continue
                d["calls"] += 1
                rt, ct = c.get("reasoning_tokens") or 0, c.get("completion_tokens") or 0
                d["reasoning"].append(rt)
                d["visible"].append(ct - rt)
                d["empty"] += 1 if c.get("empty_text") else 0
                d["fallback_pattern"] += 1 if (c.get("raw_response") or "").strip() and rt > 0 and ct - rt <= 5 else 0
                d["parsed_ok"] += 1 if c.get("parse_status") == "ok" or (c.get("kind") == "nomination" and c.get("parsed")) else 0
                d["refusals"] += 1 if REFUSAL.search(c.get("raw_response") or "") else 0
                d["truthful_reask_fired"] += 1 if TRUTHFUL in (c.get("prompt") or "") else 0
            spend = st.mean(r["spend"] for r in v) if v else None
            d["arms"][name] = dict(campaigns=len(v), cost_per_campaign=spend, n_main=n,
                                   lost=[r["lost_slots"] for r in v], rounds_lost=[r["rounds_lost_slots"] for r in v],
                                   share=[round(100 * r["replication_fraction"], 1) for r in v],
                                   distinct=[r["n_distinct_measured"] for r in v])
            if len(v) != 2:
                bad.append((m, name, "%d of 2 campaigns" % len(v)))
            if any(x > L.LOST_LIMIT for x in d["arms"][name]["lost"]):
                bad.append((m, name, "a campaign lost more than %d slots" % L.LOST_LIMIT))
        d["parse_rate"] = d["parsed_ok"] / d["calls"] if d["calls"] else None
        d["median_reasoning"] = st.median(d["reasoning"]) if d["reasoning"] else None
        d["median_visible"] = st.median(d["visible"]) if d["visible"] else None
        d["projected_main"] = sum(a["n_main"] * (a["cost_per_campaign"] or 0) for a in d["arms"].values())
        for k in ("empty", "fallback_pattern", "refusals"):
            if d[k]:
                bad.append((m, "%d %s" % (d[k], k)))
        del d["reasoning"], d["visible"]
        out[m] = d
        print("%s: %d calls, empty %d, fallback-pattern %d, parse rate %.1f%%, refusals %d, failed campaigns %d, "
              "median reasoning %s and visible %s tokens per call"
              % (m, d["calls"], d["empty"], d["fallback_pattern"], 100 * (d["parse_rate"] or 0), d["refusals"],
                 d["failed_campaigns"], d["median_reasoning"], d["median_visible"]))
        for name, a in d["arms"].items():
            print("   %-10s %d campaigns, $%s per campaign, share %s, lost %s (rounds %s), distinct %s"
                  % (name, a["campaigns"], "%.4f" % a["cost_per_campaign"] if a["cost_per_campaign"] else "n/a",
                     a["share"], a["lost"], a["rounds_lost"], a["distinct"]))
        print("   projected main run (grid Blind 60, GB1 Blind 30, GB1 Menu 30): $%.2f" % d["projected_main"])
        print("   truthful re-ask fired in %d of %d calls; campaigns started %d, written %d, abandoned %d"
              % (d["truthful_reask_fired"], d["calls"], d["started"], d["written"], len(d["abandoned"])))
        for ab in d["abandoned"]:
            print("      abandoned (%s): %s" % (ab["arm"], ab["line"]))
        if len(d["abandoned"]) > 1:
            bad.append((m, "%d of %d smoke campaigns abandoned" % (len(d["abandoned"]), d["started"])))
    out["_comparators"] = COMPARATORS
    json.dump(out, open(os.path.join(ROOT, "results", "smoke_0an7_report.json"), "w"), indent=1)
    for k, v in COMPARATORS.items():
        print("comparator, %s: %s" % (k, v))
    print("SMOKE GATE: %s" % ("PASS" if not bad else "FAIL %s" % bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--smoke-report", action="store_true")
    ap.add_argument("--main", action="store_true", help="the main run (0an.7 note 3)")
    ap.add_argument("--rerun", action="store_true", help="re-run each abandoned seed once (0an.7 note 3)")
    a = ap.parse_args()
    if a.smoke_report:
        return smoke_report()
    if a.rerun:
        return rerun(a.run)
    if a.main:
        plan = main_arms()
        for tag, m, name, n, args in plan:
            if os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)):
                raise SystemExit("REFUSED: %s already holds campaigns" % tag)
            print("launch %s: %s" % (tag, " ".join(args)))
        print("ceilings: %s" % {"%s|%s" % (SHORT[m], name): c for (m, name), c in arm_ceilings().items()})
        if not a.run:
            print("dry: nothing launched. Re-run with --run.")
            return 0
        procs = []
        for tag, _m, _n, _k, args in plan:
            log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a")
            procs.append((tag, subprocess.Popen([sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args,
                                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)))
        codes = {tag: p.wait() for tag, p in procs}
        print("exit codes: %s" % codes)
        return max(codes.values())
    for tag, _a in arms():
        if os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)):
            raise SystemExit("REFUSED: %s already holds campaigns" % tag)
    cmds = [(tag, [sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args) for tag, args in arms()]
    for tag, c in cmds:
        print("launch %s: %s" % (tag, " ".join(c[2:]).replace(ROOT + "/", "")))
    if not a.run:
        print("dry: nothing launched. Re-run with --run.")
        return 0
    procs = []
    for tag, c in cmds:
        log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a")
        procs.append((tag, subprocess.Popen(c, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)))
    codes = {tag: p.wait() for tag, p in procs}
    print("exit codes: %s" % codes)
    return max(codes.values())


if __name__ == "__main__":
    sys.exit(main())
