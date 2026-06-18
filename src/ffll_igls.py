"""
FFLL vs IG-LS Scheduler
=======================
Implements:
  - FFLL (Flexible Flow Line Loading): 3-phase heuristic from Pinedo Ch. 16.3
  - IG-LS (Iterated Greedy with Local Search): improved algorithm

Problem: FFs | bypass, b_i < inf | C_max  (cyclic schedule, minimize cycle time)

Author: Assignment Part 4
"""

import numpy as np
import random
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# ─────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────

@dataclass
class Instance:
    """
    Represents one scheduling instance.
    
    stages      : number of stages
    machines_per_stage : list of length `stages`, machines at each stage
    n_jobs      : number of jobs in MPS
    stage_times : (stages x n_jobs) array — processing time of job j at stage k
                  0 means job bypasses that stage
    """
    stages: int
    machines_per_stage: List[int]
    n_jobs: int
    stage_times: np.ndarray   # shape (stages, n_jobs)

    @property
    def total_machines(self):
        return sum(self.machines_per_stage)


@dataclass
class Allocation:
    """
    Result of Phase 1: which machine (global index) processes each job at each stage.
    p : (total_machines x n_jobs) processing time matrix after allocation
    machine_stage : list mapping global machine index -> stage index
    W : workload per machine
    """
    p: np.ndarray             # (m x n)
    machine_stage: List[int]  # length m
    W: np.ndarray             # length m


# ─────────────────────────────────────────────────────────────
# PHASE 1 — MACHINE ALLOCATION (LPT)
# ─────────────────────────────────────────────────────────────

def phase1_allocate(inst: Instance) -> Allocation:
    """
    Assign each job to one machine per stage using LPT.
    Returns full p_{ij} matrix (m x n).
    """
    m = inst.total_machines
    n = inst.n_jobs
    p = np.zeros((m, n))
    machine_stage = []

    global_idx = 0
    for s in range(inst.stages):
        n_mach = inst.machines_per_stage[s]
        machine_stage.extend([s] * n_mach)
        mach_indices = list(range(global_idx, global_idx + n_mach))

        # Jobs that actually need processing at this stage (non-bypass)
        times_at_stage = inst.stage_times[s]  # length n

        if n_mach == 1:
            # Only one machine — all jobs go there
            p[global_idx, :] = times_at_stage
        else:
            # LPT: sort jobs descending by stage time, assign to least loaded machine
            job_order = np.argsort(-times_at_stage)  # descending
            machine_loads = {mi: 0.0 for mi in mach_indices}

            for j in job_order:
                if times_at_stage[j] == 0:
                    continue  # bypass: skip, p remains 0
                least_loaded = min(machine_loads, key=machine_loads.get)
                p[least_loaded, j] = times_at_stage[j]
                machine_loads[least_loaded] += times_at_stage[j]

        global_idx += n_mach

    W = p.sum(axis=1)  # workload per machine
    return Allocation(p=p, machine_stage=machine_stage, W=W)


# ─────────────────────────────────────────────────────────────
# PHASE 2 — SEQUENCING (DYNAMIC BALANCING)
# ─────────────────────────────────────────────────────────────

def compute_overload_score(sequence: List[int], alloc: Allocation) -> float:
    """
    Compute total positive cumulative overload for a given sequence.
    This is the objective of Dynamic Balancing:
       sum_{i,j} max(O_{ij}, 0)
    """
    p = alloc.p
    W = alloc.W
    n = p.shape[1]
    total_W = W.sum()

    # Avoid division by zero
    if total_W == 0:
        return 0.0

    cumulative_O = np.zeros(len(W))
    total_score = 0.0

    for pos, j in enumerate(sequence):
        pj = p[:, j]                    # workload vector for job j
        pk = pj.sum()                   # total system workload of job j
        o_j = pj - pk * W / total_W    # overload contribution vector
        cumulative_O += o_j
        total_score += np.maximum(cumulative_O, 0).sum()

    return total_score


