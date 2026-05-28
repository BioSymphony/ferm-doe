"""Inline SVG generator showing the BoFire strategy-routing pipeline.

The SVG visualizes the per-run path: manifest -> routing decision ->
Domain translation -> strategy dispatch (DoE / SOBO / MOBO / MultiFid)
-> ask() -> candidate rows -> HTML report. The path actually taken on
this run is highlighted; the unused strategy branches are dimmed.

Stdlib only — no Plotly, no JS dependencies, offline-safe.
"""

from __future__ import annotations

from typing import Any


# Color palette
ACTIVE_FILL = "#0d6efd"
ACTIVE_TEXT = "#ffffff"
ACTIVE_STROKE = "#084298"
DIM_FILL = "#e9ecef"
DIM_TEXT = "#6c757d"
DIM_STROKE = "#adb5bd"
SUCCESS_FILL = "#198754"
SUCCESS_TEXT = "#ffffff"
FAILURE_FILL = "#dc3545"
FAILURE_TEXT = "#ffffff"
DECISION_FILL = "#fff3cd"
DECISION_STROKE = "#ffc107"


STRATEGY_LABELS = {
    "constrained_doe": "DoEStrategy\n(D-optimal)",
    "single_objective": "SoboStrategy\n(single obj BO)",
    "multi_objective": "MoboStrategy\n(qLogNEHVI)",
    "multi_fidelity": "MultiFidelity\nStrategy",
}

STRATEGY_KINDS = ("constrained_doe", "single_objective", "multi_objective", "multi_fidelity")


def render_pipeline_svg(report: dict[str, Any]) -> str:
    """Render the routing pipeline as inline SVG."""

    route = report.get("route") or {}
    strategy_kind = str(report.get("strategy_kind") or "not_routed")
    adapter_status = str(report.get("adapter_status") or "unknown")
    should_route = bool(route.get("should_route"))
    reasons = route.get("reasons") or []
    candidate_count = int(report.get("candidate_design_count") or 0)

    parts: list[str] = []
    parts.append('<svg viewBox="0 0 820 540" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="BoFire routing pipeline">')
    parts.append('<defs>')
    parts.append('<marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">')
    parts.append('<path d="M0,0 L0,6 L9,3 z" fill="#495057"/>')
    parts.append('</marker>')
    parts.append('<marker id="arrowhead-dim" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">')
    parts.append(f'<path d="M0,0 L0,6 L9,3 z" fill="{DIM_STROKE}"/>')
    parts.append('</marker>')
    parts.append('</defs>')

    # Stage 1: manifest
    parts.append(_cylinder(40, 40, 140, 60, "campaign\nmanifest.json", ACTIVE_FILL, ACTIVE_TEXT, ACTIVE_STROKE))
    # Arrow to routing decision
    parts.append(_arrow(180, 70, 230, 70, dim=False))

    # Stage 2: routing decision (diamond)
    parts.append(_diamond(230, 40, 110, 60, "routing\ndecision", DECISION_FILL, "#212529", DECISION_STROKE))

    # Stage 3: outcome
    if should_route:
        # Arrow down to translation
        parts.append(_arrow(285, 100, 285, 145, dim=False))
        # Annotation: reasons
        reasons_text = ", ".join(reasons) if reasons else "(no reasons)"
        parts.append(f'<text x="350" y="125" font-size="11" fill="#495057">route reasons: {_escape(reasons_text)}</text>')

        # Stage 4: Domain translation
        parts.append(_rect(230, 145, 110, 50, "Domain\ntranslate", ACTIVE_FILL, ACTIVE_TEXT, ACTIVE_STROKE))
        # Arrow down to strategy dispatch
        parts.append(_arrow(285, 195, 285, 235, dim=False))

        # Stage 5: strategy dispatch (4 boxes side-by-side, highlighted one in ACTIVE color)
        for i, kind in enumerate(STRATEGY_KINDS):
            x = 30 + i * 200
            is_active = (kind == strategy_kind)
            fill = ACTIVE_FILL if is_active else DIM_FILL
            text = ACTIVE_TEXT if is_active else DIM_TEXT
            stroke = ACTIVE_STROKE if is_active else DIM_STROKE
            label = STRATEGY_LABELS.get(kind, kind)
            parts.append(_rect(x, 235, 170, 60, label, fill, text, stroke))
            # Arrow from translation down to this strategy box (dim if not active)
            mid_x_to = x + 85
            parts.append(_arrow(285, 235, mid_x_to, 235, dim=not is_active, curved=(i != 1)))

        # Stage 6: ask() — only highlighted strategy connects forward
        active_index = STRATEGY_KINDS.index(strategy_kind) if strategy_kind in STRATEGY_KINDS else 0
        active_x = 30 + active_index * 200 + 85
        parts.append(_arrow(active_x, 295, 410, 340, dim=False))
        parts.append(_rect(355, 340, 110, 50, ".ask(N)", ACTIVE_FILL, ACTIVE_TEXT, ACTIVE_STROKE))

        # Stage 7: candidate rows
        parts.append(_arrow(465, 365, 510, 365, dim=False))
        cyl_fill = SUCCESS_FILL if adapter_status == "executed" and candidate_count > 0 else FAILURE_FILL if adapter_status in {"execution_failed", "not_available"} else DECISION_FILL
        cyl_text = SUCCESS_TEXT if adapter_status == "executed" and candidate_count > 0 else FAILURE_TEXT if adapter_status in {"execution_failed", "not_available"} else "#212529"
        cyl_stroke = "#0f5132" if adapter_status == "executed" else "#842029" if adapter_status in {"execution_failed", "not_available"} else "#856404"
        cyl_label = f"{candidate_count} candidate\nrow{'s' if candidate_count != 1 else ''}" if adapter_status == "executed" else adapter_status.replace("_", "\n")
        parts.append(_cylinder(510, 340, 140, 50, cyl_label, cyl_fill, cyl_text, cyl_stroke))

        # Stage 8: HTML report
        parts.append(_arrow(650, 365, 700, 365, dim=False))
        parts.append(_rect(700, 340, 110, 50, "HTML\nreport", ACTIVE_FILL, ACTIVE_TEXT, ACTIVE_STROKE))

        # Status banner
        parts.append(_status_banner(40, 450, adapter_status, candidate_count))
    else:
        # not_routed path: arrow right to fallback
        parts.append(_arrow(340, 70, 510, 70, dim=False))
        parts.append(_rect(510, 40, 200, 60, "stdlib augment-design\nfallback path", DIM_FILL, "#495057", DIM_STROKE))
        parts.append(f'<text x="350" y="125" font-size="11" fill="#495057">no non-box constraints declared</text>')

    parts.append('</svg>')
    return "".join(parts)


