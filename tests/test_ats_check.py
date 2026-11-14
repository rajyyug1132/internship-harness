"""Run: python3 -m unittest discover -s tests  (from the harness folder)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FX = os.path.join(HERE, "fixtures")
sys.path.insert(0, ROOT)
import ats_check  # noqa: E402


def run(*args):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "ats_check.py"), *args],
                       capture_output=True, text=True)
    return p.returncode, json.loads(p.stdout) if p.stdout.strip() else None, p.stderr


class AmexReport(unittest.TestCase):
    """The 26 Sep 2026 ATS Check report scored this resume 44/100."""

    def test_score_matches_report(self):
        code, r, _ = run(f"{FX}/amex_terms.json", "--resume", f"{FX}/amex_resume.txt")
        self.assertEqual(round(r["score"]), 44)
        self.assertEqual(r["verdict"], "FIX")
        self.assertEqual(code, 1)

    def test_synonyms_score_zero(self):
        # "data-first", "iterate", "competitive programming" are partials in the report.
        _, r, _ = run(f"{FX}/amex_terms.json", "--resume", f"{FX}/amex_resume.txt")
        missing = {m["term"] for m in r["missing"]}
        self.assertTrue({"Data-driven", "Continuous improvement", "Problem solving"} <= missing)

    def test_java_not_matched_by_javascript(self):
        _, r, _ = run(f"{FX}/amex_terms.json", "--resume", f"{FX}/amex_resume.txt")
        self.assertIn("JavaScript", r["hits"])
        self.assertNotIn("Java", r["hits"])

    def test_degree_knockout(self):
        code, r, _ = run(f"{FX}/amex_terms.json", "--jd", f"{FX}/amex_jd.txt")
        self.assertEqual(code, 1)
        self.assertIn("needs a completed degree", [k["reason"] for k in r["knockouts"]])


class Gates(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def write(self, name, text):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def terms(self, *ts):
        return self.write("t.json", json.dumps({"terms": [
            {"term": t, "section": "Core", "weight": 2} for t in ts]}))

    def test_ceiling_kill_lists_gaps(self):
        t = self.terms("Python", "FastAPI", "Kubernetes")
        led = self.write("l.md", "- Python and FastAPI services")
        code, r, _ = run(t, "--ledger", led)
        self.assertEqual(r["ceiling"], 66.7)
        self.assertEqual(r["ceiling_gaps"], ["Kubernetes"])
        self.assertEqual((code, r["verdict"]), (1, "KILL"))

    def test_ceiling_pass(self):
        t = self.terms("Python", "FastAPI")
        led = self.write("l.md", "Python, FastAPI")
        code, r, _ = run(t, "--ledger", led)
        self.assertEqual((code, r["verdict"], r["ceiling"]), (0, "BUILD", 100.0))

    def test_bar_is_strict(self):
        # 14 of 15 equal-weight terms = 93.3, which must NOT pass.
        names = [f"term{i}" for i in range(15)]
        t = self.terms(*names)
        res = self.write("r.txt", " ".join(names[:14]))
        code, r, _ = run(t, "--resume", res)
        self.assertEqual(r["score"], 93.3)
        self.assertEqual((code, r["verdict"]), (1, "FIX"))

    def test_ship(self):
        t = self.terms("Python", "React")
        res = self.write("r.txt", "Python and React")
        code, r, _ = run(t, "--resume", res)
        self.assertEqual((code, r["verdict"]), (0, "SHIP"))

    def test_multiword_and_hyphen_linebreak(self):
        t = self.terms("code reviews", "full-stack")
        res = self.write("r.txt", "ran code\nreviews on full\nstack work")
        _, r, _ = run(t, "--resume", res)
        self.assertEqual(r["score"], 100.0)

    def test_parse_damage(self):
        self.assertEqual(ats_check.parse_damage({"a": "(cid:127) Built it", "b": "\x7fBuilt it ok"}), 1)
        self.assertEqual(ats_check.parse_damage({"a": "• Built it"}), 0)

    def test_eligibility_clean_for_students(self):
        jd = "Open to 2nd and 3rd year B.E. students. Python, React."
        self.assertEqual(ats_check.eligibility(jd), [])

    def test_bad_weight_rejected(self):
        t = self.write("t.json", json.dumps({"terms": [{"term": "x", "section": "Trait", "weight": 3}]}))
        code, _, err = run(t, "--resume", t)
        self.assertNotEqual(code, 0)
        self.assertIn("out of range", err)

    def test_real_base_resume_parses_clean(self):
        pdf = os.path.join(ROOT, "resume-base.pdf")
        if not os.path.exists(pdf):
            self.skipTest("no resume-base.pdf")
        self.assertEqual(ats_check.parse_damage(ats_check.pdf_text(pdf)), 0)


if __name__ == "__main__":
    unittest.main()
