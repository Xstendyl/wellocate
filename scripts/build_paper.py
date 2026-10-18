#!/usr/bin/env python3
"""Regenerate the paper's figures and compile it. Nothing in paper/ refers outside it.

  python3 scripts/build_paper.py            # figures, then compile with tectonic
  python3 scripts/build_paper.py --no-pdf   # figures only
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "paper")
INCLUDE = re.compile(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}")


def main():
    print("regenerating figures from the analysis outputs...")
    subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "figures.py")],
                   check=True, cwd=ROOT, capture_output=True)
    # The figure list is read from the .tex files main.tex reaches; an unreached .tex file is refused.
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import paper_files as PF
    orphans = PF.orphans()
    if orphans:
        raise SystemExit("REFUSED: paper/ holds %s, which main.tex never reaches. Remove it, so the released "
                         "source carries nothing the paper does not use." % ", ".join(orphans))
    wanted = set()
    for rel in [PF.MAIN_TEX] + [f for files in PF.parts().values() for f in files]:
        wanted.update(INCLUDE.findall(open(os.path.join(PAPER, rel)).read()))
    missing = [f for f in sorted(wanted) if not os.path.exists(os.path.join(PAPER, "figures", f))]
    if missing:
        raise SystemExit("REFUSED: the paper includes %s, which figures.py did not produce"
                         % ", ".join(missing))
    for f in sorted(wanted):
        print("  %s  %d bytes" % (f, os.path.getsize(os.path.join(PAPER, "figures", f))))
    stale = [f for f in sorted(os.listdir(os.path.join(PAPER, "figures"))) if f not in wanted]
    if stale:
        raise SystemExit("REFUSED: paper/figures holds %s, which no .tex includes. Remove it, so the "
                         "released source carries nothing the paper does not use." % ", ".join(stale))
    subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "make_bib.py"), "--write-paper"],
                   check=True, cwd=ROOT)
    # The tables are generated from the analysis output, like the bibliography.
    subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "make_table_cells.py"), "--write-paper"],
                   check=True, cwd=ROOT)
    subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "make_table_prompt.py"), "--write-paper"],
                   check=True, cwd=ROOT)
    if "--no-pdf" in sys.argv:
        return 0
    print("compiling...")
    r = subprocess.run(["tectonic", "-X", "compile", "main.tex", "--keep-logs"],
                       cwd=os.path.join(ROOT, "paper"), capture_output=True, text=True)
    sys.stdout.write(r.stdout[-3000:])
    sys.stderr.write(r.stderr[-6000:])
    pdf = os.path.join(ROOT, "paper", "main.pdf")
    if r.returncode or not os.path.exists(pdf):
        raise SystemExit("compile FAILED (exit %d)" % r.returncode)
    print("\nwrote paper/main.pdf, %.0f KB" % (os.path.getsize(pdf) / 1024))
    # Fail the build if a figure lands far from the text that cites it or a page is left half empty.
    fp = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "float_pages.py"), pdf],
                        capture_output=True, text=True)
    sys.stdout.write(fp.stdout)
    if fp.returncode:
        raise SystemExit("a layout rule failed: figure placement or blank space (scripts/float_pages.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
