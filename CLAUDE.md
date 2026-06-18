# CLAUDE.md — How we work in this repo

This is a **TU Munich Operations Research coursework project** (Intelligent Scheduling,
SS2026, Group 2) on Pinedo Chapter 16.3. It is a small, self-contained project: one
Python file, a test suite, and a written report. Keep the workflow light — this is
coursework, not production software.

The parent workspace rules live in `../../../CLAUDE.md` (read for *why*); this file owns
the *how* for this project.

## What this project is

- **Goal:** implement and improve the FFLL scheduling heuristic from Pinedo 16.3, and
  document it in a report. Problem: `FFs | bypass, b_i < ∞ | C_max`.
- **Two deliverables that must agree:**
  1. `docs/Chapter16_3_Project_Solution.pdf` — the report (graded).
  2. `src/ffll_igls.py` — the implementation the report describes.
- **Entry point:** `python src/ffll_igls.py` reproduces the experiment table.

## The one rule that matters: code and report must agree

The report quotes specific numbers (Example A cycle time = 18, Example B = 20, the
10-instance table, "33.8% → 15.1%"). These come from the code. So:

- If you **change the algorithm or instances**, re-run `python src/ffll_igls.py` and
  `pytest`, then check whether any number in the report moved. If it did, the report is
  now wrong — flag it and update it (or tell Leon what changed).
- If you **change the report**, make sure the code still backs the claim.
- Never silently let the two drift. A mismatch between code and report is the worst bug
  here, because it is what gets graded.

## Workflow (lightweight)

For any change, follow this loop. Don't skip Verify or Record.

1. **Understand** — read `PROGRESS.md` (the running log) and the relevant part of the
   report/code before touching anything.
2. **Change** — make the smallest change that does the job. Match the existing style.
3. **Verify** — run `pytest` and `python src/ffll_igls.py`. Both must be green and the
   output sane. Computational checks first; reasoning/eyeballing second.
4. **Record** — append a dated entry to `PROGRESS.md`: what changed, why, and whether the
   report needs updating. This is what lets the next session (or teammate) continue
   without you.

That's it. No specs, no REQ-IDs, no multi-agent pipeline — the project is too small to
earn that overhead.

## Code style

Match what's already in `src/ffll_igls.py` — it's clean, readable, and well-commented.

- Keep functions small and single-purpose; type hints on signatures; a short docstring
  on each public function.
- This is a scientific script: `print()` for the experiment output is fine (it *is* the
  output). Don't add a logging framework.
- **Determinism:** every experiment uses a fixed seed. Keep it that way — results must be
  reproducible across runs and machines, or the report can't cite them.
- No new dependencies beyond `numpy` unless there's a real reason. If you add one, put it
  in `requirements.txt` and note it in `PROGRESS.md`.

## Tests

`tests/` locks the report's claims so changes can't silently break them:
- The two worked examples (A → 18, B → 20).
- The 10-instance summary (all improved, FFLL gap > IG-LS gap).

When you change behaviour, update the test to the new expected value **and** the report in
the same change — never loosen a test just to make it pass.

## Git

- Small repo, simple flow. Commit logical units with clear messages
  (`feat:`, `fix:`, `docs:`, `test:` prefixes are nice but not enforced).
- Commit only when Leon asks, or when wrapping up a clearly-finished piece of work.
- Don't commit `.venv/`, caches, or `__pycache__/` (see `.gitignore`).

## Tone

Terse. Lead with the answer. State what you're about to do before a multi-step change.
English throughout (code, comments, docs, commits).
