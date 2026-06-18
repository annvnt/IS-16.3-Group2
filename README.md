# IS 16.3 — Scheduling a Flexible Flow Line with Limited Buffers and Bypass

Group 2 project for **Intelligent Scheduling** (TU Munich, SS2026). Operations Research
project based on **Chapter 16.3** of Pinedo, *Scheduling: Theory, Algorithms, and Systems*.

**Problem:** `FFs | bypass, b_i < ∞ | C_max` — a Flexible Flow Shop (stages in series,
parallel machines per stage) with job bypass and finite buffers. The goal is a cyclic
schedule for one Minimum Part Set (MPS) that minimizes cycle time (maximizes throughput).

**Deliverables:**
- `docs/Chapter16_3_Project_Solution.pdf` — the written report (problem statement, MIP,
  FFLL algorithm, IG-LS improvement, experiments).
- `src/ffll_igls/` — the implementation: **FFLL** (3-phase heuristic) + **IG-LS**
  (Iterated Greedy with Local Search) + the 10-instance experiment runner.

## Layout

```
src/ffll_igls/       implementation package (one module per logical part)
  models.py            data structures (Instance, Allocation, Schedule)
  allocation.py        Phase 1 — LPT machine allocation
  sequencing.py        Phase 2 — Dynamic Balancing
  simulation.py        cycle time + makespan evaluation (Phase 3 / objective)
  ffll.py              the FFLL heuristic
  igls.py              IG-LS (local search, perturbation)
  instances.py         random instance generator + lower bound
  experiments.py       the 10-instance experiment harness (computation)
  reporting.py         console output (I/O, kept separate from computation)
  __main__.py          entry point
tests/               regression tests that lock the report's claims
docs/                the report PDF
PROGRESS.md          running log of decisions and changes (read this first)
CLAUDE.md            how Claude / contributors work in this repo
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run the experiments (reproduces the report's table)

```bash
PYTHONPATH=src python -m ffll_igls    # from the repo root
# or:  cd src && python -m ffll_igls
```

This prints the FFLL-vs-IG-LS comparison over 10 fixed-seed random instances plus two
detailed traces. The numbers match Section 4.3 of the report (avg gap to lower bound:
FFLL 33.8% → IG-LS 15.1%, all 10 instances improved).

## Tests

```bash
pytest
```

The tests are the guardrail: they assert the worked examples from the report (Example A
cycle time = 18, Example B = 20) and that the 10-instance summary still matches. If you
change the algorithm, run these and update the report if the numbers move.
