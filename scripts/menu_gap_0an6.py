#!/usr/bin/env python3
"""How much of the gap to the guessing rule the menu tool closed on scrambled GB1, for the two models that explored least.

Descriptive, computed from results/basins.json (the source of the paper's basins table): each model's mean pick in
its GB1 Blind control and in its GB1 menu arm, and the guessing rule's mean pick on the 1,500 reference seeds at
its best k (k = 0). The share of the gap closed is
    (Menu pick - Blind pick) / (guessing pick - Blind pick).
The arms are unpaired here, as in the table; Table 2 gives the paired change.

Usage: python3 scripts/menu_gap_0an6.py      (writes results/menu_gap_0an6.json)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    b = json.load(open(os.path.join(ROOT, "results", "basins.json")))
    g = b["scripted"]["GB1"]["guessing rule"]["nominee_value"]
    out = dict(source="results/basins.json", guessing_pick=g, models={})
    for label in ("Gemini 2.5 Flash", "DeepSeek V3.1"):
        blind = b["arms"]["GB1 Blind"][label]["nominee_value"]
        menu = b["arms"]["GB1 Menu"][label]["nominee_value"]
        share = 100.0 * (menu - blind) / (g - blind)
        out["models"][label] = dict(blind_pick=blind, menu_pick=menu, gap_closed_pct=share)
        print("%-17s Blind %.4f  Menu %.4f  guessing %.4f  gap closed %.1f%%" % (label, blind, menu, g, share))
    json.dump(out, open(os.path.join(ROOT, "results", "menu_gap_0an6.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