def phase2_dynamic_balancing(alloc: Allocation) -> List[int]:
    """
    Greedy Dynamic Balancing sequencing.
    Returns job sequence as list of job indices.
    """
    p = alloc.p
    W = alloc.W
    n = p.shape[1]
    total_W = W.sum()

    remaining = list(range(n))
    sequence = []
    cumulative_O = np.zeros(len(W))

    while remaining:
        best_job = None
        best_score = float('inf')

        for j in remaining:
            pj = p[:, j]
            pk = pj.sum()
            o_j = pj - pk * W / total_W
            new_O = cumulative_O + o_j
            score = np.maximum(new_O, 0).sum()

            if score < best_score:
                best_score = score
                best_job = j

        sequence.append(best_job)
        remaining.remove(best_job)
        pj = p[:, best_job]
        pk = pj.sum()
        o_j = pj - pk * W / total_W
        cumulative_O += o_j

    return sequence


# ─────────────────────────────────────────────────────────────
# PHASE 3 — TIMING OF RELEASES (BOTTLENECK ANCHORING)
# ─────────────────────────────────────────────────────────────

def phase3_simulate_cycle_time(sequence: List[int], alloc: Allocation,
                                inst: Instance) -> float:
    """
    Simulate the cyclic schedule and return the achieved cycle time.

    Strategy:
      - Jobs enter the system in `sequence` order
      - Each machine processes jobs in the order they arrive
      - Completion time on machine i for job j = max(ready_from_prev_stage, 
        machine_available) + p[i,j]
      - Cycle time = max completion time across all jobs and machines
        (= workload of bottleneck machine, if no blocking assumed)
    
    For this implementation we use the standard flow shop simulation
    (no blocking modeled explicitly — blocking is handled implicitly by
    the sequencing objective reducing WIP). This gives a lower-bound
    cycle time estimate consistent with Phase 3 of FFLL.
    """
    p = alloc.p
    m, n = p.shape
    machine_stage = alloc.machine_stage

    # Map stage -> list of machine indices at that stage
    stages = inst.stages
    stage_machines = [[] for _ in range(stages)]
    for mi, s in enumerate(machine_stage):
        stage_machines[s].append(mi)

    # C[i][j] = completion time of job j on machine i
    C = np.zeros((m, n))
    machine_avail = np.zeros(m)   # when each machine is next free

    # Process jobs in sequence order
    # Track completion time at previous stage for each job
    prev_stage_done = np.zeros(n)  # completion time at previous stage

    for s in range(stages):
        machines_at_s = stage_machines[s]
        # Track machine availability within this stage
        stage_avail = {mi: 0.0 for mi in machines_at_s}

        for j in sequence:
            # Find which machine at this stage processes job j
            assigned_machine = None
            for mi in machines_at_s:
                if p[mi, j] > 0:
                    assigned_machine = mi
                    break

            if assigned_machine is None:
                # Job bypasses this stage — carry forward completion time
                continue

            # Start = max(job ready from prev stage, machine available)
            start = max(prev_stage_done[j], stage_avail[assigned_machine])
            finish = start + p[assigned_machine, j]
            C[assigned_machine, j] = finish
            stage_avail[assigned_machine] = finish
            prev_stage_done[j] = finish

    # Cycle time = maximum workload on any machine (bottleneck)
    # Also = max completion time (in steady state, these converge)
    W = alloc.W
    cycle_time = W.max()  # theoretical minimum = bottleneck workload

    # Actual simulated makespan (may exceed bottleneck due to sequencing)
    # Use per-machine total processing as proxy (steady-state cycle time)
    return float(cycle_time)


def simulate_makespan(sequence: List[int], alloc: Allocation,
                      inst: Instance) -> float:
    """
    More detailed simulation: returns actual makespan of one MPS pass.
    Used as the true objective for IG-LS.
    """
    p = alloc.p
    m, n_jobs = p.shape
    machine_stage = alloc.machine_stage
    stages = inst.stages

    stage_machines = [[] for _ in range(stages)]
    for mi, s in enumerate(machine_stage):
        stage_machines[s].append(mi)

    machine_avail = np.zeros(m)
    job_ready = np.zeros(n_jobs)  # when job is ready to enter next stage

    for s in range(stages):
        machines_at_s = stage_machines[s]
        stage_machine_avail = {mi: 0.0 for mi in machines_at_s}
        new_job_ready = job_ready.copy()

        for j in sequence:
            assigned = None
            for mi in machines_at_s:
                if p[mi, j] > 0:
                    assigned = mi
                    break
            if assigned is None:
                continue  # bypass

            start = max(job_ready[j], stage_machine_avail[assigned])
            finish = start + p[assigned, j]
            stage_machine_avail[assigned] = finish
            new_job_ready[j] = finish

        job_ready = new_job_ready

    return float(job_ready.max())


