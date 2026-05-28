"""Stdlib-only first-batch DoE generators for biosymphony-ferm-doe.

Public entrypoint: :func:`generate_design`. Each family returns a uniform
shape: ``{family, claim_level, n_runs, factors, rows, metadata, warnings}``.

Claim levels are conservative. Designs whose construction is exact and
well-defined (full factorial, Plackett-Burman, fractional factorial with
declared generators, simplex-lattice / centroid mixture, central composite,
Box-Behnken k=3 or k=4, Latin hypercube basic, definitive screening for the
k values whose conference matrices are tabulated below) emit ``exact``.
Designs that depend on heuristic search or are computed on-the-fly without
optimality guarantees (D-optimal / I-optimal coordinate exchange,
extreme-vertices mixture) emit ``heuristic``. A statistician should review
anything other than ``exact`` before expensive runs.
"""

from __future__ import annotations

import math
import random
from itertools import combinations, product
from typing import Any, Iterable, Sequence

EXACT = "exact"
HEURISTIC = "heuristic"

SUPPORTED_FAMILIES: frozenset[str] = frozenset(
    {
        "full_factorial",
        "fractional_factorial",
        "plackett_burman",
        "definitive_screening",
        "central_composite",
        "box_behnken",
        "latin_hypercube",
        "scheffe_mixture",
        "optimal_d",
        "optimal_i",
        "extreme_vertices_mixture",
    }
)


# === Plackett-Burman cyclic generators (Williams construction) ===
# First row of length n-1; cyclically shifted to fill rows 1..n-1; row n is all '-'.
_PB_GENERATORS: dict[int, str] = {
    8: "+++-+--",
    12: "++-+++---+-",
    16: "++++-+-++--+---",
    20: "++--++++-+-+----++-",
    24: "+++++-+-++--++--+-+----",
}


