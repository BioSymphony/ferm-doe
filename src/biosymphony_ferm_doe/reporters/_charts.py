"""Optional Plotly-backed interactive charts for the BoFire HTML reporter.

The module soft-imports Plotly and exposes three figure builders:
``render_constraint_slice`` (input visualization), ``render_cost_stack``
(output visualization), and ``render_factor_heatmap`` (output design
coverage). Each returns an HTML div fragment when Plotly is installed
and an empty string otherwise so the parent reporter can fall back
cleanly to its stdlib tabular sections.
"""

from __future__ import annotations

import importlib.util
import json
from typing import Any


CARBON_FACTORS = ("glucose", "glycerol", "lactose", "sucrose", "xylose")


_CATEGORY_COLORS = {
    "carbon_source": "#2ca02c",
    "nitrogen_inorganic": "#1f77b4",
    "nitrogen_complex": "#8c564b",
    "trace": "#9467bd",
    "induction": "#e377c2",
    "other": "#7f7f7f",
}


def is_available() -> bool:
    return importlib.util.find_spec("plotly") is not None


def render_constraint_slice(
    report: dict[str, Any],
    manifest: dict[str, Any],
    *,
    x_factor: str | None = None,
    y_factor: str | None = None,
    grid: int = 60,
    include_plotlyjs: bool = True,
) -> str:
    """2D feasibility slice across two carbon factors.

    Sweeps the chosen pair on a regular grid; every other carbon and
    nitrogen factor is fixed at zero; every "induction" factor is fixed
    at its midpoint. Each cell is colored by feasibility under the
    declared linear constraints (total carbon, cost budget) and the
    n-choose-k cardinality (since the slice has at most 2 carbons
    active, n-choose-k is automatically satisfied).
    """

    if not is_available():
        return ""
    import plotly.graph_objects as go

    factor_lookup = {f.get("factor_id"): f for f in manifest.get("factors", []) if isinstance(f, dict)}
    candidates = _pick_pair(factor_lookup, x_factor, y_factor)
    if candidates is None:
        return ""
    x_id, y_id = candidates

    x_factor_obj = factor_lookup[x_id]
    y_factor_obj = factor_lookup[y_id]
    x_low, x_high = float(x_factor_obj.get("low", 0)), float(x_factor_obj.get("high", 50))
    y_low, y_high = float(y_factor_obj.get("low", 0)), float(y_factor_obj.get("high", 50))

    constraints = manifest.get("constraints", [])
    cost_budget, cost_coeffs = _extract_cost_constraint(constraints)
    total_carbon = _extract_total_carbon(constraints)

    other_factor_floor: dict[str, float] = {}
    for fid, f in factor_lookup.items():
        if fid in {x_id, y_id}:
            continue
        if f.get("category") == "induction":
            other_factor_floor[fid] = (float(f.get("low", 0)) + float(f.get("high", 0))) / 2.0
        else:
            other_factor_floor[fid] = float(f.get("low", 0))

    xs = _linspace(x_low, x_high, grid)
    ys = _linspace(y_low, y_high, grid)
    feasibility = [[1 for _ in xs] for _ in ys]

    for i, y_val in enumerate(ys):
        for j, x_val in enumerate(xs):
            if total_carbon is not None and (x_val + y_val) > total_carbon + 1e-9:
                feasibility[i][j] = 0
                continue
            if cost_coeffs is not None and cost_budget is not None:
                cost = (
                    cost_coeffs.get(x_id, 0.0) * x_val
                    + cost_coeffs.get(y_id, 0.0) * y_val
                    + sum(cost_coeffs.get(k, 0.0) * v for k, v in other_factor_floor.items())
                )
                if cost > cost_budget + 1e-9:
                    feasibility[i][j] = 0
                    continue

    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=feasibility,
            x=xs,
            y=ys,
            colorscale=[[0, "#ffe7e7"], [1, "#e7f5e7"]],
            showscale=False,
            hovertemplate=(
                f"{x_id}: %{{x:.1f}} g/L<br>"
                f"{y_id}: %{{y:.1f}} g/L<br>"
                "feasible: %{z}<extra></extra>"
            ),
        )
    )

    if total_carbon is not None:
        max_x_on_line = min(x_high, total_carbon)
        max_y_on_line = min(y_high, total_carbon)
        fig.add_trace(
            go.Scatter(
                x=[total_carbon, 0],
                y=[0, total_carbon],
                mode="lines",
                line=dict(color="#dc3545", width=2, dash="dash"),
                name=f"Σ carbon = {total_carbon:g} g/L",
                hovertemplate="total-carbon boundary<extra></extra>",
            )
        )

    if cost_budget is not None and cost_coeffs is not None:
        background_cost = sum(
            cost_coeffs.get(k, 0.0) * v for k, v in other_factor_floor.items()
        )
        remaining_budget = cost_budget - background_cost
        if remaining_budget > 0:
            a, b = cost_coeffs.get(x_id, 0.0), cost_coeffs.get(y_id, 0.0)
            if a > 0 and b > 0:
                x_intercept = remaining_budget / a
                y_intercept = remaining_budget / b
                fig.add_trace(
                    go.Scatter(
                        x=[min(x_intercept, x_high), 0],
                        y=[0, min(y_intercept, y_high)],
                        mode="lines",
                        line=dict(color="#0d6efd", width=2, dash="dot"),
                        name=f"cost = ${cost_budget:g}/L (others at floor)",
                        hovertemplate="cost boundary<extra></extra>",
                    )
                )

    fig.update_layout(
        title=f"Feasibility slice: {x_id} vs {y_id}",
        xaxis_title=f"{x_id} (g/L)",
        yaxis_title=f"{y_id} (g/L)",
        height=420,
        margin=dict(l=60, r=20, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0),
        plot_bgcolor="#ffffff",
    )
    return fig.to_html(
        include_plotlyjs="inline" if include_plotlyjs else False,
        full_html=False,
        div_id="constraint-slice-fig",
        config={"displayModeBar": False, "responsive": True},
    )


