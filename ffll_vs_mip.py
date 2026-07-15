

"""
Explanation of the Code:

The given code has been created to run the FFLL heuristic and the Gurobi MIP on the same small instances 
of a flexible flow line scheduling problem. The goal is to compare the performance of the FFLL heuristic 
against the exact solutions provided by Gurobi MIP.

The given examples and Gantt charts in the report are generated using the provided code. 
The code defines the structure of the problem, implements

Berk Bozdağ (03825499)
Nguyen Tam An Vo (03812033)
Leon Ihrig (03827171)

FFLL vs Gurobi MIP -- Instance Comparison
==========================================
Implements:
  - FFLL heuristic (three-phase: LPT allocation, Dynamic Balancing, Bottleneck timing)
  - Gurobi MIP corresponding EXACTLY to the formulation in Chapter 2 of the report

Both are run on the SAME small instances (3-5 jobs, 2-3 stages) so that Gurobi
can provide guaranteed optimal solutions, giving FFLL a rigorous benchmark.

Problem: FFc | M_j, b_i < inf | C_max
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import time
import numpy as np
import gurobipy as gp
from gurobipy import GRB

DEFAULT_SEED = 42


# ─────────────────────────────────────────────────────────────
# INSTANCE REPRESENTATION
# ─────────────────────────────────────────────────────────────

@dataclass
class Instance:
    """
    stages             : number of stages
    machines_per_stage : list of length `stages`, machines at each stage
    n_jobs             : number of jobs in MPS
    stage_times        : (stages x n_jobs) array; p'_{k,j} = time of job j at stage k.
                         0 => job bypasses that stage
    eligibility        : optional list of length `stages`, each a
                         (machines_per_stage[s] x n_jobs) boolean array where
                         eligibility[s][k, j] = True if the k-th machine at stage s
                         may process job j. If None, all machines eligible for all jobs.
    buffer_capacity    : buffer size b_s between consecutive stages (int)
    """
    stages: int
    machines_per_stage: List[int]
    n_jobs: int
    stage_times: np.ndarray
    eligibility: Optional[List[np.ndarray]] = None
    buffer_capacity: int = 2

    @property
    def total_machines(self):
        return sum(self.machines_per_stage)

    def eligible_mask(self, s):
        if self.eligibility is None:
            return np.ones((self.machines_per_stage[s], self.n_jobs), dtype=bool)
        return self.eligibility[s]


# ─────────────────────────────────────────────────────────────
# FFLL HEURISTIC
# ─────────────────────────────────────────────────────────────

@dataclass
class Allocation:
    p: np.ndarray             # (m x n) processing time on assigned machine
    machine_stage: List[int]  # machine_stage[i] = stage of machine i
    W: np.ndarray             # workload per machine


def phase1_allocate(inst: Instance) -> Allocation:
    """Eligibility-restricted LPT: each job goes to least-loaded ELIGIBLE machine."""
    m = inst.total_machines
    n = inst.n_jobs
    p = np.zeros((m, n))
    machine_stage = []

    gi = 0
    for s in range(inst.stages):
        n_mach = inst.machines_per_stage[s]
        machine_stage.extend([s] * n_mach)
        mach_indices = list(range(gi, gi + n_mach))
        elig = inst.eligible_mask(s)
        times = inst.stage_times[s]

        if n_mach == 1:
            p[gi, :] = times
        else:
            job_order = np.argsort(-times)
            loads = {mi: 0.0 for mi in mach_indices}
            for j in job_order:
                if times[j] == 0:
                    continue
                eligible_local = np.where(elig[:, j])[0]
                if len(eligible_local) == 0:
                    raise ValueError(f"Job {j} has no eligible machine at stage {s}")
                eligible_global = [mach_indices[k] for k in eligible_local]
                mi = min(eligible_global, key=lambda x: loads[x])
                p[mi, j] = times[j]
                loads[mi] += times[j]

        gi += n_mach

    return Allocation(p=p, machine_stage=machine_stage, W=p.sum(axis=1))


def phase2_dynamic_balancing(alloc: Allocation) -> List[int]:
    """Greedy sequencing: minimize cumulative positive overload."""
    p = alloc.p
    m, n = p.shape
    W = alloc.W
    W_total = W.sum()
    if W_total == 0:
        return list(range(n))

    p_j = p.sum(axis=0)                                  # workload of each job
    # o[i, j] = p_ij - p_j * W_i / W_total (per-machine overload contribution
    # of job j). Correct formula uses outer product; a 3-D broadcast form
    # here was previously buggy.
    o = p - np.outer(W, p_j) / W_total

    sequence = []
    remaining = list(range(n))
    cumulative_overload = np.zeros(m)

    for pos in range(n):
        best_j = None
        best_score = float('inf')
        for j in remaining:
            new_cum = cumulative_overload + o[:, j]
            score = np.maximum(new_cum, 0).sum()
            if score < best_score:
                best_score = score
                best_j = j
        sequence.append(best_j)
        cumulative_overload = cumulative_overload + o[:, best_j]
        remaining.remove(best_j)

    return sequence


def simulate_makespan(sequence: List[int], alloc: Allocation,
                      inst: Instance) -> float:
    """Simulate the schedule under finite buffers; return makespan of one MPS."""
    p = alloc.p
    m, n = p.shape
    machine_stage = alloc.machine_stage
    stages = inst.stages
    b = inst.buffer_capacity

    stage_machines = [[] for _ in range(stages)]
    for mi, s in enumerate(machine_stage):
        stage_machines[s].append(mi)

    job_ready = np.zeros(n)     # when job j is available at NEXT stage
    completion = np.zeros((m, n))

    for s in range(stages):
        machines_at_s = stage_machines[s]
        avail = {mi: 0.0 for mi in machines_at_s}
        buffer_departures = []   # times at which jobs left this buffer (moved downstream)

        new_ready = np.zeros(n)
        for j in sequence:
            assigned = None
            for mi in machines_at_s:
                if p[mi, j] > 0:
                    assigned = mi
                    break
            if assigned is None:
                new_ready[j] = job_ready[j]
                continue

            ready = job_ready[j]
            machine_free = avail[assigned]
            start = max(ready, machine_free)
            finish = start + p[assigned, j]

            # Check if buffer downstream is full at 'finish' time
            if s < stages - 1:
                buffer_departures = [t for t in buffer_departures if t > finish]
                if len(buffer_departures) >= b:
                    # Have to wait until oldest job leaves buffer
                    wait_until = min(buffer_departures)
                    finish = max(finish, wait_until)
                buffer_departures.append(finish)

            avail[assigned] = finish
            completion[assigned, j] = finish
            new_ready[j] = finish

        job_ready = new_ready

    return float(job_ready.max())


def simulate_schedule(sequence: List[int], alloc: Allocation, inst: Instance):
    """
    Simulate the schedule under finite buffers and return
    (schedule, makespan) where schedule is a list of tuples
    (machine_index, stage, job_index, start_time, finish_time)
    for every (machine, job) actually processed (bypass entries excluded).
    """
    p = alloc.p
    m, n = p.shape
    machine_stage = alloc.machine_stage
    stages = inst.stages
    b = inst.buffer_capacity

    stage_machines = [[] for _ in range(stages)]
    for mi, s in enumerate(machine_stage):
        stage_machines[s].append(mi)

    job_ready = np.zeros(n)
    schedule = []

    for s in range(stages):
        machines_at_s = stage_machines[s]
        avail = {mi: 0.0 for mi in machines_at_s}
        buffer_departures = []

        new_ready = np.zeros(n)
        for j in sequence:
            assigned = None
            for mi in machines_at_s:
                if p[mi, j] > 0:
                    assigned = mi
                    break
            if assigned is None:
                new_ready[j] = job_ready[j]
                continue

            ready = job_ready[j]
            machine_free = avail[assigned]
            start = max(ready, machine_free)
            finish = start + p[assigned, j]

            if s < stages - 1:
                buffer_departures = [t for t in buffer_departures if t > finish]
                if len(buffer_departures) >= b:
                    wait_until = min(buffer_departures)
                    finish = max(finish, wait_until)
                buffer_departures.append(finish)

            avail[assigned] = finish
            new_ready[j] = finish
            schedule.append((assigned, s, j, float(start), float(finish)))

        job_ready = new_ready

    return schedule, float(job_ready.max())


def phase3_lower_bound(alloc: Allocation) -> float:
    """Cycle-time lower bound = max machine workload after LPT."""
    return float(alloc.W.max())


def ffll(inst: Instance) -> Tuple[List[int], float, float]:
    """Return (sequence, lower_bound, makespan)."""
    alloc = phase1_allocate(inst)
    seq = phase2_dynamic_balancing(alloc)
    lb = phase3_lower_bound(alloc)
    ms = simulate_makespan(seq, alloc, inst)
    return seq, lb, ms


# ─────────────────────────────────────────────────────────────
# GUROBI MIP  (mirrors the formulation in Chapter 2 of the report)
# ─────────────────────────────────────────────────────────────

def solve_mip(inst: Instance, time_limit: float = 300.0,
              verbose: bool = False):
    """
    Build and solve the MIP for this instance.

    Returns dict with keys:
      'obj'           : optimal or best-known makespan (may be a lower bound
                        if buffers are violated post-hoc)
      'status'        : 'optimal', 'time_limit', 'infeasible', ...
      'solve_time'    : wall-clock seconds
      'sequence'      : jobs ordered by stage-1 completion time (proxy)
      'schedule'      : list of (machine_index, stage, job_index, start, finish)
                        for every (i,j) with x[i,j]=1 AND p[i,j] > 0
      'workloads'     : list of W_i values, one per machine
      'buffer_ok'     : True if every b_s buffer capacity is respected in the
                        MIP-derived schedule (post-hoc check); False if not,
                        in which case 'obj' is a valid LOWER BOUND on the
                        true optimal makespan under buffer constraints.
      'max_buf_use'   : peak observed buffer occupancy between each pair of
                        consecutive stages (list of length S-1)
    """
    n = int(inst.n_jobs)
    S = int(inst.stages)
    m = int(inst.total_machines)

    # Machine -> stage map, and stage -> [machines] map
    machine_stage = []
    stage_machines = [[] for _ in range(S)]
    gi = 0
    for s in range(S):
        for _ in range(inst.machines_per_stage[s]):
            machine_stage.append(s)
            stage_machines[s].append(gi)
            gi += 1

    # Processing times p_{ij} and eligibility E_{ij}.
    # Per the paper's convention: if job j bypasses stage s (stage_times[s,j]=0),
    # then E_{i,j} = 1 for ALL i in M_s (any machine can host the "ghost" visit)
    # and p_{i,j} = 0. If job j does NOT bypass and is eligible, E=1 and p>0.
    # If job j does not bypass but is INELIGIBLE for machine i, E=0.
    p = np.zeros((m, n))
    E = np.zeros((m, n), dtype=int)
    for i in range(m):
        s = machine_stage[i]
        local_i = i - stage_machines[s][0]
        elig = inst.eligible_mask(s)
        for j in range(n):
            if inst.stage_times[s, j] == 0:
                # Bypass: p=0, E=1 for all machines at this stage
                E[i, j] = 1
            elif elig[local_i, j]:
                p[i, j] = inst.stage_times[s, j]
                E[i, j] = 1
            # else: E=0, p=0 (job cannot use this machine)

    # Planning horizon and big-M
    H = int(inst.stage_times.sum() * n)
    L = float(H + 100)

    model = gp.Model('flexible_flow_line')
    if not verbose:
        model.setParam('OutputFlag', 0)
    model.setParam('TimeLimit', time_limit)

    # ── Decision variables ──
    x = model.addVars(m, n, vtype=GRB.BINARY, name='x')
    # y[i,j,jp] defined only for j < jp (unordered pair). y=1 means job j
    # precedes job jp on machine i; y=0 means jp precedes j.
    y = {}
    for i in range(m):
        for j in range(n):
            for jp in range(j + 1, n):
                y[i, j, jp] = model.addVar(vtype=GRB.BINARY, name=f'y_{i}_{j}_{jp}')
    C = model.addVars(m, n, lb=0.0, name='C')
    W = model.addVars(m, lb=0.0, name='W')
    T = model.addVar(lb=0.0, name='T')

    model.setObjective(T, GRB.MINIMIZE)

    # ── (C1a) sum over eligible machines at each stage = 1  ──
    # Per convention: if the job bypasses, M_s(j) = M_s and we still enforce
    # sum = 1 (the "ghost" assignment carries p_ij = 0). Do NOT filter out
    # bypass jobs; the constraint must be imposed unconditionally.
    for j in range(n):
        for s in range(S):
            eligible_at_s = [i for i in stage_machines[s] if E[i, j] == 1]
            # eligible_at_s is always non-empty by construction: if the job
            # doesn't bypass, at least one machine must be eligible (otherwise
            # the instance is infeasible), and if it does bypass, ALL machines
            # are eligible.
            model.addConstr(gp.quicksum(x[i, j] for i in eligible_at_s) == 1,
                            name=f'c1a_j{j}_s{s}')

    # ── (C1b) x_ij <= E_ij (eligibility bound) ──
    for i in range(m):
        for j in range(n):
            if E[i, j] == 0:
                model.addConstr(x[i, j] == 0, name=f'c1b_i{i}_j{j}')

    # ── (C2a/C2b) disjunctive with SINGLE y per unordered pair ──
    # For j < jp on the same machine i:
    #   y[i,j,jp] = 1  =>  j precedes jp: C_{i,jp} >= C_{i,j} + p_{i,jp}
    #   y[i,j,jp] = 0  =>  jp precedes j: C_{i,j}  >= C_{i,jp} + p_{i,j}
    # Both only enforced when BOTH x_{i,j} = x_{i,jp} = 1.
    for i in range(m):
        for j in range(n):
            for jp in range(j + 1, n):
                # C2a: if y=1 (j before jp), jp's finish >= j's finish + jp's proc
                model.addConstr(
                    C[i, jp] >= C[i, j] + p[i, jp] * x[i, jp]
                    - L * (1 - y[i, j, jp]) - L * (2 - x[i, j] - x[i, jp]),
                    name=f'c2a_i{i}_j{j}_jp{jp}'
                )
                # C2b: if y=0 (jp before j), j's finish >= jp's finish + j's proc
                model.addConstr(
                    C[i, j] >= C[i, jp] + p[i, j] * x[i, j]
                    - L * y[i, j, jp] - L * (2 - x[i, j] - x[i, jp]),
                    name=f'c2b_i{i}_j{j}_jp{jp}'
                )

    # ── (C3) series precedence ──
    for j in range(n):
        for s in range(1, S):
            for i in stage_machines[s]:
                for i_prev in stage_machines[s - 1]:
                    model.addConstr(
                        C[i, j] >= C[i_prev, j] + p[i, j] * x[i, j]
                        - L * (2 - x[i, j] - x[i_prev, j]),
                        name=f'c3_j{j}_s{s}_i{i}_ip{i_prev}'
                    )

    # ── (C3b) job's completion on its machine >= its own proc time ──
    for i in range(m):
        for j in range(n):
            model.addConstr(C[i, j] >= p[i, j] * x[i, j],
                            name=f'c3b_i{i}_j{j}')


                            

    # ── (C5a) W_i = sum_j p_ij * x_ij  (definition of workload) ──
    for i in range(m):
        model.addConstr(W[i] == gp.quicksum(p[i, j] * x[i, j] for j in range(n)),
                        name=f'c6a_i{i}')

    # ── (C5b) T >= W_i  (cycle time bounds workload) ──
    for i in range(m):
        model.addConstr(T >= W[i], name=f'c6b_i{i}')

    # ── (C4) Buffer capacity, fully implemented per the paper's formulation ──
    # We use two auxiliary binaries per (job, stage-boundary, time):
    #   a_{j,s,t} = 1 iff job j has departed its stage-s machine by time t
    #   b_{j,s,t} = 1 iff job j has not yet started its stage-(s+1) machine by time t
    # z_{j,s,t} = 1 iff job j is physically in the buffer between stages s
    # and s+1 at time t (i.e., a AND b AND assigned to both machines).
    #
    # Time is discretized as t = 0, 1, ..., H_buf where H_buf is a tight
    # upper bound on any C_ij value (total processing time across all jobs).
    H_buf = int(sum(p[i, j] for i in range(m) for j in range(n)))
    T_grid = list(range(H_buf + 1))

    a = {}
    b = {}
    z = {}
    for j in range(n):
        for s in range(S - 1):
            for t in T_grid:
                a[j, s, t] = model.addVar(vtype=GRB.BINARY,
                                          name=f'a_j{j}_s{s}_t{t}')
                b[j, s, t] = model.addVar(vtype=GRB.BINARY,
                                          name=f'b_j{j}_s{s}_t{t}')
                z[j, s, t] = model.addVar(vtype=GRB.BINARY,
                                          name=f'z_j{j}_s{s}_t{t}')

    # For each job j, its stage-s completion is the C_ij of whichever machine i
    # in stage s it is assigned to. Since exactly one x_ij = 1 in each stage,
    # we can define a stage-level completion time via
    #     Cstg_{j,s} = sum_{i in stage s} C_ij * x_ij
    # but that would be a product of a continuous and a binary. Instead we
    # express the constraints in terms of individual C_ij for each machine i
    # in stage s and stage s+1, adding the standard big-L relaxation so the
    # constraint only fires when the relevant x_ij = 1.

    for j in range(n):
        for s in range(S - 1):
            up_machines = stage_machines[s]        # machines at stage s (upstream)
            dn_machines = stage_machines[s + 1]    # machines at stage s+1 (downstream)
            for t in T_grid:
                # (C4a) t - C_{i',j} <= L * a_{j,s,t} + L*(1 - x_{i',j})
                # For each candidate upstream machine i', if x_{i',j}=1 and job
                # has departed (t >= C_{i',j}), a must be 1.
                for i_prev in up_machines:
                    model.addConstr(
                        t - C[i_prev, j] <= L * a[j, s, t]
                        + L * (1 - x[i_prev, j]),
                        name=f'c4a_j{j}_s{s}_t{t}_ip{i_prev}'
                    )
                # (C4b) C_{i',j} - t <= L*(1 - a_{j,s,t}) + L*(1 - x_{i',j})
                # If x_{i',j}=1 and job has NOT departed (t < C_{i',j}), a must be 0.
                for i_prev in up_machines:
                    model.addConstr(
                        C[i_prev, j] - t <= L * (1 - a[j, s, t])
                        + L * (1 - x[i_prev, j]),
                        name=f'c4b_j{j}_s{s}_t{t}_ip{i_prev}'
                    )
                # (C4c) C_{i,j} - (t+1) <= L * b_{j,s,t} + L*(1 - x_{i,j})
                # For each candidate downstream machine i, if x_{i,j}=1 and job
                # has NOT yet started (C_{i,j} > t, i.e. C_{i,j} >= t+1), b must be 1.
                for i_dn in dn_machines:
                    model.addConstr(
                        C[i_dn, j] - (t + 1) <= L * b[j, s, t]
                        + L * (1 - x[i_dn, j]),
                        name=f'c4c_j{j}_s{s}_t{t}_i{i_dn}'
                    )
                # (C4d) (t+1) - C_{i,j} <= L*(1 - b_{j,s,t}) + L*(1 - x_{i,j})
                # If x_{i,j}=1 and job has already started (C_{i,j} <= t), b must be 0.
                for i_dn in dn_machines:
                    model.addConstr(
                        (t + 1) - C[i_dn, j] <= L * (1 - b[j, s, t])
                        + L * (1 - x[i_dn, j]),
                        name=f'c4d_j{j}_s{s}_t{t}_i{i_dn}'
                    )
                # (C4e) z_{j,s,t} >= a_{j,s,t} + b_{j,s,t} - 1
                # Force z=1 when both a and b are 1 (job is in the buffer).
                # (No upper bounds z<=a, z<=b needed because z appears only
                # in C4g's cap constraint with no reward for spurious z=1.)
                model.addConstr(
                    z[j, s, t] >= a[j, s, t] + b[j, s, t] - 1,
                    name=f'c4e_j{j}_s{s}_t{t}'
                )

    # (C4g) buffer capacity cap
    for s in range(S - 1):
        for t in T_grid:
            model.addConstr(
                gp.quicksum(z[j, s, t] for j in range(n))
                <= inst.buffer_capacity,
                name=f'c4g_s{s}_t{t}'
            )

    start_time = time.time()
    try:
        model.optimize()
    except gp.GurobiError as e:
        solve_time = time.time() - start_time
        err_msg = str(e).lower()
        if 'license' in err_msg or 'size-limited' in err_msg:
            status_str = 'license_size_limit'
        else:
            status_str = f'error: {e}'
        return {
            'obj': None,
            'status': status_str,
            'solve_time': solve_time,
            'sequence': None,
            'schedule': None,
            'workloads': None,
            'buffer_ok': None,
            'max_buf_use': None,
            'stage_machines': stage_machines,
        }
    solve_time = time.time() - start_time

    status_str = {GRB.OPTIMAL: 'optimal', GRB.TIME_LIMIT: 'time_limit',
                  GRB.INFEASIBLE: 'infeasible',
                  GRB.INF_OR_UNBD: 'inf_or_unbd'}.get(model.status,
                                                     f'status_{model.status}')

    if model.status in (GRB.OPTIMAL, GRB.TIME_LIMIT) and model.SolCount > 0:
        obj_val = model.objVal
        if abs(obj_val - round(obj_val)) < 1e-4:
            obj_val = float(round(obj_val))

        # Extract schedule: (machine, stage, job, start, finish) for every
        # (i,j) with x=1 AND p>0 (i.e. actual processing, not a bypass ghost).
        schedule = []
        for i in range(m):
            for j in range(n):
                if x[i, j].X > 0.5 and p[i, j] > 0:
                    finish = C[i, j].X
                    start = finish - p[i, j]
                    # Snap near-integer values (Gurobi tolerance)
                    if abs(start - round(start)) < 1e-4:
                        start = float(round(start))
                    if abs(finish - round(finish)) < 1e-4:
                        finish = float(round(finish))
                    schedule.append((i, machine_stage[i], j, start, finish))

        workloads = [W[i].X for i in range(m)]
        # Snap near-integer workload values
        workloads = [float(round(w)) if abs(w - round(w)) < 1e-4 else w
                     for w in workloads]

        # Derive a sequence proxy from stage-0 completion times
        stage0_completions = []
        for j in range(n):
            c_val = 0
            for i in stage_machines[0]:
                if x[i, j].X > 0.5:
                    c_val = C[i, j].X
                    break
            stage0_completions.append((c_val, j))
        stage0_completions.sort()
        sequence = [j for _, j in stage0_completions]

        # Post-hoc buffer feasibility check.
        buffer_ok, max_buf_use = check_buffer_feasibility(
            schedule, inst.stages, inst.buffer_capacity, machine_stage
        )

        return {
            'obj': obj_val,
            'status': status_str,
            'solve_time': solve_time,
            'sequence': sequence,
            'schedule': schedule,
            'workloads': workloads,
            'buffer_ok': buffer_ok,
            'max_buf_use': max_buf_use,
            'stage_machines': stage_machines,
        }
    else:
        return {
            'obj': None,
            'status': status_str,
            'solve_time': solve_time,
            'sequence': None,
            'schedule': None,
            'workloads': None,
            'buffer_ok': None,
            'max_buf_use': None,
            'stage_machines': stage_machines,
        }


def check_buffer_feasibility(schedule, n_stages, buffer_capacity, machine_stage):
    """
    Given the extracted schedule, count peak buffer occupancy between each
    pair of consecutive stages and check against buffer_capacity.

    A job is "in the buffer between stage s and s+1" during the interval
    (finish_time_at_stage_s, start_time_at_stage_s+1). We compute peak
    occupancy by sweeping events.

    Returns (ok: bool, max_use_per_buffer: list of length n_stages-1).
    """
    if n_stages < 2:
        return True, []

    # For each job, find its finish time at stage s and start time at stage s+1
    # for every consecutive stage pair, IF the job is present at both stages
    # (i.e. it doesn't bypass either).
    max_use = []
    for s in range(n_stages - 1):
        # Collect (finish_at_s, start_at_s+1) intervals per job
        finish_s = {}
        start_sp1 = {}
        for (mi, stg, j, start, finish) in schedule:
            if stg == s:
                finish_s[j] = finish
            elif stg == s + 1:
                start_sp1[j] = start

        # A job occupies the buffer iff it appears at both s and s+1
        # (jobs that bypass either endpoint don't occupy this buffer)
        intervals = []
        for j in finish_s:
            if j in start_sp1 and start_sp1[j] > finish_s[j] + 1e-6:
                intervals.append((finish_s[j], start_sp1[j]))

        # Sweep to find peak overlap count
        events = []
        for f, st in intervals:
            events.append((f, +1))
            events.append((st, -1))
        events.sort(key=lambda e: (e[0], -e[1]))  # ties: +1 (enter) before -1 (leave)
        current = 0
        peak = 0
        for _, delta in events:
            current += delta
            peak = max(peak, current)
        max_use.append(peak)

    ok = all(u <= buffer_capacity for u in max_use)
    return ok, max_use


# ─────────────────────────────────────────────────────────────
# GANTT PLOTTING
# ─────────────────────────────────────────────────────────────

def plot_gantt(schedule, inst, title, ax=None, makespan=None,
               stage_machines=None, color_map=None):
    """
    Draw a Gantt chart of `schedule` on `ax` (creates one if None).

    schedule       : list of (machine_index, stage, job_index, start, finish)
    inst           : Instance (used for stage/machine grouping labels)
    title          : chart title
    makespan       : if given, draw a dashed vertical line + annotation
    stage_machines : per-stage list of global machine indices (needed if the
                     schedule's machine indexing doesn't match FFLL's flat
                     ordering); if None, derive from inst.
    color_map      : dict mapping job_index -> color, for consistent colors
                     across FFLL and MIP charts; if None, one is built.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, max(3, 0.5 * inst.total_machines + 1.5)))

    if stage_machines is None:
        stage_machines = [[] for _ in range(inst.stages)]
        gi = 0
        for s in range(inst.stages):
            for _ in range(inst.machines_per_stage[s]):
                stage_machines[s].append(gi)
                gi += 1

    # y-axis: list machines in stage order, labeled "S{s}-M{local}"
    machine_labels = []
    machine_to_y = {}
    y = 0
    for s in range(inst.stages):
        for local, mi in enumerate(stage_machines[s]):
            machine_to_y[mi] = y
            machine_labels.append(f'S{s}-M{local}')
            y += 1

    if color_map is None:
        cmap = plt.cm.tab20
        color_map = {j: cmap(j % 20) for j in range(inst.n_jobs)}

    # Draw bars
    for (mi, stg, j, start, finish) in schedule:
        y_pos = machine_to_y[mi]
        width = finish - start
        if width <= 0:
            continue
        ax.barh(y_pos, width, left=start, height=0.7,
                color=color_map[j], edgecolor='black', linewidth=0.6)
        # Label with job index
        ax.text(start + width / 2, y_pos, f'J{j+1}',
                ha='center', va='center', fontsize=9,
                color='white' if _color_is_dark(color_map[j]) else 'black',
                fontweight='bold')

    # Makespan line
    if makespan is not None:
        ax.axvline(x=makespan, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
        ax.text(makespan, len(machine_labels) - 0.3, f' C_max = {makespan:g}',
                color='red', fontsize=10, fontweight='bold', va='top')

    ax.set_yticks(range(len(machine_labels)))
    ax.set_yticklabels(machine_labels, fontsize=9)
    ax.set_ylim(-0.5, len(machine_labels) - 0.5)
    ax.invert_yaxis()
    ax.set_xlabel('Time')
    ax.set_title(title, fontsize=11)
    ax.grid(axis='x', linestyle=':', alpha=0.4)

    return ax, color_map


def _color_is_dark(rgba):
    """Rough luminance test to pick readable text color."""
    r, g, b = rgba[:3]
    return (0.299 * r + 0.587 * g + 0.114 * b) < 0.55


def plot_comparison(inst, ffll_schedule, ffll_ms, mip_schedule, mip_obj,
                    mip_status, mip_buffer_ok, label, out_path,
                    stage_machines_mip=None):
    """
    Produce a single figure with two stacked Gantt subplots (FFLL on top,
    MIP on bottom) sharing the x-axis for easy visual diffing. Save to
    `out_path`.
    """
    import matplotlib.pyplot as plt

    # Build a shared color map so both charts use the same color per job
    cmap = plt.cm.tab20
    color_map = {j: cmap(j % 20) for j in range(inst.n_jobs)}

    if mip_schedule is not None:
        fig, (ax_top, ax_bot) = plt.subplots(
            2, 1, figsize=(11, max(6, 0.5 * inst.total_machines * 2 + 3)),
            sharex=True
        )
        plot_gantt(ffll_schedule, inst,
                   f'{label} — FFLL, C_max = {ffll_ms:g}',
                   ax=ax_top, makespan=ffll_ms, color_map=color_map)
        mip_label = f'{label} — MIP, C_max = {mip_obj:g} [{mip_status}'
        if not mip_buffer_ok:
            mip_label += ', buffer VIOLATED — LB only'
        mip_label += ']'
        plot_gantt(mip_schedule, inst, mip_label,
                   ax=ax_bot, makespan=mip_obj, color_map=color_map,
                   stage_machines=stage_machines_mip)
        plt.tight_layout()
    else:
        fig, ax = plt.subplots(figsize=(10, max(3, 0.5 * inst.total_machines + 1.5)))
        plot_gantt(ffll_schedule, inst,
                   f'{label} — FFLL, C_max = {ffll_ms:g}  '
                   f'(MIP: no feasible solution, status={mip_status})',
                   ax=ax, makespan=ffll_ms, color_map=color_map)
        plt.tight_layout()

    fig.savefig(out_path, dpi=110, bbox_inches='tight')
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# INSTANCE GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_small_instance(n_jobs, n_stages, max_mach_per_stage, max_proc,
                            bypass_prob=0.0, seed=DEFAULT_SEED) -> Instance:
    rng = np.random.default_rng(seed)
    machines_per_stage = [rng.integers(1, max_mach_per_stage + 1)
                          for _ in range(n_stages)]
    stage_times = np.zeros((n_stages, n_jobs), dtype=float)
    for s in range(n_stages):
        for j in range(n_jobs):
            if rng.random() < bypass_prob:
                stage_times[s, j] = 0
            else:
                stage_times[s, j] = rng.integers(1, max_proc + 1)
    return Instance(
        stages=n_stages,
        machines_per_stage=machines_per_stage,
        n_jobs=n_jobs,
        stage_times=stage_times,
    )


