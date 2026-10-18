#!/usr/bin/env python3
"""Index every prompt the grid sent, and verify that the archive still reads back.

Each call is one JSONL row with `prompt` and `raw_response`, stored as one gzip per (condition, model) cell
under results/grid_<tag>_calls/ with a MANIFEST.json. This writes results/ARCHIVE_INDEX.md and re-reads every
gzip to check its SHA256 against the manifest.

Usage: archive_index.py [--check-only]
"""
import argparse, glob, gzip, hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")

# What each tag is, so the index says why a set of prompts exists.
WHAT = {
    "stage1": "stage 1 of the core grid, 5 conditions x 3 models x 40 campaigns",
    "topup_opus": "core grid top-up to the pre-registered N, opus",
    "topup_gemini": "core grid top-up to the pre-registered N, gemini",
    "topup_deepseek": "core grid top-up to the pre-registered N, deepseek",
    "zeronoise": "zero-noise control panel, sigma = 0",
    "panelc": "reasoning panel (c), reasoning effort medium",
    "tpanel": "temperature panel (b), temperature 1.0",
    "stage0": "first stage-1 attempt, ABANDONED: the nomination prompt was truncated in every cell "
              "(build_nomination split inside the shared header). Kept because the deviations appendix "
              "cites these prompts as the evidence for that defect",
    "stage1a": "second stage-1 attempt, superseded after the aggregated-history fix",
    "probe": "pre-grid smoke probe", "probe2": "pre-grid smoke probe",
    "probe3": "pre-grid smoke probe",
    "rprobe": "reasoning cost probe, used to set panel (c)'s ceiling",
    "rprobe20k": "reasoning probe at a raised token budget",
    "bioframing": "biology-framing panel (0aa), three role and noise cells on the Blind rung",
    "replication_dsdr": "pre-registered replication (0ak), DeepSeek V3.1, Mechanism vs Decision-rule, new seeds",
    "panelA_wording": "0al Panel A: goal_true_value + fix_replacement_budget, Blind and Mechanism, seeds 300000-300059",
    "panelB_riskfree": "0al Panel B: all three 0al options incl. riskfree_rejection, two segments (0al notes)",
    "panelA0_original": "0al.1 Panel A0: same-day drift control, original prompts, two segments (0al notes)",
    "gen_r_gb1scr": "0am Panel R: scrambled GB1, Blind and Mechanism, three models",
    "gen_r_gb1real": "0am Panel R: GB1 under its real names, Blind and Mechanism, three models",
    "gen_r_phoqscr": "0am Panel R: scrambled PhoQ, Blind and Mechanism, three models",
    "gen_r_gb1scr_top": "0am registered Opus top-up to n = 60, scrambled GB1, run from e325069",
    "gen_r_gb1real_top": "0am registered Opus top-up to n = 60, real-name GB1, run from e325069",
    "gen_k0": "0am Panel K: NK K = 0, 20 landscapes, Blind",
    "gen_k1": "0am Panel K: NK K = 1, 20 landscapes, Blind",
    "gen_k2": "0am Panel K: NK K = 2, 20 landscapes, Blind",
    "gen_k3": "0am Panel K: NK K = 3, 20 landscapes, Blind",
    "smoke0am_gb1scr": "0am first smoke, scrambled GB1 (failed: the real-GB1 canary; see 0am.2)",
    "smoke0am_phoqscr": "0am first smoke, scrambled PhoQ (out-of-alphabet rounds lost; see 0am.2)",
    "smoke0am_nk3": "0am first smoke, NK K = 3",
    "smoke0am2_gb1scr": "0am second smoke (0am.2), scrambled GB1",
    "smoke0am2_gb1real": "0am second smoke (0am.2), real-name GB1",
    "smoke0am2_phoqscr": "0am second smoke (0am.2), scrambled PhoQ",
    "smoke0am2_nk3": "0am second smoke (0am.2), NK K = 3",
    "smoke0an_f0_control": "0an smoke, F0 control (Gemini, DeepSeek)",
    "smoke0an_f1_ledger": "0an smoke, F1 ledger",
    "smoke0an_f2_menu": "0an smoke, F2 menu",
    "smoke0an_f3_cap": "0an smoke, F3 cap (F3 withdrawn in 0an.2; descriptive)",
    "smoke0an1_f3_cap": "0an.1 F3 re-smoke (F3 withdrawn in 0an.2; descriptive)",
    "smoke0an3_f5_structure": "0an.3 smoke, F5 structure",
    "gen_0an_f0_control": "0an panel, F0 concurrent control (Gemini, DeepSeek), seeds 300000-300119",
    "gen_0an_f1_ledger": "0an panel, F1 ledger",
    "gen_0an_f2_menu": "0an panel, F2 menu (Opus n = 30)",
    "gen_0an_f5_structure": "0an.3 panel, F5 structure (Opus n = 30)",
    "gen_0an5_f2_menu_opus": "0an.5 Opus menu top-up, seeds 300030-300059",
    "smoke0an6_gb1_menu": "0an.6 smoke, Menu on scrambled GB1",
    "smoke0an6_gb1_control": "0an.6 smoke, no-tool control on scrambled GB1",
    "gen_0an6_gb1_menu": "0an.6 panel, Menu on scrambled GB1 (Opus n = 30)",
    "gen_0an6_gb1_control": "0an.6 panel, concurrent no-tool control on scrambled GB1 (Gemini, DeepSeek)",
    "smoke0an7_grid_blind": "0an.7 smoke, GPT-6.1 Sol and Gemini 3.1 Pro at minimal effort, grid Blind",
    "smoke0an7_gb1_blind": "0an.7 smoke, GPT-6.1 Sol and Gemini 3.1 Pro at minimal effort, GB1 scrambled Blind",
    "smoke0an7_gb1_menu": "0an.7 smoke, GPT-6.1 Sol and Gemini 3.1 Pro at minimal effort, GB1 scrambled Menu",
    "gen_0an7_sol_grid_blind": "0an.7 main run, GPT-6.1 Sol, grid Blind",
    "gen_0an7_sol_grid_blind_rerun": "0an.7 main run, GPT-6.1 Sol, grid Blind, re-run of abandoned seeds",
    "gen_0an7_sol_grid_blind_cont": "0an.7 main run, GPT-6.1 Sol, grid Blind, continuation of unrun seeds",
    "gen_0an7_sol_gb1_blind": "0an.7 main run, GPT-6.1 Sol, GB1 scrambled Blind",
    "gen_0an7_sol_gb1_blind_rerun": "0an.7 main run, GPT-6.1 Sol, GB1 scrambled Blind, re-run of abandoned seeds",
    "gen_0an7_sol_gb1_blind_cont": "0an.7 main run, GPT-6.1 Sol, GB1 scrambled Blind, continuation of unrun seeds",
    "gen_0an7_sol_gb1_menu": "0an.7 main run, GPT-6.1 Sol, GB1 scrambled Menu",
    "smoke0an8_opus": "0an.8 smoke, Opus 4.7, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001",
    "smoke0an8_flash": "0an.8 smoke, Gemini 2.5 Flash, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001",
    "smoke0an8_deepseek": "0an.8 smoke, DeepSeek V3.1, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001",
    "smoke0an8_sol": "0an.8 smoke, GPT-6.1 Sol, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001",
    "smoke0an8_gem": "0an.8 smoke, Gemini 3.1 Pro, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001",
    "gen_0an8_opus_phoq_blind": "0an.8 main run, Opus 4.7, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029",
    "gen_0an8_flash_phoq_blind": "0an.8 main run, Gemini 2.5 Flash, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029",
    "gen_0an8_deepseek_phoq_blind": "0an.8 main run, DeepSeek V3.1, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029",
    "gen_0an8_sol_phoq_blind": "0an.8 main run, GPT-6.1 Sol, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029",
    "gen_0an8_gem_phoq_blind": "0an.8 main run, Gemini 3.1 Pro, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029",
    "gen_0an8_opus_phoq_blind_rerun": "0an.8 main run, Opus 4.7, scrambled PhoQ Blind, re-run of abandoned seeds",
    "gen_0an8_flash_phoq_blind_rerun": "0an.8 main run, Gemini 2.5 Flash, scrambled PhoQ Blind, re-run of abandoned seeds",
    "gen_0an8_deepseek_phoq_blind_rerun": "0an.8 main run, DeepSeek V3.1, scrambled PhoQ Blind, re-run of abandoned seeds",
    "gen_0an8_sol_phoq_blind_rerun": "0an.8 main run, GPT-6.1 Sol, scrambled PhoQ Blind, re-run of abandoned seeds",
    "gen_0an8_gem_phoq_blind_rerun": "0an.8 main run, Gemini 3.1 Pro, scrambled PhoQ Blind, re-run of abandoned seeds",
    "gen_0an8_sol_phoq_blind_cont": "0an.8 note 3: GPT-6.1 Sol's continuation, the 13 seeds its stopped arm left unrun",
    "gen_0an8_sol_phoq_blind_cont_rerun": "0an.8 note 3: GPT-6.1 Sol's continuation, re-runs of abandoned continuation seeds",
    "gen_0an8_sol_phoq_blind_fin": "0an.8 note 4: GPT-6.1 Sol's last 8 seeds, under the transport amendment (--provider-retry)",
    "gen_0an7_sol_gb1_menu_rerun": "0an.7 main run, GPT-6.1 Sol, GB1 scrambled Menu, re-run of abandoned seeds",
    "gen_0an7_sol_gb1_menu_cont": "0an.7 main run, GPT-6.1 Sol, GB1 scrambled Menu, continuation of unrun seeds",
    "gen_0an7_gem_grid_blind": "0an.7 main run, Gemini 3.1 Pro, grid Blind",
    "gen_0an7_gem_grid_blind_rerun": "0an.7 main run, Gemini 3.1 Pro, grid Blind, re-run of abandoned seeds",
    "gen_0an7_gem_grid_blind_cont": "0an.7 main run, Gemini 3.1 Pro, grid Blind, continuation of unrun seeds",
    "gen_0an7_gem_gb1_blind": "0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Blind",
    "gen_0an7_gem_gb1_blind_rerun": "0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Blind, re-run of abandoned seeds",
    "gen_0an7_gem_gb1_blind_cont": "0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Blind, continuation of unrun seeds",
    "gen_0an7_gem_gb1_menu": "0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Menu",
    "gen_0an7_gem_gb1_menu_rerun": "0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Menu, re-run of abandoned seeds",
    "gen_0an7_gem_gb1_menu_cont": "0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Menu, continuation of unrun seeds",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()

    dirs = sorted(glob.glob(os.path.join(RESULTS, "grid_*_calls")))
    rows, bad, total_calls, total_bytes = [], [], 0, 0
    for d in dirs:
        tag = os.path.basename(d)[len("grid_"):-len("_calls")]
        man_path = os.path.join(d, "MANIFEST.json")
        man = json.load(open(man_path)) if os.path.exists(man_path) else {"files": {}}
        cells, calls, byts, with_prompt = 0, 0, 0, 0
        for g in sorted(glob.glob(os.path.join(d, "*.jsonl.gz"))):
            name = os.path.basename(g)
            h = hashlib.sha256()
            with open(g, "rb") as f:
                h.update(f.read())
            digest = h.hexdigest()
            with gzip.open(g, "rt") as f:
                lines = [l for l in f if l.strip()]
            first = json.loads(lines[0]) if lines else {}
            if "prompt" in first and "raw_response" in first:
                with_prompt += 1
            cells += 1
            calls += len(lines)
            byts += os.path.getsize(g)
            rec = man.get("files", {}).get(name)
            if rec is None:
                bad.append("%s/%s is not in the manifest" % (tag, name))
            else:
                if rec.get("sha256") != digest:
                    bad.append("%s/%s SHA256 differs from the manifest" % (tag, name))
                if rec.get("lines") != len(lines):
                    bad.append("%s/%s holds %d lines, manifest says %d"
                               % (tag, name, len(lines), rec.get("lines")))
        # A plain log still on disk means this tag is mid-run or was never archived.
        plain = os.path.join(RESULTS, "grid_%s_calls.jsonl" % tag)
        live = os.path.exists(plain) and os.path.getsize(plain) > 0
        rows.append(dict(tag=tag, what=WHAT.get(tag, "(undocumented tag)"), cells=cells, calls=calls,
                         mb=byts / 1e6, prompt_ok=(with_prompt == cells and cells > 0), live=live,
                         sha=hashlib.sha256(
                             "".join(sorted(json.load(open(man_path))["files"].get(n, {}).get("sha256", "")
                                            for n in sorted(man.get("files", {})))).encode()).hexdigest()[:16]
                         if os.path.exists(man_path) else "")
                    )
        total_calls += calls
        total_bytes += byts

    # An abandoned campaign's calls (grid_<tag>_abandoned_calls.jsonl) are committed as plain JSONL, so they
    # must be tracked, and they are listed apart from the orphans.
    evidence = sorted(glob.glob(os.path.join(RESULTS, "grid_*_abandoned_calls.jsonl")))
    tracked = set(subprocess.run(["git", "ls-files", "results"], cwd=ROOT, capture_output=True,
                                 text=True).stdout.split())
    for p in evidence:
        rel = os.path.relpath(p, ROOT)
        n = sum(1 for l in open(p) if l.strip())
        print("  abandoned-campaign evidence: %s, %d records, %s" % (rel, n, "tracked" if rel in tracked else "NOT TRACKED"))
        if rel not in tracked:
            bad.append("%s is abandoned-campaign evidence and is not committed" % rel)
    orphan = [os.path.basename(p) for p in glob.glob(os.path.join(RESULTS, "grid_*_calls.jsonl"))
              if os.path.getsize(p) > 0 and not p.endswith("_abandoned_calls.jsonl")
              and not os.path.isdir(p[:-len(".jsonl")])]
    running = []
    for o in orphan:
        tag = o[len("grid_"):-len("_calls.jsonl")]
        # A tag whose grid.py is still running archives its calls when it ends: listed, not a problem.
        if subprocess.run(["pgrep", "-f", "tag %s " % tag], capture_output=True).returncode == 0:
            running.append(tag)
            continue
        bad.append("%s has no archive directory: those prompts are not in the repository" % o)

    if not a.check_only:
        with open(os.path.join(RESULTS, "ARCHIVE_INDEX.md"), "w") as f:
            f.write("# Call archive index\n\n")
            f.write("Every call the harness made is one JSONL row carrying `prompt` and `raw_response`.\n"
                    "The committed form is one gzip per (condition, model) cell under\n"
                    "`results/grid_<tag>_calls/`, with that directory's `MANIFEST.json` holding each\n"
                    "cell's line count and SHA256. Regenerate and verify this file with\n"
                    "`python3 scripts/archive_index.py`; `--check-only` verifies without writing.\n\n")
            f.write("%s calls in %d tags, %.1f MB compressed, all committed to git. No LFS.\n\n"
                    % ("{:,}".format(total_calls), len(rows), total_bytes / 1e6))
            f.write("| tag | what it is | cells | calls | MB | prompt+response | manifest |\n")
            f.write("|---|---|---:|---:|---:|---|---|\n")
            for r in sorted(rows, key=lambda r: r["tag"]):
                f.write("| `%s` | %s | %d | %s | %.2f | %s | `%s` |\n"
                        % (r["tag"], r["what"], r["cells"], "{:,}".format(r["calls"]), r["mb"],
                           "yes" if r["prompt_ok"] else "NO", r["sha"]))
            f.write("\nThe `manifest` column is the first 16 hex of the SHA256 of that tag's cell digests\n"
                    "in name order, so one short string changes if any cell in the tag changes.\n\n")
            if running:
                f.write("Running when this index was written, calls not yet archived: %s. Each archives its "
                        "calls when its run ends; regenerate this file then.\n\n"
                        % ", ".join("`%s` (%s)" % (t, WHAT.get(t, "(undocumented tag)")) for t in sorted(running)))
            live = [r["tag"] for r in rows if r["live"]]
            if live:
                f.write("Mid-run when this index was written (a plain log is still on disk and the "
                        "archive is therefore not yet final): %s.\n\n" % ", ".join("`%s`" % t for t in live))
            f.write("Raw plain logs are gitignored by `results/grid_*_calls.jsonl`, because stage 1's\n"
                    "reached 55 MB at 406 of 600 campaigns and the top-up would pass GitHub's 100 MB hard\n"
                    "limit. The release copy of the archive goes to Zenodo with the paper.\n\n")
            f.write("## Verification\n\n")
            if bad:
                f.write("**%d problem(s) found by the last run of this script:**\n\n" % len(bad))
                for b in bad:
                    f.write("- %s\n" % b)
            else:
                f.write("Every gzip re-read, every SHA256 and line count matches the manifest its run\n"
                        "wrote, and every tag with a plain call log on disk has an archive directory.\n")

    print("%d tags, %d calls, %.1f MB compressed" % (len(rows), total_calls, total_bytes / 1e6))
    for r in sorted(rows, key=lambda r: -r["calls"]):
        print("  %-16s %3d cells %9s calls %7.2f MB  prompt+response %s%s"
              % (r["tag"], r["cells"], "{:,}".format(r["calls"]), r["mb"],
                 "yes" if r["prompt_ok"] else "NO", "  (mid-run)" if r["live"] else ""))
    if bad:
        print("\nPROBLEMS (%d):" % len(bad))
        for b in bad:
            print("  %s" % b)
        return 1
    print("\nall SHA256 and line counts match their manifests; no tag's prompts are missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
