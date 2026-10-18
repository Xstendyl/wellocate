#!/usr/bin/env python3
"""The paper's eleven figures, every value read from a results file and none typed into a plotting call.

  python3 scripts/figures.py

All in one style (scripts/figstyle.py). Main text:
  fig_headline         Figure 1, re-testing share and final pick for the five models against the scripted rules
  fig1_environment     Figure 2, a schematic of one campaign loop
  fig_landscape_env    Figure 3, the grid: every candidate's true value, and slices through the best and the start
  fig_loss_directions  exploration loss against selection loss per model
  fig_fixes            the aids, 2 x 2: grid aids, the Menu on scrambled GB1 (share, pick), a final round
  fig_noise_sweep      the guessing rule's final pick against re-tests per round at five noise levels
                       (a slot is lost after three rejected replacements)
Appendix (the pre-registered grid):
  fig2_headline        final pick against re-testing share, with the scripted rules' curves at k = 0..4
  fig3_split           re-testing share against distinct candidates
  fig5_zero_noise      the zero-noise control, as a dumbbell per model
  figA3_shortfall_global  exploration and selection loss per cell
  figA2_simulation     the simulation sweep, one panel per setting
  fig_noise_sweep_free the noise sweep where a rejection costs no slot (Using Wellocate)

Every number comes from `results/`; `tests/test_figures_have_no_typed_numbers.py` fails if a numeric literal
other than an axis limit or a layout coordinate appears in a plotting call.
"""
import collections, itertools, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import figstyle as FS                                                  # noqa: E402

plt = FS.use()


def grid_cells():
    g = FS.results(os.path.join("analysis_final", "grid", "summary.json"))
    return g["cells_detail"]


def fig1_environment():
    """A schematic of one campaign with the lab term for each part. The only numbers are the budget."""
    # The y range ends just above the boxes, and the figure height shrinks with it to keep element sizes fixed.
    top = 0.75
    fig, ax = plt.subplots(figsize=(FS.FULL, 2.6 * top / 0.95))
    ax.axis("off")
    boxes = [(0.02, "Agent orders", "4 candidates,\none per assay well"), (0.27, "Assay measures", "noisy readings"),
             (0.52, "History updates", "readings so far"), (0.77, "Final pick", "1 candidate to\ntake forward")]
    for x, label, lab in boxes:
        ax.add_patch(plt.Rectangle((x, 0.42), 0.19, 0.30, fill=False, linewidth=0.9))
        ax.text(x + 0.095, 0.61, label, ha="center", va="center", fontsize=FS.MIN_PT + 1)
        ax.text(x + 0.095, 0.49, lab, ha="center", va="center", fontsize=FS.MIN_PT, style="italic")
    for x in (0.21, 0.46, 0.71):
        ax.annotate("", xy=(x + 0.06, 0.57), xytext=(x, 0.57),
                    arrowprops=dict(arrowstyle="->", linewidth=0.9))
    ax.annotate("", xy=(0.115, 0.42), xytext=(0.615, 0.42),
                arrowprops=dict(arrowstyle="->", linewidth=0.9, linestyle=(0, (3, 2)),
                                connectionstyle="bar,fraction=-0.22"))
    ax.text(0.365, 0.255, "the next round, until the budget is spent",
            ha="center", fontsize=FS.MIN_PT, style="italic")
    ax.text(0.365, 0.03, "15 rounds of 4 wells, 60 measurements in total",
            ha="center", fontsize=FS.MIN_PT + 1)
    ax.text(0.865, 0.33, "scored on its\ntrue value", ha="center", fontsize=FS.MIN_PT)
    ax.set_xlim(0, 1)
    ax.set_ylim(0.0, top)
    return FS.save(fig, "fig1_environment")


def fig2_headline():
    """Final pick against re-testing share, with the informed and guessing rules' curves at k = 0..4."""
    c = FS.results("reference_curve_alphabet.json")["curves"]
    fig, ax = plt.subplots(figsize=(FS.FULL, 3.6))
    ks = sorted(c["fair"], key=int)
    for scope, style, colour, label in (("pool", "-", FS.OKABE["black"], FS.REF_LABEL["pool"]),
                                        ("fair", "--", FS.OKABE["purple"], FS.REF_LABEL["fair"])):
        xs = [100.0 * int(k) / len(ks[:-1]) for k in ks]
        ys = [c[scope][k]["mean"] for k in ks]
        es = [1.96 * c[scope][k]["se"] for k in ks]
        ax.errorbar(xs, ys, yerr=es, linestyle=style, color=colour, marker=".", linewidth=1.0,
                    capsize=2, elinewidth=0.7, label=label, zorder=2)
    for key, label, colour, marker in FS.MODELS:
        short = key.split("/")[-1]
        pts = [(100 * x["replication"]["over slots used"], x["mean"])
               for x in grid_cells() if x["model"] == short]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=colour, marker=marker,
                   s=26, label=label, zorder=3, edgecolor="white", linewidth=0.4)
    ax.set_xlabel("re-testing share, % of slots")
    ax.set_ylabel("final pick (true value)")
    FS.grid_on(ax, "y")
    ax.legend(frameon=False, loc="lower left", ncol=2)
    return FS.save(fig, "fig2_outcome_vs_replication")


