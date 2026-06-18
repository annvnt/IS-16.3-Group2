"""IG-LS: Iterated Greedy with Local Search — improves FFLL's Phase 2."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .allocation import allocate_machines
from .models import Instance, Schedule
from .sequencing import dynamic_balancing
from .simulation import bottleneck_cycle_time, simulate_makespan

# Smallest makespan reduction treated as a real improvement (guards float noise).
EPSILON = 1e-9
DEFAULT_ITERATIONS = 150
DEFAULT_BLOCK_SIZE = 2
DEFAULT_SEED = 42


@dataclass(frozen=True)
class IGLSConfig:
    """Tuning parameters for IG-LS.

    Attributes:
        iterations: Number of perturbation + local-search rounds.
        block_size: Length of the contiguous block moved during perturbation.
        seed: Seed for the perturbation RNG (keeps runs reproducible).
    """

    iterations: int = DEFAULT_ITERATIONS
    block_size: int = DEFAULT_BLOCK_SIZE
    seed: int = DEFAULT_SEED


def igls(inst: Instance, config: IGLSConfig | None = None) -> Schedule:
    """Run IG-LS: FFLL Phases 1 and 3 with an improved sequencing phase.

    Starts from the Dynamic Balancing sequence, refines it with 2-opt local
    search, then repeatedly perturbs and re-optimizes, keeping only improvements.

    Args:
        inst: The scheduling instance.
        config: Tuning parameters; defaults to :class:`IGLSConfig`.

    Returns:
        The best schedule found (sequence, cycle time, makespan).
    """
    config = config or IGLSConfig()
    rng = random.Random(config.seed)
    alloc = allocate_machines(inst)

    sequence, best_makespan = local_search_2opt(dynamic_balancing(alloc), alloc)
    for _ in range(config.iterations):
        candidate = perturb(sequence, config.block_size, rng)
        candidate, candidate_makespan = local_search_2opt(candidate, alloc)
        if candidate_makespan < best_makespan - EPSILON:
            sequence, best_makespan = candidate, candidate_makespan

    return Schedule(
        sequence=sequence,
        cycle_time=bottleneck_cycle_time(alloc),
        makespan=best_makespan,
    )


def local_search_2opt(sequence, alloc):
    """Apply 2-opt swaps until no pairwise swap improves the makespan.

    Args:
        sequence: The starting job order.
        alloc: The Phase 1 allocation.

    Returns:
        A ``(sequence, makespan)`` tuple at the local optimum.
    """
    best = sequence[:]
    best_makespan = simulate_makespan(best, alloc)
    improved = True
    while improved:
        improved, best, best_makespan = _first_improving_swap(best, best_makespan, alloc)
    return best, best_makespan


def _first_improving_swap(sequence, makespan, alloc):
    """Return the first pairwise swap that lowers the makespan.

    Returns a ``(found, sequence, makespan)`` tuple; ``found`` is False (with the
    inputs echoed back) when no improving swap exists.
    """
    for i in range(len(sequence)):
        for j in range(i + 1, len(sequence)):
            candidate = sequence[:]
            candidate[i], candidate[j] = candidate[j], candidate[i]
            candidate_makespan = simulate_makespan(candidate, alloc)
            if candidate_makespan < makespan - EPSILON:
                return True, candidate, candidate_makespan
    return False, sequence, makespan


def perturb(sequence: list[int], block_size: int, rng: random.Random) -> list[int]:
    """Remove a random contiguous block of jobs and reinsert it elsewhere.

    This is the destruction-reconstruction step of Iterated Greedy.

    Args:
        sequence: The current job order.
        block_size: Length of the block to relocate.
        rng: Random source (injected for reproducibility).

    Returns:
        A new perturbed sequence.
    """
    n = len(sequence)
    if n <= block_size:
        shuffled = sequence[:]
        rng.shuffle(shuffled)
        return shuffled

    start = rng.randint(0, n - block_size)
    block = sequence[start : start + block_size]
    remaining = sequence[:start] + sequence[start + block_size :]
    insert_at = rng.randint(0, len(remaining))
    return remaining[:insert_at] + block + remaining[insert_at:]
