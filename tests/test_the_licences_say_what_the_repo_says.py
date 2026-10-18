#!/usr/bin/env python3
"""Tests that the licence files, the README and the citation record agree with each other and with the paper.

The licence texts are checked for presence and completeness, not re-derived from their canonical sources.
"""
import os, re, unittest

try:
    import yaml
except ImportError:                                   # pragma: no cover
    # PyYAML is optional; only the checks that parse CITATION.cff skip without it.
    yaml = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class Licences(unittest.TestCase):

    def test_the_mit_licence_is_present_and_complete(self):
        t = read("LICENSE")
        self.assertIn("MIT License", t)
        self.assertIn("Copyright (c) 2026 Abdul Karim and Matt Keon", t)
        for clause in ("Permission is hereby granted, free of charge",
                       "The above copyright notice and this permission notice shall be included",
                       'THE SOFTWARE IS PROVIDED "AS IS"',
                       "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT"):
            self.assertIn(clause, t, "the MIT text is missing %r" % clause)

    def test_the_cc_by_legal_code_is_present_and_complete(self):
        t = read("LICENSE-DATA")
        self.assertIn("Attribution 4.0 International", t)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", t)
        # All eight sections, so a truncated copy cannot pass as the licence.
        sections = re.findall(r"^Section (\d) --", t, re.M)
        self.assertEqual([str(i) for i in range(1, 9)], sections,
                         "the legal code is not the full eight sections: %s" % sections)
        self.assertIn("Creative Commons may be contacted at creativecommons.org.", t,
                      "the legal code does not run to its end")

    def test_the_data_licence_names_what_it_covers_and_what_it_does_not(self):
        t = read("LICENSE-DATA")
        for covered in ("results/", "paper/", "spec/", "independent_check/"):
            self.assertIn(covered, t, "the data licence does not say it covers %s" % covered)
        self.assertIn("A .py file inside independent_check/ is code", t,
                      "the data licence does not carve the independent check's code out to MIT")
        self.assertIn("MIT", t, "the data licence does not point at the code licence")
        self.assertIn("not ours to license", t,
                      "the data licence does not exclude the third-party landscapes")
        self.assertIn("https://github.com/Xstendyl/wellocate", t,
                      "CC BY requires attribution and the form must give the link")

    def test_the_readme_names_both_licences_and_claims_neither_falsely(self):
        t = read("README.md")
        self.assertIn("`LICENSE`", t)
        self.assertIn("`LICENSE-DATA`", t)
        self.assertNotIn("all rights reserved", t.lower(),
                         "the README still says the code is all rights reserved")
        self.assertNotIn("not yet chosen", t.lower(),
                         "the README still says a licence has not been chosen")

    @unittest.skipIf(yaml is None, "PyYAML is not installed; CITATION.cff cannot be parsed here")
    def test_the_citation_record_validates_against_the_official_schema(self):
        """CITATION.cff validates against the pinned CFF 1.2.0 schema, kept beside this test so no network is needed."""
        try:
            import jsonschema
        except ImportError:                               # pragma: no cover
            self.skipTest("jsonschema is not installed")
        import json
        schema = json.loads(read("tests", "fixtures_cff_schema_1_2_0.json"))
        jsonschema.validate(yaml.safe_load(read("CITATION.cff")), schema)

    @unittest.skipIf(yaml is None, "PyYAML is not installed; CITATION.cff cannot be parsed here")
    def test_the_citation_record_carries_the_year_and_no_identifier_yet(self):
        d = yaml.safe_load(read("CITATION.cff"))
        pc = d["preferred-citation"]
        self.assertEqual(2026, pc["year"])
        self.assertEqual(d["title"], pc["title"], "the two titles in CITATION.cff disagree")
        self.assertEqual("unpublished", pc["type"],
                         "the paper is not posted; the type must say so")
        for field in ("doi", "identifiers"):
            self.assertNotIn(field, d, "no identifier goes in until the paper is posted")
            self.assertNotIn(field, pc, "no identifier goes in until the paper is posted")

    @unittest.skipIf(yaml is None, "PyYAML is not installed; CITATION.cff cannot be parsed here")
    def test_the_citation_record_matches_the_paper(self):
        d = yaml.safe_load(read("CITATION.cff"))
        for field in ("cff-version", "message", "title", "authors"):
            self.assertIn(field, d, "CITATION.cff is missing the required field %r" % field)
        title = re.search(r"\\title\{(.*?)\}", read("paper", "main.tex"), re.S).group(1)
        self.assertEqual(" ".join(title.replace("\\\\", " ").split()), d["title"],
                         "CITATION.cff and the paper disagree about the title")
        self.assertEqual(["Karim", "Keon"], [a["family-names"] for a in d["authors"]])
        self.assertEqual("MIT", d["license"], "CITATION.cff names a licence the repository does not use")

    def test_every_source_file_is_claimed_by_the_code_licence(self):
        """Every tracked source file sits under a path the MIT licence names."""
        import subprocess
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True).stdout.split()
        code = [f for f in tracked if f.endswith((".py", ".sh"))]
        self.assertTrue(code, "no source files found; the check is not testing anything")
        named = read("LICENSE") + read("LICENSE-DATA")
        unclaimed = [f for f in code
                     if not any(f.startswith(d) for d in
                                ("repdef/", "wellocate/", "examples/", "scripts/", "tests/", "training/",
                                 "independent_check/", ".githooks/"))]
        self.assertEqual([], unclaimed,
                         "source files sit outside every directory the MIT licence names:\n  " +
                         "\n  ".join(unclaimed))
        for d in ("wellocate/", "examples/", "independent_check/"):
            self.assertIn(d, named, "%s is not named in either licence" % d)

    def test_no_licence_file_is_empty(self):
        for name in ("LICENSE", "LICENSE-DATA", "CITATION.cff"):
            self.assertGreater(len(read(name).strip()), 200, "%s is too short to be real" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