def fig3_split():
    """Re-testing share against distinct candidates, with the scripted rules and protocols as labelled points."""
    r = FS.refs()
    lp = FS.results("lab_protocols.json")["rows"]
    fig, ax = plt.subplots(figsize=(FS.FULL, 3.6))
    for key, label, colour, marker in FS.MODELS:
        short = key.split("/")[-1]
        pts = [(x["distinct"], 100 * x["replication"]["over slots used"])
               for x in grid_cells() if x["model"] == short]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=colour, marker=marker, s=26,
                   label=label, zorder=3, edgecolor="white", linewidth=0.4)
    ax.axhline(r["kstar_share"], linestyle=(0, (4, 3)), color=FS.OKABE["black"], linewidth=0.8, zorder=1)
    # Each star's label sits centred above it; the two labels are narrower than the gap between the stars.
    for dist, lab, off, ha in ((r["fair_distinct"], FS.REF_LABEL["fair"], (0, 7), "center"),
                               (r["pool_distinct"], FS.REF_LABEL["pool"], (0, 7), "center")):
        ax.scatter([dist], [r["kstar_share"]], marker="*", s=90, color=FS.OKABE["black"], zorder=4)
        ax.annotate(lab, xy=(dist, r["kstar_share"]), xytext=off, textcoords="offset points",
                    ha=ha, fontsize=FS.MIN_PT)
    for key, short, colour, marker in FS.PROTOCOLS:
        row = lp["%s|pool" % key]
        ax.scatter([row["distinct"]], [row["replication"]], marker=marker, s=34, color=colour,
                   zorder=4, edgecolor="white", linewidth=0.4)
        ax.annotate(short, xy=(row["distinct"], row["replication"]), xytext=(4, -9),
                    textcoords="offset points", fontsize=FS.MIN_PT, color=colour)
    ax.set_xlabel("distinct candidates measured")
    ax.set_ylabel("re-testing share, % of slots")
    FS.grid_on(ax, "y")
    ax.legend(frameon=False, loc="upper right")
    # Labels are placed against the final limits; get_xlim() before the last artist is drawn is provisional.
    y0, y1 = ax.get_ylim()
    ax.set_ylim(y0 - 0.07 * (y1 - y0), y1)          # room under the lowest protocol label
    FS.turn_labels_inward(ax)
    ax.annotate("rules' best setting", xy=(ax.get_xlim()[0], r["kstar_share"]), xytext=(4, 3),
                textcoords="offset points", ha="left", fontsize=FS.MIN_PT)
    return FS.save(fig, "fig3_replication_vs_exploration")


def figA3_shortfall_global():
    """The shortfall to the global best, exploration and selection stacked, grouped by model."""
    cells = {(x["condition"], x["model"]): x for x in grid_cells()}
    fig, axes = plt.subplots(1, len(FS.MODELS), figsize=(FS.FULL, 2.6), sharex=True)
    for ax, (key, label, colour, _m) in zip(axes, FS.MODELS):
        short = key.split("/")[-1]
        ys = range(len(FS.CONDITIONS))
        expl = [cells[(c, short)]["exploration_shortfall"] for c in FS.CONDITIONS]
        sel = [cells[(c, short)]["selection_shortfall"] for c in FS.CONDITIONS]
        # One hue per panel; the two parts differ by fill, so the legend names the fill, not a colour.
        ax.barh(list(ys), expl, color=colour, label="exploration loss", height=0.62)
        ax.barh(list(ys), sel, left=expl, color="white", edgecolor=colour, hatch="///",
                linewidth=0.6, label="selection loss", height=0.62)
        ax.set_yticks(list(ys))
        ax.set_yticklabels(FS.CONDITIONS if ax is axes[0] else [])
        ax.invert_yaxis()
        ax.set_title(label, fontsize=FS.MIN_PT + 1)
        FS.grid_on(ax, "x")
    handles, labels = axes[0].get_legend_handles_labels()
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=FS.GREY, edgecolor=FS.GREY),
               plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=FS.GREY, hatch="///",
                             linewidth=0.6)]
    axes[1].set_xlabel("shortfall to the global best")
    fig.tight_layout()
    fig.legend(handles, labels, frameon=False, loc="lower center", ncol=len(labels),
               bbox_to_anchor=(0.5, 1.0))
    return FS.save(fig, "figA3_shortfall_global")