def render_cost_stack(
    report: dict[str, Any],
    manifest: dict[str, Any],
    *,
    include_plotlyjs: bool = False,
) -> str:
    """Stacked bar chart: per-candidate $/L stack by component category."""

    if not is_available():
        return ""
    import plotly.graph_objects as go

    rows = report.get("candidate_design") or []
    if not rows:
        return ""

    factor_lookup = {f.get("factor_id"): f for f in manifest.get("factors", []) if isinstance(f, dict)}
    constraints = manifest.get("constraints", [])
    cost_budget, cost_coeffs = _extract_cost_constraint(constraints)
    if cost_coeffs is None:
        return ""

    components = list(cost_coeffs.keys())
    run_ids = [str(r.get("run_id") or f"row-{i}") for i, r in enumerate(rows)]

    fig = go.Figure()
    for comp in components:
        category = str((factor_lookup.get(comp) or {}).get("category", "other"))
        color = _CATEGORY_COLORS.get(category, _CATEGORY_COLORS["other"])
        coeff = cost_coeffs[comp]
        values = [coeff * float(r.get(comp) or 0.0) for r in rows]
        fig.add_trace(
            go.Bar(
                name=comp,
                x=run_ids,
                y=values,
                marker_color=color,
                hovertemplate=(
                    f"{comp}<br>"
                    "$/L: %{y:.4f}<extra></extra>"
                ),
                legendgroup=category,
                legendgrouptitle_text=category,
            )
        )

    if cost_budget is not None:
        fig.add_hline(
            y=cost_budget,
            line_dash="dash",
            line_color="#dc3545",
            annotation_text=f"budget = ${cost_budget:g}/L",
            annotation_position="top right",
        )

    fig.update_layout(
        title="Per-candidate cost stack ($/L)",
        xaxis_title="run id",
        yaxis_title="$/L of finished media",
        barmode="stack",
        height=420,
        margin=dict(l=60, r=20, t=50, b=80),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        plot_bgcolor="#ffffff",
    )
    return fig.to_html(
        include_plotlyjs="inline" if include_plotlyjs else False,
        full_html=False,
        div_id="cost-stack-fig",
        config={"displayModeBar": False, "responsive": True},
    )


