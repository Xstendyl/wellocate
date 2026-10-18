#!/usr/bin/env python3
"""Run the main grid: five prompt conditions on an NK landscape under multiplicative noise, three models.

The agent names its own answer, and the shrinkage comparator is recorded on every campaign. Spend is printed as it
accrues and the run stops at the spending ceiling.

Usage:
  python3 scripts/grid.py --probe                  # cost probe: 5 campaigns per model, Mechanism condition
  python3 scripts/grid.py --campaigns 40           # the grid
  python3 scripts/grid.py --probe --dry            # print one prompt per model, spend nothing
"""
import hashlib
import io
import urllib.request
import argparse, collections, json, math, os, statistics as st, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C, envs as EV, llm_policy as LP, policies as P, prompts
from repdef.nk import NKLandscape

ENV = os.path.expanduser("<sibling-project>/.env")
RESULTS = os.path.join(ROOT, "results")

# --- settings fixed by the pre-registration ---------------------------------------------------
CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762
K, SEED, PCT = 1, 1, 93.0
ROUNDS, SLOTS, FAIL_PCT = 15, 4, 15
CONDITIONS = [("Blind", "blind"), ("Quantitative", "informed"), ("Mechanism", "instructed"),
              ("Aggregated", "aggregated"), ("Decision-rule", "decision_rule")]
# Biology-framing panel: three cells on the Blind rung, differing in the opening sentence and in sigma.
# Kept out of CONDITIONS so a plain grid run never selects them; each cell carries its own environment.
BIO_CONDITIONS = [("BioRole", "blind"), ("BioRoleNoisy", "blind"), ("BioRoleExact", "blind")]
CELL_ENV = {
    "BioRole":      ("bio_role", "multiplicative"),
    "BioRoleNoisy": ("bio_role_noisy", "multiplicative"),
    "BioRoleExact": ("bio_role_exact", "exact"),
}
# Release date of each model version: the provider's public release, not the OpenRouter listing date.
MODELS = [("frontier", "anthropic/claude-opus-4.7", "2026-02"),
          ("mid-tier", "google/gemini-2.5-flash", "2025-06"),
          ("open-weight", "deepseek/deepseek-chat-v3.1", "2025-08")]
# Run only when --models names them; a run that names none uses the grid's three.
EXTRA_MODELS = [("frontier-openai", "openai/gpt-6.1-sol", "2026-09"),
                ("frontier-google", "google/gemini-3.1-pro-preview", "2026-02")]
STAGE_CEILING_USD = 600.0
LANDSCAPE_PROMPT = "abstract"        # a generated landscape gets the abstract framing, never biology

# The reference point is derived from the landscape: the pool-median sequence, lexicographically first
# among ties. The format example is the lexicographically first Hamming-1 neighbour, not selected for
# viability, matching GB1's pattern (ADGV is one mutation from VDGV).
ALPHABET = "ABCDEFGHIJKLMNOPQRST"


def reference_point(fit, pool):
    med = st.median([fit[s] for s in pool])
    anchor = min(sorted(pool), key=lambda s: (abs(fit[s] - med), s))
    h1 = sorted(anchor[:i] + c + anchor[i + 1:] for i in range(4) for c in ALPHABET
                if c != anchor[i])
    return anchor, h1[0], fit[anchor]


def spotcheck(log_rows, models, tag, per_model=20):
    """Write raw responses beside parsed proposals for 20 calls per model, sampled deterministically by index."""
    import repdef.rng as R
    dest = os.path.join(RESULTS, "grid_%s_spotcheck.txt" % tag)
    with open(dest, "w") as f:
        f.write("SPOT CHECK: raw model output beside the proposals the harness accepted.\n")
        f.write("Sampled deterministically, %d calls per model. Written for a human to read.\n" % per_model)
        for role, model, _rel in models:
            cs = [c for c in log_rows if c["model"] == model and c.get("kind") != "nomination"]
            if not cs:
                continue
            idx = sorted({R._u64("spot", i, model) % len(cs) for i in range(per_model * 3)})[:per_model]
            f.write("\n" + "=" * 100 + "\n%s  (%s)   %d calls, showing %d\n" % (model, role, len(cs), len(idx)))
            f.write("=" * 100 + "\n")
            for j in idx:
                c = cs[j]
                f.write("\n--- round %s  slots %s  status %s  tier %s  accepted %s  tokens-anywhere %s  "
                        "parsers agree %s ---\n"
                        % (c.get("round"), c.get("n_slots"), c.get("parse_status"),
                           c.get("format_tier"), c.get("n_accepted"),
                           c.get("n_candidates_anywhere"), c.get("parsers_agree")))
                f.write("PARSED   : %s\n" % (c.get("parsed"),))
                f.write("SECONDARY: %s\n" % (c.get("parsed_secondary"),))
                f.write("RAW:\n%s\n" % (c.get("raw_response") or "")[:1200])
    return dest


def disagreement(log_rows):
    """Disagreement between the two parsers, split into genuine and by-design cases.

    Genuine: both parsers returned sequences and they differ (the 1% ceiling applies to these). By design: the
    primary returned nothing because the count did not match, while the secondary still read the pipe lines.

    Returns (genuine_rate, genuine, by_design, total).
    """
    cs = [c for c in log_rows if c.get("kind") != "nomination" and "parsers_agree" in c]
    if not cs:
        return 0.0, 0, 0, 0
    genuine = by_design = 0
    for c in cs:
        if c.get("parsers_agree"):
            continue
        if not c.get("parsed"):
            by_design += 1
        else:
            genuine += 1
    return genuine / len(cs), genuine, by_design, len(cs)


def archive_calls(tag, cpath, lpath):
    """Split the call log into one gzip per (condition, model) cell with a SHA256 manifest, and verify before deleting.

    The plain log is removed only after the gzips are read back and reproduce every line. A rerun of a tag merges
    into the existing archive: archived rows are kept for every campaign the new log does not contain.
    """
    import gzip, hashlib
    if not os.path.exists(lpath):
        return
    rows = [l for l in open(lpath) if l.strip()]
    cells_out = collections.defaultdict(list)
    for l in rows:
        try:
            d = json.loads(l)
        except ValueError:
            cells_out[("UNPARSEABLE", "UNPARSEABLE")].append(l)
            continue
        cells_out[(d.get("rung", "?"), d.get("model", "?"))].append(l)
    man, adir = {}, os.path.join(RESULTS, "grid_%s_calls" % tag)
    os.makedirs(adir, exist_ok=True)

    def cell_name(rung, model):
        return "%s__%s.jsonl.gz" % (rung, str(model).replace("/", "_"))

    def camp_key(line):
        try:
            d = json.loads(line)
        except ValueError:
            return None
        # The campaign key includes the cell, since one panel runs several cells on the same rung and seeds.
        # `cell` falls back to `rung` for tags written without it.
        return (d.get("cell") or d.get("rung"), d.get("campaign_seed"), d.get("model"))

    existing = {}
    for name in sorted(os.listdir(adir)):
        if name.endswith(".jsonl.gz"):
            with gzip.open(os.path.join(adir, name), "rt", encoding="utf-8") as f:
                existing[name] = [l if l.endswith("\n") else l + "\n" for l in f if l.strip()]
    rerun = {k for k in (camp_key(l) for l in rows) if k is not None}
    carried = replaced = 0
    for (rung, model), lines in sorted(cells_out.items()):
        keep = []
        for l in existing.pop(cell_name(rung, model), []):
            k = camp_key(l)
            if k is not None and k in rerun:
                replaced += 1
            else:
                keep.append(l)
        carried += len(keep)
        cells_out[(rung, model)] = keep + lines
    # Cells the rerun did not touch stay as they are and are still listed in the manifest.
    untouched = 0
    for name, lines in sorted(existing.items()):
        h = hashlib.sha256()
        with open(os.path.join(adir, name), "rb") as f:
            h.update(f.read())
        man[name] = dict(lines=len(lines), sha256=h.hexdigest(),
                         bytes=os.path.getsize(os.path.join(adir, name)), verified=True,
                         written_by_this_run=False)
        untouched += len(lines)
    for (rung, model), lines in sorted(cells_out.items()):
        name = cell_name(rung, model)
        dest = os.path.join(adir, name)
        with gzip.open(dest, "wt", encoding="utf-8") as f:
            f.writelines(lines)
        with gzip.open(dest, "rt", encoding="utf-8") as f:
            back = [l for l in f if l.strip()]
        h = hashlib.sha256()
        with open(dest, "rb") as f:
            h.update(f.read())
        man[name] = dict(lines=len(lines), sha256=h.hexdigest(),
                         bytes=os.path.getsize(dest), verified=(len(back) == len(lines)),
                         written_by_this_run=True)
    ok = all(v["verified"] for v in man.values())
    total = sum(v["lines"] for v in man.values())
    expected = len(rows) + carried + untouched
    # An archive with no lines is marked empty and never counts as verified.
    man_path = os.path.join(adir, "MANIFEST.json")
    json.dump(dict(tag=tag, cells=len(man), total_lines=total, source_lines=len(rows),
                   carried_forward_lines=carried, untouched_cell_lines=untouched,
                   replaced_lines=replaced, expected_total_lines=expected,
                   all_verified=(ok and total > 0), empty=(total == 0),
                   files=man), open(man_path, "w"), indent=1)
    if total == 0:
        print("  ARCHIVE IS EMPTY: the call log held no parseable rows. Nothing is removed.")
        return
    print("  call log archived: %d cells, %d lines (%d new, %d carried, %d untouched, %d replaced), "
          "%.1f MB, all verified %s"
          % (len(man), total, len(rows), carried, untouched, replaced,
             sum(v["bytes"] for v in man.values()) / 1e6, ok))
    if ok and total == expected:
        os.remove(lpath)
        print("  plain call log removed after verification: %s" % os.path.basename(lpath))
    else:
        print("  PLAIN LOG KEPT: verification failed (%d archived of %d expected lines)"
              % (total, expected))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIRS = ("repdef/", "scripts/")


