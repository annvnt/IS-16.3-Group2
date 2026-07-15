# IS 16.3 — Scheduling a Flexible Flow Line with Limited Buffers and Bypass

Group 2 project for **Intelligent Scheduling** (TU Munich, SS2026). Operations Research
project based on **Chapter 16.3** of Pinedo, *Scheduling: Theory, Algorithms, and Systems*.

**Problem:** `FFc | Mj, bi < ∞ | Cmax` — a Flexible Flow Shop (stages in series, parallel
machines per stage) with machine eligibility restrictions and finite buffers between
stages. The goal is a cyclic schedule for one Minimum Part Set (MPS) that minimizes
makespan (cycle time).

**Deliverables:**
- `docs/Chapter16-3_Group2_updated.pdf` — the written report (problem statement, Graham
  classification, MIP formulation, FFLL algorithm, worked examples, and the FFLL-vs-MIP
  instance comparison of Section 4).
- `ffll_vs_mip.py` — the implementation backing report Section 4: the **FFLL** heuristic
  (LPT allocation → Dynamic Balancing → bottleneck timing) and an **exact Gurobi MIP**
  that mirrors the Section 2 formulation exactly (machine eligibility + full time-indexed
  buffer constraints), run head-to-head on the same ten small instances.

## Layout

```
ffll_vs_mip.py       FFLL heuristic + Gurobi MIP + instance generator + comparison runner
docs/                the report PDF
gantt_charts/         generated Gantt charts (one PNG per instance, FFLL vs. MIP) —
                      produced by `python ffll_vs_mip.py`
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires `gurobipy` and a Gurobi license (a free size-limited/academic license is enough
for these instance sizes).

## Run the comparison (reproduces the report's Table 6)

```bash
python ffll_vs_mip.py
```

Solves the same ten small instances used in the report (3–5 jobs, 2–3 stages, 1–2
machines per stage; S9/S10 include bypass) with both FFLL and the Gurobi MIP, prints a
comparison table (FFLL makespan, MIP-optimal `T*`, gap, solve time, buffer-feasibility
check), and (re)generates `gantt_charts/gantt_S1.png` … `gantt_S10.png` — one side-by-side
Gantt chart per instance (FFLL on top, MIP-optimal on the bottom, consistent job colours
in both). The charts already in the repo were produced this way; re-run the script to
refresh them after any change to the instances or algorithms. Matches Table 6 of the
report: FFLL matches the optimum on 5/10 instances, with an average gap of 6.8%.

To reproduce the minimal counter-example (Example B) with its own Gantt chart:

```python
from ffll_vs_mip import run_example_b
run_example_b()
```
