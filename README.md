# internship-harness

A recurring internship scan with resume tailoring and a deterministic ATS score gate.

- `WORKFLOW.md` explains the steps.
- `ats_check.py` scores a resume against a job's weighted terms (ceiling check, score, parse damage, eligibility knockouts). No model calls.
- Tests: `python3 -m unittest discover -s tests`

Personal files (ledger, resumes, application log) are not in this repo; see the `*.example.md` files.
