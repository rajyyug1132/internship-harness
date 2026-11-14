# Internship scan workflow

Finds internships that fit, tailors a one-page resume for the best one, checks it, and reports. Runs Mon/Wed/Fri at 07:40 IST. It never applies or sends anything.

## Target
- Internships in AI/ML, backend or full-stack, in Bengaluru or remote (India).
- Candidate: a student who has not graduated yet; set eligibility in `ats_check.py` (`KNOCKOUTS`).
- Skip anything needing final-year status, a graduate degree or a PhD.

## Who does what
| step | runs on | why |
|---|---|---|
| Orchestrate | the scheduled task's model (set it to Sonnet in task settings) | only coordinates, never reads raw pages |
| Scan the three sources | Haiku subagent, low effort | mechanical list reading, the bulk of tokens |
| Read JDs, score fit, write `terms/<id>.json` | Sonnet subagent, low effort | short judgment over at most 5 JDs |
| Ceiling check and ATS score | `ats_check.py` | free, same answer every run |
| Tailor each resume | Sonnet subagent, medium effort, one per packet | building from a fixed plan |
| Trace bullets to the ledger | Haiku subagent, medium effort | blind check by a different model from the writer |
| Fix rounds | Sonnet subagent, given only the missing terms and untraced bullets | small, targeted context |

## Steps
1. **Load context.** Read `ledger.md` (confirmed facts), `seen.txt` (roles already seen) and `applications.md`.
2. **Scan** three sources, cheapest first, all read-only. Read pages as text only.
   - **Indeed** (connector, no browser): four fixed searches (AI/ML, backend, full stack, software engineer intern) for Bengaluru and remote, internship type, India. Keep roles posted within 30 days.
   - **Astra** (built-in browser, signed in by the user): six fixed searches: AI intern, machine learning, backend, full stack, software engineer intern, SDE intern.
   - **LinkedIn** (built-in browser, read-only): two fixed searches (software engineer intern, AI/ML intern), internship filter, newest first. Use the Bengaluru location id (`geoId=105214831`) in the search URL; the plain `location=` parameter falls back to Gurugram. Skip rows already marked Applied or Saved. If a login wall appears, skip LinkedIn for this run and say so in the digest.
3. **Dedupe.** Drop anything in `seen.txt`; the same role on two sources counts once (match on company and title). If nothing is new, write a one-line digest and stop.
4. **Score.** Open at most 5 new job descriptions (Bengaluru, remote or India only). Score fit 1, 3 or 5, each backed by one quoted line from the description. Fit 1 is skipped, fit 3 is queued, fit 5 gets a packet.
5. **Ceiling check** (free). `python3 ats_check.py terms/<id>.json --ledger ledger.md --jd jd/<id>.txt` scores the ledger itself against the job's weighted terms. If that ceiling is 93.3 or lower, or the job description knocks out a 2nd-year student (completed degree, final year, Master's, PhD, an earlier graduation year), the role is dropped with the missing terms listed. No resume is built for it.
6. **Packets** for the top 3 roles that pass the ceiling check.
   - Copy the nearest `resume-*.tex`, change only the bullets and skills line, compile twice with `pdflatex`. One page.
   - Write a cover letter (120 words max) and a hiring-manager DM (300 characters max).
   - Every claim must trace to a line in `ledger.md`. No invented metrics, titles or dates.
7. **Verify and ATS check.** `python3 ats_check.py terms/<id>.json --resume <pdf> --jd jd/<id>.txt` gives the ATS score, parse damage (words garbled by any of three PDF parsers) and knockouts. Separately, a Haiku subagent that sees only the PDF text and `ledger.md` traces every bullet to a ledger line. A packet ships only if the score is **above 93.3**, parse damage is 0, nothing is knocked out and every bullet traces. If not, up to 2 fix rounds, adding only terms the ledger already supports. Still failing: KILL. Never stuff keywords, never edit the terms file after the ceiling check, never lower the bar.
8. **Record.** Append a row to `applications.md` with status `draft`. Add every scanned role to `seen.txt`.
9. **Report.** A digest of at most 8 lines: scanned, new, shipped packets with their ATS scores, queue, kills with reasons, skills to build within 48 hours.

## Limits and stops
- Up to 3 packets, 5 job-description opens and 2 fix rounds per packet per run.
- On LinkedIn: never apply, use Easy Apply, save jobs or sign in.
- Stop and ask for a sign-in if Astra shows a login wall or locks more than half the results behind Pro.
- Never submit, send, create accounts or type passwords.

## Files
| file | purpose |
|---|---|
| `ledger.md` | confirmed facts, the only source for resume claims (local, untracked; see `ledger.example.md`) |
| `applications.md` | one row per packet built (local, untracked; see `applications.example.md`) |
| `seen.txt` | roles already scanned (local, untracked) |
| `resume-*.tex` | your resume variants, from Overleaf's Jake's Resume template (local, untracked) |
| `ats_check.py` | ATS Check V.2026.8 scoring as code: ceiling, score, parse damage, knockouts |
| `tests/` | `python3 -m unittest discover -s tests` (reproduces the Amex report's 44) |
| `jd/`, `terms/` | per-role job text and weighted terms, kept local |
| `packets/` | per-company output, kept local |