# === Box-Behnken pair-block designs (k=3, 4 only — exact) ===
# Each block lists factor indices; for each block, a 2-level full factorial
# over the indexed positions with others held at 0.
_BB_BLOCKS: dict[int, list[tuple[int, ...]]] = {
    3: [(0, 1), (0, 2), (1, 2)],
    4: [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
}


# === Conference matrices for Definitive Screening Designs (Jones-Nachtsheim 2011) ===
# Conference matrix C of order m satisfies C C^T = (m-1) I with zeros on the diagonal.
# Tabulated for m in {4, 6, 10} — covers k in {3, 4, 5, 6, 9, 10}. Larger k must
# use plackett_burman or fractional_factorial in this build; conference matrices
# for m in {8, 12} require non-Paley constructions not yet vetted here.
_CONFERENCE_MATRICES: dict[int, list[tuple[int, ...]]] = {
    4: [
        (0, 1, 1, 1),
        (1, 0, -1, 1),
        (1, 1, 0, -1),
        (1, -1, 1, 0),
    ],
    6: [
        (0, 1, 1, 1, 1, 1),
        (1, 0, 1, -1, -1, 1),
        (1, 1, 0, 1, -1, -1),
        (1, -1, 1, 0, 1, -1),
        (1, -1, -1, 1, 0, 1),
        (1, 1, -1, -1, 1, 0),
    ],
    10: [
        (0, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        (1, 0, 1, 1, 1, 1, -1, -1, -1, -1),
        (1, 1, 0, 1, -1, -1, 1, 1, -1, -1),
        (1, 1, 1, 0, -1, -1, -1, -1, 1, 1),
        (1, 1, -1, -1, 0, 1, 1, -1, 1, -1),
        (1, 1, -1, -1, 1, 0, -1, 1, -1, 1),
        (1, -1, 1, -1, 1, -1, 0, 1, 1, -1),
        (1, -1, 1, -1, -1, 1, 1, 0, -1, 1),
        (1, -1, -1, 1, 1, -1, 1, -1, 0, 1),
        (1, -1, -1, 1, -1, 1, -1, 1, 1, 0),
    ],
}


# === Standard fractional factorial generators by k (number of factors) and resolution ===
# Each entry maps (k, resolution) -> list of generator strings.
# Generators define added factors as products of base factors; e.g. "ABC" means
# the factor is the product of base factors A, B, C.
_FF_GENERATORS: dict[tuple[int, int], list[str]] = {
    (3, 3): ["AB"],
    (4, 4): ["ABC"],
    (5, 5): ["ABCD"],
    (5, 3): ["AB", "AC"],
    (6, 4): ["ABC", "BCD"],
    (6, 3): ["AB", "AC", "BC"],
    (7, 4): ["ABC", "ABD", "BCD"],
    (7, 3): ["AB", "AC", "BC", "ABC"],
    (8, 4): ["BCDE", "ACDE", "ABCE", "ABCD"],
}


def generate_design(manifest: dict[str, Any], *, seed: int | None = None) -> dict[str, Any]:
    """Generate a first-batch design from a campaign manifest.

    The manifest's ``doe.family`` selects the generator. Numeric factors must
    declare ``low`` and ``high``; categorical factors must declare ``levels``.
    The output rows are mapped to engineering units, not coded values.

    Returns ``{family, claim_level, n_runs, factors, rows, metadata, warnings}``.
    Raises :class:`ValueError` for unsupported families or factor-type mismatches.
    """
    doe = manifest.get("doe") or {}
    family = doe.get("family")
    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"unsupported_doe_family: {family!r}")
    factors = manifest.get("factors") or []
    if not factors:
        raise ValueError("manifest_has_no_factors")
    rng = random.Random(seed)

    if family == "full_factorial":
        result = _full_factorial(factors, doe)
    elif family == "fractional_factorial":
        result = _fractional_factorial(factors, doe)
    elif family == "plackett_burman":
        result = _plackett_burman(factors, doe)
    elif family == "definitive_screening":
        result = _definitive_screening(factors, doe)
    elif family == "central_composite":
        result = _central_composite(factors, doe)
    elif family == "box_behnken":
        result = _box_behnken(factors, doe)
    elif family == "latin_hypercube":
        result = _latin_hypercube(factors, doe, rng)
    elif family == "scheffe_mixture":
        result = _scheffe_mixture(factors, doe)
    elif family in {"optimal_d", "optimal_i"}:
        result = _optimal(factors, doe, rng, criterion=family)
    elif family == "extreme_vertices_mixture":
        result = _extreme_vertices(factors, doe)
    else:  # pragma: no cover — defensive, SUPPORTED_FAMILIES is exhaustive
        raise ValueError(f"unsupported_doe_family: {family!r}")

    rows = result["rows"]
    randomized = bool(doe.get("randomized", True))
    if randomized:
        rng.shuffle(rows)
    for index, row in enumerate(rows, start=1):
        row.setdefault("design_run_id", f"D{index:03d}")
        row["run_order"] = index
    result["randomized"] = randomized
    result["seed"] = seed
    return result


# =====================================================================
# Generators
# =====================================================================


def _full_factorial(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    levels_per_factor: list[list[Any]] = []
    factor_ids: list[str] = []
    for factor in factors:
        fid = factor.get("factor_id")
        ftype = factor.get("type", "numeric")
        if not fid:
            raise ValueError("factor_missing_factor_id")
        factor_ids.append(fid)
        if ftype in {"numeric", "ordinal"}:
            n_levels = int(factor.get("n_levels", 2))
            if n_levels < 2:
                raise ValueError(f"factor_{fid}_needs_at_least_two_levels")
            low = float(factor["low"])
            high = float(factor["high"])
            if n_levels == 2:
                values = [low, high]
            else:
                step = (high - low) / (n_levels - 1)
                values = [round(low + i * step, 6) for i in range(n_levels)]
            levels_per_factor.append(values)
        elif ftype in {"categorical", "block"}:
            levels = factor.get("levels")
            if not levels:
                raise ValueError(f"factor_{fid}_needs_levels")
            levels_per_factor.append(list(levels))
        else:
            raise ValueError(f"full_factorial_does_not_support_factor_type_{ftype}_for_{fid}")

    rows: list[dict[str, Any]] = []
    for combo in product(*levels_per_factor):
        row = {fid: value for fid, value in zip(factor_ids, combo)}
        row["center_point"] = False
        rows.append(row)

    return {
        "family": "full_factorial",
        "claim_level": EXACT,
        "n_runs": len(rows),
        "factors": factor_ids,
        "rows": rows,
        "metadata": {"levels_per_factor": {fid: lvls for fid, lvls in zip(factor_ids, levels_per_factor)}},
        "warnings": [],
    }


def _plackett_burman(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    factor_ids, _ = _two_level_factor_axes(factors, "plackett_burman")
    k = len(factor_ids)
    n = _next_pb_size(k)
    if n not in _PB_GENERATORS:
        raise ValueError(f"plackett_burman_size_{n}_not_tabulated_max_{max(_PB_GENERATORS)}")
    matrix = _build_pb_matrix(n)  # n x (n-1) ±1 matrix
    rows: list[dict[str, Any]] = []
    for run in matrix:
        row: dict[str, Any] = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_two_level(factors[index], run[index])
        row["center_point"] = False
        rows.append(row)
    metadata = {
        "n_factors": k,
        "n_runs": n,
        "resolution": "III",
        "alias_structure": "main_effects_aliased_with_two_factor_interactions",
    }
    warnings: list[str] = []
    if k < n - 1:
        warnings.append(f"declared_{k}_factors_in_design_with_{n-1}_columns_unused_columns_dropped")
    return {
        "family": "plackett_burman",
        "claim_level": EXACT,
        "n_runs": n,
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": warnings,
    }


def _fractional_factorial(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    factor_ids, _ = _two_level_factor_axes(factors, "fractional_factorial")
    k = len(factor_ids)
    if k < 3:
        raise ValueError("fractional_factorial_requires_at_least_three_factors")
    declared_resolution = doe.get("resolution")
    declared_generators = doe.get("generators")

    if declared_generators:
        generators = list(declared_generators)
        base_k = k - len(generators)
        resolution = declared_resolution or _resolution_from_generators(generators)
    else:
        resolution_int = _resolution_to_int(declared_resolution) if declared_resolution else None
        generators, base_k, resolution = _select_ff_generators(k, resolution_int)

    if base_k < 1:
        raise ValueError("fractional_factorial_inferred_zero_or_negative_base_factors")

    base_letters = [chr(ord("A") + i) for i in range(base_k)]
    generator_specs = []
    for gen in generators:
        indices = []
        for ch in gen:
            if ch.upper() not in base_letters:
                raise ValueError(f"fractional_factorial_generator_{gen}_references_unknown_base_factor_{ch}")
            indices.append(base_letters.index(ch.upper()))
        generator_specs.append(indices)

    rows: list[dict[str, Any]] = []
    n_runs = 2 ** base_k
    for combo in product([-1, 1], repeat=base_k):
        coded = list(combo)
        for spec in generator_specs:
            value = 1
            for idx in spec:
                value *= combo[idx]
            coded.append(value)
        row: dict[str, Any] = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_two_level(factors[index], coded[index])
        row["center_point"] = False
        rows.append(row)
    generator_labels = [
        f"{chr(ord('A') + base_k + i)}={generators[i]}" for i in range(len(generators))
    ]
    metadata = {
        "n_factors": k,
        "n_runs": n_runs,
        "base_factors": base_k,
        "fraction": f"2^({k}-{len(generators)})",
        "resolution": resolution,
        "generators": generator_labels,
        "alias_structure": "consult_resolution_table",
    }
    return {
        "family": "fractional_factorial",
        "claim_level": EXACT,
        "n_runs": n_runs,
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": [],
    }


def _definitive_screening(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    factor_ids, _ = _three_level_factor_axes(factors, "definitive_screening")
    k = len(factor_ids)
    if k < 3:
        raise ValueError("definitive_screening_requires_at_least_three_factors")
    m = k if k % 2 == 0 else k + 1
    if m not in _CONFERENCE_MATRICES:
        raise ValueError(f"definitive_screening_for_k={k}_needs_conference_matrix_order_{m}_not_tabulated")
    conference = _CONFERENCE_MATRICES[m]
    folded: list[list[int]] = []
    for row in conference:
        folded.append(list(row[:k]))
    for row in conference:
        folded.append([-v for v in row[:k]])
    folded.append([0] * k)

    rows: list[dict[str, Any]] = []
    for run in folded:
        row: dict[str, Any] = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_three_level(factors[index], run[index])
        row["center_point"] = all(v == 0 for v in run)
        rows.append(row)

    metadata = {
        "n_factors": k,
        "n_runs": len(rows),
        "conference_matrix_order": m,
        "structure": "[C; -C; 0] folded conference design",
    }
    warnings: list[str] = []
    if m != k:
        warnings.append(f"odd_factor_count_{k}_used_conference_order_{m}_dropped_last_column")
    return {
        "family": "definitive_screening",
        "claim_level": EXACT,
        "n_runs": len(rows),
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": warnings,
    }


def _central_composite(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    factor_ids, _ = _three_level_factor_axes(factors, "central_composite")
    k = len(factor_ids)
    if k < 2:
        raise ValueError("central_composite_requires_at_least_two_factors")
    variant = doe.get("variant", "face_centered")
    n_center = int(doe.get("n_center_points", max(3, k)))
    declared_alpha = doe.get("axial_distance")

    factorial_runs: list[list[int]] = [list(c) for c in product([-1, 1], repeat=k)]
    n_factorial = len(factorial_runs)

    if declared_alpha is not None:
        alpha = float(declared_alpha)
    elif variant == "face_centered":
        alpha = 1.0
    elif variant == "rotatable":
        alpha = round(n_factorial ** 0.25, 6)
    elif variant == "orthogonal":
        alpha = round(((n_factorial * (n_factorial + 2 * k + n_center)) ** 0.5 - n_factorial) ** 0.5, 6)
    else:
        raise ValueError(f"unknown_central_composite_variant_{variant}")

    axial_runs: list[list[float]] = []
    for index in range(k):
        for sign in (-1, 1):
            run = [0.0] * k
            run[index] = sign * alpha
            axial_runs.append(run)

    center_runs: list[list[float]] = [[0.0] * k for _ in range(n_center)]

    rows: list[dict[str, Any]] = []
    for run in factorial_runs:
        row: dict[str, Any] = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_two_level(factors[index], run[index])
        row["center_point"] = False
        rows.append(row)
    for run in axial_runs:
        row = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_axial(factors[index], run[index])
        row["center_point"] = False
        rows.append(row)
    for run in center_runs:
        row = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_axial(factors[index], 0.0)
        row["center_point"] = True
        rows.append(row)

    warnings: list[str] = []
    if variant != "face_centered" and alpha > 1.0:
        warnings.append(
            f"axial_alpha_{alpha}_extends_beyond_declared_factor_range_operator_must_confirm_extrapolation_safe"
        )

    metadata = {
        "n_factors": k,
        "variant": variant,
        "axial_distance": alpha,
        "n_factorial_runs": n_factorial,
        "n_axial_runs": 2 * k,
        "n_center_points": n_center,
    }
    return {
        "family": "central_composite",
        "claim_level": EXACT,
        "n_runs": len(rows),
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": warnings,
    }


def _box_behnken(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    factor_ids, _ = _three_level_factor_axes(factors, "box_behnken")
    k = len(factor_ids)
    n_center = int(doe.get("n_center_points", max(3, k)))
    if k not in _BB_BLOCKS:
        from .adapters import get_adapter

        pydoe3 = get_adapter("pydoe3")
        if pydoe3 is not None and "box_behnken" in pydoe3.supported_families():
            rows = pydoe3.generate_box_behnken_extended(factors, n_center_points=n_center)
            return {
                "family": "box_behnken",
                "claim_level": EXACT,
                "n_runs": len(rows),
                "factors": factor_ids,
                "rows": rows,
                "metadata": {"n_factors": k, "n_runs": len(rows), "n_center_points": n_center, "backend": "pydoe3"},
                "warnings": [],
            }
        raise ValueError(
            f"box_behnken_for_k={k}_not_supported_supported_values={sorted(_BB_BLOCKS)}_or_install_pydoe3"
        )
    blocks = _BB_BLOCKS[k]

    rows: list[dict[str, Any]] = []
    for block in blocks:
        for combo in product([-1, 1], repeat=len(block)):
            run = [0] * k
            for offset, idx in enumerate(block):
                run[idx] = combo[offset]
            row: dict[str, Any] = {}
            for index, fid in enumerate(factor_ids):
                row[fid] = _decode_three_level(factors[index], run[index])
            row["center_point"] = False
            rows.append(row)
    for _ in range(n_center):
        row = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_three_level(factors[index], 0)
        row["center_point"] = True
        rows.append(row)
    metadata = {
        "n_factors": k,
        "n_runs": len(rows),
        "n_center_points": n_center,
        "blocks": [list(block) for block in blocks],
    }
    return {
        "family": "box_behnken",
        "claim_level": EXACT,
        "n_runs": len(rows),
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": [],
    }


def _latin_hypercube(
    factors: list[dict[str, Any]], doe: dict[str, Any], rng: random.Random
) -> dict[str, Any]:
    factor_ids: list[str] = []
    for factor in factors:
        fid = factor.get("factor_id")
        ftype = factor.get("type", "numeric")
        if ftype not in {"numeric", "ordinal"}:
            raise ValueError(f"latin_hypercube_only_supports_numeric_or_ordinal_factors_{fid}_is_{ftype}")
        factor_ids.append(fid)
    k = len(factor_ids)
    n = int(doe.get("n_runs", max(2 * k, 8)))
    if n < 2:
        raise ValueError("latin_hypercube_requires_at_least_two_runs")

    if doe.get("criterion") == "maximin":
        from .adapters import get_adapter

        pydoe3 = get_adapter("pydoe3")
        if pydoe3 is not None:
            rows = pydoe3.generate_lhs_maximin(factors, n_runs=n, seed=rng.randint(0, 2**31 - 1))
            return {
                "family": "latin_hypercube",
                "claim_level": EXACT,
                "n_runs": n,
                "factors": factor_ids,
                "rows": rows,
                "metadata": {"n_factors": k, "n_runs": n, "construction": "maximin_lhs_via_pydoe3", "backend": "pydoe3"},
                "warnings": [],
            }

    columns: list[list[float]] = []
    for index in range(k):
        permutation = list(range(n))
        rng.shuffle(permutation)
        column = []
        for slot in permutation:
            offset = rng.random()
            column.append((slot + offset) / n)
        columns.append(column)

    rows: list[dict[str, Any]] = []
    for run_idx in range(n):
        row: dict[str, Any] = {}
        for index, fid in enumerate(factor_ids):
            factor = factors[index]
            low = float(factor["low"])
            high = float(factor["high"])
            value = low + columns[index][run_idx] * (high - low)
            row[fid] = round(value, 6)
        row["center_point"] = False
        rows.append(row)
    return {
        "family": "latin_hypercube",
        "claim_level": EXACT,
        "n_runs": n,
        "factors": factor_ids,
        "rows": rows,
        "metadata": {"n_factors": k, "n_runs": n, "construction": "uniform_intervals_random_within"},
        "warnings": [],
    }


def _scheffe_mixture(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    mixture_factors = [f for f in factors if f.get("type") == "mixture"]
    if not mixture_factors:
        raise ValueError("scheffe_mixture_requires_at_least_one_mixture_factor")
    factor_ids = [f["factor_id"] for f in mixture_factors]
    q = len(factor_ids)
    total = float(doe.get("mixture_total", 1.0))
    construction = doe.get("construction", "simplex_centroid")

    rows: list[dict[str, Any]] = []
    if construction == "simplex_centroid":
        for size in range(1, q + 1):
            for indices in combinations(range(q), size):
                row: dict[str, Any] = {fid: 0.0 for fid in factor_ids}
                share = total / size
                for idx in indices:
                    row[factor_ids[idx]] = round(share, 6)
                row["center_point"] = size == q
                rows.append(row)
    elif construction == "simplex_lattice":
        m = int(doe.get("lattice_degree", 2))
        if m < 1:
            raise ValueError("simplex_lattice_degree_must_be_at_least_one")
        step = total / m
        for combo in _compositions(m, q):
            row = {}
            for index, fid in enumerate(factor_ids):
                row[fid] = round(combo[index] * step, 6)
            row["center_point"] = False
            rows.append(row)
    else:
        raise ValueError(f"unknown_scheffe_mixture_construction_{construction}")

    metadata = {
        "n_components": q,
        "n_runs": len(rows),
        "construction": construction,
        "mixture_total": total,
    }
    if construction == "simplex_lattice":
        metadata["lattice_degree"] = doe.get("lattice_degree", 2)
    warnings: list[str] = []
    for row in rows:
        s = sum(row[fid] for fid in factor_ids)
        if abs(s - total) > 1e-3:
            warnings.append("mixture_row_did_not_sum_to_total_within_tolerance")
            break
    return {
        "family": "scheffe_mixture",
        "claim_level": EXACT,
        "n_runs": len(rows),
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": warnings,
    }


def _optimal(
    factors: list[dict[str, Any]], doe: dict[str, Any], rng: random.Random, *, criterion: str
) -> dict[str, Any]:
    factor_ids, _ = _two_level_factor_axes(factors, criterion)
    k = len(factor_ids)
    n_runs = int(doe.get("n_runs", max(2 * k + 1, 8)))
    iterations = int(doe.get("optimal_iterations", 50))

    candidate_pool: list[list[int]] = [list(c) for c in product([-1, 0, 1], repeat=k)]
    design_indices = rng.sample(range(len(candidate_pool)), min(n_runs, len(candidate_pool)))
    if len(design_indices) < n_runs:
        design_indices += rng.choices(range(len(candidate_pool)), k=n_runs - len(design_indices))
    score = _optimality_score(candidate_pool, design_indices, criterion=criterion)

    for _ in range(iterations):
        improved = False
        for slot in range(n_runs):
            best_replacement = design_indices[slot]
            best_score = score
            for cand_idx in range(len(candidate_pool)):
                if cand_idx == design_indices[slot]:
                    continue
                trial = list(design_indices)
                trial[slot] = cand_idx
                trial_score = _optimality_score(candidate_pool, trial, criterion=criterion)
                if trial_score > best_score + 1e-9:
                    best_score = trial_score
                    best_replacement = cand_idx
            if best_replacement != design_indices[slot]:
                design_indices[slot] = best_replacement
                score = best_score
                improved = True
        if not improved:
            break

    rows: list[dict[str, Any]] = []
    for cand_idx in design_indices:
        coded = candidate_pool[cand_idx]
        row: dict[str, Any] = {}
        for index, fid in enumerate(factor_ids):
            row[fid] = _decode_three_level(factors[index], coded[index])
        row["center_point"] = all(v == 0 for v in coded)
        rows.append(row)
    metadata = {
        "n_factors": k,
        "n_runs": n_runs,
        "criterion": criterion,
        "iterations_run": iterations,
        "candidate_pool_size": len(candidate_pool),
        "final_score": score,
    }
    return {
        "family": criterion,
        "claim_level": HEURISTIC,
        "n_runs": n_runs,
        "factors": factor_ids,
        "rows": rows,
        "metadata": metadata,
        "warnings": [
            f"{criterion}_designs_emitted_at_claim_heuristic_review_with_a_statistician_before_use",
        ],
    }


def _extreme_vertices(factors: list[dict[str, Any]], doe: dict[str, Any]) -> dict[str, Any]:
    mixture_factors = [f for f in factors if f.get("type") == "mixture"]
    if not mixture_factors:
        raise ValueError("extreme_vertices_requires_at_least_one_mixture_factor")
    factor_ids = [f["factor_id"] for f in mixture_factors]
    q = len(factor_ids)
    total = float(doe.get("mixture_total", 1.0))
    bounds = []
    for factor in mixture_factors:
        low = float(factor.get("low", 0.0))
        high = float(factor.get("high", total))
        bounds.append((low, high))

    raw_vertices: list[list[float]] = []
    for fixed_indices in combinations(range(q), q - 1):
        for combo in product(*((bounds[i][0], bounds[i][1]) for i in fixed_indices)):
            assignment = [0.0] * q
            assigned_total = 0.0
            for offset, idx in enumerate(fixed_indices):
                assignment[idx] = combo[offset]
                assigned_total += combo[offset]
            free_index = next(i for i in range(q) if i not in fixed_indices)
            free_value = total - assigned_total
            if bounds[free_index][0] - 1e-9 <= free_value <= bounds[free_index][1] + 1e-9:
                assignment[free_index] = round(max(bounds[free_index][0], min(bounds[free_index][1], free_value)), 6)
                if assignment not in raw_vertices:
                    raw_vertices.append([round(v, 6) for v in assignment])

    if not raw_vertices:
        raise ValueError("extreme_vertices_constraint_region_empty_check_component_bounds")

    centroid = [round(sum(v[i] for v in raw_vertices) / len(raw_vertices), 6) for i in range(q)]
    raw_vertices.append(centroid)

    rows: list[dict[str, Any]] = []
    for assignment in raw_vertices:
        row = {fid: assignment[index] for index, fid in enumerate(factor_ids)}
        row["center_point"] = assignment == centroid
        rows.append(row)

    return {
        "family": "extreme_vertices_mixture",
        "claim_level": HEURISTIC,
        "n_runs": len(rows),
        "factors": factor_ids,
        "rows": rows,
        "metadata": {
            "n_components": q,
            "n_runs": len(rows),
            "mixture_total": total,
            "construction": "mclean_anderson_basic_with_centroid",
        },
        "warnings": [
            "extreme_vertices_design_uses_basic_constraint_enumeration_review_for_coverage_with_a_statistician",
        ],
    }


# =====================================================================
# Helpers
# =====================================================================


def _two_level_factor_axes(
    factors: list[dict[str, Any]], family: str
) -> tuple[list[str], list[tuple[float, float]]]:
    factor_ids: list[str] = []
    bounds: list[tuple[float, float]] = []
    for factor in factors:
        fid = factor.get("factor_id")
        ftype = factor.get("type", "numeric")
        if ftype not in {"numeric", "ordinal"}:
            raise ValueError(
                f"{family}_only_supports_numeric_or_ordinal_factors_{fid}_is_{ftype}"
            )
        if "low" not in factor or "high" not in factor:
            raise ValueError(f"factor_{fid}_missing_low_or_high")
        factor_ids.append(fid)
        bounds.append((float(factor["low"]), float(factor["high"])))
    return factor_ids, bounds


def _three_level_factor_axes(
    factors: list[dict[str, Any]], family: str
) -> tuple[list[str], list[tuple[float, float]]]:
    return _two_level_factor_axes(factors, family)


def _decode_two_level(factor: dict[str, Any], coded: int) -> float:
    low = float(factor["low"])
    high = float(factor["high"])
    if coded > 0:
        return high
    if coded < 0:
        return low
    return round((low + high) / 2, 6)


def _decode_three_level(factor: dict[str, Any], coded: int) -> float:
    low = float(factor["low"])
    high = float(factor["high"])
    if coded > 0:
        return high
    if coded < 0:
        return low
    return round((low + high) / 2, 6)


def _decode_axial(factor: dict[str, Any], coded: float) -> float:
    low = float(factor["low"])
    high = float(factor["high"])
    midpoint = (low + high) / 2.0
    half_range = (high - low) / 2.0
    return round(midpoint + coded * half_range, 6)


def _next_pb_size(k: int) -> int:
    n = 4
    while n - 1 < k:
        n += 4
    return n


def _build_pb_matrix(n: int) -> list[list[int]]:
    base = _PB_GENERATORS[n]
    base_signs = [1 if ch == "+" else -1 for ch in base]
    matrix: list[list[int]] = []
    current = list(base_signs)
    for _ in range(n - 1):
        matrix.append(list(current))
        current = [current[-1]] + current[:-1]
    matrix.append([-1] * (n - 1))
    return matrix


def _select_ff_generators(k: int, resolution: int | None) -> tuple[list[str], int, str]:
    candidates = [
        ((kk, rr), gens) for (kk, rr), gens in _FF_GENERATORS.items() if kk == k
    ]
    if not candidates:
        raise ValueError(f"fractional_factorial_no_tabulated_generators_for_k={k}")
    if resolution is not None:
        match = next((entry for entry in candidates if entry[0][1] == resolution), None)
        if match is None:
            raise ValueError(
                f"fractional_factorial_no_tabulated_generators_for_k={k}_resolution={resolution}"
            )
        (kk, rr), gens = match
    else:
        candidates.sort(key=lambda entry: -entry[0][1])
        (kk, rr), gens = candidates[0]
    base_k = k - len(gens)
    return list(gens), base_k, _resolution_label(rr)


def _resolution_to_int(label: Any) -> int | None:
    if label is None:
        return None
    if isinstance(label, int):
        return label
    label = str(label).upper()
    table = {"III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
    if label in table:
        return table[label]
    if label.isdigit():
        return int(label)
    raise ValueError(f"unknown_resolution_label_{label}")


def _resolution_label(value: int) -> str:
    table = {3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
    return table.get(value, str(value))


def _resolution_from_generators(generators: Sequence[str]) -> str:
    min_word = min(len(gen) for gen in generators) + 1 if generators else 0
    return _resolution_label(min_word) if min_word else "III"


def _compositions(m: int, q: int) -> Iterable[tuple[int, ...]]:
    """Integer compositions of m into q non-negative parts."""
    if q == 1:
        yield (m,)
        return
    for first in range(m + 1):
        for rest in _compositions(m - first, q - 1):
            yield (first, *rest)


def _optimality_score(pool: list[list[int]], indices: Sequence[int], *, criterion: str) -> float:
    rows = [pool[i] for i in indices]
    n = len(rows)
    k = len(rows[0]) if rows else 0
    n_terms = 1 + k + k * (k - 1) // 2
    matrix: list[list[float]] = []
    for row in rows:
        terms: list[float] = [1.0]
        terms.extend(float(v) for v in row)
        for i in range(k):
            for j in range(i + 1, k):
                terms.append(float(row[i] * row[j]))
        matrix.append(terms)
    info = [[0.0] * n_terms for _ in range(n_terms)]
    for vec in matrix:
        for i in range(n_terms):
            for j in range(n_terms):
                info[i][j] += vec[i] * vec[j]
    determinant = _determinant(info)
    if criterion == "optimal_d":
        if determinant <= 0:
            return -math.inf
        return math.log(determinant)
    if criterion == "optimal_i":
        if determinant <= 0:
            return -math.inf
        return -math.log(_trace(info)) - math.log(n)
    return -math.inf


def _determinant(matrix: list[list[float]]) -> float:
    n = len(matrix)
    if n == 0:
        return 1.0
    a = [row[:] for row in matrix]
    det = 1.0
    for i in range(n):
        pivot = i
        for r in range(i + 1, n):
            if abs(a[r][i]) > abs(a[pivot][i]):
                pivot = r
        if abs(a[pivot][i]) < 1e-12:
            return 0.0
        if pivot != i:
            a[i], a[pivot] = a[pivot], a[i]
            det = -det
        det *= a[i][i]
        for r in range(i + 1, n):
            factor = a[r][i] / a[i][i]
            for c in range(i, n):
                a[r][c] -= factor * a[i][c]
    return det


def _trace(matrix: list[list[float]]) -> float:
    return sum(matrix[i][i] for i in range(len(matrix)))


__all__ = ["generate_design", "SUPPORTED_FAMILIES", "EXACT", "HEURISTIC"]