class UncommittedCode(SystemExit):
    """The code about to run is not the code any commit contains."""


def _git(*args):
    try:
        r = subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_head():
    """The commit the run was produced by, recorded in the results."""
    return _git("rev-parse", "HEAD").strip() or "unknown"


CREDIT_FLOOR_USD = 50.0
REPDEF_ENV = os.path.join(REPO, ".env")
SIBLING_ENV = os.path.expanduser("<sibling-project>/.env")


def _key_line(path):
    """The key's value from a .env file, or None. Never returned to a caller that prints."""
    try:
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    v = line.split("=", 1)[1].strip().strip("'\"")
                    return v or None
    except OSError:
        return None
    return None


def _fp(v):
    """A short fingerprint: the first eight hex characters of the key's SHA256."""
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:8] if v else None


def key_source():
    """Which API key this run will use; refuse if it would come from `llm._key`'s fallback .env file.

    Returns (label, fingerprint). Raises SystemExit when the key would come from the fallback.
    """
    env = (os.environ.get("OPENROUTER_API_KEY") or "").strip() or None
    mine = _key_line(REPDEF_ENV)
    theirs = _key_line(SIBLING_ENV)
    if env is None:
        raise SystemExit(
            "REFUSED: OPENROUTER_API_KEY is not in the environment, so llm._key would fall back to\n"
            "  %s\n"
            "which is the sibling project's shared key. Launch with:\n"
            "  set -a; . ./.env; set +a; python3 scripts/grid.py ..." % SIBLING_ENV)
    if theirs is not None and env == theirs:
        raise SystemExit(
            "REFUSED: the key in the environment is the SAME as the one in\n  %s\n"
            "so this run would spend the sibling project's credit. Source repdef/.env "
            "instead." % SIBLING_ENV)
    if mine is not None and env == mine:
        return "repdef/.env", _fp(env)
    return "environment (matches no .env file on disk)", _fp(env)


