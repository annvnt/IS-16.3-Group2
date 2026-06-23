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

### 2026-06-18 — Add animated FFLL-vs-IG-LS race
- New `animation.py` + `flowline.py` render an animated **race**: two flow lines run the
  same jobs in real time (queue -> machine with progress bar -> buffer/WIP -> done) with a
  live data panel (clock, WIP, busy machines, done, progress bars). The IG-LS line clears
  the board while FFLL is still running — the clearest demonstration of the improvement.
  Run: `PYTHONPATH=src python -m ffll_igls.animation [--instance N] [--out STEM]`.
  Outputs `figures/race.mp4` + `figures/race.gif`.
- Default is **Instance 6** (FFLL 49 -> IG-LS 35, 29% sooner; only 4 machines / 3 stages —
  the most dramatic *and* most readable race).
- `flowline.py` is pure logic (layout + "where is each job at time t"), `animation.py` is
  the matplotlib drawing — same compute/drawing split as timeline vs. viz.
- Deps: GIF needs `matplotlib`+`pillow`; MP4 also needs system `ffmpeg`. New tests:
  `test_flowline.py` (bucket accounting, layout, start/end states) and `test_animation.py`
  (render smoke test, skipped without ffmpeg). Suite now 11 tests.

### 2026-06-18 — Add Gantt + convergence visualization
- New `viz.py` renders a 3-panel figure for one instance: FFLL schedule Gantt, IG-LS
  schedule Gantt (so the makespan shrink is visible), and the IG-LS convergence curve.
  Run: `PYTHONPATH=src python -m ffll_igls.viz [--instance N] [--out PATH]`.
  Default is **Instance 7** (its iterated phase visibly improves 56 -> 50, so the
  convergence curve is a real staircase; it also matches the report's worked trace).
- Supporting refactors (behaviour-preserving, verified byte-identical + tests green):
  - New `timeline.py` (`build_timeline`, `Operation`) extracts per-operation start/finish
    times. `simulate_makespan` now derives the makespan from it — single source of truth,
    removes the duplicated stage simulation.
  - `igls` now drives the search via a public `igls_states` generator; `igls` takes the
    last state, the convergence plot consumes the whole makespan history. No duplicated
    loop.
- New deps: `matplotlib` (viz only — core package imports without it). New tests:
  `test_timeline.py` (makespan consistency, no machine overlap, bypass handling) and
  `test_viz.py` (PNG smoke test, skipped if matplotlib missing). Suite now 7 tests.
- Figure committed at `figures/algorithm_overview.png` (regenerate any time with the
  command above; `--instance 9` is a good alternative — biggest absolute drop 97 -> 72).

### 2026-06-18 — Fix report wording to match the package layout
- Edited the report PDF's closing caption (page 10) from "a separate file: ffll_igls.py"
  to "a separate package: src/ffll_igls/", matching the refactored layout. Done in place
  with PyMuPDF (redact + re-insert, same Helvetica-Oblique 9pt gray, centered) since there
  is no editable report source — only the PDF. Code and report now agree on the wording too.

### 2026-06-18 — Refactor src into a clean package (no behaviour change)
- Split the single `src/ffll_igls.py` into a `src/ffll_igls/` package, one module per
  logical part: `models`, `allocation` (Phase 1), `sequencing` (Phase 2), `simulation`
  (cycle time + makespan), `ffll`, `igls`, `instances`, `experiments` (computation),
  `reporting` (I/O), `__main__`. Public API re-exported from `__init__.py`.
- Applied clean-code rules: parameter objects (`InstanceConfig`, `IGLSConfig`), named
  constants (`EPSILON`, default IG-LS params), guard clauses, `Schedule` NamedTuple and
  `InstanceResult` dataclass instead of bare tuples/dicts, injected RNG into `perturb`.
- **Removed dead code:** the old `phase3_simulate_cycle_time` built a full schedule
  simulation but then returned `W.max()` regardless — replaced by
  `bottleneck_cycle_time(alloc) = W.max()`. Return value unchanged.
- **Behaviour verified identical:** experiment output is byte-for-byte equal to the old
  version (timing columns aside); all 3 tests pass; `ruff` clean. Report numbers unchanged.
- **Run command changed:** `python src/ffll_igls.py` → `PYTHONPATH=src python -m ffll_igls`.
- Report wording about the implementation file fixed in a follow-up (see entry above).

### 2026-06-18 — Repo cleanup + workflow setup
- Restructured into `src/`, `tests/`, `docs/`. Moved `ffll_igls.py` → `src/`, the report
  PDF → `docs/`.
- Added `README.md`, `CLAUDE.md` (how-we-work), this `PROGRESS.md`, `requirements.txt`,
  `.gitignore`.
- Added `tests/test_ffll_igls.py` locking the report's claims (Examples A/B + 10-instance
  summary). Verified the existing code reproduces the report's table.
- No algorithm changes — pure scaffolding so the project is reproducible and Claude can
  pick it up independently across sessions.