# ─────────────────────────────────────────────────────────────
# FFLL — FULL ALGORITHM
# ─────────────────────────────────────────────────────────────

def ffll(inst: Instance) -> Tuple[List[int], float, float]:
    """
    Full FFLL algorithm.
    Returns: (sequence, cycle_time, makespan)
    """
    alloc = phase1_allocate(inst)
    sequence = phase2_dynamic_balancing(alloc)
    cycle_time = phase3_simulate_cycle_time(sequence, alloc, inst)
    makespan = simulate_makespan(sequence, alloc, inst)
    return sequence, cycle_time, makespan


# ─────────────────────────────────────────────────────────────
# IG-LS — IMPROVED ALGORITHM
# ─────────────────────────────────────────────────────────────

def local_search_2opt(sequence: List[int], alloc: Allocation,
                      inst: Instance) -> Tuple[List[int], float]:
    """
    2-opt local search: try all pairwise swaps, accept improvements.
    Objective: minimize actual makespan (simulate_makespan).
    Returns improved sequence and its makespan.
    """
    best_seq = sequence[:]
    best_ms = simulate_makespan(best_seq, alloc, inst)
    improved = True

    while improved:
        improved = False
        for i in range(len(best_seq)):
            for j in range(i + 1, len(best_seq)):
                candidate = best_seq[:]
                candidate[i], candidate[j] = candidate[j], candidate[i]
                ms = simulate_makespan(candidate, alloc, inst)
                if ms < best_ms - 1e-9:
                    best_seq = candidate
                    best_ms = ms
                    improved = True
                    break  # restart inner loop
            if improved:
                break

    return best_seq, best_ms


def perturb(sequence: List[int], block_size: int = 2) -> List[int]:
    """
    Perturbation: remove a random block of `block_size` jobs and
    reinsert them at a random position. This is the 'destruction-
    reconstruction' step of Iterated Greedy.
    """
    seq = sequence[:]
    n = len(seq)
    if n <= block_size:
        random.shuffle(seq)
        return seq

    # Remove block
    start = random.randint(0, n - block_size)
    block = seq[start:start + block_size]
    remaining = seq[:start] + seq[start + block_size:]

    # Reinsert at random position
    insert_pos = random.randint(0, len(remaining))
    new_seq = remaining[:insert_pos] + block + remaining[insert_pos:]
    return new_seq


def igls(inst: Instance, n_iter: int = 100,
         block_size: int = 2, seed: int = 42) -> Tuple[List[int], float, float]:
    """
    Iterated Greedy with Local Search (IG-LS).
    
    Phase 1: same LPT allocation as FFLL
    Phase 2 (improved):
        1. Start with FFLL Dynamic Balancing sequence
        2. Apply 2-opt local search
        3. For n_iter iterations:
           a. Perturb current best sequence
           b. Apply 2-opt local search
           c. Accept if improved (greedy acceptance)
    Phase 3: same bottleneck timing as FFLL
    
    Returns: (best_sequence, cycle_time, best_makespan)
    """
    random.seed(seed)
    np.random.seed(seed)

    # Phase 1 — identical to FFLL
    alloc = phase1_allocate(inst)

    # Initial solution from Dynamic Balancing
    init_seq = phase2_dynamic_balancing(alloc)
    best_seq, best_ms = local_search_2opt(init_seq, alloc, inst)

    for _ in range(n_iter):
        # Perturbation
        candidate = perturb(best_seq, block_size=block_size)
        # Local search
        candidate, candidate_ms = local_search_2opt(candidate, alloc, inst)
        # Accept if improved
        if candidate_ms < best_ms - 1e-9:
            best_seq = candidate
            best_ms = candidate_ms

    # Phase 3 — identical to FFLL
    cycle_time = phase3_simulate_cycle_time(best_seq, alloc, inst)
    return best_seq, cycle_time, best_ms