# ─────────────────────────────────────────────────────────────
# COMPARISON RUNNER
# ─────────────────────────────────────────────────────────────

def run_comparison(gantt_dir='gantt_charts'):
    """
    Solve a suite of small instances with both FFLL and the Gurobi MIP.
    Print a comparison table AND save side-by-side Gantt charts for each
    instance to `gantt_dir`.
    """
    import os
    os.makedirs(gantt_dir, exist_ok=True)

    configs = [
        (3, 2, 2, 6, 0.0, 1,  'S1: 3j-2s'),
        (3, 2, 2, 8, 0.0, 2,  'S2: 3j-2s'),
        (4, 2, 2, 6, 0.0, 3,  'S3: 4j-2s'),
        (4, 2, 2, 8, 0.0, 4,  'S4: 4j-2s'),
        (4, 3, 2, 6, 0.0, 5,  'S5: 4j-3s'),
        (5, 2, 2, 6, 0.0, 6,  'S6: 5j-2s'),
        (5, 2, 2, 8, 0.0, 7,  'S7: 5j-2s'),
        (5, 3, 2, 6, 0.0, 8,  'S8: 5j-3s'),
        (4, 2, 2, 8, 0.2, 9,  'S9: 4j-2s+bp'),
        (5, 3, 2, 8, 0.15, 10, 'S10: 5j-3s+bp'),
    ]

    print('\n' + '=' * 108)
    print(f' {"#":>3}  {"Instance":<15}  {"FFLL":>6}  {"MIP*":>6}  '
          f'{"Gap%":>7}  {"MIP time":>10}  {"Status":<12}  {"Buffer":<20}')
    print('=' * 108)

    results = []
    for idx, (nj, ns, mm, mp, bp, seed, label) in enumerate(configs, 1):
        inst = generate_small_instance(nj, ns, mm, mp, bp, seed)

        # FFLL with full schedule extraction
        alloc = phase1_allocate(inst)
        seq = phase2_dynamic_balancing(alloc)
        lb = phase3_lower_bound(alloc)
        ffll_schedule, ffll_ms = simulate_schedule(seq, alloc, inst)

        # MIP
        mip = solve_mip(inst, time_limit=120)
        opt_val = mip['obj']
        status = mip['status']
        tsolve = mip['solve_time']
        buffer_ok = mip['buffer_ok']
        max_buf = mip['max_buf_use']

        # Interpret buffer status honestly
        if opt_val is None:
            buf_str = 'n/a'
            opt_str = '  --  '
            gap_str = '  --  '
            gap = None
        else:
            if buffer_ok is None or buffer_ok:
                if max_buf:
                    buf_str = f'peak={max(max_buf) if max_buf else 0}<=' \
                              f'{inst.buffer_capacity} ok'
                else:
                    buf_str = 'ok (no interstage)'
                # Legitimate optimum, safe to compute gap
                gap = 100 * (ffll_ms - opt_val) / opt_val if opt_val > 0 else 0.0
                opt_str = f'{opt_val:6.2f}'
                gap_str = f'{gap:5.1f}%'
            else:
                buf_str = f'peak={max(max_buf)}>{inst.buffer_capacity} LB only'
                # MIP obj is only a lower bound; DO NOT compute "gap" as if
                # it were true optimality
                opt_str = f'{opt_val:6.2f}*'
                gap_str = '  LB   '
                gap = None

        print(f' {idx:>3}  {label:<15}  {ffll_ms:6.2f}  {opt_str}  '
              f'{gap_str:>7}  {tsolve:9.2f}s  {status:<12}  {buf_str:<20}')

        # Gantt chart
        gantt_path = os.path.join(gantt_dir, f'gantt_{label.split(":")[0]}.png')
        plot_comparison(
            inst, ffll_schedule, ffll_ms,
            mip['schedule'], opt_val, status, buffer_ok,
            label, gantt_path,
            stage_machines_mip=mip['stage_machines']
        )

        results.append({
            'idx': idx, 'label': label,
            'n_jobs': nj, 'n_stages': ns,
            'ffll_ms': ffll_ms, 'mip_obj': opt_val, 'gap': gap,
            'solve_time': tsolve, 'status': status,
            'buffer_ok': buffer_ok, 'max_buf_use': max_buf,
        })

    print('=' * 108)

    # Summary (only over instances that were truly solved to optimality)
    truly_optimal = [r for r in results
                     if r['status'] == 'optimal' and r['buffer_ok'] and r['gap'] is not None]
    if truly_optimal:
        avg_gap = np.mean([r['gap'] for r in truly_optimal])
        matches = sum(1 for r in truly_optimal if abs(r['gap']) < 1e-6)
        print(f'\nOf {len(truly_optimal)} instances solved to '
              f'true optimality (MIP optimal AND buffer respected):')
        print(f'  FFLL matches optimum on {matches}/{len(truly_optimal)}')
        print(f'  FFLL average gap: {avg_gap:.2f}%')

    # Report any buffer-violating instances explicitly
    buf_violations = [r for r in results if r['buffer_ok'] is False]
    if buf_violations:
        print(f'\nBuffer capacity ({inst.buffer_capacity}) was VIOLATED in the '
              f'MIP-optimal schedule of {len(buf_violations)} instance(s):')
        for r in buf_violations:
            print(f'  {r["label"]}: peak buffer use = {max(r["max_buf_use"])} '
                  f'(MIP obj {r["mip_obj"]} is a LOWER BOUND, not optimum)')

    print(f'\nGantt charts saved to: {gantt_dir}/')
    return results