def fig5_zero_noise():
    """A dumbbell per model: the level under noise and the level with exact readings."""
    rows = FS.results(os.path.join("analysis_final", "zeronoise", "table2c_central_test.json"))["rows"]
    by = {(r["condition"], r["model"].split("/")[-1]): r for r in rows}
    fig, axes = plt.subplots(1, len(FS.MODELS), figsize=(FS.FULL, 2.6), sharex=True)
    for ax, (key, label, colour, marker) in zip(axes, FS.MODELS):
        short = key.split("/")[-1]
        for i, cond in enumerate(FS.CONDITIONS):
            r = by[(cond, short)]
            zero = 100 * r["panel_level"]
            noisy = 100 * (r["panel_level"] - r["diff"])
            ax.plot([zero, noisy], [i, i], color=FS.OKABE["black"], linewidth=0.8, zorder=1)
            ax.scatter([noisy], [i], color=FS.OKABE["black"], marker="|", s=40, zorder=3)
            ax.scatter([zero], [i], color=colour, marker=marker, s=26, zorder=3,
                       edgecolor="white", linewidth=0.4)
        ax.set_yticks(range(len(FS.CONDITIONS)))
        ax.set_yticklabels(FS.CONDITIONS if ax is axes[0] else [])
        ax.invert_yaxis()
        ax.set_title(label, fontsize=FS.MIN_PT + 1)
        FS.grid_on(ax, "x")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=FS.GREY, marker="o", markerfacecolor=FS.GREY, linewidth=0,
                      markersize=4, label="exact readings"),
               Line2D([], [], color=FS.OKABE["black"], marker="|", linewidth=0, markersize=7,
                      label="readings under noise")]
    axes[1].set_xlabel("post-repeat re-testing, % of slots")
    fig.tight_layout()
    fig.legend(handles=handles, frameon=False, loc="lower center", ncol=len(handles),
               bbox_to_anchor=(0.5, 1.0))
    return FS.save(fig, "fig5_zero_noise")


def figA2_simulation():
    """Small multiples of the simulation sweep: mean against k, with SE bars, k* and ties marked."""
    path = os.path.join(ROOT, "results", "learnability_fresh_n200.json")
    d = json.load(open(path))
    rows = d["settings"]
    if any("se" not in r["sweep"]["0"] for r in rows):
        raise SystemExit("REFUSED: the simulation output has no per-k standard error. Re-run "
                         "scripts/learnability_sim.py, which now records it.")
    ncol = 6
    nrow = int(math.ceil(len(rows) / float(ncol)))
    fig, axes = plt.subplots(nrow, ncol, figsize=(FS.FULL, 1.5 * nrow), sharex=True)
    for ax, r in zip(axes.ravel(), rows):
        ks = sorted(r["sweep"], key=int)
        ys = [r["sweep"][k]["mean"] for k in ks]
        es = [r["sweep"][k]["se"] for k in ks]
        ax.errorbar([int(k) for k in ks], ys, yerr=es, marker=".", markersize=3, linewidth=0.8,
                    color=FS.OKABE["blue"], capsize=1.5, elinewidth=0.6)
        ax.scatter([r["kstar"]], [r["sweep"][str(r["kstar"])]["mean"]], marker="*", s=42,
                   color=FS.OKABE["vermillion"], zorder=4)
        ax.set_title("K=%d, cv x%.1f\n%s%s" % (r["K"], r["cv_mult"], FS.REF_SHORT[r["scope"]],
                                               ", tie" if r["gap_is_a_tie"] else ""),
                     fontsize=FS.MIN_PT - 1)
        ax.set_xticks([int(k) for k in ks])          # k is a count of repeats, so the ticks are integers
        ax.tick_params(labelsize=FS.MIN_PT - 1)
        FS.grid_on(ax, "y")
    for ax in axes.ravel()[len(rows):]:
        ax.axis("off")
    for ax in axes[-1]:
        ax.set_xlabel("$k$", fontsize=FS.MIN_PT)
    axes[0][0].set_ylabel("mean outcome", fontsize=FS.MIN_PT)
    fig.tight_layout()
    return FS.save(fig, "figA2_simulation")