def credit_balance(detail=False):
    """Spendable credit: the minimum of the account balance and this key's remaining allowance.

    Returns the binding figure, or None when it cannot be read. With detail=True it returns a dict, so the
    manifest can record both and which one bound. Read-only, and returns None on any failure.
    """
    try:
        key = LP.llm._key(ENV)
    except Exception:                                        # noqa: BLE001
        return None
    def _get(ep):
        req = urllib.request.Request("https://openrouter.ai/api/v1/" + ep,
                                     headers={"Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()).get("data") or {}

    account = key_left = expires = None
    try:
        d = _get("credits")
        if d.get("total_credits") is not None and d.get("total_usage") is not None:
            account = float(d["total_credits"]) - float(d["total_usage"])
    except Exception:                                        # noqa: BLE001
        pass
    try:
        k = _get("key")
        if k.get("limit_remaining") is not None:
            key_left = float(k["limit_remaining"])
        elif k.get("limit") is not None and k.get("usage") is not None:
            key_left = float(k["limit"]) - float(k["usage"])
        expires = k.get("expires_at")
    except Exception:                                        # noqa: BLE001
        pass
    have = [v for v in (account, key_left) if v is not None]
    binding = min(have) if have else None
    if detail:
        return dict(account=account, key_remaining=key_left, binding=binding, key_expires_at=expires,
                    bound_by=("key" if (key_left is not None and binding == key_left) else
                              ("account" if account is not None else None)))
    return binding


def check_credit(where, floor=CREDIT_FLOOR_USD):
    """Print both limits and the binding one, and say whether it is below the floor."""
    d = credit_balance(detail=True)
    bal = d["binding"] if isinstance(d, dict) else d
    if isinstance(d, dict) and bal is not None:
        print("  credit (%s): account $%s, key $%s -> BINDING $%.2f (%s)%s"
              % (where,
                 "%.2f" % d["account"] if d["account"] is not None else "unreadable",
                 "%.2f" % d["key_remaining"] if d["key_remaining"] is not None else "unreadable",
                 bal, d["bound_by"],
                 ", key expires %s" % d["key_expires_at"][:10] if d.get("key_expires_at") else ""))
    if bal is None:
        print("  credit check (%s): UNAVAILABLE, continuing. A monitoring endpoint must not stop an "
              "experiment." % where)
        return None, True
    ok = bal >= floor
    print("  credit check (%s): $%.2f spendable, floor $%.2f -> %s"
          % (where, bal, floor, "ok" if ok else "BELOW FLOOR"))
    return bal, ok


def code_provenance():
    """What `git_commit` describes, and whether it describes the code that will run."""
    dirty = [l for l in _git("status", "--porcelain").splitlines()
             if l[3:].strip().strip('"').startswith(CODE_DIRS)
             or any(("-> " + d) in l for d in CODE_DIRS)]
    diff = _git("diff", "HEAD", "--", *CODE_DIRS)
    return dict(
        git_commit=_git_head(),
        git_status_porcelain=_git("status", "--porcelain").rstrip("\n").splitlines(),
        code_dirty=bool(dirty),
        code_dirty_paths=dirty,
        code_diff_sha256=hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else None,
        git_commit_describes_the_code=not dirty)


def refuse_if_the_code_is_uncommitted(prov, allow_dirty, tag):
    """Refuse to run uncommitted code unless --allow-dirty is given.

    With --allow-dirty the run records every changed path, the SHA256 of the diff and the diff itself beside
    the manifest, and sets `git_commit_describes_the_code` to false.
    """
    if not prov["code_dirty"]:
        return
    print("!" * 100)
    print("!! UNCOMMITTED CHANGES under %s" % " or ".join(CODE_DIRS))
    for l in prov["code_dirty_paths"]:
        print("!!   %s" % l)
    print("!! HEAD is %s and does NOT describe the code that would run." % prov["git_commit"][:8])
    print("!" * 100)
    if not allow_dirty:
        raise UncommittedCode(
            "REFUSED: commit the changes above, or pass --allow-dirty to record them as a deviation. "
            "A manifest that names a commit the code does not match makes every number in the run "
            "untraceable.")
    dst = os.path.join(RESULTS, "grid_%s_uncommitted.diff" % tag)
    os.makedirs(RESULTS, exist_ok=True)
    with open(dst, "w") as f:
        f.write(_git("diff", "HEAD", "--", *CODE_DIRS))
        # Untracked files do not appear in `git diff`, so append each one in full.
        for l in prov["code_dirty_paths"]:
            if not l.startswith("??"):
                continue
            rel = l[3:].strip().strip('"')
            f.write("\n--- UNTRACKED FILE, in no commit and in no diff: %s ---\n" % rel)
            try:
                f.write(io.open(os.path.join(REPO, rel), encoding="utf-8", errors="replace").read())
            except Exception as e:
                f.write("<<could not be read: %r>>\n" % (e,))
    print("  --allow-dirty: the diff is saved to %s and flagged in the manifest."
          % os.path.relpath(dst, REPO))


def scripted_reference():
    """The scripted k* policy's mean nominated fitness, read from the curve file.

    The primary outcome compares the agent against this value, because selection shortfall alone rewards an
    agent that never explores.
    """
    with open(os.path.join(RESULTS, "step7_nk_reference_curve.json")) as f:
        d = json.load(f)
    out = {}
    for rule, c in d["curves"].items():
        ks = str(c["kstar"])
        out[rule] = dict(kstar=c["kstar"], mean=c["rows"][ks]["mean"], se=c["rows"][ks]["se"],
                         k0_mean=c["rows"]["0"]["mean"])
    return out


def landscape():
    nk = NKLandscape(k=K, seed=SEED, threshold_percentile=PCT, dist="uniform")
    f = GB1_MAX / max(nk.fitness.values())
    fit = {k: v * f for k, v in nk.fitness.items()}
    return fit, nk.pool


def check_the_menu_reads_this_landscape(fit, pool, anchor, prompt_land, label=""):
    """Check that the Menu takes its letters, reference point and candidates from the landscape it runs on.

    Two menus built on this landscape (no readings, then two measured viable candidates) must hold only this
    landscape's strings, each one letter from the candidates it says it neighbours, and `pool` must be this
    landscape's own. Refuses on any mismatch."""
    from repdef import tools
    bad = []
    own = P.alphabet_of(fit)
    used = prompts.LANDSCAPES[prompt_land]["alphabet"]
    if sorted(used) != sorted(own):
        bad.append("menu alphabet %s, landscape alphabet %s" % ("".join(sorted(used)), "".join(sorted(own))))
    if anchor not in pool or not pool <= set(fit):
        bad.append("the reference %s is not viable here, or the pool is not this landscape's" % anchor)
    one = lambda a, b: sum(1 for x, y in zip(a, b) if x != y) == 1
    cands, _r = tools.menu([], anchor, used, 0, 1)
    if not cands or any(c not in fit or not one(c, anchor) for c in cands):
        bad.append("the first menu holds strings outside this landscape or not one letter from %s" % anchor)
    meas = [s_ for s_ in sorted(pool) if one(s_, anchor)][:2] or sorted(pool)[:2]
    rows = [(1, meas[0], "ok", fit[meas[0]]), (2, meas[1], "ok", fit[meas[1]])]
    cands, _r = tools.menu(rows, anchor, used, 0, 5)
    if not cands or any(c not in fit or c in meas or not any(one(c, m) for m in meas) for c in cands):
        bad.append("a menu after two readings holds strings outside this landscape or not next to them")
    if bad:
        raise SystemExit("ABORT: the Menu does not read %s: %s" % (label or "this landscape", "; ".join(bad)))
    print("menu checked on %s: alphabet %s, reference %s, %d of %d candidates viable"
          % (label or "this landscape", "".join(sorted(own)), anchor, len(pool), len(fit)))


def check_the_structure_paragraph(fit, pool):
    """Check that the STRUCTURE paragraph's numbers match scripts/structure_facts_0an3.py on this landscape.
    Refuses on any mismatch."""
    f = json.load(open(os.path.join(ROOT, "results", "structure_facts_0an3.json")))
    want = [("space", len(fit)), ("viable", len(pool))]
    bad = [(k, f[k], v) for k, v in want if f[k] != v]
    text = prompts.STRUCTURE_GRID
    if "%d%% are viable" % round(100 * f["viable_rate_among_neighbours_of_viable"]) not in text:
        bad.append(("neighbour viable rate", f["viable_rate_among_neighbours_of_viable"], "not in the text"))
    if "against %d%% of all" % round(100 * f["base_rate"]) not in text:
        bad.append(("base rate", f["base_rate"], "not in the text"))
    for pair in ("1-3", "2-4"):
        if f["interaction"][pair]["share_below_1e9"] != 1.0:
            bad.append(("positions %s add up" % pair, f["interaction"][pair]["share_below_1e9"], 1.0))
    for pair in ("1-2", "2-3", "3-4", "1-4"):
        if f["interaction"][pair]["share_below_1e9"] > 0.0:
            bad.append(("positions %s interact" % pair, f["interaction"][pair]["share_below_1e9"], 0.0))
    if bad:
        raise SystemExit("ABORT: the STRUCTURE paragraph is not supported on this landscape: %s" % bad)
    print("structure paragraph checked against results/structure_facts_0an3.json")


def check_the_prompt_tells_the_truth(fit, pool, anchor, example, reading):
    """Check the three facts the prompt states about the environment; refuse to start if any is false."""
    if anchor not in pool:
        raise SystemExit("ABORT: the prompt calls %r the reference point but it is NOT VIABLE, so "
                         "every campaign would open by ordering it and be told it was rejected."
                         % anchor)
    if abs(fit[anchor] - reading) > 0.05 * max(1e-9, abs(fit[anchor])):
        raise SystemExit("ABORT: the prompt says the reference point reads about %.4f and it "
                         "actually reads %.4f." % (reading, fit[anchor]))
    if len(pool) >= len(fit) / 2:
        raise SystemExit("ABORT: the prompt says only a MINORITY of candidates are viable and "
                         "%d of %d are." % (len(pool), len(fit)))
    if example == anchor:
        raise SystemExit("ABORT: the format example is the reference point itself.")
    print("prompt facts checked: reference %s is viable and reads %.4f (stated %.4f), pool is "
          "%.2f%% of the space, example %s%s"
          % (anchor, fit[anchor], reading, 100.0 * len(pool) / len(fit), example,
             " (viable)" if example in pool else " (not viable, as on GB1)"))


def prompt_canary(anchor, example, reading, noise, landscape=None):
    """Refuse to launch if any rung's nomination prompt has lost its rung blocks.

    The primary outcome is read from the nomination call. This runs before the first API call.
    """
    tail = "and its slots count against your budget."
    landscape = landscape or LANDSCAPE_PROMPT
    bad = []
    for rung in ("blind", "informed", "instructed", "aggregated", "decision_rule"):
        kw = dict(landscape=landscape, parent=anchor, example=example,
                  anchor_reading=("%.2f" % reading), max_reasks=3)
        if noise == "exact":
            kw["noise_model"] = "exact"
        else:
            kw.update(noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        nom = prompts.build_nomination(rung, [(1, anchor, "ok", reading)], ROUNDS, SLOTS, 0.0, **kw)
        rnd = prompts.build(rung, [(1, anchor, "ok", reading)], 1, ROUNDS, SLOTS, 60, 0.0, **kw)
        if tail not in nom:
            bad.append("%s: nomination TRUNCATED inside the header" % rung)
        for name in prompts._BLOCKS[rung]:
            if noise == "exact":
                name = {"baseline": "baseline_exact", "informed": "informed_exact",
                        "instructed": "instructed_exact"}.get(name, name)
            elif name == "informed":
                name = "informed_multiplicative"
            blk = prompts._BLOCK_TEXT[name].format(
                **prompts._fmt_dict(landscape, anchor, example, "%.2f" % reading,
                                    ROUNDS, SLOTS, 60, FAIL_PCT, 0.0,
                                    (CV if noise != "exact" else None),
                                    (FLOOR if noise != "exact" else None), 3))
            if blk not in nom:
                bad.append("%s: nomination is missing a block: %r" % (rung, blk[:50]))
            if blk not in rnd:
                bad.append("%s: ROUND prompt is missing a block: %r" % (rung, blk[:50]))
    if bad:
        raise SystemExit("ABORT, prompt canary:\n  " + "\n  ".join(bad))
    print("prompt canary: all five rungs carry their blocks in both the round and nomination prompts")


def comparator_liveness(fit, pool, prior, rng_key=None):
    """How many of 60 scripted campaigns pick differently under shrinkage than under the mean rule."""
    ps = tuple(sorted(pool))
    pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
    # Neighbours over the landscape's own letters.
    pol.alphabet = P.alphabet_of(fit)
    diff = 0
    for i in range(60):
        r = C.run(fit, pool, pol, 0.0, 991_000 + i, 0.15, pool_sorted=ps,
                  nomination="shrinkage", prior=prior, noise_model="multiplicative",
                  cv=CV, noise_floor=FLOOR, rng_key=rng_key)
        if r.ref_shrinkage is None:
            raise SystemExit("ABORT: ref_shrinkage is not being recorded.")
        diff += (r.ref_shrinkage != r.ref_mean)
    return diff


def canary(fit, pool, prior, rng_key=None):
    """Check that the shrinkage comparator is live before reporting anything."""
    if not hasattr(C, "UnusableSigma"):
        raise SystemExit("ABORT: the shrinkage fallback bug is present in campaign.py.")
    diff = comparator_liveness(fit, pool, prior, rng_key)
    if diff == 0:
        raise SystemExit("ABORT: the shrinkage comparator matched the mean rule on all 60 "
                         "campaigns, so no comparison below would mean anything.")
    print("canary: comparator live, differs from the mean rule on %d of 60 scripted campaigns\n"
          % diff)


PROMPT_OPTIONS = ("goal_true_value", "fix_replacement_budget", "riskfree_rejection", "truthful_reask",
                  "ledger", "menu", "repeat_cap", "structure")


def one_campaign(fit, pool, ps, prior, model, rung, seed, log_rows, max_tokens, max_reasks,
                 stage_label="", reasoning_effort=None, noise="multiplicative", temperature=0.0,
                 opening="grid", cell=None, prompt_options=None, env=None, provider_retry=False):
    """Run one campaign. max_reasks is passed to both the prompt and the harness, so the two agree.

    `env` is a `repdef.envs.Env`: another landscape, with its own reference point, prompt landscape and draw
    key. None is the grid's own landscape."""
    started_at = time.time()
    if env is None:
        anchor_seq, example, reading = reference_point(fit, pool)
        prompt_land, land_label, rng_key = LANDSCAPE_PROMPT, "nk_uniform_k%d_s%d_p%.1f" % (K, SEED, PCT), None
    else:
        anchor_seq, example, reading = env.anchor, env.example, env.reading
        prompt_land, land_label, rng_key = env.prompt_landscape, env.label, env.rng_key
    anchor = anchor_seq
    pol = LP.LLMPolicy(model, rung, 0.0, parent=anchor, temperature=temperature, env_file=ENV,
                       max_tokens=max_tokens, fail_pct=FAIL_PCT, landscape=prompt_land,
                       reasoning_effort=reasoning_effort,
                       noise_model=noise, cv=CV, noise_floor=FLOOR,
                       anchor_reading=("%.2f" % reading), example=example, opening=opening)
    pol.max_reasks_disclosed = max_reasks
    pol.cell = cell or rung
    pol.provider_retry = bool(provider_retry)           # off unless --provider-retry
    # One dict sets the prompt and, for riskfree_rejection, the campaign's own rule, so the two always agree.
    opts = {k: bool((prompt_options or {}).get(k)) for k in PROMPT_OPTIONS}
    unknown = set(prompt_options or {}) - set(PROMPT_OPTIONS)
    if unknown:
        raise SystemExit("unknown prompt option(s): %s" % ", ".join(sorted(unknown)))
    pol.goal_true_value = opts["goal_true_value"]
    pol.fix_replacement_budget = opts["fix_replacement_budget"]
    pol.riskfree_rejection = opts["riskfree_rejection"]
    pol.truthful_reask = opts["truthful_reask"]
    # One dict sets each tool arm's prompt and, for the cap, the campaign's own rule.
    pol.ledger = opts["ledger"]
    pol.menu = opts["menu"]
    if pol.menu and (sorted(pol.alphabet) != sorted(P.alphabet_of(fit)) or pol.parent != anchor):
        raise SystemExit("ABORT: the Menu's alphabet or reference point is not this landscape's (0an.6)")
    _cap = 1 if opts["repeat_cap"] else None
    pol.repeat_cap = _cap
    pol.structure_text = prompts.STRUCTURE_GRID if opts["structure"] else None
    t0 = time.time()
    # The zero-noise panel uses additive noise with sigma = 0 (the oracle refuses multiplicative noise with
    # cv = 0). Synthesis failures stay at 15%, as the prompt states.
    if noise == "exact":
        _nm, _sig, _cv, _fl = "additive", 0.0, None, 0.0
    else:
        _nm, _sig, _cv, _fl = "multiplicative", 0.0, CV, FLOOR
    try:
        r = C.run(fit, pool, pol, _sig, seed, FAIL_PCT / 100.0, pool_sorted=ps,
                  nomination="agent", prior=prior, noise_model=_nm, cv=_cv,
                  noise_floor=_fl, rounds=ROUNDS, slots_per_round=SLOTS, max_reasks=max_reasks,
                  global_best=max(fit[s] for s in pool), riskfree_rejection=opts["riskfree_rejection"],
                  rng_key=rng_key, repeat_cap=_cap)
    except BaseException as e:
        # Abandon path only: the calls made so far ride on the exception, labelled as below, so main() can
        # keep them beside the failing request.
        e.abandoned_calls = [dict(c, campaign_seed=seed, landscape=land_label, total_rounds=ROUNDS,
                                  slots_per_round=SLOTS) for c in pol.calls + pol.transport_retries]
        raise
    for c in pol.calls:
        c["campaign_seed"] = seed
        c["landscape"] = land_label
        c["total_rounds"] = ROUNDS
        c["slots_per_round"] = SLOTS
        log_rows.append(c)
    # Overloaded attempts resent by the provider retry, appended after the campaign's own calls. Empty unless
    # --provider-retry is set and an overload happened.
    for c in pol.transport_retries:
        log_rows.append(dict(c, campaign_seed=seed, landscape=land_label, total_rounds=ROUNDS, slots_per_round=SLOTS))
    # The shortfall decomposition, asserted as an identity:
    #   global best - nominated = (global best - best measured) + (best measured - nominated)
    #                           =  exploration shortfall        +  selection shortfall
    gbest = max(fit[s] for s in pool)
    shortfall = r.best_true_measured - r.nominated_true
    explor = gbest - r.best_true_measured
    assert abs((gbest - r.nominated_true) - (explor + shortfall)) < 1e-9, "decomposition broken"
    rep = r.replication_count

    # Replication, four ways. The prompt gives the agent the reference point's reading, so the definitions
    # differ in whether re-proposing the reference counts.
    ok_hist = [h for h in r.history if h.outcome == "ok"]
    seen, reps_excl_anchor = set(), 0
    for h in ok_hist:
        if h.seq in seen and h.seq != anchor_seq:
            reps_excl_anchor += 1
        seen.add(h.seq)
    n_slots_total = ROUNDS * SLOTS
    # Extra fields, written only off the grid's landscape so a grid row is unchanged.
    extra = {}
    if env is not None:
        # Out-of-alphabet proposals, every attempt counted, with the letters used.
        ooa = [t.upper() for c in pol.calls for t in (c.get("out_of_alphabet") or [])]
        letters = collections.Counter(ch for t in ooa for ch in t if ch not in env.alphabet)
        extra = dict(landscape=env.label, landscape_name=env.name, nk_k=env.meta.get("nk_k"),
                     nk_seed=env.meta.get("nk_seed"), anchor=env.anchor,
                     out_of_alphabet_proposals=len(ooa), out_of_alphabet_letters=dict(letters),
                     **EV.round1_orders(r.history, env))
    return dict(seed=seed, model=model, rung=rung, **extra,
                # Wall-clock start, so drift of the outcome over time can be checked per cell.
                stage=stage_label,
                started_at=started_at,
                started_iso=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started_at)),
                global_best=gbest,
                exploration_shortfall=explor,
                total_shortfall=gbest - r.nominated_true,
                n_distinct_measured=len({h.seq for h in ok_hist}),
                # Lost slots: slots consumed with nothing measured, counted from the records.
                # `slots_unaccounted` should be zero; a nonzero value means the slot accounting is off.
                slots_abandoned=sum(1 for h in r.history if h.outcome == "abandoned"),
                rounds_lost_slots=sum(1 for h in r.history if h.outcome == "round_lost"),
                # a slot the repeat cap touched and then lost; zero with the cap off
                slots_cap_lost=sum(1 for h in r.history if h.outcome == "cap_lost"),
                lost_slots=sum(1 for h in r.history
                               if h.outcome in ("abandoned", "round_lost", "cap_lost")),
                slots_unaccounted=(ROUNDS * SLOTS) - r.slots_used,
                replication_fraction_of_budget=rep / n_slots_total,
                replication_count_excl_anchor=reps_excl_anchor,
                replication_fraction_excl_anchor=(reps_excl_anchor / r.slots_used
                                                  if r.slots_used else 0.0),
                replication_fraction_excl_anchor_of_budget=reps_excl_anchor / n_slots_total,
                anchor_orders=sum(1 for h in ok_hist if h.seq == anchor_seq),
                nominated=r.nominated, nominated_true=r.nominated_true,
                best_true_measured=r.best_true_measured, selection_shortfall=shortfall,
                ref_mean=r.ref_mean, ref_max=r.ref_max, ref_shrinkage=r.ref_shrinkage,
                shortfall_vs_shrinkage=(fit[r.ref_shrinkage] - r.nominated_true
                                        if r.ref_shrinkage else None),
                agent_chose_mean=(r.nominated == r.ref_mean),
                agent_chose_max=(r.nominated == r.ref_max),
                agent_chose_shrinkage=(r.nominated == r.ref_shrinkage),
                slots_used=r.slots_used, n_ok=r.n_ok, n_rejected=r.n_rejected,
                replication_count=rep,
                replication_fraction=(rep / r.slots_used if r.slots_used else 0.0),
                replication_by_round=_rep_by_round(r),
                intents=dict(pol.intent_counts()), statuses=dict(pol.status_counts()),
                spend=pol.spend_usd, secs=round(time.time() - t0, 1),
                agent_reason=r.agent_reason,
                prompt_options=opts, rejection_cap_hits=r.rejection_cap_hits,
                n_capped=r.n_capped, repeat_cap_hits=r.repeat_cap_hits)


def _rep_by_round(r):
    seen, out = set(), []
    for rnd in range(1, ROUNDS + 1):
        this = [h for h in r.history if h.round == rnd and h.outcome == "ok"]
        out.append(sum(1 for h in this if h.seq in seen))
        seen |= {h.seq for h in this}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="cost probe: 5 campaigns per model, Mechanism only, to set the final N")
    ap.add_argument("--campaigns", type=int, default=40)
    ap.add_argument("--conditions", default="")
    ap.add_argument("--models", default="")
    ap.add_argument("--seed0", type=int, default=300_000)
    # Room for the longest late-round histories without truncation.
    ap.add_argument("--max-tokens", type=int, default=6000)
    # campaign.py's own default. A replacement is itself non-viable about a quarter of the time, so a cap
    # of 1 loses many slots. The prompt states the cap and what happens after it.
    ap.add_argument("--max-reasks", type=int, default=3)
    ap.add_argument("--budget-usd", type=float, default=STAGE_CEILING_USD)
    # Three optional prompt variants, off by default so the grid is reproducible.
    ap.add_argument("--goal-true-value", action="store_true",
                    help="GOAL also says the score is the nominated candidate's true value (round and "
                         "replacement prompts, identical in all five conditions)")
    ap.add_argument("--fix-replacement-budget", action="store_true",
                    help="the replacement prompt's BUDGET line states the real orders per round")
    ap.add_argument("--ledger", action="store_true",
                    help="0an F1: round prompts add a computed table of every measured candidate (n, mean, SE)")
    ap.add_argument("--menu", action="store_true",
                    help="0an F2: round prompts add 10 never-ordered candidates ranked by a stated additive model")
    ap.add_argument("--repeat-cap", action="store_true",
                    help="0an F3: each candidate can be ordered at most twice; a further order is refused at no cost "
                         "and the agent chooses again, to the risk-free bound of campaign.RISKFREE_CAP")
    ap.add_argument("--structure", action="store_true",
                    help="0an.3 F5: a STRUCTURE paragraph of measured facts about the grid's landscape in every "
                         "prompt; refused unless results/structure_facts_0an3.json still supports each number")
    ap.add_argument("--truthful-reask", action="store_true",
                    help="0am.2: when lines are dropped for letters outside the alphabet, the re-ask names "
                         "them and restates the alphabet; every other re-ask is unchanged")
    ap.add_argument("--provider-retry", action="store_true",
                    help="0an.8 note 4: resend an identical request after an explicit provider overload (an error "
                         "with code 502 or 503, or error_type provider_unavailable), up to 5 attempts after 30, "
                         "60, 120 and 240 s, each attempt kept in the call archive. Off by default.")
    ap.add_argument("--riskfree-rejection", action="store_true",
                    help="a non-viable order costs nothing and the agent chooses again, to a hard cap of "
                         "campaign.RISKFREE_CAP replacement asks per slot; cap hits are counted")
    ap.add_argument("--tag", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--seeds", default="",
                    help="0an.7: an explicit comma-separated list of campaign seeds, run in place of seed0 .. seed0 + n - 1; "
                         "the shuffled path only. Used to continue exactly the seeds an arm left unrun")
    ap.add_argument("--shuffle", action="store_true",
                    help="run all cells INTERLEAVED in a seeded shuffled order instead of in "
                         "condition blocks. Stage 1 ran in blocks, which lets time of day, provider "
                         "load and model-side drift line up with condition; the top-up shuffles so "
                         "they cannot. The order is derived from --order-seed and recorded, so the "
                         "run is reproducible.")
    ap.add_argument("--order-seed", type=int, default=20260927)
    ap.add_argument("--credit-floor", type=float, default=CREDIT_FLOOR_USD,
                    help="Refuse to launch, and halt mid-run, when the OpenRouter balance falls below "
                         "this. Checked at launch and every 50 campaigns.")
    ap.add_argument("--ignore-credit-floor", action="store_true",
                    help="Launch below the floor anyway. Recorded in the manifest.")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="Launch with uncommitted changes under repdef/ or scripts/. The diff is saved "
                         "beside the manifest and the manifest records that its commit does NOT "
                         "describe the code. Without this the run refuses to start.")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="0.0 for the grid (section 0m). The exploratory temperature panel uses 1.0 to "
                         "ask whether the anchor lock survives sampling.")
    ap.add_argument("--reasoning-effort", default=None,
                    help="low/medium/high. Sends OpenRouter's reasoning.effort. Reasoning tokens are "
                         "BILLED, so the reasoning panel measures its own per-campaign cost on a small "
                         "probe before the full cell is sized (section 0q).")
    ap.add_argument("--noise", default="multiplicative", choices=["multiplicative", "exact"],
                    help="'exact' is the zero-noise panel: sigma = 0 with synthesis failures KEPT at "
                         "15%%, so the Blind prompt stays byte-identical to the grid's.")
    ap.add_argument("--stage", default="",
                    help="recorded on every campaign. The top-up-only sensitivity analysis of section 0m "
                         "needs an explicit discriminator; stage-1 campaigns carry no label, so absence "
                         "means stage 1.")
    ap.add_argument("--workers", type=int, default=8,
                    help="campaigns run CONCURRENTLY. They are independent by construction: each is "
                         "keyed by its own seed through the counter-based RNG, so concurrency cannot "
                         "change any result, only the wall clock. Measured at 78s per opus campaign, "
                         "the full-power grid is about 68 hours sequentially and under 9 at 8 "
                         "workers. Cost is unaffected.")
    # Other landscapes, off by default. "grid" is the grid's NK K=1 seed=1.
    ap.add_argument("--landscape", default="grid", choices=("grid",) + EV.NAMES,
                    help="0am: gb1_scrambled, gb1_real, phoq_scrambled, or nk (Panel K, with --nk-k). "
                         "Each is built by repdef/envs.py under the grid's own rules.")
    ap.add_argument("--nk-k", type=int, default=None,
                    help="0am Panel K: the K of the 20 fresh NK landscapes. Campaign seed0 + i runs on "
                         "landscape i mod 20 (envs.panel_k_index).")
    ap.add_argument("--campaigns-by-model", default="",
                    help="0am sizing: role=N or model=N pairs, comma separated, overriding --campaigns for "
                         "those models. Seeds are seed0 .. seed0 + N - 1 for each model, so a smaller cell "
                         "is a prefix of a larger one and pairs with it by seed.")
    a = ap.parse_args()

    if a.landscape == "nk" and a.nk_k not in EV.PANEL_K:
        sys.exit("--landscape nk needs --nk-k in %s" % (EV.PANEL_K,))
    if a.landscape != "nk" and a.nk_k is not None:
        sys.exit("--nk-k applies only to --landscape nk")
    if a.landscape == "grid":
        fit, pool = landscape()
        envs_all = []
    else:
        envs_all = EV.all_envs(a.landscape, a.nk_k)
        fit, pool = envs_all[0].fit, envs_all[0].pool
    ps = tuple(sorted(pool))
    vals = [fit[s] for s in pool]
    prior = (st.mean(vals), st.variance(vals))

    def args_for(sd):
        """The landscape campaign seed `sd` runs on: the grid's own unless --landscape chose another."""
        if not envs_all:
            return fit, pool, ps, prior, None
        e = EV.env_for(a.landscape, sd - a.seed0, a.nk_k)
        return e.fit, e.pool, e.ps, e.prior, e

    conds = ([("Mechanism", "instructed")] if a.probe else CONDITIONS)
    if a.conditions:
        keep = set(a.conditions.split(","))
        # BIO_CONDITIONS is searched too, so the panel is selected by name and never picked up by default.
        _all = CONDITIONS + BIO_CONDITIONS
        conds = [c for c in _all if c[0] in keep or c[1] in keep]
        unknown = keep - {c[0] for c in _all} - {c[1] for c in _all}
        if unknown:
            raise SystemExit("unknown condition(s): %s" % ", ".join(sorted(unknown)))
    models = MODELS
    if a.models:
        keep = set(a.models.split(","))
        models = [m for m in MODELS + EXTRA_MODELS if m[1] in keep or m[0] in keep]
    n = 5 if a.probe else a.campaigns
    n_by = {}
    for part in [x for x in a.campaigns_by_model.split(",") if x.strip()]:
        key, _eq, val = part.partition("=")
        hit = [m for m in models if key.strip() in (m[0], m[1])]
        if len(hit) != 1 or not val.strip().isdigit():
            raise SystemExit("--campaigns-by-model: %r names no single model in this run" % part)
        n_by[hit[0][1]] = int(val)

    def n_for(model):
        return n_by.get(model, n)
    # Provenance check first, before the banner and the canary.
    tag_now = a.tag or ("probe" if a.probe else "grid")
    prov = code_provenance()
    refuse_if_the_code_is_uncommitted(prov, a.allow_dirty, tag_now)
    # Check the credit balance before launch.
    _ksrc, _kfp = key_source()
    print("  key source: %s  (fingerprint %s, never the key)" % (_ksrc, _kfp))
    _bal, _ok = check_credit("launch", a.credit_floor)
    if not _ok and not a.ignore_credit_floor:
        sys.exit("REFUSED: $%.2f remaining is below the $%.2f floor. Add credits, or pass "
                 "--ignore-credit-floor to launch anyway and have it recorded in the manifest."
                 % (_bal, a.credit_floor))

    print("=" * 100)
    if envs_all:
        print("%s  0am landscape %s%s (%d landscape%s)  multiplicative cv=%.3f floor=%.5f"
              % ("COST PROBE" if a.probe else "GRID", a.landscape,
                 " K=%d" % a.nk_k if a.nk_k is not None else "", len(envs_all),
                 "" if len(envs_all) == 1 else "s", CV, FLOOR))
    else:
        print("%s  NK uniform K=%d seed=%d pct=%.1f  multiplicative cv=%.3f floor=%.5f"
              % ("COST PROBE" if a.probe else "GRID", K, SEED, PCT, CV, FLOOR))
    print("=" * 100)
    print("  pool %d of %d | %d conditions x %d models, campaigns per model %s = %d campaigns"
          % (len(pool), len(fit), len(conds), len(models),
             ", ".join("%s %d" % (r_, n_for(m_)) for r_, m_, _d in models),
             len(conds) * sum(n_for(m_) for _r, m_, _d in models)))
    print("  ceiling $%.2f | %d rounds x %d slots | agent nominates, shrinkage recorded"
          % (a.budget_usd, ROUNDS, SLOTS))
    for role, m, rel in models:
        print("    %-12s %-32s released %s" % (role, m, rel))

    anchor, example, reading = reference_point(fit, pool)
    prompt_land = LANDSCAPE_PROMPT
    if envs_all:
        anchor, example, reading = envs_all[0].anchor, envs_all[0].example, envs_all[0].reading
        prompt_land = envs_all[0].prompt_landscape
    # Every landscape the run can touch is checked, not just the first.
    for _f, _p, _a, _x, _r, _pl in ([(e.fit, e.pool, e.anchor, e.example, e.reading, e.prompt_landscape)
                                     for e in envs_all] or
                                    [(fit, pool, anchor, example, reading, LANDSCAPE_PROMPT)]):
        check_the_prompt_tells_the_truth(_f, _p, _a, _x, float("%.2f" % _r))
        # Before anything else, including --dry, because it costs nothing.
        prompt_canary(_a, _x, _r, a.noise, _pl)
    if a.menu:
        for _f, _p, _a, _pl, _lab in ([(e.fit, e.pool, e.anchor, e.prompt_landscape, getattr(e, "name", ""))
                                       for e in envs_all] or [(fit, pool, anchor, LANDSCAPE_PROMPT, "the grid")]):
            check_the_menu_reads_this_landscape(_f, _p, _a, _pl, _lab)
    if a.structure:
        if envs_all:
            raise SystemExit("REFUSED: the STRUCTURE paragraph states facts about the grid's landscape only")
        check_the_structure_paragraph(fit, pool)
    if a.seeds and not a.shuffle:
        raise SystemExit("REFUSED: --seeds runs on the shuffled path only; add --shuffle")
    manifest = dict(
        seeds=[int(x) for x in a.seeds.split(",") if x.strip()] or None,
        tag=tag_now, started=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        landscape="nk_uniform_k%d_s%d_p%.1f" % (K, SEED, PCT),
        K=K, seed=SEED, pct=PCT, cv=CV, noise_floor=FLOOR, gb1_max=GB1_MAX,
        rounds=ROUNDS, slots=SLOTS, fail_pct=FAIL_PCT,
        conditions=[c[0] for c in conds], models=[{"role": r, "id": m, "released": d}
                                                  for r, m, d in models],
        campaigns_per_cell=max(n_for(m) for _r, m, _d in models), seed0=a.seed0, workers=a.workers,
        campaigns_by_model={m: n_for(m) for _r, m, _d in models},
        max_tokens=a.max_tokens, max_reasks=a.max_reasks, budget_usd=a.budget_usd,
        shuffled=bool(a.shuffle), order_seed=a.order_seed, stage=a.stage,
        reasoning_effort=a.reasoning_effort, noise=a.noise, temperature=a.temperature,
        prompt_options={k: bool(getattr(a, k)) for k in PROMPT_OPTIONS},
        riskfree_cap=(C.RISKFREE_CAP if a.riskfree_rejection else None),
        provider_retry=bool(a.provider_retry),
        prompt_landscape=LANDSCAPE_PROMPT, anchor=anchor, anchor_reading=reading,
        example=example, pool=len(pool), space=len(fit),
        global_best=max(fit[s] for s in pool),
        scripted=scripted_reference(),
        comparator="empirical-Bayes prior fitted per campaign from that campaign's own readings",
        prior_rel_floor=0.01,
        primary_outcome="nominated true fitness vs the scripted k* policy")
    if envs_all:
        # What the run actually ran on, landscape by landscape. The grid's K and seed do not apply.
        manifest.update(
            landscape=(envs_all[0].label if len(envs_all) == 1
                       else "nk_panel_k%d (%d landscapes)" % (a.nk_k, len(envs_all))),
            landscape_option=a.landscape, nk_k=a.nk_k, K=a.nk_k, seed=None,
            prompt_landscape=prompt_land, landscapes=[e.describe() for e in envs_all],
            landscape_of_offset=("envs.panel_k_index: offset mod %d" % EV.PANEL_K_N
                                 if a.landscape == "nk" else "one landscape"),
            anchor=(anchor if len(envs_all) == 1 else None),
            anchor_reading=(reading if len(envs_all) == 1 else None),
            example=(example if len(envs_all) == 1 else None),
            yardsticks="results/yardsticks_0am.json")
    manifest["key_source"] = _ksrc
    manifest["key_fingerprint_sha256_8"] = _kfp
    manifest["credit_floor_usd"] = a.credit_floor
    manifest["credit_balance_at_launch"] = _bal
    manifest["credit_detail_at_launch"] = credit_balance(detail=True)
    manifest["launched_below_credit_floor"] = bool(not _ok)
    manifest.update(prov)                      # provenance last, so nothing above can shadow it
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "grid_%s_manifest.json" % tag_now), "w") as f:
        json.dump(manifest, f, indent=1)
    print("manifest saved: results/grid_%s_manifest.json (commit %s%s)"
          % (tag_now, manifest["git_commit"][:8],
             "" if prov["git_commit_describes_the_code"]
             else ", WHICH DOES NOT DESCRIBE THE CODE: see code_dirty_paths"))
    if a.dry:
        print("\n--- the exact round-1 prompt, Mechanism condition ---")
        print(prompts.build("instructed", [], 1, ROUNDS, SLOTS, ROUNDS * SLOTS, 0.0,
                            parent=anchor, fail_pct=FAIL_PCT, total=ROUNDS * SLOTS,
                            landscape=prompt_land, noise_model="multiplicative",
                            cv=CV, noise_floor=FLOOR, anchor_reading=("%.2f" % reading),
                            example=example))
        return 0

    for role, m, rel in models:
        print("    %-12s %-32s released %s" % (role, m, rel))
    # The canary tests the comparator on the grid's landscape whatever this run uses. On other landscapes
    # shrinkage may change nothing, so liveness there is recorded per landscape and does not stop the run.
    _gf, _gp = landscape()
    _gv = [_gf[x] for x in _gp]
    canary(_gf, _gp, (st.mean(_gv), st.variance(_gv)))
    if envs_all:
        live = {e.label: comparator_liveness(e.fit, e.pool, e.prior, e.rng_key) for e in envs_all}
        print("comparator liveness per landscape (of 60 scripted campaigns): %s" % live)
        manifest["comparator_liveness_of_60"] = live
        with open(os.path.join(RESULTS, "grid_%s_manifest.json" % tag_now), "w") as f:
            json.dump(manifest, f, indent=1)
    log_rows, rows, spent = [], [], 0.0
    lock = threading.Lock()
    stopped = False
    # Each campaign is appended and fsynced as soon as it returns, under the lock that updates the totals,
    # so the file on disk is always a prefix of the run.
    cpath = os.path.join(RESULTS, "grid_%s_campaigns.jsonl" % tag_now)
    lpath = os.path.join(RESULTS, "grid_%s_calls.jsonl" % tag_now)

    # Resume: a restart skips (condition, model, seed) triples already on disk.
    done = set()
    if os.path.exists(cpath):
        for line in open(cpath):
            try:
                d0 = json.loads(line)
            except ValueError:
                continue
            done.add((d0.get("condition"), d0.get("model"), d0.get("seed")))
            rows.append(d0)
            spent += d0.get("spend") or 0.0
        if done:
            print("resuming: %d campaigns already on disk, $%.4f already spent" % (len(done), spent))

    # Single-element lists, because the halt path writes them from inside a nested function.
    credits_out = [False]
    transport_fails = [0]
    cf = open(cpath, "a")
    lf = open(lpath, "a")

    apath = os.path.join(RESULTS, "grid_%s_abandoned_calls.jsonl" % tag_now)

    def keep_abandoned(e, seed, model, cell):
        """Save an abandoned campaign's calls and the failed request to grid_<tag>_abandoned_calls.jsonl.
        The file is not used in analysis and the campaign stays unwritten. Never raises."""
        try:
            recs = [dict(c, abandoned=True) for c in (getattr(e, "abandoned_calls", None) or [])]
            recs.append(dict(getattr(e, "failed_request", None) or {}, abandoned=True, failing_call=True,
                             campaign_seed=seed, model=model, cell=cell, exception=str(e)))
            with open(apath, "a") as fa:
                for r in recs:
                    fa.write(json.dumps(r, default=str) + "\n")
        except Exception as e2:                                    # noqa: BLE001
            print("      (could not keep the abandoned calls of seed %s: %s)" % (seed, e2))

    def flush(d, own):
        cf.write(json.dumps(d) + "\n")
        for c in own:
            lf.write(json.dumps(c) + "\n")
        cf.flush()
        lf.flush()
        os.fsync(cf.fileno())
        os.fsync(lf.fileno())
    if a.shuffle:
        # One flat seeded shuffle over every (condition, model, seed), recorded in the manifest, so no
        # condition sits in one stretch of wall-clock time.
        import repdef.rng as R
        seed_list = [int(x) for x in a.seeds.split(",") if x.strip()]
        tasks = [(cn, rg, ro, md, sd)
                 for cn, rg in conds for ro, md, _d in models
                 for sd in (seed_list or [a.seed0 + i for i in range(n_for(md))])
                 if (cn, md, sd) not in done]
        keyed = sorted(tasks, key=lambda t: R._u64("order", a.order_seed, t[0], t[3], t[4]))
        print("\n  SHUFFLED order over %d campaigns across %d cells (order seed %d)"
              % (len(keyed), len(conds) * len(models), a.order_seed))

        def work_one(t):
            cn, rg, ro, md, sd = t
            own = []
            _open, _noise = CELL_ENV.get(cn, ("grid", a.noise))
            _f, _p, _ps, _pr, _e = args_for(sd)
            d = one_campaign(_f, _p, _ps, _pr, md, rg, sd, own, a.max_tokens, a.max_reasks,
                             a.stage, a.reasoning_effort, _noise, a.temperature, opening=_open, cell=cn,
                             prompt_options={k: getattr(a, k) for k in PROMPT_OPTIONS}, env=_e,
                             provider_retry=a.provider_retry)
            d["condition"] = cn
            d["role"] = ro
            return d, own

        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(work_one, t): t for t in keyed}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    d, own = fut.result()
                except Exception as e:
                    print("      %s %s seed %d FAILED: %s" % (t[0], t[3], t[4], e))
                    with lock:
                        keep_abandoned(e, t[4], t[3], t[0])
                    continue
                with lock:
                    rows.append(d); log_rows.extend(own); spent += d["spend"]; cum = spent
                    flush(d, own)
                print("      %-13s %-11s seed %-6d ok %2d rep %2d (%3.0f%%) | nom %7.4f | "
                      "distn %2d | $%.4f cum $%.2f | %.0fs"
                      % (d["condition"], d["role"], d["seed"], d["n_ok"], d["replication_count"],
                         100 * d["replication_fraction"], d["nominated_true"],
                         d["n_distinct_measured"], d["spend"], cum, d["secs"]))
                if cum >= a.budget_usd:
                    print("      CEILING STOP at $%.2f" % cum)
                    stopped = True
                    for f2 in futs:
                        f2.cancel()
                    break
        conds = []                      # the blocked loop below has nothing left to do

    for cname, rung in conds:
        for role, model, _rel in models:
            if stopped:
                break
            print("\n  --- %-14s %-12s %s   (%d workers) ---"
                  % (cname, role, model, a.workers))
            # Each campaign gets its own log list, merged under the lock after it returns.
            def work(i, _c=cname, _r=role, _m=model, _g=rung):
                own = []
                _open, _noise = CELL_ENV.get(_c, ("grid", a.noise))
                _f, _p, _ps, _pr, _e = args_for(a.seed0 + i)
                d = one_campaign(_f, _p, _ps, _pr, _m, _g, a.seed0 + i, own,
                                 a.max_tokens, a.max_reasks, a.stage, a.reasoning_effort, _noise,
                                 a.temperature, opening=_open, cell=_c,
                                 prompt_options={k: getattr(a, k) for k in PROMPT_OPTIONS}, env=_e,
                                 provider_retry=a.provider_retry)
                d["condition"] = _c
                d["role"] = _r
                return d, own

            if credits_out[0]:
                break
            cell_start = len(log_rows)
            todo = [i for i in range(n_for(model)) if (cname, model, a.seed0 + i) not in done]
            if len(todo) < n_for(model):
                print("      skipping %d already on disk" % (n_for(model) - len(todo)))
            with ThreadPoolExecutor(max_workers=a.workers) as ex:
                futs = {ex.submit(work, i): i for i in todo}
                for fut in as_completed(futs):
                    i = futs[fut]
                    try:
                        d, own = fut.result()
                    except LP.CreditsExhausted as e:
                        # Every further call would fail the same way, so the run stops.
                        print("\n" + "!" * 100)
                        print("!! HALTING THE RUN: OPENROUTER CREDITS EXHAUSTED (HTTP 402)")
                        print("!! %s" % e)
                        bal = credit_balance()
                        print("!! balance now: %s" % ("$%.2f" % bal if bal is not None else "unreadable"))
                        print("!! %d campaigns are on disk for this tag and every one of them is clean,"
                              % len(rows))
                        print("!! because a campaign with a transport error is abandoned unwritten.")
                        print("!! Add credits, then relaunch with the same tag: resume reruns the gap.")
                        print("!" * 100)
                        credits_out[0] = True
                        with lock:
                            keep_abandoned(e, a.seed0 + i, model, cname)
                        for f2 in futs:
                            f2.cancel()
                        break
                    except LP.TransportFailure as e:
                        # Not charged to the agent and not written, but counted.
                        transport_fails[0] += 1
                        print("      seed %-6d ABANDONED (transport, not charged): %s"
                              % (a.seed0 + i, e))
                        with lock:
                            keep_abandoned(e, a.seed0 + i, model, cname)
                        continue
                    except Exception as e:
                        print("      seed %-6d FAILED: %s" % (a.seed0 + i, e))
                        with lock:
                            keep_abandoned(e, a.seed0 + i, model, cname)
                        continue
                    with lock:
                        rows.append(d)
                        log_rows.extend(own)
                        spent += d["spend"]
                        cum = spent
                        flush(d, own)
                    print("      seed %-6d ok %2d rep %2d (%3.0f%%) | shortfall %7.4f | nom=%s "
                          "%s | $%.4f cum $%.2f | %.0fs"
                          % (d["seed"], d["n_ok"], d["replication_count"],
                             100 * d["replication_fraction"], d["selection_shortfall"],
                             d["nominated"],
                             "MEAN" if d["agent_chose_mean"] else
                             ("MAX" if d["agent_chose_max"] else "OTHER"),
                             d["spend"], cum, d["secs"]))
                    # Re-check the balance every 50 campaigns, since it can drain mid-run.
                    if len(rows) % 50 == 0:
                        _b, _k = check_credit("after %d campaigns" % len(rows), a.credit_floor)
                        if not _k:
                            print("\n" + "!" * 100)
                            print("!! HALTING: $%.2f remaining is below the $%.2f floor." % (_b, a.credit_floor))
                            print("!! Every campaign on disk is clean. Add credits and relaunch with the")
                            print("!! same tag; resume reruns only what is missing.")
                            print("!" * 100)
                            credits_out[0] = True
                            for f3 in futs:
                                f3.cancel()
                            break
                    cell_rows = [c for c in own if c.get("kind") != "nomination"]
                    if cum >= a.budget_usd:
                        print("      CEILING STOP at $%.2f" % cum)
                        stopped = True
                        for f2 in futs:
                            f2.cancel()
                        break

    tag = tag_now
    cf.close()
    lf.close()

    # Two-parser check: in a probe any disagreement blocks launch; in the grid a rate above 1% in a cell
    # pauses it. Nomination calls are counted separately.
    nom_calls = [c for c in log_rows if c.get("kind") == "nomination"]
    if nom_calls:
        na = sum(1 for c in nom_calls if c.get("parsers_agree"))
        nb = sum(1 for c in nom_calls if "parsers_agree" in c)
        print("\n  NOMINATION CALLS: %d, of which %d carry a two-parser comparison, %d agree"
              % (len(nom_calls), nb, na))
        if nb and na < nb:
            print("    %d nomination calls DISAGREE, and each one decides a campaign's primary outcome"
                  % (nb - na))
    rate, bad, by_design, tot = disagreement(log_rows)
    print("\n  TWO-PARSER CHECK over %d ROUND calls (nomination calls above)" % tot)
    print("    GENUINE disagreement (both read, and differ)      %4d  %.2f%%" % (bad, 100 * rate))
    print("    by design (primary refused the count, spent none) %4d  %.2f%%"
          % (by_design, 100.0 * by_design / tot if tot else 0.0))
    if bad:
        print("  DISAGREEING CALLS, first 5:")
        shown = 0
        for c in log_rows:
            if (c.get("kind") != "nomination" and not c.get("parsers_agree", True)
                    and c.get("parsed")):
                print("    round %s status %s tier %s | primary %s | secondary %s"
                      % (c.get("round"), c.get("parse_status"), c.get("format_tier"),
                         c.get("parsed"), c.get("parsed_secondary")))
                shown += 1
                if shown >= 5:
                    break
    if a.probe and bad:
        print("\n  LAUNCH BLOCKED: a probe must show ZERO parser disagreement before the grid runs.")
    elif not a.probe and rate > 0.01:
        print("\n  PAUSE: parser disagreement %.2f%% exceeds the 1%% ceiling." % (100 * rate))
    sc = spotcheck(log_rows, models, tag)
    print("  spot check written: %s" % os.path.relpath(sc, ROOT))     # relative: a run log is tracked
    archive_calls(tag, cpath, lpath)          # already flushed per campaign; a second write here would duplicate rows

    print("\n" + "=" * 100)
    print("SUMMARY   %s" % tag)
    print("=" * 100)
    ref = scripted_reference()
    kstar = ref["shrinkage"]
    # The run summary prints variances and health only; condition means come from a separate analysis
    # script run after the final N.
    print("  VARIANCES AND HEALTH ONLY. The primary outcome by condition is NOT printed here; see")
    print("  scripts/stage1_variance.py for the sizing inputs and the final analysis script for means.")
    print("  (scripted reference for later use: k*=%d at %.4f, k=0 at %.4f)"
          % (kstar["kstar"], kstar["mean"], kstar["k0_mean"]))
    print("  %-13s %-11s %3s | %11s %11s | %7s | %13s | %10s"
          % ("condition", "role", "n", "sd(nominated)", "sd(distinct)", "distn",
             "rep of budget", "$/campaign"))
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["condition"], r["role"])].append(r)
    def boot_ci(v, stat=st.mean, b=2000, lo=2.5, hi=97.5):
        """Percentile bootstrap interval."""
        import repdef.rng as R
        if len(v) < 2:
            return float("nan"), float("nan")
        n_ = len(v)
        draws = sorted(stat([v[R._u64("ci", i, j) % n_] for j in range(n_)]) for i in range(b))
        return draws[int(lo / 100.0 * b)], draws[min(b - 1, int(hi / 100.0 * b))]

    for k, v in sorted(by.items()):
        nom = [x["nominated_true"] for x in v]
        sf = [x["selection_shortfall"] for x in v]
        ex = [x["exploration_shortfall"] for x in v]
        nd = [x["n_distinct_measured"] for x in v]
        rb = [x["replication_fraction_of_budget"] for x in v]
        nse = (st.stdev(nom) / math.sqrt(len(nom))) if len(nom) > 1 else 0.0
        sd_nom = st.stdev(nom) if len(nom) > 1 else float("nan")
        sd_nd = st.stdev(nd) if len(nd) > 1 else float("nan")
        print("  %-13s %-11s %3d | %13.4f %11.4f | %7.1f | %12.1f%% %10.4f"
              % (k[0], k[1], len(v), sd_nom, sd_nd, st.mean(nd), 100 * st.mean(rb),
                 st.mean([x["spend"] for x in v])))
    print("\n  TOTAL SPEND $%.4f over %d calls, %d campaigns" % (spent, len(log_rows), len(rows)))
    # Response health per model: a reasoning model can spend its budget thinking and return empty visible
    # text. Reported before launch so max_tokens can be set per model.
    print("\n  RESPONSE HEALTH PER MODEL")
    print("  %-30s %6s %11s %13s %11s %9s %9s"
          % ("model", "calls", "empty", "malformed", "trunc", "mean rsn", "max rsn"))
    health = {}
    for role, model, _rel in models:
        cs = [c for c in log_rows if c["model"] == model]
        if not cs:
            continue
        empty = sum(1 for c in cs if c.get("empty_text"))
        mal = sum(1 for c in cs if c.get("parse_status") != "ok")
        trunc = sum(1 for c in cs if str(c.get("finish_reason")) == "length")
        rsn = [int(c.get("reasoning_tokens") or 0) for c in cs]
        health[model] = dict(calls=len(cs), empty=empty, malformed=mal, truncated=trunc,
                             mean_reasoning=(st.mean(rsn) if rsn else 0),
                             max_reasoning=(max(rsn) if rsn else 0),
                             max_completion=max(int(c.get("completion_tokens") or 0) for c in cs))
        # Counts first, then the percentage, since one call in thousands rounds to 0%.
        print("  %-30s %6d %5d %4.1f%% %6d %5.1f%% %5d %4.1f%% %9.0f %9d"
              % (model, len(cs), empty, 100.0 * empty / len(cs), mal, 100.0 * mal / len(cs),
                 trunc, 100.0 * trunc / len(cs), health[model]["mean_reasoning"],
                 health[model]["max_reasoning"]))
    bad = [m for m, h in health.items() if h["empty"] or h["truncated"]]
    if bad:
        print("\n  DO NOT LAUNCH on %s: empty or truncated responses present. Raise max_tokens above"
              % ", ".join(bad))
        for m in bad:
            need = health[m]["max_reasoning"] + health[m]["max_completion"]
            print("    %-30s observed reasoning+completion peak %d, so max_tokens >= %d"
                  % (m, need, int(need * 1.5)))
    else:
        print("\n  No empty and no truncated responses on any model at max_tokens=%d."
              % a.max_tokens)
    json.dump(health, open(os.path.join(RESULTS, "grid_%s_health.json" % tag), "w"), indent=1)

    if a.probe and rows:
        print("\n  COST PROBE RESULT, which sets the final N:")
        per = {}
        for role, model, _rel in models:
            v = [r["spend"] for r in rows if r["model"] == model]
            if v:
                per[model] = st.mean(v)
                print("    %-30s $%.4f per campaign" % (model, st.mean(v)))
        if per:
            blended = sum(per.values())            # one campaign in each model's cell
            cells = len(CONDITIONS)
            print("    one campaign in all %d models costs $%.4f, so %d conditions cost $%.4f"
                  % (len(per), blended, cells, blended * cells))
            for target in (383, 250, 150, 100, 60, 40):
                tot = blended * cells * target
                det = 2.8 * 0.2179 * 1.25 / math.sqrt(target)
                print("      N=%-4d -> $%8.2f  %-5s detectable shortfall difference %.4f"
                      % (target, tot, "FITS" if tot <= a.budget_usd else "over", det))
    return 0


if __name__ == "__main__":
    sys.exit(main())
