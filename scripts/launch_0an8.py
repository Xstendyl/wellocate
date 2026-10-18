#!/usr/bin/env python3
"""Repeat the GB1 Blind arm on scrambled PhoQ for all five models: trial run, trial checks and main run.

The arm uses the paper's PhoQ scramble, the Blind condition with the truthful re-ask, multiplicative assay noise
(CV 0.073), 15% failures and 15 rounds of 4, with each model at the reasoning setting and output budget of its
GB1 Blind arm, on seeds 17,000,000 to 17,000,029. The trial checks per model that campaigns complete, replies
parse, no campaign loses more than 10 slots, no prompt leaks a true value or names PhoQ, each history replays
exactly through the oracle, and the projected cost fits the ceiling. The main run goes one model and one seed
at a time, gated on the credit balance, skips seeds already written, and re-runs each abandoned seed once.

Usage:
  set -a; . ./.env; set +a
  python3 scripts/launch_0an8.py --check            (seeds, scramble, plan; no call)
  python3 scripts/launch_0an8.py --smoke [--run]
  python3 scripts/launch_0an8.py --smoke-report
  python3 scripts/launch_0an8.py --main [--run]
  python3 scripts/launch_0an8.py --auto --run       (trial, checks, then the main run if the checks pass)
Logs: results/launch_0an8.log; balances: results/balance_0an8.jsonl; the checks: results/smoke_0an8_report.json.
"""
import argparse, glob, json, os, re, shutil, statistics as st, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import launch_0an as L                                                        # noqa: E402

# (short, model, output tokens, reasoning effort, ceiling in $), in the paper's order
MODELS = (("opus", "anthropic/claude-opus-4.7", 6000, None, 40.0),
          ("flash", "google/gemini-2.5-flash", 6000, None, 15.0),
          ("deepseek", "deepseek/deepseek-chat-v3.1", 6000, None, 15.0),
          ("sol", "openai/gpt-6.1-sol", 16000, "minimal", 15.0),
          ("gem", "google/gemini-3.1-pro-preview", 32000, "minimal", 30.0))
SEED0, N = 17_000_000, 30
SMOKE_SEED0, SMOKE_N = 18_000_000, 2
SEEDS = [SEED0 + i for i in range(N)]
SMOKE_BUDGET = {"opus": 1.50, "flash": 0.30, "deepseek": 0.30, "sol": 1.50, "gem": 3.00}
PANEL_CEILING = 100.0
PROCEED_AT_MOST = 80.0
ABANDON_LIMIT = 1                                   # 5% of 30
LOST_ROUND_LIMIT = 10
LANDSCAPE_LABEL = "phoq_scrambled_s20261004_p93.0"
LETTER_MAPS = ["IGLSJKDBHCOPRATENMFQ", "BFJGHMTDQENILAOCRPSK", "GMLAHFRBNDQPOIJTESKC", "BFAOHNCLGSITMJEDKPQR"]
START, EXAMPLE = "EDQS", "IDQS"
COMMON = [x for x in L.COMMON]
COMMON[COMMON.index("--max-tokens"):COMMON.index("--max-tokens") + 2] = []
COMMON += ["--landscape", "phoq_scrambled"]
RES = os.path.join(ROOT, "results")
LOG = os.path.join(RES, "launch_0an8.log")
BAL = os.path.join(RES, "balance_0an8.jsonl")
STATE = os.path.join(RES, "state_0an8.json")
FAILED = re.compile(r"seed\s+(\d+)\s+(?:FAILED|ABANDONED)")
REFUSAL = re.compile(r"\b(?:I can't|I cannot|I won't|I'm sorry|I am sorry|unable to help|can't assist)\b", re.I)
FORBIDDEN = re.compile(r"phoq|protein|amino|gb1|kinase|histidine", re.I)
DECIMAL = re.compile(r"(?<![\w.])-?\d+\.\d+")       # greedy; a sentence-final "1.234." still matches


BARE_TOKEN = re.compile(r"^[A-T]{4}$")


def bare_single_token(c):
    """A reply that is exactly one valid candidate token, read as that token by the primary parser, counts as
    parser agreement, since the secondary parser needs "| reason" and reads nothing from a bare token."""
    raw = (c.get("raw_response") or "").strip()
    return bool(BARE_TOKEN.match(raw)) and list(c.get("parsed") or []) == [raw]


def genuine_disagreement(c):
    """The parsers differ, the primary read something, and the reply is not a bare single valid token."""
    return not c.get("parsers_agree", True) and bool(c.get("parsed")) and not bare_single_token(c)


def say(s):
    print(s, flush=True)
    with open(LOG, "a") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z ") + s + "\n")


def smoke_tag(short):
    return "smoke0an8_" + short


def main_tag(short):
    return "gen_0an8_%s_phoq_blind" % short