def fig_landscape_env():
    """The grid landscape alone: (a) every candidate, (b) the slice through the best candidate and (c) the slice
    through the start, with (b) and (c) on one colour scale. Data from results/landscape_summary.json."""
    L = FS.results("landscape_summary.json")
    # Constrained layout keeps the two square slices as wide as the text width allows, with one colourbar beside
    # both. The start's and the best's labels lean away from each other so they cannot meet in the narrower (a).
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(FS.FULL, 2.6), layout="constrained",
                                  gridspec_kw=dict(width_ratios=[1.15, 1, 1]))
    _landscape_hist(a, L, "true value")
    ref, best = L["reference"], L["best"]
    a.text(ref["value"], 1.01, "start\n(%s)" % ref["seq"], fontsize=6.5, ha="right", va="bottom",
           transform=a.get_xaxis_transform())
    a.text(best["value"], 1.01, "best\npossible", fontsize=6.5, ha="left", va="bottom",
           transform=a.get_xaxis_transform())
    _landscape_hist_finish(a, L)
    im = _landscape_slice(b, L, L["slice"], best["seq"], outline=True)
    _landscape_slice(c, L, L["start_slice"], ref["seq"], outline=True)
    c.set_ylabel("")                                    # the same letters as (b), beside it
    _landscape_colorbar(fig.colorbar(im, ax=[b, c], fraction=0.03, pad=0.02), "true value (viable)")
    for ax, label, dx in ((a, "(a)", -0.14), (b, "(b)", -0.18), (c, "(c)", -0.18)):
        ax.text(dx, 1.02, label, transform=ax.transAxes, fontsize=9, fontweight="bold")
    return FS.save(fig, "fig_landscape_env")


def _landscape_hist(a, L, xlabel):
    """Panel (a) of both landscape figures: the true value of every candidate, viable ones in blue, on a log scale,
    with the start (dotted) and the best possible (dashed) as lines. Returns the top of the y range, which the
    callers place their labels against."""
    edges, hist = L["histogram"]["edges"], L["histogram"]
    left = edges[:-1]
    a.hist(left, bins=edges, weights=hist["not_viable"], color="#BBBBBB",
           label="not viable (%d%%)" % round(100 - L["viable_pct"]))
    a.hist(left, bins=edges, weights=hist["viable"], color=FS.OKABE["skyblue"],
           label="viable (%d%%)" % round(L["viable_pct"]))
    a.set_yscale("log")
    a.set_xlabel(xlabel)
    a.set_ylabel("candidates (log scale)")
    a.grid(axis="x", visible=False)
    ymax = a.get_ylim()[1]
    a.axvline(L["reference"]["value"], color=FS.OKABE["black"], lw=0.9, ls=":")
    a.axvline(L["best"]["value"], color=FS.OKABE["black"], lw=0.9, ls="--")
    return ymax


def _landscape_hist_finish(a, L):
    """Panel (a)'s legend and limits, after the caller's own labels and markers."""
    edges = L["histogram"]["edges"]
    a.legend(loc="upper left", frameon=False, fontsize=6.5, handlelength=1.4)
    a.set_xlim(edges[0], edges[-1] + 0.45)


def _landscape_slice(ax, L, S, star, outline=False):
    """A 20 x 20 slice (positions 3 and 4 fixed, positions 1 and 2 varying) on the colour scale every slice shares:
    viable cells by true value from the viability cutoff to the best possible, non-viable cells grey. A star marks
    `star`; with `outline`, its row and column, its one-letter neighbours in the slice, are outlined. Returns the
    image the colourbar reads."""
    alphabet = S["alphabet"]
    import numpy as np
    G, V = np.array(S["fitness"]), np.array(S["viable"], dtype=bool)
    im = ax.imshow(np.where(V, G, np.nan), origin="lower", cmap="viridis", vmin=L["cutoff"],
                   vmax=L["best"]["value"], interpolation="nearest")
    ax.imshow(np.where(V, np.nan, 1.0), origin="lower", cmap="Greys", vmin=0, vmax=4, interpolation="nearest")
    ax.set_xticks(range(len(alphabet)))
    ax.set_xticklabels(list(alphabet), fontsize=5.5)
    ax.set_yticks(range(len(alphabet)))
    ax.set_yticklabels(list(alphabet), fontsize=5.5)
    ax.set_xlabel("letter at position 1")
    ax.set_ylabel("letter at position 2")
    ax.grid(False)
    i, j = alphabet.index(star[0]), alphabet.index(star[1])
    ax.plot([i], [j], marker="*", color="white", ms=8, mec="black", mew=0.5, zorder=6)
    if outline:
        n = len(alphabet)
        for xy, w, h in (((-0.5, j - 0.5), n, 1), ((i - 0.5, -0.5), 1, n)):
            ax.add_patch(plt.Rectangle(xy, w, h, fill=False, edgecolor=FS.OKABE["black"], lw=1.1, zorder=5))
    for sp in ax.spines.values():
        sp.set_visible(True)
    return im


def _landscape_colorbar(cb, label):
    cb.set_label(label, fontsize=7)
    cb.ax.tick_params(labelsize=6)


