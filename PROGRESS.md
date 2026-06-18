# PROGRESS — running log

The brain of the project. Read this first; append to it last. Newest entry on top.
One entry per meaningful change: **what** changed, **why**, and **does the report need
updating**.

## Status

- **FFLL + IG-LS implemented** in `src/ffll_igls.py`, verified against the report.
- **Report** written: `docs/Chapter16_3_Project_Solution.pdf` (Sections 1–4 complete).
- Code reproduces the report's Section 4.3 table exactly (FFLL avg gap 33.8% → IG-LS
  15.1%, all 10 instances improved).

## Open / next

- _(nothing pending — add items here as they come up)_

## Known facts to protect (don't let these drift between code and report)

- Example A (2 stages, 4 jobs, no bypass): cycle time **T = 18** (= bottleneck, optimal).
- Example B (3 stages, 5 jobs, bypass on jobs 2 & 5): cycle time **T = 20** (optimal).
- 10-instance experiment: FFLL avg gap **33.8%**, IG-LS avg gap **15.1%**, avg improvement
  **12.9%**, **10/10** instances improved (instances 3 & 4 reach the lower bound).
- All experiments use fixed seeds → fully reproducible.

---

## Log

### 2026-06-18 — Repo cleanup + workflow setup
- Restructured into `src/`, `tests/`, `docs/`. Moved `ffll_igls.py` → `src/`, the report
  PDF → `docs/`.
- Added `README.md`, `CLAUDE.md` (how-we-work), this `PROGRESS.md`, `requirements.txt`,
  `.gitignore`.
- Added `tests/test_ffll_igls.py` locking the report's claims (Examples A/B + 10-instance
  summary). Verified the existing code reproduces the report's table.
- No algorithm changes — pure scaffolding so the project is reproducible and Claude can
  pick it up independently across sessions.
