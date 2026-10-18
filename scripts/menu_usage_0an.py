#!/usr/bin/env python3
"""How the menu arm is used: how many suggestions are viable, and how often the agent orders from the list.

Read from the archived calls of a menu-arm tag, in call order. For every prompt that carried a menu it records the
suggested candidates, whether each is viable on the grid's landscape, and which accepted proposals were on the
list, also over new names only (a re-test can never be on the list). For new names it gives the viable rate of
those taken from the list and of the agent's own. Descriptive only.

Usage: python3 scripts/menu_usage_0an.py <tag>      (prints, and writes results/menu_usage_<tag>.json)
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                            # noqa: E402
import grid                                                         # noqa: E402

ITEM = re.compile(r"^\d+\. ([A-Z]{4})$", re.M)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "smoke0an_f2_menu"
    _fit, pool = grid.landscape()
    per = collections.defaultdict(lambda: dict(menus=0, shown=0, viable=0, proposals=0, from_menu=0, calls_using=0,
                                                new_proposals=0, new_from_menu=0, new_from_menu_viable=0,
                                                new_own=0, new_own_viable=0))
    seen = collections.defaultdict(set)
    for c in A0.calls(tag):
        if c.get("kind") == "nomination":
            continue
        before = seen[(c["model"], c["campaign_seed"])]
        got = c.get("parsed") or []
        if "SUGGESTED NEW CANDIDATES" not in (c.get("prompt") or ""):
            before.update(got)
            continue
        menu = ITEM.findall(c["prompt"].split("SUGGESTED NEW CANDIDATES", 1)[1])
        d = per[c["model"]]
        d["menus"] += 1
        d["shown"] += len(menu)
        d["viable"] += sum(1 for s in menu if s in pool)
        d["proposals"] += len(got)
        hit = sum(1 for s in got if s in set(menu))
        new = [s for s in got if s not in before]
        d["new_proposals"] += len(new)
        d["new_from_menu"] += sum(1 for s in new if s in set(menu))
        d["new_from_menu_viable"] += sum(1 for s in new if s in set(menu) and s in pool)
        d["new_own"] += sum(1 for s in new if s not in set(menu))
        d["new_own_viable"] += sum(1 for s in new if s not in set(menu) and s in pool)
        before.update(got)
        d["from_menu"] += hit
        d["calls_using"] += 1 if hit else 0
    out = {}
    for m, d in sorted(per.items()):
        out[m] = dict(d, viable_share=d["viable"] / d["shown"] if d["shown"] else None,
                      from_menu_share=d["from_menu"] / d["proposals"] if d["proposals"] else None,
                      calls_using_share=d["calls_using"] / d["menus"] if d["menus"] else None,
                      new_from_menu_share=d["new_from_menu"] / d["new_proposals"] if d["new_proposals"] else None,
                      menu_new_viable_rate=d["new_from_menu_viable"] / d["new_from_menu"] if d["new_from_menu"] else None,
                      own_new_viable_rate=d["new_own_viable"] / d["new_own"] if d["new_own"] else None)
        print("%-30s %4d menus: %.0f%% of suggestions viable; %.0f%% of proposals taken from the list; "
              "%.0f%% of calls used it; %d of %d new names from the list"
              % (m, d["menus"], 100 * out[m]["viable_share"], 100 * (out[m]["from_menu_share"] or 0),
                 100 * out[m]["calls_using_share"], d["new_from_menu"], d["new_proposals"]))
        print("%-30s      viable: %.1f%% of new names from the list (%d), %.1f%% of its own new names (%d)"
              % ("", 100 * (out[m]["menu_new_viable_rate"] or 0), d["new_from_menu"],
                 100 * (out[m]["own_new_viable_rate"] or 0), d["new_own"]))
    json.dump(out, open(os.path.join(ROOT, "results", "menu_usage_%s.json" % tag), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