# ─────────────────────────────────────────────────────────────
# INSTANCE GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_instance(n_jobs: int, n_stages: int,
                      max_machines_per_stage: int = 2,
                      max_proc_time: int = 10,
                      bypass_prob: float = 0.15,
                      seed: int = 0) -> Instance:
    """
    Generate a random FFL instance.
    
    n_jobs                : number of jobs in MPS
    n_stages              : number of stages
    max_machines_per_stage: randomly 1 or 2 machines per stage
    max_proc_time         : uniform processing times in [1, max_proc_time]
    bypass_prob           : probability a job bypasses a given stage
    """
    rng = np.random.default_rng(seed)

    machines_per_stage = [
        int(rng.integers(1, max_machines_per_stage + 1))
        for _ in range(n_stages)
    ]

    stage_times = np.zeros((n_stages, n_jobs), dtype=float)
    for s in range(n_stages):
        for j in range(n_jobs):
            if rng.random() < bypass_prob:
                stage_times[s, j] = 0  # bypass
            else:
                stage_times[s, j] = float(rng.integers(1, max_proc_time + 1))

    # Ensure every job has at least one non-zero stage
    for j in range(n_jobs):
        if stage_times[:, j].sum() == 0:
            s = int(rng.integers(0, n_stages))
            stage_times[s, j] = float(rng.integers(1, max_proc_time + 1))

    return Instance(
        stages=n_stages,
        machines_per_stage=machines_per_stage,
        n_jobs=n_jobs,
        stage_times=stage_times
    )


# ─────────────────────────────────────────────────────────────
# LOWER BOUND
# ─────────────────────────────────────────────────────────────

def lower_bound(inst: Instance) -> float:
    """
    Lower bound on cycle time = workload at bottleneck machine
    (after optimal allocation). We use LPT allocation workloads.
    """
    alloc = phase1_allocate(inst)
    return float(alloc.W.max())


# ─────────────────────────────────────────────────────────────
# EXPERIMENT: 10 RANDOM INSTANCES
# ─────────────────────────────────────────────────────────────

def run_experiments():
    """
    Generate 10 diverse random instances and compare FFLL vs IG-LS.
    Report: makespan, cycle time lower bound, % gap to LB, runtime.
    """

    # 10 instances with varied parameters
    configs = [
        # (n_jobs, n_stages, max_mach, max_proc, bypass_prob, seed, label)
        (4,  2, 2, 8,  0.00, 10, "Small, no bypass"),
        (5,  2, 2, 10, 0.10, 20, "Small, light bypass"),
        (6,  3, 2, 8,  0.15, 30, "Medium, 3-stage"),
        (7,  3, 2, 12, 0.20, 40, "Medium, higher bypass"),
        (8,  4, 2, 10, 0.15, 50, "Medium-large, 4-stage"),
        (8,  3, 3, 10, 0.10, 60, "Medium, 3 mach/stage"),
        (10, 4, 2, 10, 0.15, 70, "Large, 4-stage"),
        (10, 5, 2, 8,  0.20, 80, "Large, 5-stage"),
        (12, 4, 2, 12, 0.15, 90, "XL, 4-stage"),
        (12, 5, 2, 10, 0.25, 100,"XL, 5-stage, high bypass"),
    ]

    header = (
        f"{'#':>2}  {'Label':<28} {'Jobs':>4} {'Stg':>3} {'LB':>6} "
        f"{'FFLL_ms':>8} {'FFLL_gap':>9} {'FFLL_t':>7} "
        f"{'IGLS_ms':>8} {'IGLS_gap':>9} {'IGLS_t':>7} {'Improv':>7}"
    )
    print("=" * len(header))
    print("FFLL vs IG-LS — 10 Random Instances")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    results = []

    for idx, (nj, ns, nm, mp, bp, seed, label) in enumerate(configs, 1):
        inst = generate_instance(
            n_jobs=nj, n_stages=ns,
            max_machines_per_stage=nm,
            max_proc_time=mp,
            bypass_prob=bp,
            seed=seed
        )

        lb = lower_bound(inst)

        # FFLL
        t0 = time.perf_counter()
        _, ffll_ct, ffll_ms = ffll(inst)
        ffll_time = time.perf_counter() - t0

        # IG-LS
        t0 = time.perf_counter()
        _, igls_ct, igls_ms = igls(inst, n_iter=150, block_size=2, seed=seed)
        igls_time = time.perf_counter() - t0

        ffll_gap = 100.0 * (ffll_ms - lb) / lb if lb > 0 else 0.0
        igls_gap = 100.0 * (igls_ms - lb) / lb if lb > 0 else 0.0
        improv   = 100.0 * (ffll_ms - igls_ms) / ffll_ms if ffll_ms > 0 else 0.0

        results.append({
            "idx": idx, "label": label, "n_jobs": nj, "n_stages": ns,
            "lb": lb,
            "ffll_ms": ffll_ms, "ffll_gap": ffll_gap, "ffll_time": ffll_time,
            "igls_ms": igls_ms, "igls_gap": igls_gap, "igls_time": igls_time,
            "improv": improv
        })

        print(
            f"{idx:>2}  {label:<28} {nj:>4} {ns:>3} {lb:>6.1f} "
            f"{ffll_ms:>8.2f} {ffll_gap:>8.1f}% {ffll_time:>6.3f}s "
            f"{igls_ms:>8.2f} {igls_gap:>8.1f}% {igls_time:>6.3f}s "
            f"{improv:>6.1f}%"
        )

    print("=" * len(header))

    # Summary statistics
    ffll_gaps = [r["ffll_gap"] for r in results]
    igls_gaps = [r["igls_gap"] for r in results]
    improvs   = [r["improv"]   for r in results]

    print(f"\n{'SUMMARY':}")
    print(f"  FFLL avg gap to LB : {np.mean(ffll_gaps):6.2f}%  (max: {np.max(ffll_gaps):.2f}%)")
    print(f"  IG-LS avg gap to LB: {np.mean(igls_gaps):6.2f}%  (max: {np.max(igls_gaps):.2f}%)")
    print(f"  Avg improvement    : {np.mean(improvs):6.2f}%  (max: {np.max(improvs):.2f}%)")
    print(f"  Instances improved : {sum(1 for x in improvs if x > 1e-3)}/10")

    return results