def _rect(x: int, y: int, w: int, h: int, label: str, fill: str, text_color: str, stroke: str) -> str:
    cx = x + w / 2
    cy = y + h / 2
    lines = label.split("\n")
    text_blocks = "".join(
        f'<tspan x="{cx}" dy="{0 if i == 0 else 14}">{_escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" ry="6" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="{cx}" y="{cy - (len(lines) - 1) * 7 + 4}" text-anchor="middle" font-size="12" fill="{text_color}" font-family="-apple-system, system-ui, sans-serif">{text_blocks}</text>'
    )


def _cylinder(x: int, y: int, w: int, h: int, label: str, fill: str, text_color: str, stroke: str) -> str:
    ry = 6
    cx = x + w / 2
    cy = y + h / 2
    lines = label.split("\n")
    text_blocks = "".join(
        f'<tspan x="{cx}" dy="{0 if i == 0 else 14}">{_escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<rect x="{x}" y="{y + ry}" width="{w}" height="{h - 2 * ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<ellipse cx="{cx}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<ellipse cx="{cx}" cy="{y + h - ry}" rx="{w / 2}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="{cx}" y="{cy - (len(lines) - 1) * 7 + 4}" text-anchor="middle" font-size="12" fill="{text_color}" font-family="-apple-system, system-ui, sans-serif">{text_blocks}</text>'
    )


def _diamond(x: int, y: int, w: int, h: int, label: str, fill: str, text_color: str, stroke: str) -> str:
    cx = x + w / 2
    cy = y + h / 2
    points = f"{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}"
    lines = label.split("\n")
    text_blocks = "".join(
        f'<tspan x="{cx}" dy="{0 if i == 0 else 14}">{_escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="{cx}" y="{cy - (len(lines) - 1) * 7 + 4}" text-anchor="middle" font-size="12" fill="{text_color}" font-family="-apple-system, system-ui, sans-serif">{text_blocks}</text>'
    )


def _arrow(x1: float, y1: float, x2: float, y2: float, *, dim: bool, curved: bool = False) -> str:
    color = DIM_STROKE if dim else "#495057"
    marker = "arrowhead-dim" if dim else "arrowhead"
    if curved and y1 != y2:
        midy = (y1 + y2) / 2
        path = f"M{x1},{y1} C{x1},{midy} {x2},{midy} {x2},{y2}"
        return f'<path d="{path}" stroke="{color}" stroke-width="1.5" fill="none" marker-end="url(#{marker})"/>'
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#{marker})"/>'


def _status_banner(x: int, y: int, status: str, count: int) -> str:
    fill = SUCCESS_FILL if status == "executed" else FAILURE_FILL if status in {"not_available", "execution_failed", "translation_blocked"} else DECISION_FILL
    text_color = SUCCESS_TEXT if status == "executed" else FAILURE_TEXT if status in {"not_available", "execution_failed", "translation_blocked"} else "#212529"
    label = f"adapter_status: {status}"
    if status == "executed":
        label += f" — {count} feasible row{'s' if count != 1 else ''} emitted"
    return (
        f'<rect x="{x}" y="{y}" width="740" height="36" rx="4" fill="{fill}" stroke="none"/>'
        f'<text x="{x + 12}" y="{y + 23}" font-size="13" fill="{text_color}" font-family="-apple-system, system-ui, sans-serif" font-weight="500">{_escape(label)}</text>'
    )


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
