#!/usr/bin/env python3
"""Verify every citation's identifier, title, authors and venue against arXiv's API or Crossref. Saves the raw records.

Where the API disagrees with the expected fields, the script prints MISMATCH.
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}

# (arxiv id, first author surname we expect or None, a distinctive title fragment we expect)
CLAIMS = [
    ("2403.15371", "Krishnamurthy", "explore in-context"),
    ("2509.21403", None, "Bayesian Optimization"),
    ("2603.26177", None, "Lab-in-the-Loop"),
    ("2602.11348", None, "Noise"),
    ("2311.01195", "Dai", "Batch Bayesian Optimization"),
    # Technometrics 61(1), 2019, doi 10.1080/00401706.2018.1469433; arXiv's title casing is used.
    ("1710.03206", "Binois", "Replication or exploration"),
    # Closest related environments, cited in Related Work.
    ("2501.01540", "Gandhi", "BoxingGym"),
    ("2604.13151", None, "Exploration and Exploitation Errors"),
    # This paper was renamed between versions (v1 "AlloBench", v2 "AllocBench"); both are pinned and the
    # current version is cited.
    ("2607.23332v1", "Wang", "AlloBench:"),
    ("2607.23332v2", "Wang", "AllocBench:"),
    ("2607.29626", None, "Hyperparameter"),
    # LLM agents designing experiments, and an LLM inside Bayesian optimisation.
    ("2405.17631", "Roohani", "BioDiscoveryAgent"),
    ("2402.03921", "Liu", "Large Language Models to Enhance Bayesian Optimization"),
]

# Sources with a DOI and no arXiv id, resolved through Crossref with the same checks.
# (doi, first author surname, distinctive title fragment, venue fragment)
DOI_CLAIMS = [
    ("10.1016/S0022-5193(89)80019-0", "Kauffman", "NK model", "Theoretical Biology"),
    ("10.7554/eLife.16965", "Wu", "indirect paths", "eLife"),
    # Self-driving labs that choose which variants to test next.
    ("10.1038/s44286-023-00002-4", "Rapp", "Self-driving laboratories to autonomously navigate",
     "Nature Chemical Engineering"),
    ("10.1021/acs.chemrev.4c00055", "Tom", "Self-Driving Laboratories for Chemistry and Materials",
     "Chemical Reviews"),
    # The PhoQ landscape (data/phoq.csv).
    ("10.1126/science.1257360", "Podgornaia", "Pervasive degeneracy and epistasis", "Science"),
    # Budget allocation for selection, an LLM agent running chemistry, and ML-guided directed evolution on GB1.
    ("10.1023/A:1008349927281", "Chen", "Simulation Budget Allocation", "Discrete Event Dynamic Systems"),
    ("10.1038/s41586-023-06792-0", "Boiko", "Autonomous chemical research with large language models", "Nature"),
    ("10.1073/pnas.1901979116", "Wu", "Machine learning-assisted directed protein evolution", "Proceedings of the National Academy"),
    # How predictable evolutionary trajectories are on fitness landscapes.
    ("10.1371/journal.pcbi.1002302", "Lobkovsky", "Predictability of evolutionary trajectories", "PLoS Computational Biology"),
]


def fetch_doi(doi, tries=4):
    """One Crossref record. Crossref asks callers to identify themselves in the User-Agent."""
    url = "https://api.crossref.org/works/%s" % urllib.parse.quote(doi, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "repdef-citation-check/1.0"})
    last = None
    for attempt in range(tries):
        if attempt:
            time.sleep(min(30, 3 * (2 ** (attempt - 1))))
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())["message"]
        except urllib.error.HTTPError as e:                   # noqa: PERF203
            last = e
            if e.code not in (429, 500, 502, 503):
                raise
        except Exception as e:                                # noqa: BLE001
            last = e
    raise last


def check_dois():
    """Returns (records, number that failed a claim)."""
    out, bad = [], 0
    for doi, surname, frag, venue in DOI_CLAIMS:
        try:
            m = fetch_doi(doi)
        except Exception as e:                                # noqa: BLE001
            print("=" * 100)
            print("doi %s   FETCH FAILED: %s" % (doi, e))
            bad += 1
            continue
        title = " ".join(" ".join(m.get("title") or []).split())
        authors = ["%s %s" % (a.get("given", ""), a.get("family", "")) for a in m.get("author") or []]
        container = " ".join(" ".join(m.get("container-title") or []).split())
        parts = (m.get("published-print") or m.get("published-online")
                 or m.get("issued") or {}).get("date-parts") or [[None]]
        year = parts[0][0]
        print("=" * 100)
        print("doi %s" % doi)
        print("  TITLE      %s" % title)
        print("  AUTHORS    %s" % ", ".join(authors))
        print("  VENUE      %s %s, volume %s, issue %s, pages %s"
              % (container, year, m.get("volume"), m.get("issue"), m.get("page")))
        ok = True
        if surname.lower() not in (authors[0] if authors else "").lower():
            print("  MISMATCH   expected first author %r, Crossref says %r"
                  % (surname, authors[0] if authors else None))
            ok = False
        if frag.lower() not in title.lower():
            print("  MISMATCH   expected the title to contain %r" % frag)
            ok = False
        if venue.lower() not in container.lower():
            print("  MISMATCH   expected the venue to contain %r, Crossref says %r" % (venue, container))
            ok = False
        print("  VERDICT    %s" % ("fields confirmed" if ok else "DO NOT CITE AS CLAIMED"))
        bad += int(not ok)
        out.append(dict(doi=doi, title=title, authors=authors, container=container, year=year,
                        volume=m.get("volume"), issue=m.get("issue"), page=m.get("page"),
                        publisher=m.get("publisher"), claim_ok=ok))
    return out, bad


def fetch(aid, tries=5):
    """One arXiv record, at most one request every three seconds, retrying a rate-limit refusal with backoff."""
    url = "https://export.arxiv.org/api/query?id_list=%s" % aid
    last = None
    for attempt in range(tries):
        if attempt:
            time.sleep(min(60, 5 * (2 ** (attempt - 1))))
        else:
            time.sleep(3.0)                      # the interval arXiv asks callers to keep
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:      # noqa: PERF203
            last = e
            if e.code not in (429, 503):
                raise
        except Exception as e:                   # noqa: BLE001
            last = e
    raise last


def main():
    out, bad = [], 0
    for aid, surname, frag in CLAIMS:
        try:
            xml = fetch(aid)
        except Exception as e:                                # noqa: BLE001
            print("=== %s === FETCH FAILED: %s" % (aid, e))
            bad += 1
            continue
        root = ET.fromstring(xml)
        e = root.find("a:entry", NS)
        if e is None:
            print("=== %s === NO SUCH PAPER" % aid)
            bad += 1
            continue
        title = " ".join((e.find("a:title", NS).text or "").split())
        authors = [a.find("a:name", NS).text for a in e.findall("a:author", NS)]
        published = (e.find("a:published", NS).text or "")[:10]
        updated = (e.find("a:updated", NS).text or "")[:10]
        com = e.find("x:comment", NS)
        comment = " ".join((com.text or "").split()) if com is not None else ""
        jref = e.find("x:journal_ref", NS)
        journal = " ".join((jref.text or "").split()) if jref is not None else ""
        cats = [c.get("term") for c in e.findall("a:category", NS)]
        print("=" * 100)
        print("arXiv %s" % aid)
        print("  TITLE      %s" % title)
        print("  AUTHORS    %s%s" % (", ".join(authors[:4]),
                                     " (+%d more)" % (len(authors) - 4) if len(authors) > 4 else ""))
        print("  PUBLISHED  %s   UPDATED %s   PRIMARY %s" % (published, updated, cats[0] if cats else "?"))
        print("  COMMENT    %s" % (comment or "none"))
        print("  JOURNAL    %s" % (journal or "none stated"))
        ok = True
        if surname and surname.lower() not in (authors[0] or "").lower():
            print("  MISMATCH   expected first author %r, API says %r" % (surname, authors[0]))
            ok = False
        if frag.lower() not in title.lower():
            print("  MISMATCH   expected title to contain %r" % frag)
            ok = False
        print("  VERDICT    %s" % ("fields confirmed" if ok else "DO NOT CITE AS CLAIMED"))
        bad += int(not ok)
        abstract = " ".join((e.find("a:summary", NS).text or "").split())
        out.append(dict(arxiv=aid, title=title, authors=authors, published=published,
                        updated=updated, comment=comment, journal_ref=journal,
                        categories=cats, claim_ok=ok, abstract=abstract))
    # BioDesignBench is not on arXiv; its abstract is fetched from PMC and saved for quote checking.
    try:
        import re as _re, html as _html
        req = urllib.request.Request("https://pmc.ncbi.nlm.nih.gov/articles/PMC13174699/",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode("utf-8", "replace")
        t = _re.sub(r"<script.*?</script>|<style.*?</style>", "", raw, flags=_re.S)
        t = _re.sub(r"\s+", " ", _html.unescape(_re.sub(r"<[^>]+>", " ", t)))
        i = t.find("Abstract")
        j = t.find("Introduction", i if i > 0 else 0)
        abs_ = t[i:j].strip() if 0 < i < j else ""
        out.append(dict(arxiv=None, doi="10.1101/2026.05.06.723381", pmc="PMC13174699",
                        title="Benchmarking and behavioral characterization of LLM agents for protein design",
                        note="NOT on arXiv; abstract only, fetched for quote verification",
                        claim_ok=bool(abs_), abstract=abs_))
        print("=" * 100)
        print("bioRxiv 2026.05.06.723381 (BioDesignBench, PMC13174699)")
        print("  ABSTRACT   %d characters saved for quote checking" % len(abs_))
    except Exception as e:                                    # noqa: BLE001
        print("  BioDesignBench abstract FETCH FAILED: %s" % e)
        bad += 1

    doi_records, doi_bad = check_dois()
    out.extend(doi_records)
    bad += doi_bad

    dst = os.path.join(ROOT, "results", "citations_verified.json")
    # Write the record only when every entry was fetched (temp file, then rename), so an interrupted run
    # leaves the previous record in place.
    expected = len(CLAIMS) + 1 + len(DOI_CLAIMS)    # arXiv, the bioRxiv abstract, and the DOI records
    if len(out) < expected:
        print("\n  RECORD NOT WRITTEN: %d of %d entries were fetched. The previous "
              "results/citations_verified.json is left in place." % (len(out), expected))
        return 1
    # A fetch that returns less (for example an empty abstract) keeps the previous verified entry.
    if os.path.exists(dst):
        prev = {(e.get("arxiv") or e.get("doi")): e for e in json.load(open(dst))}
        for i, e in enumerate(out):
            old_e = prev.get(e.get("arxiv") or e.get("doi"))
            if (old_e and old_e.get("claim_ok") and old_e.get("abstract")
                    and not e.get("abstract")):
                print("  KEPT PREVIOUS RECORD for %s: the live fetch returned no abstract where the "
                      "verified record has %d characters." % (e.get("arxiv") or e.get("doi"),
                                                              len(old_e["abstract"])))
                out[i] = old_e
    tmp = dst + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, dst)
    print("\nwrote %s   (%d checked, %d problems)" % (os.path.relpath(dst, ROOT), len(out), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