def noise_name(lv, levels):
    """A curve's legend name: its noise as a percentage of the true value, computed from the CV (0.0365 is 3.65%).
    The lowest level carries the word "noise", the assay's level says it is the real assay's, and the design sweep's
    levels say they are beyond realistic."""
    pct = "%g%%" % round(100 * lv["cv"], 4)
    if lv["key"] == "assay":
        return pct + " (real assay)"
    if lv["kind"] != "preset":
        return pct + " (beyond realistic)"
    return pct + (" noise" if lv["cv"] == min(x["cv"] for x in levels) else "")


def _noise_sweep_row(curve, kfield, stem):
    """One row of the noise sweep (wellocate_noise_sweep.json): the guessing rule's final pick against re-tests per
    round (k = 0 to 4), one curve per noise level, one panel per landscape, each curve's best k marked with a star.
    Solid curves are the three presets; dashed curves are the design sweep (CV 0.3 and 0.6). The star is drawn only
    where the results file's best k is the curve's highest mean pick."""
    d = FS.results("wellocate_noise_sweep.json")
    levels = d["levels"]
    lands = list(d["lands"])
    cmap = plt.get_cmap("viridis")
    colours = [cmap(i / max(1, len(levels) - 1) * 0.85) for i in range(len(levels))]
    fig, axes = plt.subplots(1, len(lands), figsize=(FS.FULL, 2.45), sharex=True)
    for ax, label in zip(axes, lands):
        land = d["lands"][label]
        for lv, colour in zip(levels, colours):
            x = land["levels"][lv["key"]]
            ks = sorted(int(k) for k in x[curve])
            ys = [x[curve][str(k)]["pick"]["mean"] for k in ks]
            lo = [y - x[curve][str(k)]["pick"]["ci"][0] for y, k in zip(ys, ks)]
            hi = [x[curve][str(k)]["pick"]["ci"][1] - y for y, k in zip(ys, ks)]
            ax.errorbar(ks, ys, yerr=[lo, hi], color=colour, linestyle="-" if lv["kind"] == "preset" else "--",
                        linewidth=0.9, marker="o", markersize=2.5, capsize=1.5, label=noise_name(lv, levels))
            kst = x[kfield]
            if kst != ks[max(range(len(ks)), key=lambda i: ys[i])]:
                raise SystemExit("REFUSED: %s %s %s: the best k on file, %s, is not the curve's highest mean pick"
                                 % (stem, label, lv["key"], kst))
            ax.scatter([kst], [x[curve][str(kst)]["pick"]["mean"]], marker="*", s=70, color=colour,
                       edgecolor="black", linewidth=0.4, zorder=4)
        ax.set_title(label, fontsize=FS.MIN_PT + 1)
        ax.set_xticks(ks)
        FS.grid_on(ax, "y")
    axes[0].set_ylabel("final pick (true value)")
    axes[len(axes) // 2].set_xlabel("re-tests of the current best per round, k")
    # Two legend rows, the three presets above the design sweep: on one row the five names are wider than the figure.
    # The legend fills column by column, so presets and sweep levels alternate in the list.
    entries = list(zip(*axes[0].get_legend_handles_labels()))
    presets = [e for e, lv in zip(entries, levels) if lv["kind"] == "preset"]
    sweep = [e for e, lv in zip(entries, levels) if lv["kind"] != "preset"]
    order = [e for pair in itertools.zip_longest(presets, sweep) for e in pair if e is not None]
    fig.tight_layout()
    fig.legend([h for h, _l in order], [l for _h, l in order], frameon=False, loc="lower center", ncol=len(presets),
               fontsize=FS.MIN_PT, bbox_to_anchor=(0.5, 1.0), columnspacing=1.2, handlelength=1.8)
    return FS.save(fig, stem)


def fig_noise_sweep():
    """The noise sweep under the grid's rule: a slot is lost after three rejected replacements."""
    return _noise_sweep_row("guessing", "kstar", "fig_noise_sweep")


def fig_noise_sweep_free():
    """The same noise sweep where a rejection costs no slot."""
    return _noise_sweep_row("riskfree", "kstar_riskfree", "fig_noise_sweep_free")


# The three scripted rules in the headline figure, keyed as in wellocate_scorecard.json, one line style each.
HEADLINE_RULES = (("guessing at k*", "guessing rule", "--"), ("informed at k*", "informed rule", "-"),
                  ("model-guided", "model-guided rule", ":"))


def fig_headline():
    """Re-testing share and final pick for the five models against the three scripted rules (grid, Blind prompt).
    Values come from paper_figdata.json and wellocate_scorecard.json; the figure is not drawn if they disagree."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    d = FS.results("paper_figdata.json")
    rules = FS.results("wellocate_scorecard.json")["splits"]["nk:paper"]["baselines"]
    lo, hi = d["references"]["band"]
    shared = ((rules["guessing at k*"]["pick"]["mean"], d["references"]["guessing_pick"]),
              (rules["informed at k*"]["pick"]["mean"], d["references"]["informed_pick"]),
              (rules["guessing at k*"]["share_budget"]["mean"], lo), (rules["model-guided"]["share_budget"]["mean"], hi))
    if any(abs(x - y) > 1e-9 for x, y in shared):
        raise SystemExit("wellocate_scorecard.json and paper_figdata.json disagree on the scripted rules")
    names = sorted(d["models"], key=lambda n: -d["models"][n]["share_budget"]["mean"])
    ys = list(range(len(names)))
    fig, (a, b) = plt.subplots(1, 2, figsize=(FS.FULL, 2.6), sharey=True, gridspec_kw=dict(width_ratios=[1.3, 1]))
    a.axvspan(lo, hi, color=FS.GREY, alpha=0.15, linewidth=0)
    for key, _label, style in HEADLINE_RULES:
        a.axvline(rules[key]["share_budget"]["mean"], color=FS.OKABE["black"], linestyle=style, linewidth=0.9)
        b.axvline(rules[key]["pick"]["mean"], color=FS.OKABE["black"], linestyle=style, linewidth=0.9)
    for y, n in zip(ys, names):
        colour, marker = FS.STYLE_BY_LABEL[n]
        for ax, key in ((a, "share_budget"), (b, "pick")):
            m = d["models"][n][key]
            ax.errorbar([m["mean"]], [y], xerr=[[m["mean"] - m["ci"][0]], [m["ci"][1] - m["mean"]]], color=colour,
                        marker=marker, markersize=5, capsize=2, linewidth=1.0, zorder=3)
    a.set_yticks(ys)
    a.set_yticklabels(names)
    a.invert_yaxis()
    a.set_xlabel("re-testing share, % of slots")
    b.set_xlabel("final pick (true value)")
    handles = [Line2D([], [], color=FS.OKABE["black"], linestyle=style, linewidth=0.9, label=label)
               for _key, label, style in HEADLINE_RULES]
    handles.append(Patch(facecolor=FS.GREY, alpha=0.15, label="scripted band"))
    fig.legend(handles=handles, frameon=False, fontsize=FS.MIN_PT + 1, loc="lower center", ncol=len(handles),
               bbox_to_anchor=(0.55, 0.98))
    for ax in (a, b):
        FS.grid_on(ax, "x")
    fig.tight_layout()
    return FS.save(fig, "fig_headline")


def fig_loss_directions():
    """Exploration loss against selection loss per model, with the scripted rules at their best settings as
    reference points and a line of equal total loss through the guessing rule's point."""
    d = FS.results("paper_figdata.json")
    base = FS.results("wellocate_scorecard.json")["splits"]["nk:paper"]["baselines"]
    g = base["guessing at k*"]
    others = (("informed at k*", "informed rule", "v"), ("model-guided", "model-guided rule", "h"))
    # The legend sits under the axes: with eight entries it would cover a point anywhere inside them. The figure is
    # taller by the legend's height, so the axes keep their size.
    fig, ax = plt.subplots(figsize=(FS.HALF * 1.5, 3.45))
    gx, gy = g["exploration_shortfall"]["mean"], g["selection_shortfall"]["mean"]
    xs = ([d["models"][n]["exploration_shortfall"]["mean"] for n in d["models"]] + [gx] +
          [base[key]["exploration_shortfall"]["mean"] for key, _l, _m in others])
    span = [min(xs) * 0.9, max(xs) * 1.05]
    for total, style in ((gx + gy, "--"),):
        ax.plot(span, [total - x for x in span], color=FS.GREY, linestyle=style, linewidth=0.7)
    for n, m in d["models"].items():
        colour, marker = FS.STYLE_BY_LABEL[n]
        ex, se = m["exploration_shortfall"], m["selection_shortfall"]
        ax.errorbar([ex["mean"]], [se["mean"]], xerr=[[ex["mean"] - ex["ci"][0]], [ex["ci"][1] - ex["mean"]]],
                    yerr=[[se["mean"] - se["ci"][0]], [se["ci"][1] - se["mean"]]], color=colour, marker=marker,
                    markersize=5, capsize=2, linewidth=0.9, label=n)
    ax.errorbar([gx], [gy], xerr=[[gx - g["exploration_shortfall"]["ci"][0]], [g["exploration_shortfall"]["ci"][1] - gx]],
                yerr=[[gy - g["selection_shortfall"]["ci"][0]], [g["selection_shortfall"]["ci"][1] - gy]],
                color=FS.OKABE["black"], marker="*", markersize=8, capsize=2, linewidth=0.9, label="guessing rule")
    # The other two scripted rules are drawn hollow and grey, so the guessing rule stays the reference.
    for key, label, marker in others:
        ex, se = base[key]["exploration_shortfall"], base[key]["selection_shortfall"]
        ax.errorbar([ex["mean"]], [se["mean"]], xerr=[[ex["mean"] - ex["ci"][0]], [ex["ci"][1] - ex["mean"]]],
                    yerr=[[se["mean"] - se["ci"][0]], [se["ci"][1] - se["mean"]]], color=FS.GREY, marker=marker,
                    markersize=5, markerfacecolor="white", markeredgecolor=FS.GREY, capsize=2, linewidth=0.7,
                    label=label)
    ax.set_xlim(*span)
    ax.set_ylim(bottom=0)
    ax.text(0.98, 0.80, "re-tests too much:\nfew new candidates", transform=ax.transAxes, ha="right", va="center",
            fontsize=FS.MIN_PT, style="italic")
    ax.text(0.03, 0.97, "re-tests too little:\npicks on single readings", transform=ax.transAxes, ha="left", va="top",
            fontsize=FS.MIN_PT, style="italic")
    ax.set_xlabel("exploration loss (best in landscape minus best measured)")
    ax.set_ylabel("selection loss\n(best measured minus pick)")
    FS.grid_on(ax, "y")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=FS.MIN_PT, loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    return FS.save(fig, "fig_loss_directions")


# Panel (a) of the fixes figure stacks the three models within each aid at these offsets, as fractions of a row; layout,
# not data.
FIX_OFFSETS = (-0.24, 0.0, 0.24)


def fig_fixes():
    """What the aids do, 2 x 2. (a) the change in re-testing share against each model's paired control for the
    ledger, the landscape note and the Menu on the grid. (b) and (c) the Menu on scrambled GB1, share and pick
    change. (d) a simulated confirmation round on the agents' own grid traces: pick change against k candidates
    re-measured, with each model's selection loss as a dotted line."""
    a0 = FS.results("analysis_0an.json")["cells"]
    a5 = FS.results("opus_topup_0an5.json")
    a6 = FS.results("analysis_0an6.json")["cells"]
    a7 = FS.results("analysis_0an7.json")["menu_minus_blind"]
    a1 = FS.results("confirm_counterfactual_0an7.json")
    grid = [("Opus 4.7", "Opus"), ("Gemini 2.5 Flash", "Gemini"), ("DeepSeek V3.1", "DeepSeek")]
    aids = [("ledger", lambda k: a0["F1 ledger|%s" % k]), ("landscape note", lambda k: a0["F5 structure|%s" % k]),
            ("Menu", lambda k: a5["60"] if k == "Opus" else a0["F2 menu|%s" % k])]
    rows = [("Opus 4.7", a6["Opus"]["d_share"], a6["Opus"]["d_share_ci"], a6["Opus"]["d_pick"], a6["Opus"]["d_pick_ci"]),
            ("Gemini 2.5 Flash", a6["Gemini"]["d_share"], a6["Gemini"]["d_share_ci"], a6["Gemini"]["d_pick"],
             a6["Gemini"]["d_pick_ci"]),
            ("DeepSeek V3.1", a6["DeepSeek"]["d_share"], a6["DeepSeek"]["d_share_ci"], a6["DeepSeek"]["d_pick"],
             a6["DeepSeek"]["d_pick_ci"]),
            ("GPT-6.1 Sol", a7["sol"]["d_share_budget"], a7["sol"]["d_share_budget_ci"], a7["sol"]["d_pick"],
             a7["sol"]["d_pick_ci"]),
            ("Gemini 3.1 Pro", a7["gem"]["d_share_budget"], a7["gem"]["d_share_budget_ci"], a7["gem"]["d_pick"],
             a7["gem"]["d_pick_ci"])]
    fig, axes = plt.subplots(2, 2, figsize=(FS.FULL, 4.4))
    pa, pb, pc, pd = axes[0][0], axes[0][1], axes[1][0], axes[1][1]
    # (a) the grid aids: one row per aid, the three models side by side within it
    for (name, key), off in zip(grid, FIX_OFFSETS):
        colour, marker = FS.STYLE_BY_LABEL[name]
        for i, (_aid, cell) in enumerate(aids):
            c = cell(key)
            m, ci = c["d_share"], c["d_share_ci"]
            pa.errorbar([m], [i + off], xerr=[[m - ci[0]], [ci[1] - m]], color=colour, marker=marker, markersize=5,
                        capsize=2, linewidth=1.0)
    pa.set_yticks(range(len(aids)))
    pa.set_yticklabels([aid for aid, _c in aids])
    pa.set_title("Grid: three aids", fontsize=FS.MIN_PT + 1)
    # (b) and (c) the Menu on scrambled GB1
    ys = list(range(len(rows)))
    for y, (n, ds, dsc, dp, dpc) in zip(ys, rows):
        colour, marker = FS.STYLE_BY_LABEL[n]
        for ax, m, c in ((pb, ds, dsc), (pc, dp, dpc)):
            ax.errorbar([m], [y], xerr=[[m - c[0]], [c[1] - m]], color=colour, marker=marker, markersize=5, capsize=2,
                        linewidth=1.0)
    for ax in (pb, pc):
        ax.set_yticks(ys)
        ax.set_yticklabels([r[0] for r in rows])
    # On one line this label is wider than its panel, and the saved figure clips what overhangs the right edge.
    for ax in (pa, pb):
        ax.set_xlabel("change in re-testing share\n(points)")
    pb.set_title("GB1: the Menu", fontsize=FS.MIN_PT + 1)
    pc.set_title("GB1: the Menu", fontsize=FS.MIN_PT + 1)
    pc.set_xlabel("change in final pick")
    for ax in (pa, pb, pc):
        ax.axvline(0.0, color=FS.GREY, linewidth=0.6)
        ax.invert_yaxis()
        FS.grid_on(ax, "x")
    # (d) a final round of re-tests, simulated on the agents' own grid traces
    ends = []
    for n in ("Gemini 3.1 Pro", "GPT-6.1 Sol"):
        colour, marker = FS.STYLE_BY_LABEL[n]
        ks = sorted(a1[n]["k"], key=int)
        m = [a1[n]["k"][k]["d_vs_agent"] for k in ks]
        lo = [v - a1[n]["k"][k]["d_vs_agent_ci"][0] for v, k in zip(m, ks)]
        hi = [a1[n]["k"][k]["d_vs_agent_ci"][1] - v for v, k in zip(m, ks)]
        ends += [a1[n]["k"][k]["d_vs_agent_ci"][1] for k in ks]
        pd.errorbar([int(k) for k in ks], m, yerr=[lo, hi], color=colour, marker=marker, markersize=4, capsize=2,
                    linewidth=0.9)
    pd.axhline(0.0, color=FS.GREY, linewidth=0.6)
    pd.set_xticks([int(k) for k in ks])
    pd.set_xlabel("top m re-measured, last round")
    pd.set_ylabel("pick change (simulated)")
    # Each model's selection loss as a dotted line in its colour; labels sit on the line or above the highest
    # interval end, so no label covers data.
    losses = {n: a1[n]["selection_shortfall"] for n in ("Gemini 3.1 Pro", "GPT-6.1 Sol")}
    y0 = pd.get_ylim()[0]
    pd.set_ylim(y0, max(losses.values()) + 0.15 * (max(losses.values()) - y0))
    for n, label in (("Gemini 3.1 Pro", "Gemini 3.1 Pro's selection loss"), ("GPT-6.1 Sol", "Sol's selection loss")):
        colour = FS.STYLE_BY_LABEL[n][0]
        pd.axhline(losses[n], color=colour, linestyle=":", linewidth=0.9)
        pd.annotate(label, xy=(pd.get_xlim()[1], max(losses[n], max(ends))), xytext=(-2, 2), textcoords="offset points",
                    ha="right", va="bottom", color=colour, fontsize=FS.MIN_PT)
    FS.grid_on(pd, "y")
    for ax, letter in zip((pa, pb, pc, pd), "abcd"):
        ax.text(-0.02, 1.04, "(%s)" % letter, transform=ax.transAxes, fontsize=FS.MIN_PT + 1, ha="right")
    # One legend for the whole figure, above it: every panel colours the models the same way, and a legend inside a
    # panel reads as data.
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=FS.STYLE_BY_LABEL[n][0], marker=FS.STYLE_BY_LABEL[n][1], linestyle="none",
                      markersize=5, label=n) for n, *_r in rows]
    fig.legend(handles=handles, frameon=False, fontsize=FS.MIN_PT, loc="upper center", ncol=len(handles),
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return FS.save(fig, "fig_fixes")


def main():
    made = []
    for fn in (fig1_environment, fig_landscape_env, fig2_headline, fig3_split, fig5_zero_noise, figA2_simulation,
               figA3_shortfall_global, fig_noise_sweep, fig_noise_sweep_free, fig_headline, fig_loss_directions,
               fig_fixes):
        try:
            pdf, png = fn()
        except SystemExit as e:
            print("  %-26s SKIPPED: %s" % (fn.__name__, e))
            continue
        made.append(pdf)
        print("  %-26s %s  (%d KB pdf)" % (fn.__name__, os.path.basename(pdf),
                                           os.path.getsize(pdf) // 1024))
    print("\n  %d of 12 figures written to results/figures/" % len(made))
    return 0 if len(made) == 12 else 1


if __name__ == "__main__":
    sys.exit(main())
