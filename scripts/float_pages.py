#!/usr/bin/env python3
"""Check two layout rules on the built PDF: figures near the text that cites them, and no half-empty pages.

Each figure must sit on the page of its first mention or up to MAX_AFTER pages after it, never before; tables
are reported but not enforced. No page except the last may have a blank band taller than MAX_BLANK of its
text block, read from a 30 dpi render. Both rules are checked together, since a layout can meet one and
break the other.

Usage: python3 scripts/float_pages.py [paper/main.pdf]   (exit 1 if either rule fails)
"""
import os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_AFTER = 2
MAX_BLANK = 0.15


def mentions(kind, n, text):
    """True if `text` cites `kind` n: "Figure 5", "Figure 5a" or "Figure 5." count; "Figure 50" and the caption
    line "Figure 5:" do not."""
    return re.search(r"\b%s %d(?![\d:])" % (kind, n), text) is not None


def pages(pdf):
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True)
    return out.stdout.split("\f")


def blank_bands(pdf):
    """Per page, the longest run of empty rows inside the text block, as a fraction of its height."""
    from PIL import Image
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["pdftoppm", "-r", "30", "-gray", "-png", pdf, os.path.join(d, "p")], check=True)
        out = []
        for f in sorted(os.listdir(d)):
            im = Image.open(os.path.join(d, f)).convert("L")
            w, h = im.size
            px = im.load()
            top, bot = int(0.09 * h), int(0.91 * h)
            run = best = 0
            for y in range(top, bot):
                blank = all(px[x, y] > 245 for x in range(int(0.1 * w), int(0.9 * w), 2))
                run = run + 1 if blank else 0
                best = max(best, run)
            out.append(best / (bot - top))
        return out
    finally:
        shutil.rmtree(d)


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "paper", "main.pdf")
    pg = [re.sub(r"\s+", " ", p) for p in pages(pdf)]
    refs = next(i for i, p in enumerate(pg) if re.search(r"\bReferences\b", p) and "Acknowledgements" in
                "".join(pg[max(0, i - 1):i + 1]))
    bad = []
    print("%-9s %14s %12s" % ("float", "first mention", "float page"))
    # Every main-text float, found in the PDF: one whose caption sits before the References.
    floats = []
    for kind in ("Figure", "Table"):
        nums = sorted({int(m.group(1)) for i, p in enumerate(pg[:refs + 1])
                       for m in re.finditer(r"\b%s (\d+):" % kind, p)})
        floats += [(kind, k) for k in nums]
    for kind, n in floats:
        cap = [i + 1 for i, p in enumerate(pg) if re.search(r"\b%s %d:" % (kind, n), p)]
        men = [i + 1 for i, p in enumerate(pg[:refs + 1]) if mentions(kind, n, p)]
        if not cap or not men:
            bad.append("%s %d: caption on %s, mentioned on %s" % (kind, n, cap, men))
            continue
        ok = 0 <= cap[0] - men[0] <= MAX_AFTER
        print("%-9s %14d %12d  %s" % ("%s %d" % (kind, n), men[0], cap[0],
                                      "ok" if ok else "TOO FAR" if kind == "Figure" else "reported"))
        if not ok and kind == "Figure":
            bad.append("%s %d: first mentioned on page %d, placed on page %d (rule: 0 to %d pages after)"
                       % (kind, n, men[0], cap[0], MAX_AFTER))
    bands = blank_bands(pdf)
    worst = max(range(len(bands) - 1), key=lambda i: bands[i])
    print("largest blank band: %.0f%% on page %d (limit %.0f%%, last page exempt)"
          % (100 * bands[worst], worst + 1, 100 * MAX_BLANK))
    for i, b in enumerate(bands[:-1]):
        if b > MAX_BLANK:
            bad.append("page %d: a blank band of %.0f%% of the text block (limit %.0f%%)"
                       % (i + 1, 100 * b, 100 * MAX_BLANK))
    for b in bad:
        print("  " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
