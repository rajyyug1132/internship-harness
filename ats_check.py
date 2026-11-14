#!/usr/bin/env python3
"""ATS Check V.2026.8 scoring as code. No model calls, same answer every run.

The model's only job is to turn a job description into terms.json once:

    {"role": "Company - Title",
     "terms": [
       {"term": "Python", "section": "Core", "weight": 3},
       {"term": "APIs", "section": "Core", "weight": 2, "forms": ["API", "REST API"]},
       ...
     ]}

  section : Must | Core | Trait | Domain
  weight  : Must/Core 2-3, Trait/Domain 1
  forms   : other spellings the JD itself uses. Synonyms the JD does not use
            are NOT allowed here: a partial match scores 0.

Usage:
  ats_check.py terms.json --ledger ledger.md                     # ceiling gate
  ats_check.py terms.json --ledger ledger.md --resume r.pdf      # full check
  ats_check.py terms.json --resume r.pdf --jd jd.txt             # + eligibility

Exit code 0 = passes (ceiling or SHIP), 1 = fails, 2 = bad input.
"""
import argparse
import json
import re
import subprocess
import sys

BAR = 93.3
MAX_WEIGHT = {"Must": 3, "Core": 3, "Trait": 1, "Domain": 1}

# JD lines that knock out a 2nd-year student graduating 2029.
KNOCKOUTS = [
    (r"\bcompleted?\s+(?:their\s+|your\s+)?(?:graduation|degree|bachelor)", "needs a completed degree"),
    (r"\b(?:recent|fresh)\s+graduates?\b", "for recent graduates"),
    (r"\bfinal[-\s]year\b", "final-year students only"),
    (r"\b(?:master'?s|m\.?\s?tech|m\.?s\.?)\s+(?:students?|candidates?|degree)\b", "Master's only"),
    (r"\bph\.?\s?d\b", "PhD"),
    (r"\b(?:20(?:2[4-7]))\s+(?:graduates?|grads?|pass(?:ed)?[-\s]?outs?|batch)\b", "graduation year before 2029"),
    (r"\bgraduating\s+in\s+20(?:2[5-8])\b", "graduation year before 2029"),
]


def norm(text):
    text = text.replace("­", "")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # re-join hyphenated line breaks
    return re.sub(r"\s+", " ", text).lower()


def pattern(form):
    words = [re.escape(w) for w in re.split(r"[\s\-/]+", form.strip().lower()) if w]
    body = r"[\s\-/]+".join(words)
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")


def count(term, text):
    forms = [term["term"]] + term.get("forms", [])
    return sum(len(pattern(f).findall(text)) for f in forms)


def weighted(terms, text):
    total = sum(t["weight"] for t in terms)
    rows, got = [], 0
    for t in terms:
        n = count(t, text)
        if n:
            got += t["weight"]
        rows.append({"term": t["term"], "section": t["section"], "weight": t["weight"], "found": n})
    return (round(100 * got / total, 1) if total else 0.0), rows


def pdf_text(path):
    """Text per parser, so parse damage shows up the way an ATS sees it."""
    out = {}
    try:
        out["pdftotext"] = subprocess.run(["pdftotext", "-layout", path, "-"],
                                          capture_output=True, text=True, check=True).stdout
    except Exception as e:  # noqa: BLE001
        out["pdftotext"] = ""
        print(f"warn: pdftotext failed: {e}", file=sys.stderr)
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            out["pdfplumber"] = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:  # noqa: BLE001
        pass
    try:
        from pypdf import PdfReader
        out["pypdf"] = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    except Exception:  # noqa: BLE001
        pass
    return out


BAD_GLYPH = re.compile(r"\(cid:\d+\)|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f�]")


def parse_damage(texts):
    """Words with stray glyphs, worst parser wins."""
    worst = 0
    for t in texts.values():
        worst = max(worst, sum(1 for w in t.split() if BAD_GLYPH.search(w)))
    return worst


def eligibility(jd):
    j = norm(jd)
    hits = []
    for rx, why in KNOCKOUTS:
        m = re.search(rx, j)
        if m and why not in [h["reason"] for h in hits]:
            s = max(0, m.start() - 60)
            hits.append({"reason": why, "quote": j[s:m.end() + 60].strip()})
    return hits


def validate(spec):
    terms = spec.get("terms")
    if not terms:
        sys.exit("terms.json has no terms")
    for t in terms:
        for k in ("term", "section", "weight"):
            if k not in t:
                sys.exit(f"term missing '{k}': {t}")
        if t["section"] not in MAX_WEIGHT:
            sys.exit(f"bad section {t['section']!r} for {t['term']}")
        if not 1 <= t["weight"] <= MAX_WEIGHT[t["section"]]:
            sys.exit(f"weight {t['weight']} out of range for {t['section']} term {t['term']}")
    return terms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms")
    ap.add_argument("--ledger")
    ap.add_argument("--resume", help="PDF, or .txt/.tex for a dry run")
    ap.add_argument("--jd", help="JD text file, for the eligibility gate")
    ap.add_argument("--bar", type=float, default=BAR)
    a = ap.parse_args(argv)

    try:
        spec = json.load(open(a.terms, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"bad terms file: {e}", file=sys.stderr)
        return 2
    terms = validate(spec)
    report = {"role": spec.get("role", ""), "bar": a.bar}
    ok = True

    if a.ledger:
        ceiling, rows = weighted(terms, norm(open(a.ledger, encoding="utf-8").read()))
        report["ceiling"] = ceiling
        report["ceiling_gaps"] = [r["term"] for r in rows if not r["found"]]
        ok &= ceiling > a.bar

    if a.jd:
        report["knockouts"] = eligibility(open(a.jd, encoding="utf-8").read())
        ok &= not report["knockouts"]

    if a.resume:
        if a.resume.lower().endswith(".pdf"):
            texts = pdf_text(a.resume)
            report["parse_damage"] = parse_damage(texts)
            body = texts.get("pdftotext") or next(iter(texts.values()), "")
        else:
            report["parse_damage"] = 0
            body = open(a.resume, encoding="utf-8").read()
        score, rows = weighted(terms, norm(body))
        report["score"] = score
        report["hits"] = [r["term"] for r in rows if r["found"]]
        report["missing"] = [{"term": r["term"], "weight": r["weight"]} for r in rows if not r["found"]]
        ok &= score > a.bar and report["parse_damage"] == 0
        report["verdict"] = "SHIP" if ok else "FIX"
    else:
        report["verdict"] = "BUILD" if ok else "KILL"

    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