def model_args(short, model, tokens, effort, tag, campaigns, seed0, budget, workers):
    a = ["--models", model, "--campaigns", str(campaigns), "--seed0", str(seed0), "--tag", tag,
         "--stage", "0an8_smoke" if tag.startswith("smoke") else "0an8_main", "--budget-usd", "%.2f" % budget,
         "--max-tokens", str(tokens)] + COMMON
    if effort:
        a += ["--reasoning-effort", effort]
    a[a.index("--workers") + 1] = str(workers)
    return a


# ---------------------------------------------------------------- seeds, scramble, balance ----------------------
def check_seeds():
    """Main and trial seeds new everywhere: results, run manifests, seed bases in tracked code (this file excepted),
    and Wellocate's frozen splits."""
    import replicate_decision_rule as RD
    sp = json.load(open(os.path.join(ROOT, "wellocate", "splits.json")))["splits"]
    used = seeds_in_results_but_ours()
    own = [main_tag(m[0]) for m in MODELS] + [main_tag(m[0]) + "_rerun" for m in MODELS] + [smoke_tag(m[0]) for m in MODELS]
    for lo, hi, what in ((SEED0, SEED0 + N, "main"), (SMOKE_SEED0, SMOKE_SEED0 + SMOKE_N, "smoke")):
        hit = sorted(set(range(lo, hi)) & used)
        if hit:
            raise SystemExit("REFUSED: %s seeds %s are already used in results" % (what, hit[:5]))
        for a, b, src in RD.ranges_in_manifests():
            if a < hi and lo < b and not any(("grid_%s_manifest" % t) in src for t in own):
                raise SystemExit("REFUSED: %s seeds overlap %s's range [%d, %d)" % (what, src, a, b))
        for base, src in RD.bases_in_code():
            if "launch_0an8.py" not in src and "references_0an8.py" not in src and "analyse_0an8.py" not in src \
                    and base < hi and lo < base + RD.SPAN:
                raise SystemExit("REFUSED: %s seeds fall within %d of the seed base %d at %s" % (what, RD.SPAN, base, src))
        for name, s in sp.items():
            a, b = s["campaign_seed_start"], s["campaign_seed_start"] + s["episodes"]
            if a < hi and lo < b:
                raise SystemExit("REFUSED: %s seeds overlap Wellocate's %s" % (what, name))
    print("seeds clear: main %d..%d, smoke %d..%d" % (SEED0, SEED0 + N - 1, SMOKE_SEED0, SMOKE_SEED0 + SMOKE_N - 1))


def seeds_in_results_but_ours():
    """replicate_decision_rule.seeds_in_results, leaving out this run's own files so that a relaunch is not
    refused by its own data."""
    import gzip
    out = set()
    paths = glob.glob(os.path.join(RES, "**", "*.jsonl"), recursive=True) + \
        glob.glob(os.path.join(RES, "**", "*.jsonl.gz"), recursive=True)
    for p in paths:
        if "0an8" in os.path.relpath(p, RES):
            continue
        fh = gzip.open(p, "rt", errors="replace") if p.endswith(".gz") else open(p, errors="replace")
        with fh:
            for line in fh:
                if '"seed"' in line or '"campaign_seed"' in line:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    for k in ("seed", "campaign_seed"):
                        if isinstance(r.get(k), int):
                            out.add(r[k])
    return out


def check_scramble():
    """The paper's PhoQ scramble, and no overlap with the frozen splits' scrambles."""
    from repdef import envs as EV
    e = EV.phoq_scrambled()
    sp = json.load(open(os.path.join(ROOT, "wellocate", "splits.json")))["splits"]
    if e.label != LANDSCAPE_LABEL or e.meta["letter_maps"] != LETTER_MAPS or e.anchor != START or e.example != EXAMPLE:
        raise SystemExit("REFUSED: phoq_scrambled is not 0am's scramble: %s %s %s" % (e.label, e.anchor, e.meta["letter_maps"]))
    seed = e.meta["scramble_seed"]
    others = {name: [i for i in s["instances"] if i.startswith("phoq/scramble:")] for name, s in sp.items()
              if s["family"] == "phoq" and name != "phoq:paper"}
    clash = [n for n, ins in others.items() if "phoq/scramble:%d" % seed in ins]
    if clash or sp["phoq:paper"]["instances"] != ["phoq/scramble:%d" % seed]:
        raise SystemExit("REFUSED: scramble %d appears in %s" % (seed, clash or "no paper split"))
    n = sum(len(v) for v in others.values())
    print("scramble %d is the phoq:paper instance and none of the %d train, validation and test scrambles" % (seed, n))
    return e


def balance():
    import grid
    for _ in range(3):
        b = grid.credit_balance()
        if b is not None:
            return b
        time.sleep(10)
    return None


def record_balance(event, **kw):
    b = balance()
    row = dict(t=time.strftime("%Y-%m-%dT%H:%M:%S%z"), event=event, balance=b, **kw)
    with open(BAL, "a") as f:
        f.write(json.dumps(row) + "\n")
    say("balance %s: %s" % (event, "$%.4f" % b if b is not None else "UNREADABLE"))
    return b


