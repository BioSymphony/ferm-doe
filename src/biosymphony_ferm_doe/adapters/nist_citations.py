"""NIST/SEMATECH e-Handbook citation references for DoE families.

Pure data adapter — no external dependency. Always importable.

Grounds the family recommender's decision tree in the NIST/SEMATECH
e-Handbook of Statistical Methods (https://www.itl.nist.gov/div898/handbook/),
public domain. Each entry maps a supported family to the relevant section
URL plus a one-line selection rule from that chapter. Designs that are
post-handbook (e.g. Definitive Screening, Jones-Nachtsheim 2011) cite the
primary literature directly.

Public API:

- :data:`REFERENCES` — dict keyed by family id
- :func:`lookup` (family) → reference dict or None
- :func:`is_available` → True (always)
"""

from __future__ import annotations

REFERENCES: dict[str, dict[str, str | None]] = {
    "full_factorial": {
        "section": "5.3.3.3",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri333.htm",
        "selection_rule": "All combinations across declared levels; supports all main effects and interactions.",
        "title": "NIST/SEMATECH e-Handbook 5.3.3.3 — Full factorial designs",
    },
    "fractional_factorial": {
        "section": "5.3.3.4",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri334.htm",
        "selection_rule": "2-level fractions 2^(k-p); resolution determines aliasing of main effects with interactions.",
        "title": "NIST/SEMATECH e-Handbook 5.3.3.4 — Fractional factorial designs",
    },
    "plackett_burman": {
        "section": "5.3.3.4.5",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri3346.htm",
        "selection_rule": "Resolution III screening at minimum runs; main effects only; n is next multiple of 4 ≥ k+1.",
        "title": "NIST/SEMATECH e-Handbook 5.3.3.4.5 — Plackett-Burman designs",
    },
    "central_composite": {
        "section": "5.3.3.6.1",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri3361.htm",
        "selection_rule": "RSM with curvature; 2^k factorial + 2k axial + center points; supports full quadratic.",
        "title": "NIST/SEMATECH e-Handbook 5.3.3.6.1 — Central composite designs",
    },
    "box_behnken": {
        "section": "5.3.3.6.2",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri3362.htm",
        "selection_rule": "RSM without corner points; rotatable; useful when extreme combinations are infeasible.",
        "title": "NIST/SEMATECH e-Handbook 5.3.3.6.2 — Box-Behnken designs",
    },
    "scheffe_mixture": {
        "section": "5.5.4.1",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section5/pri541.htm",
        "selection_rule": "Canonical mixture model; simplex-lattice or simplex-centroid covers the simplex region.",
        "title": "NIST/SEMATECH e-Handbook 5.5.4.1 — Mixture designs",
    },
    "extreme_vertices_mixture": {
        "section": "5.5.4.3",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section5/pri543.htm",
        "selection_rule": "Constrained mixture region; McLean-Anderson vertices when components carry non-trivial bounds.",
        "title": "NIST/SEMATECH e-Handbook 5.5.4.3 — Extreme vertices designs",
    },
    "split_plot": {
        "section": "5.3.3.5",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri335.htm",
        "selection_rule": "Hard-to-change vs easy-to-change factors; whole-plot replication preserves error structure.",
        "title": "NIST/SEMATECH e-Handbook 5.3.3.5 — Split-plot designs",
    },
    "optimal_d": {
        "section": "5.5.2",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section5/pri52.htm",
        "selection_rule": "Computer-generated; minimizes the variance of estimated coefficients (det X^T X^{-1}).",
        "title": "NIST/SEMATECH e-Handbook 5.5.2 — Optimal designs",
    },
    "optimal_i": {
        "section": "5.5.2",
        "url": "https://www.itl.nist.gov/div898/handbook/pri/section5/pri52.htm",
        "selection_rule": "Computer-generated; minimizes prediction variance averaged over the design region.",
        "title": "NIST/SEMATECH e-Handbook 5.5.2 — Optimal designs",
    },
    "latin_hypercube": {
        "section": None,
        "url": "https://www.tandfonline.com/doi/abs/10.1080/00401706.1979.10489755",
        "selection_rule": "Space-filling design; one sample per equally-spaced quantile interval per factor.",
        "title": "McKay, Beckman & Conover 1979 — Latin Hypercube Sampling",
    },
    "definitive_screening": {
        "section": None,
        "url": "https://www.tandfonline.com/doi/abs/10.1080/00224065.2011.11917841",
        "selection_rule": "Screening with curvature suspected; 2k+1 runs; main effects clear of two-factor interactions.",
        "title": "Jones & Nachtsheim 2011 — Definitive Screening Designs",
    },
}


def lookup(family: str) -> dict[str, str | None] | None:
    return REFERENCES.get(family)


def is_available() -> bool:
    return True


__all__ = ["REFERENCES", "lookup", "is_available"]