def render_factor_heatmap(
    report: dict[str, Any],
    manifest: dict[str, Any],
    *,
    include_plotlyjs: bool = False,
) -> str:
    """Heatmap of normalized factor values across candidates (design coverage)."""

    if not is_available():
        return ""
    import plotly.graph_objects as go

    rows = report.get("candidate_design") or []
    if not rows:
        return ""

    factor_lookup = {f.get("factor_id"): f for f in manifest.get("factors", []) if isinstance(f, dict)}
    factor_keys = [f.get("factor_id") for f in manifest.get("factors", []) if isinstance(f, dict) and f.get("factor_id")]

    z = []
    hover_text = []
    for fid in factor_keys:
        f = factor_lookup[fid]
        low = float(f.get("low", 0))
        high = float(f.get("high", 1))
        span = max(high - low, 1e-9)
        z_row = []
        hover_row = []
        for r in rows:
            raw = float(r.get(fid) or 0.0)
            normalized = (raw - low) / span
            z_row.append(normalized)
            hover_row.append(f"{fid}: {raw:.2f} {f.get('unit', '')}<br>normalized: {normalized:.2f}")
        z.append(z_row)
        hover_text.append(hover_row)

    run_ids = [str(r.get("run_id") or f"row-{i}") for i, r in enumerate(rows)]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=run_ids,
            y=factor_keys,
            colorscale="Viridis",
            zmin=0,
            zmax=1,
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
            colorbar=dict(title="normalized<br>factor value"),
        )
    )
    fig.update_layout(
        title="Design coverage (normalized factor values across candidates)",
        xaxis_title="run id",
        yaxis_title="factor",
        height=max(280, 30 * len(factor_keys) + 100),
        margin=dict(l=120, r=20, t=50, b=80),
        plot_bgcolor="#ffffff",
    )
    return fig.to_html(
        include_plotlyjs="inline" if include_plotlyjs else False,
        full_html=False,
        div_id="factor-heatmap-fig",
        config={"displayModeBar": False, "responsive": True},
    )


# ----- helpers -----


def _pick_pair(
    factor_lookup: dict[str, dict[str, Any]],
    x_factor: str | None,
    y_factor: str | None,
) -> tuple[str, str] | None:
    if x_factor and y_factor and x_factor in factor_lookup and y_factor in factor_lookup:
        return x_factor, y_factor
    carbons = [fid for fid in CARBON_FACTORS if fid in factor_lookup]
    if len(carbons) >= 2:
        return carbons[0], carbons[1]
    by_category = [fid for fid, f in factor_lookup.items() if f.get("category") == "carbon_source"]
    if len(by_category) >= 2:
        return by_category[0], by_category[1]
    fids = list(factor_lookup.keys())
    if len(fids) >= 2:
        return fids[0], fids[1]
    return None


def _extract_cost_constraint(constraints: list[dict[str, Any]]) -> tuple[float | None, dict[str, float] | None]:
    for c in constraints:
        if c.get("type") != "linear":
            continue
        cid = str(c.get("constraint_id") or c.get("id") or "").lower()
        if "cost" not in cid:
            continue
        coeffs = c.get("coefficients") or {}
        if not isinstance(coeffs, dict):
            continue
        rhs = c.get("rhs")
        if not isinstance(rhs, (int, float)):
            continue
        return float(rhs), {k: float(v) for k, v in coeffs.items()}
    return None, None


def _extract_total_carbon(constraints: list[dict[str, Any]]) -> float | None:
    for c in constraints:
        if c.get("type") != "linear":
            continue
        cid = str(c.get("constraint_id") or c.get("id") or "").lower()
        if "carbon" not in cid:
            continue
        coeffs = c.get("coefficients") or {}
        if not isinstance(coeffs, dict):
            continue
        if not all(abs(float(v) - 1.0) < 1e-9 for v in coeffs.values()):
            continue
        rhs = c.get("rhs")
        if isinstance(rhs, (int, float)):
            return float(rhs)
    return None


def _linspace(low: float, high: float, n: int) -> list[float]:
    if n <= 1:
        return [low]
    step = (high - low) / (n - 1)
    return [low + step * i for i in range(n)]