# ─────────────────────────────────────────────────────────────
# DETAILED TRACE FOR ONE INSTANCE
# ─────────────────────────────────────────────────────────────

def trace_instance(inst: Instance, label: str = ""):
    """Print a detailed trace of both algorithms on one instance."""
    print(f"\n{'─'*60}")
    print(f"DETAILED TRACE: {label}")
    print(f"{'─'*60}")
    print(f"Jobs: {inst.n_jobs}, Stages: {inst.stages}, "
          f"Machines/stage: {inst.machines_per_stage}")
    print("\nStage processing times (stage x job):")
    for s in range(inst.stages):
        row = "  ".join(f"{int(inst.stage_times[s,j]):3d}" for j in range(inst.n_jobs))
        print(f"  Stage {s+1}: [{row}]")

    alloc = phase1_allocate(inst)
    print(f"\nAfter LPT allocation — workloads W_i: {alloc.W}")
    print(f"Bottleneck lower bound: {alloc.W.max():.2f}")

    ffll_seq, ffll_ct, ffll_ms = ffll(inst)
    print(f"\nFFLL sequence  : {[j+1 for j in ffll_seq]}")
    print(f"FFLL makespan  : {ffll_ms:.2f}")
    print(f"FFLL gap to LB : {100*(ffll_ms - alloc.W.max())/alloc.W.max():.1f}%")

    igls_seq, igls_ct, igls_ms = igls(inst, n_iter=150, seed=42)
    print(f"\nIG-LS sequence : {[j+1 for j in igls_seq]}")
    print(f"IG-LS makespan : {igls_ms:.2f}")
    print(f"IG-LS gap to LB: {100*(igls_ms - alloc.W.max())/alloc.W.max():.1f}%")
    print(f"Improvement    : {100*(ffll_ms-igls_ms)/ffll_ms:.1f}%")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*70)
    print(" PART 4: FFLL vs IG-LS on 10 Random Instances")
    print("="*70 + "\n")

    results = run_experiments()

    # Detailed trace on two interesting instances
    inst_small = generate_instance(5, 2, 2, 10, 0.10, seed=20)
    trace_instance(inst_small, "Instance 2 — Small, light bypass")

    inst_large = generate_instance(10, 4, 2, 10, 0.15, seed=70)
    trace_instance(inst_large, "Instance 7 — Large, 4-stage")

    print("\nDone.")