def balances():
    return [json.loads(l) for l in open(BAL)] if os.path.exists(BAL) else []


def rows(tag):
    p = os.path.join(RES, "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def log_lines(tag):
    p = os.path.join(RES, "grid_%s.log" % tag)
    return open(p, errors="replace").read().splitlines() if os.path.exists(p) else []


# ---------------------------------------------------------------- the trial run ------------------------------------
def smoke(run):
    check_seeds()
    check_scramble()
    for short, *_r in MODELS:
        if rows(smoke_tag(short)):
            raise SystemExit("REFUSED: %s already holds campaigns" % smoke_tag(short))
    cmds = []
    for short, model, tokens, effort, _c in MODELS:
        a = model_args(short, model, tokens, effort, smoke_tag(short), SMOKE_N, SMOKE_SEED0, SMOKE_BUDGET[short], 2)
        cmds.append((smoke_tag(short), [sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + a))
        print("launch %s: %s" % (smoke_tag(short), " ".join(a)))
    if not run:
        print("dry: nothing launched. Re-run with --run.")
        return 0
    if record_balance("before smoke") is None:
        raise SystemExit("STOP: the credit balance cannot be read")
    procs = [(t, subprocess.Popen(c, cwd=ROOT, stdout=open(os.path.join(RES, "grid_%s.log" % t), "a"),
                                  stderr=subprocess.STDOUT)) for t, c in cmds]
    codes = {t: p.wait() for t, p in procs}
    say("smoke exit codes: %s" % codes)
    time.sleep(30)
    record_balance("after smoke")
    return max(codes.values())


def history(prompt):
    import confirm_counterfactual_0an7 as CC
    return CC.history(prompt)


def replay_ok(env, seed, lines):
    """Replay a history through the oracle with the source-keyed draws. Returns the number of mismatches."""
    from repdef import oracle as O
    import fair_reference_curve as FRC
    orc = O.Oracle(env.fit, env.pool, 0.0, seed, 0.15, noise_model="multiplicative", cv=FRC.CV,
                   noise_floor=FRC.FLOOR, rng_key=env.rng_key)
    bad = 0
    for rnd, seq, outc, obs in lines:
        if outc in ("abandoned", "round_lost"):
            orc.record_abandoned(rnd, seq, outcome=O.ABANDONED if outc == "abandoned" else O.ROUND_LOST)
            continue
        rec = orc.measure(seq, rnd)
        if rec.outcome != outc or (outc == "ok" and abs(rec.observed - obs) > 0.0006):
            bad += 1
    return bad


HIST_LINE = re.compile(r"^\s*(\d+)\s+(\S{4})\s+(.*)$")


def truth_check(prompt, start_value):
    """Decimal numbers outside the history rows that are not the start's stated value. History rows are checked
    separately: each must be a row of the campaign's nomination history, which the replay ties to the oracle's
    noisy readings. Lines with a "|" are the agent's own text quoted back in a re-ask, and are skipped."""
    stated = "%.2f" % start_value
    out = []
    for line in prompt.splitlines():
        if HIST_LINE.match(line) or "|" in line:
            continue
        out += [x for x in DECIMAL.findall(line) if x != stated]
    return out


def history_rows_outside(prompts, nomination_prompt):
    """History rows shown in a campaign's round prompts that its nomination history does not contain."""
    import collections
    full = collections.Counter(history(nomination_prompt))
    bad = []
    for p in prompts:
        if "HISTORY" not in p:
            continue
        rows_ = collections.Counter(history(p))
        if rows_ - full:
            bad.append(sorted(rows_ - full)[:3])
    return bad


def smoke_report():
    import analyse_0al as A0L
    env = check_scramble()
    out, bad = dict(models={}), []
    for short, model, tokens, effort, ceiling in MODELS:
        tag = smoke_tag(short)
        v = rows(tag)
        log = log_lines(tag)
        failed = [l.strip()[:300] for l in log if FAILED.search(l)]
        man = json.load(open(os.path.join(RES, "grid_%s_manifest.json" % tag)))
        calls = [c for c in A0L.calls(tag) if c["model"] == model]
        d = dict(tag=tag, campaigns=len(v), failed=failed, calls=len(calls),
                 empty=sum(1 for c in calls if c.get("empty_text")),
                 fallback_pattern=sum(1 for c in calls if (c.get("raw_response") or "").strip()
                                      and (c.get("reasoning_tokens") or 0) > 0
                                      and (c.get("completion_tokens") or 0) - (c.get("reasoning_tokens") or 0) <= 5),
                 refusals=sum(1 for c in calls if REFUSAL.search(c.get("raw_response") or "")),
                 truncated=sum(1 for c in calls if c.get("finish_reason") == "length"),
                 genuine_parser_disagreements=sum(1 for c in calls if genuine_disagreement(c)),
                 bare_token_agreements=sum(1 for c in calls if not c.get("parsers_agree", True) and bare_single_token(c)),
                 parse_rate=(sum(1 for c in calls if c.get("parse_status") == "ok"
                                 or (c.get("kind") == "nomination" and c.get("parsed"))) / len(calls)) if calls else None,
                 truthful_reask_fired=sum(1 for c in calls if "These candidates contain letters that are not in the alphabet"
                                          in (c.get("prompt") or "")),
                 median_reasoning=st.median([c.get("reasoning_tokens") or 0 for c in calls]) if calls else None,
                 lost_rounds=[r["rounds_lost_slots"] for r in v], lost_rejection=[r["slots_abandoned"] for r in v],
                 share=[round(100 * r["replication_count"] / r["slots_used"], 1) for r in v],
                 cost=[r["spend"] for r in v], landscape=man.get("landscape"),
                 prompt_options=man.get("prompt_options"), reasoning_effort=man.get("reasoning_effort"),
                 max_tokens=man.get("max_tokens"), git_commit=man.get("git_commit"),
                 code_dirty=man.get("code_dirty"))
        # No true value leaked and the scramble holds, over every prompt
        stray, named = [], []
        for c in calls:
            p = c.get("prompt") or ""
            stray += truth_check(p, env.fit[START])
            head = p.split("HISTORY", 1)[0]
            if 'The reference point is "%s"' % START not in head or 'for example "%s"' % START not in head:
                named.append("start not %s" % START)
            if FORBIDDEN.search(p):
                named.append(FORBIDDEN.search(p).group(0))
        d["stray_decimals"], d["scramble_problems"] = stray[:10], named[:10]
        # Each history replays exactly through the oracle
        repro, noms = [], {}
        for c in calls:
            if c.get("kind") == "nomination":
                noms[c["campaign_seed"]] = c["prompt"]
        for r in v:
            p = noms.get(r["seed"])
            if p is None:
                repro.append((r["seed"], "no nomination prompt"))
                continue
            n_bad = replay_ok(env, r["seed"], history(p))
            if n_bad:
                repro.append((r["seed"], "%d mismatches" % n_bad))
            outside = history_rows_outside([c.get("prompt") or "" for c in calls
                                            if c["campaign_seed"] == r["seed"] and c.get("kind") != "nomination"], p)
            if outside:
                repro.append((r["seed"], "round-prompt history rows not in the nomination history: %s" % outside[:2]))
            if abs(env.fit[r["nominated"]] - r["nominated_true"]) > 1e-9 if r["nominated"] in env.fit else True:
                repro.append((r["seed"], "nominee true value"))
        d["reproduction_problems"] = repro
        d["largest_campaign_cost"] = max(d["cost"]) if d["cost"] else None
        d["projected_30"] = N * d["largest_campaign_cost"] if d["cost"] else None
        d["ceiling"] = ceiling
        checks = dict(complete=len(v) == SMOKE_N and not failed,
                      replies=not (d["empty"] or d["fallback_pattern"] or d["refusals"] or d["truncated"]
                                   or d["genuine_parser_disagreements"]),
                      slots=all(x <= LOST_ROUND_LIMIT for x in d["lost_rounds"]),
                      no_truth=not stray and not repro,
                      scramble=d["landscape"] == LANDSCAPE_LABEL and not named,
                      reproduces=not repro and len(v) == SMOKE_N,
                      settings=(man.get("prompt_options", {}).get("truthful_reask") is True
                                and not any(man.get("prompt_options", {}).get(k) for k in
                                            ("goal_true_value", "fix_replacement_budget", "riskfree_rejection",
                                             "ledger", "menu", "repeat_cap", "structure"))
                                and man.get("max_tokens") == tokens and man.get("reasoning_effort") == effort
                                and man.get("temperature") == 0.0 and not man.get("code_dirty")),
                      cost=d["projected_30"] is not None and d["projected_30"] <= ceiling)
        d["checks"] = checks
        out["models"][model] = d
        for k, ok in checks.items():
            if not ok:
                bad.append((short, k))
        print("%-9s %d/%d campaigns, %d calls, parse %.1f%%, empty %d, fallback %d, refusals %d, truncated %d, "
              "disagreements %d | lost rounds %s, rejection losses %s, share %s | cost %s, projected $%.2f of $%.0f"
              % (short, len(v), SMOKE_N, d["calls"], 100 * (d["parse_rate"] or 0), d["empty"], d["fallback_pattern"],
                 d["refusals"], d["truncated"], d["genuine_parser_disagreements"], d["lost_rounds"],
                 d["lost_rejection"], d["share"], ["%.4f" % x for x in d["cost"]], d["projected_30"] or 0, ceiling))
        print("          checks: %s" % ", ".join("%s %s" % (k, "ok" if ok else "FAIL") for k, ok in checks.items()))
        for x in failed + d["stray_decimals"] + d["scramble_problems"] + [str(p) for p in repro]:
            print("          problem: %s" % x)
    total = sum(d["projected_30"] or 0 for d in out["models"].values())
    out["projected_total"] = total
    smoke_cost = sum(sum(d["cost"]) for d in out["models"].values())
    b = [x for x in balances() if x["event"] in ("before smoke", "after smoke")]
    out["smoke_recorded_cost"] = smoke_cost
    out["balance"] = b
    if len(b) == 2 and all(x["balance"] is not None for x in b):
        out["smoke_cost_by_balance"] = b[0]["balance"] - b[1]["balance"]
    if total > PROCEED_AT_MOST:
        bad.append(("panel", "projected $%.2f above $%.0f" % (total, PROCEED_AT_MOST)))
    out["gate"] = "PASS" if not bad else "FAIL"
    out["failures"] = bad
    json.dump(out, open(os.path.join(RES, "smoke_0an8_report.json"), "w"), indent=1)
    print("smoke cost: recorded $%.4f, by balance %s" % (smoke_cost, "$%.4f" % out["smoke_cost_by_balance"]
                                                          if "smoke_cost_by_balance" in out else "n/a"))
    print("projected main run: $%.2f (proceed if at most $%.0f)" % (total, PROCEED_AT_MOST))
    say("SMOKE GATE: %s %s" % (out["gate"], bad if bad else ""))
    return 0 if not bad else 1


# ---------------------------------------------------------------- the main run ------------------------------------
def biggest(short):
    v = [r["spend"] for t in (smoke_tag(short), main_tag(short), main_tag(short) + "_rerun",
                              main_tag(short) + "_cont", main_tag(short) + "_cont_rerun", main_tag(short) + "_fin")
         for r in rows(t)]
    return max(v) if v else None


def state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def run_one(short, model, tokens, effort, ceiling, tag, seed, run, s, spent_of=None, extra=()):
    """Check the balance, run one campaign, classify it. Returns 'written', 'abandoned' or raises SystemExit.
    `spent_of(balance)` gives the model's spend by balance; by default its start balance minus the balance now."""
    big = biggest(short)
    bal = balance()
    if bal is None:
        say("STOP: the credit balance cannot be read before %s seed %d" % (tag, seed))
        raise SystemExit(1)
    m_spent = spent_of(bal) if spent_of else s["model_start"][short] - bal
    p_spent = s["panel_start"] - bal
    say("before %s seed %d: balance $%.4f, %s by balance $%.4f of $%.0f, panel $%.4f of $%.0f, largest campaign $%.4f"
        % (tag, seed, bal, short, m_spent, ceiling, p_spent, PANEL_CEILING, big))
    if m_spent + big > ceiling or p_spent + big > PANEL_CEILING:
        say("STOP: the next campaign could take %s past $%.0f or the panel past $%.0f" % (short, ceiling, PANEL_CEILING))
        raise SystemExit(1)
    a = model_args(short, model, tokens, effort, tag, N, SEED0, ceiling, 1) + ["--seeds", str(seed)] + list(extra)
    if not run:
        say("dry: would run %s" % " ".join(a))
        return "dry"
    before = len(log_lines(tag))
    with open(os.path.join(RES, "grid_%s.log" % tag), "a") as f:
        subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + a, cwd=ROOT, stdout=f,
                       stderr=subprocess.STDOUT)
    mp = os.path.join(RES, "grid_%s_manifest.json" % tag)
    if os.path.exists(mp):
        shutil.copy(mp, mp.replace(".json", "_%d.json" % seed))
    ok = any(r["seed"] == seed for r in rows(tag))
    new = log_lines(tag)[before:]
    gone = any(FAILED.search(l) and int(FAILED.search(l).group(1)) == seed for l in new)
    # Only a logged FAILED or ABANDONED line counts as abandonment; a launch that never ran does not.
    if not ok and not gone:
        say("STOP: %s seed %d neither wrote a row nor failed; the run did not start. Last log lines: %s"
            % (tag, seed, " | ".join(x.strip() for x in new[-3:])))
        raise SystemExit(1)
    say("%s seed %d: %s" % (tag, seed, "written" if ok else "abandoned"))
    return "written" if ok else "abandoned"


def first_pass_abandoned(tag):
    written = {r["seed"] for r in rows(tag)}
    return sorted({int(m.group(1)) for l in log_lines(tag) for m in [FAILED.search(l)] if m} - written)


def main_run(run):
    check_seeds()
    check_scramble()
    rep = json.load(open(os.path.join(RES, "smoke_0an8_report.json")))
    if rep.get("gate") != "PASS":
        raise SystemExit("REFUSED: the smoke gate did not pass")
    s = state()
    if run and "panel_start" not in s:
        b = [x for x in balances() if x["event"] == "before smoke"]
        if not b or b[0]["balance"] is None:
            raise SystemExit("REFUSED: no balance recorded before the smoke")
        s["panel_start"] = b[0]["balance"]
        s["model_start"], s["model_end"], s["stopped"], s["dropped"] = {}, {}, {}, {}
        save_state(s)
    if not run:
        s = dict(panel_start=0.0, model_start={m[0]: 0.0 for m in MODELS}, model_end={}, stopped={}, dropped={})
    for short, model, tokens, effort, ceiling in MODELS:
        tag = main_tag(short)
        if short in s.get("model_end", {}):
            say("%s complete (%s)" % (short, s["model_end"][short]))
            continue
        if run and short not in s["model_start"]:
            time.sleep(30)                                  # let the previous model's last charges settle
            s["model_start"][short] = record_balance("start %s" % short, model=model)
            save_state(s)
        say("== %s (%s): ceiling $%.0f" % (short, model, ceiling))
        stopped = None
        for seed in SEEDS:
            written = {r["seed"] for r in rows(tag)}
            gone = first_pass_abandoned(tag)
            if seed in written or seed in gone:
                continue
            if len(gone) > ABANDON_LIMIT:
                stopped = "%d first-pass campaigns abandoned, above the limit of %d: %s" % (len(gone), ABANDON_LIMIT, gone)
                break
            run_one(short, model, tokens, effort, ceiling, tag, seed, run, s)
        gone = first_pass_abandoned(tag)
        if stopped is None and len(gone) > ABANDON_LIMIT:
            stopped = "%d first-pass campaigns abandoned, above the limit of %d: %s" % (len(gone), ABANDON_LIMIT, gone)
        if stopped:
            say("ARM STOPPED, %s: %s" % (short, stopped))
            if run:
                s["stopped"][short] = stopped
        else:
            rtag = tag + "_rerun"
            for seed in gone:
                if any(r["seed"] == seed for r in rows(rtag)):
                    continue
                if seed in first_pass_abandoned(rtag):
                    continue
                say("re-run of abandoned seed %d" % seed)
                run_one(short, model, tokens, effort, ceiling, rtag, seed, run, s)
            twice = first_pass_abandoned(rtag)
            if twice:
                say("seeds abandoned twice, dropped: %s" % twice)
                if run:
                    s["dropped"][short] = twice
        if run:
            time.sleep(30)
            end = record_balance("end %s" % short, model=model)
            s["model_end"][short] = dict(balance=end, by_balance=(s["model_start"][short] - end) if end is not None else None,
                                         recorded=sum(r["spend"] for t in (tag, tag + "_rerun") for r in rows(t)))
            save_state(s)
    if run:
        record_balance("end of main run")
    say("main run done: %s" % json.dumps({k: s.get(k) for k in ("stopped", "dropped")}))
    return 0


# ---------------------------------------------------------------- the continuation ---------------------------------
CONT_FAIL_LIMIT = 3
RESEND = os.path.join(RES, "resend_0an8.json")


def resend_failed(short, model, tokens, effort, tag):
    """Send the failing request of `tag`'s last abandoned campaign once more, exactly: the same prompt, model,
    output budget, temperature and reasoning effort. Returns True when an answer comes back. Recorded once in
    results/resend_0an8.json and never repeated."""
    import hashlib
    import grid
    from repdef import llm
    if os.path.exists(RESEND):
        r = json.load(open(RESEND))
        say("resend already made: %s" % r["outcome"])
        return r["outcome"] == "answer"
    p = os.path.join(RES, "grid_%s_abandoned_calls.jsonl" % tag)
    fails = [json.loads(l) for l in open(p) if l.strip() and json.loads(l).get("failing_call")] if os.path.exists(p) else []
    if not fails or not fails[-1].get("prompt"):
        say("STOP: no recorded failing request to resend in %s" % os.path.relpath(p, ROOT))
        raise SystemExit(1)
    f = fails[-1]
    grid.key_source()                                   # the run's own key, or refuse
    c = llm.complete(f["prompt"], model, max_tokens=tokens, temperature=0.0, reasoning_effort=effort)
    out = dict(t=time.strftime("%Y-%m-%dT%H:%M:%S%z"), tag=tag, seed=f.get("campaign_seed"), round=f.get("round"),
               kind=f.get("kind"), prompt_sha256=hashlib.sha256(f["prompt"].encode("utf-8")).hexdigest(),
               prompt_tokens_recorded=f.get("prompt_tokens"), original_error=f.get("error"),
               original_raw_payload=f.get("raw_payload"), outcome="answer" if c.ok and (c.text or "").strip() else "empty",
               resend=dict(ok=c.ok, error=c.error, text=c.text, finish_reason=c.finish_reason,
                           prompt_tokens=c.prompt_tokens, completion_tokens=c.completion_tokens,
                           reasoning_tokens=c.reasoning_tokens, provider=c.provider, cost_usd=c.cost_usd,
                           raw_payload=c.raw))
    json.dump(out, open(RESEND, "w"), indent=1, default=str)
    say("resend of %s seed %s round %s: %s" % (tag, out["seed"], out["round"], out["outcome"]))
    return out["outcome"] == "answer"


def continuation(short, run):
    """Sol only, after the main run: the probe re-run of seed 17,000,015, then the other abandoned seed's re-run,
    then the 13 unrun seeds; balance-gated, one at a time, the same settings and ceiling."""
    short, model, tokens, effort, ceiling = [m for m in MODELS if m[0] == short][0]
    s = state()
    if short not in s.get("stopped", {}):
        raise SystemExit("REFUSED: %s's arm did not stop; there is nothing to continue" % short)
    base = main_tag(short)
    rtag, ctag, crtag = base + "_rerun", base + "_cont", base + "_cont_rerun"
    gone = first_pass_abandoned(base)
    written = {r["seed"] for r in rows(base)}
    unrun = [sd for sd in SEEDS if sd not in written and sd not in gone]
    say("== continuation of %s: re-runs %s, then %d unrun seeds %d..%d; ceiling $%.0f"
        % (short, gone, len(unrun), unrun[0], unrun[-1], ceiling))
    if run:
        s.setdefault("cont_start", {})
        if short not in s["cont_start"]:
            s["cont_start"][short] = record_balance("start %s continuation" % short, model=model)
            save_state(s)
    main_spent = s["model_end"][short]["by_balance"]
    spent_of = (lambda bal: main_spent + (s["cont_start"][short] - bal)) if run else (lambda bal: 0.0)
    failures = lambda: sum(len(first_pass_abandoned(t)) for t in (rtag, ctag, crtag))

    def attempt(tag, seed):
        if any(r["seed"] == seed for r in rows(tag)) or seed in first_pass_abandoned(tag):
            return
        if failures() >= CONT_FAIL_LIMIT:
            say("STOP: %d continuation failures, the limit; reported" % failures())
            raise SystemExit(1)
        run_one(short, model, tokens, effort, ceiling, tag, seed, run, s, spent_of=spent_of)

    # The probe: seed 17,000,015's re-run. If it fails, resend its exact request once; an empty resend stops
    # everything before any other campaign runs.
    probe = gone[0]
    attempt(rtag, probe)
    if run and probe in first_pass_abandoned(rtag):
        say("the probe failed again: seed %d is dropped; resending its failing request once" % probe)
        if not resend_failed(short, model, tokens, effort, rtag):
            say("STOP: the resend came back empty; nothing more runs")
            raise SystemExit(1)
    # Then the other abandoned seed's re-run; a second failure drops it
    for seed in gone[1:]:
        attempt(rtag, seed)
    # Then the unrun seeds; a failing seed runs once more under _cont_rerun, and is dropped if it fails again
    for seed in unrun:
        attempt(ctag, seed)
    for seed in first_pass_abandoned(ctag):
        attempt(crtag, seed)
    dropped = first_pass_abandoned(rtag) + first_pass_abandoned(crtag)
    if run:
        time.sleep(30)
        end = record_balance("end %s continuation" % short, model=model)
        s["cont_end"] = s.get("cont_end", {})
        s["cont_end"][short] = dict(balance=end, by_balance=(s["cont_start"][short] - end) if end is not None else None,
                                    recorded=sum(r["spend"] for t in (rtag, ctag, crtag) for r in rows(t)),
                                    dropped=dropped, failures=failures())
        save_state(s)
    say("continuation of %s done: dropped %s, continuation failures %d" % (short, dropped, failures()))
    return 0


# ---------------------------------------------------------------- finishing Sol ------------------------------------
HEALTH = os.path.join(RES, "health_0an8.jsonl")
HEALTH_WAIT_S, HEALTH_TRIES = 15 * 60, 5          # one try, then up to 4 more, 15 minutes apart
FIN_DROP_LIMIT = 3


def health_gate(short, model, tokens, effort):
    """One cheap request to the model: its exact round-1 prompt, at the arm's settings. Nothing runs unless it
    succeeds. On a failure, wait 15 minutes and try again, at most 4 more times. Every try is recorded."""
    import analyse_0al as A0L
    import grid
    from repdef import llm
    grid.key_source()
    p = next(c["prompt"] for c in A0L.calls(main_tag(short)) if c.get("kind") == "round" and c.get("round") == 1)
    for i in range(HEALTH_TRIES):
        c = llm.complete(p, model, max_tokens=tokens, temperature=0.0, reasoning_effort=effort)
        ok = c.ok and bool((c.text or "").strip())
        rec = dict(t=time.strftime("%Y-%m-%dT%H:%M:%S%z"), try_=i + 1, ok=ok, error=c.error, provider=c.provider,
                   prompt_tokens=c.prompt_tokens, completion_tokens=c.completion_tokens, cost_usd=c.cost_usd,
                   raw_error=(c.raw or {}).get("error") if isinstance(c.raw, dict) else None)
        with open(HEALTH, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        say("health gate, try %d of %d: %s" % (i + 1, HEALTH_TRIES, "ok" if ok else "FAILED (%s)" % (c.error or "empty")))
        if ok:
            return True
        if i + 1 < HEALTH_TRIES:
            time.sleep(HEALTH_WAIT_S)
    return False


def finish(short, run):
    """Sol's last 8 seeds with provider retries (--provider-retry), tag suffix _fin: the three the continuation
    abandoned, then the five it left unrun. One at a time, balance-gated, the same ceiling. A seed still failing
    after its resends is dropped; a third such seed stops the run."""
    short, model, tokens, effort, ceiling = [m for m in MODELS if m[0] == short][0]
    s = state()
    base = main_tag(short)
    ctag, ftag = base + "_cont", base + "_fin"
    done = {r["seed"] for t in (base, base + "_rerun", ctag, base + "_cont_rerun") for r in rows(t)}
    plan = [sd for sd in first_pass_abandoned(ctag) if sd not in done] + \
           [sd for sd in SEEDS if sd not in done and sd not in first_pass_abandoned(ctag)]
    say("== finishing %s under the transport amendment: %s; ceiling $%.0f" % (short, plan, ceiling))
    bal_rows = balances()
    if run and "cont_end" not in s:
        st0 = [b for b in bal_rows if b["event"] == "start sol continuation"]
        st1 = [b for b in bal_rows if b["event"] == "after sol continuation stop"]
        s["cont_end"] = {short: dict(balance=st1[-1]["balance"], by_balance=st0[-1]["balance"] - st1[-1]["balance"],
                                     recorded=sum(r["spend"] for t in (base + "_rerun", ctag, base + "_cont_rerun")
                                                  for r in rows(t)), note="the continuation stopped at its third failure")}
        save_state(s)
    before = s["model_end"][short]["by_balance"] + (s.get("cont_end", {}).get(short, {}).get("by_balance") or 0.0)
    if run:
        if not health_gate(short, model, tokens, effort):
            say("STOP: the health gate failed %d times; nothing ran" % HEALTH_TRIES)
            raise SystemExit(1)
        s.setdefault("fin_start", {})
        if short not in s["fin_start"]:
            s["fin_start"][short] = record_balance("start %s finish" % short, model=model)
            save_state(s)
    spent_of = (lambda bal: before + (s["fin_start"][short] - bal)) if run else (lambda bal: 0.0)
    for seed in plan:
        if any(r["seed"] == seed for r in rows(ftag)) or seed in first_pass_abandoned(ftag):
            continue
        if len(first_pass_abandoned(ftag)) >= FIN_DROP_LIMIT:
            break
        run_one(short, model, tokens, effort, ceiling, ftag, seed, run, s, spent_of=spent_of,
                extra=["--provider-retry"])
    dropped = first_pass_abandoned(ftag)
    if len(dropped) >= FIN_DROP_LIMIT:
        say("STOP: %d seeds still failed after their resends, the limit: %s" % (len(dropped), dropped))
    if run:
        time.sleep(30)
        end = record_balance("end %s finish" % short, model=model)
        s["fin_end"] = s.get("fin_end", {})
        s["fin_end"][short] = dict(balance=end, by_balance=(s["fin_start"][short] - end) if end is not None else None,
                                   recorded=sum(r["spend"] for r in rows(ftag)), dropped=dropped)
        save_state(s)
    say("finishing %s done: dropped %s" % (short, dropped))
    return 1 if len(dropped) >= FIN_DROP_LIMIT else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--smoke-report", action="store_true")
    ap.add_argument("--main", action="store_true")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--continue-model", default="", help="0an.8 note 3: continue a stopped arm (sol)")
    ap.add_argument("--finish-model", default="", help="0an.8 note 4: finish an arm under the transport amendment (sol)")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.continue_model:
        return continuation(a.continue_model, a.run)
    if a.finish_model:
        return finish(a.finish_model, a.run)
    if a.check:
        check_seeds()
        check_scramble()
        for short, model, tokens, effort, ceiling in MODELS:
            print("%-9s %-32s %5d tokens, effort %-8s ceiling $%.0f, smoke budget $%.2f"
                  % (short, model, tokens, effort, ceiling, SMOKE_BUDGET[short]))
            print("          main: %s" % " ".join(model_args(short, model, tokens, effort, main_tag(short), N, SEED0,
                                                            ceiling, 1) + ["--seeds", "<seed>"]))
        return 0
    if a.smoke:
        return smoke(a.run)
    if a.smoke_report:
        return smoke_report()
    if a.main:
        return main_run(a.run)
    if a.auto:
        if not a.run:
            raise SystemExit("--auto needs --run")
        smoke(True)
        if smoke_report() != 0:
            say("STOP after the smoke: see results/smoke_0an8_report.json")
            return 1
        return main_run(True)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
