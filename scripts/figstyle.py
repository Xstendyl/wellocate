#!/usr/bin/env python3
"""One style for every figure in the paper. Plotting scripts import it instead of restating it.

It sets vector PDF output with PNG previews, page-relative sizes (FULL 6.5 in, HALF 3.2 in), a serif face at
8 to 9 pt, the Okabe-Ito colour-blind-safe palette with one colour and one marker per model, no titles inside
images, and light axes. It also defines the model names used in the paper.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FULL, HALF = 6.5, 3.2                      # inches, the paper's text width and a half-width column
BASE_PT, MIN_PT = 9, 7

# Okabe-Ito, colour-blind safe. https://jfly.uni-koeln.de/color/
OKABE = dict(black="#000000", orange="#E69F00", skyblue="#56B4E9", green="#009E73",
             yellow="#F0E442", blue="#0072B2", vermillion="#D55E00", purple="#CC79A7")

# One colour AND one marker per model, used in every figure.
MODELS = [
    ("anthropic/claude-opus-4.7", "Opus 4.7", OKABE["blue"], "o"),
    ("google/gemini-2.5-flash", "Gemini 2.5 Flash", OKABE["green"], "s"),
    ("deepseek/deepseek-chat-v3.1", "DeepSeek V3.1", OKABE["vermillion"], "^"),
]
# The two newer reasoning models, kept apart so figures that loop over MODELS are unchanged.
MODELS_NEW = [
    ("openai/gpt-6.1-sol", "GPT-6.1 Sol", OKABE["orange"], "D"),
    ("google/gemini-3.1-pro-preview", "Gemini 3.1 Pro", OKABE["purple"], "P"),
]
MODELS_ALL = MODELS + MODELS_NEW
STYLE_BY_LABEL = {label: (colour, marker) for _k, label, colour, marker in MODELS_ALL}
GREY = "#666666"                           # a neutral swatch, where a legend entry stands for a
                                           # segment drawn in each panel's own model colour
# The two scripted references, in the paper's words. The data keys stay "pool" and "fair".
REF_LABEL = {"pool": "informed rule", "fair": "guessing rule"}
REF_SHORT = {"pool": "informed", "fair": "guessing"}

BY_SHORT = {k.split("/")[-1]: (label, colour, marker) for k, label, colour, marker in MODELS}
CONDITIONS = ["Blind", "Quantitative", "Mechanism", "Aggregated", "Decision-rule"]

# The scripted lab protocols, one marker each, distinct from the models.
PROTOCOLS = [("(a) triplicate-everything", "triplicate", OKABE["purple"], "D"),
             ("(b) duplicate-everything", "duplicate", OKABE["orange"], "v"),
             ("(c) screen-then-confirm", "screen then confirm", OKABE["skyblue"], "P")]


def use():
    """Apply the style. Called once by each figure script before it draws anything."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": BASE_PT,
        "axes.labelsize": BASE_PT,
        "axes.titlesize": BASE_PT,
        "xtick.labelsize": MIN_PT + 1,
        "ytick.labelsize": MIN_PT + 1,
        "legend.fontsize": MIN_PT + 1,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "axes.axisbelow": True,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
    })
    return plt


def grid_on(ax, axis="y"):
    """A subtle grid on the value axis only."""
    ax.grid(True, axis=axis, alpha=0.25, linewidth=0.5)
    ax.grid(False, axis=("x" if axis == "y" else "y"))


def turn_labels_inward(ax, frac=0.72):
    """Flip any annotation near the right edge back into the axes. Call after the last artist is drawn."""
    x0, x1 = ax.get_xlim()
    cut = x0 + frac * (x1 - x0)
    for t in ax.texts:
        xy = getattr(t, "xy", None)
        if xy is None or xy[0] < cut or t.get_ha() == "right":
            continue
        dx, dy = t.xyann
        t.xyann = (-abs(dx), dy)
        t.set_ha("right")


def label_levels(ax, items, x, min_frac=0.05):
    """Label horizontal reference lines, pushed apart to a legible separation, with a leader line."""
    y0, y1 = ax.get_ylim()
    sep = min_frac * (y1 - y0)
    order = sorted(items)
    ys = [v for v, _lab in order]
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] < sep:
            ys[i] = ys[i - 1] + sep
    drop = max(0.0, ys[-1] - (y1 - 0.5 * sep))
    ys = [y - drop for y in ys]
    for (val, lab), y in zip(order, ys):
        ax.annotate(lab, xy=(x, y), fontsize=MIN_PT, va="center", ha="left", annotation_clip=False)
        if abs(y - val) > 1e-9:
            ax.plot([x - 0.16, x - 0.03], [val, y], color=OKABE["black"], linewidth=0.5,
                    clip_on=False, zorder=1)


def results(name):
    return json.load(open(os.path.join(ROOT, "results", name)))


def refs():
    """The two scripted references, read from the results file."""
    c = results("reference_curve_alphabet.json")["curves"]      # alphabet-corrected curves
    return dict(fair_kstar=c["fair"]["1"]["mean"], fair_k0=c["fair"]["0"]["mean"],
                pool_kstar=c["pool"]["1"]["mean"], pool_k0=c["pool"]["0"]["mean"],
                fair_distinct=c["fair"]["1"]["distinct"], pool_distinct=c["pool"]["1"]["distinct"],
                kstar_share=_kstar_share(c))


def _kstar_share(curves):
    """The optimum replication share, derived from the reference curve."""
    ks = sorted(curves["pool"], key=int)
    slots = len(ks) - 1
    best = {scope: max(ks, key=lambda k: curves[scope][k]["mean"]) for scope in ("pool", "fair")}
    if best["pool"] != best["fair"]:
        raise ValueError("REFUSED: the two scripted scopes peak at different k (%s), so there is no "
                         "one optimum share to draw." % best)
    return 100.0 * int(best["pool"]) / slots


def save(fig, stem):
    """Save a vector PDF with a PNG preview, and copy the PDF into paper/figures/."""
    out = os.path.join(ROOT, "results", "figures")
    os.makedirs(out, exist_ok=True)
    pdf = os.path.join(out, stem + ".pdf")
    png = os.path.join(out, stem + ".png")
    fig.savefig(pdf)
    fig.savefig(png, dpi=200)
    paper = os.path.join(ROOT, "paper", "figures")
    if os.path.isdir(paper):
        fig.savefig(os.path.join(paper, stem + ".pdf"))
    return pdf, png