if __name__ == '__main__':
    run_comparison()






# ─────────────────────────────────────────────────────────────
# EXAMPLE B — MINIMAL COUNTER-EXAMPLE (FFLL suboptimal)
# ─────────────────────────────────────────────────────────────

def example_b_instance() -> Instance:
    """3 jobs, 2 stages, 1 machine per stage. p' = [[1,2,1],[1,1,2]]."""
    return Instance(
        stages=2,
        machines_per_stage=[1, 1],
        n_jobs=3,
        stage_times=np.array([[1., 2., 1.],
                              [1., 1., 2.]]),
        buffer_capacity=2,
    )


def run_example_b(gantt_dir='gantt_charts'):
    import os
    os.makedirs(gantt_dir, exist_ok=True)

    inst = example_b_instance()
    label = 'ExB: 3j-2s'

    alloc = phase1_allocate(inst)
    seq = phase2_dynamic_balancing(alloc)
    lb = phase3_lower_bound(alloc)
    ffll_schedule, ffll_ms = simulate_schedule(seq, alloc, inst)

    mip = solve_mip(inst, time_limit=120)
    opt_val, status = mip['obj'], mip['status']
    buffer_ok, max_buf = mip['buffer_ok'], mip['max_buf_use']

    gap = (100 * (ffll_ms - opt_val) / opt_val
           if opt_val and buffer_ok is not False else None)

    print('\n' + '=' * 60)
    print(' EXAMPLE B — Minimal Counter-Example')
    print('=' * 60)
    print(f'  Workloads W      : {alloc.W.tolist()}')
    print(f'  Bottleneck LB    : {lb:g}')
    print(f'  FFLL sequence    : {" -> ".join(f"J{j+1}" for j in seq)}')
    print(f'  FFLL C_max       : {ffll_ms:g}')
    print(f'  MIP  C_max       : {opt_val:g}  [{status}]')
    if mip['sequence'] is not None:
        print(f'  MIP  sequence    : '
              f'{" -> ".join(f"J{j+1}" for j in mip["sequence"])}')
    print(f'  Buffer peak use  : {max_buf} (cap {inst.buffer_capacity})')
    if gap is not None:
        print(f'  FFLL gap         : {gap:.1f}%')
    print('=' * 60)

    path = os.path.join(gantt_dir, 'gantt_ExB.png')
    plot_comparison(inst, ffll_schedule, ffll_ms,
                    mip['schedule'], opt_val, status, buffer_ok,
                    label, path,
                    stage_machines_mip=mip['stage_machines'])
    print(f'Gantt chart saved to: {path}')

    return {'label': label, 'ffll_ms': ffll_ms, 'mip_obj': opt_val,
            'gap': gap, 'ffll_seq': seq, 'mip_seq': mip['sequence'],
            'status': status, 'buffer_ok': buffer_ok}