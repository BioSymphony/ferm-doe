"""Single-file HTML reporter for ``bofire_strategy_report.json`` artifacts.

The reporter consumes the JSON emitted by
``adapters.bofire_strategy.plan_bofire_wave2`` and renders a
self-contained HTML page. Output is a single file with embedded CSS and
no external assets — suitable for email handoff, Slack drop, or
inclusion in a campaign dossier without breaking offline.

The renderer is stdlib-only. Charting libraries (Plotly, matplotlib) are
deliberately not imported here; the v1 surface is dense tabular HTML
with cost/feasibility verification computed inline. A v2 may add an
optional Plotly path behind ``[report]`` extras once a concrete charting
need lands.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import _charts, _pipeline_svg


CLAIM_LEVEL = "bofire_html_reporter_v1"

NON_CLAIM = (
    "This report renders BoFire-routed planning candidates. It does not "
    "validate assay readiness, scale transfer, or physical execution; "
    "BioSymphony readiness gates and dossier checks remain authoritative."
)


__all__ = [
    "CLAIM_LEVEL",
    "NON_CLAIM",
    "render_report",
    "render_to_string",
]


def render_report(
    report_path: str | Path,
    output_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> Path:
    """Render a BoFire strategy report JSON to a single-file HTML.

    Returns the output path written. The output is overwritten if it
    exists. ``manifest_path`` is optional; when provided, the manifest
    contents are embedded for cost-coefficient lookup and provenance.
    """

    report = json.loads(Path(report_path).read_text())
    manifest = (
        json.loads(Path(manifest_path).read_text()) if manifest_path is not None else None
    )
    html_text = render_to_string(report, manifest=manifest)
    out = Path(output_path)
    out.write_text(html_text, encoding="utf-8")
    return out


def render_to_string(
    report: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
) -> str:
    """Render a report dict to an HTML string. Pure function, no I/O."""

    context = _build_context(report, manifest)
    sections = [
        _section_header(context),
        _section_strategy_decision(context),
        _section_pipeline(context),
        _section_factor_table(context),
        _section_constraint_summary(context),
        _section_constraint_slice(context),
        _section_candidate_design(context),
        _section_cost_stack(context),
        _section_factor_heatmap(context),
        _section_provenance(context),
    ]
    body = "\n".join(filter(None, sections))
    return _shell(body=body, title=context["title"], jsonld=context["jsonld"])


# ----- context assembly -----


def _build_context(
    report: dict[str, Any], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    domain = report.get("domain_spec") or {}
    inputs = list(domain.get("inputs") or [])
    fidelity = domain.get("fidelity") or {}
    if isinstance(fidelity, dict) and fidelity.get("key"):
        inputs = inputs + [fidelity]
    constraints = list(domain.get("constraints") or [])
    rendered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = (
        f"BoFire campaign report — {report.get('campaign_id') or 'unnamed campaign'}"
    )

    factor_cost_lookup = _factor_cost_lookup(manifest or {})
    cost_constraint = _find_cost_constraint(constraints, factor_cost_lookup)
    carbon_constraint = _find_total_carbon_constraint(constraints)
    nchoosek_constraints = [c for c in constraints if c.get("type") == "nchoosek"]

    candidates = list(report.get("candidate_design") or [])
    enriched_rows = [
        _enrich_candidate_row(row, inputs, cost_constraint, carbon_constraint, nchoosek_constraints)
        for row in candidates
    ]

    jsonld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "SoftwareSourceCode",
            "name": "biosymphony-ferm-doe BoFire campaign report",
            "campaignId": report.get("campaign_id"),
            "claimLevel": report.get("claim_level"),
            "nonClaim": report.get("non_claim"),
            "dateCreated": rendered_at,
            "strategyKind": report.get("strategy_kind"),
            "adapterStatus": report.get("adapter_status"),
        },
        indent=2,
    )

    return {
        "title": title,
        "report": report,
        "manifest": manifest or {},
        "inputs": inputs,
        "constraints": constraints,
        "candidate_rows": enriched_rows,
        "cost_constraint": cost_constraint,
        "carbon_constraint": carbon_constraint,
        "nchoosek_constraints": nchoosek_constraints,
        "rendered_at": rendered_at,
        "jsonld": jsonld,
    }


def _factor_cost_lookup(manifest: dict[str, Any]) -> dict[str, float]:
    lookup: dict[str, float] = {}
    for factor in manifest.get("factors") or []:
        if not isinstance(factor, dict):
            continue
        fid = factor.get("factor_id")
        cost_kg = factor.get("cost_per_kg_usd_bulk")
        if fid and isinstance(cost_kg, (int, float)):
            lookup[str(fid)] = float(cost_kg) / 1000.0
    return lookup


def _find_cost_constraint(
    constraints: list[dict[str, Any]], factor_cost_lookup: dict[str, float]
) -> dict[str, Any] | None:
    for constraint in constraints:
        if constraint.get("type") != "linear":
            continue
        coefficients = dict(zip(constraint.get("features") or [], constraint.get("coefficients") or []))
        if not coefficients:
            continue
        if "cost" in str(constraint.get("id", "")).lower():
            return {
                "id": constraint["id"],
                "coefficients": coefficients,
                "rhs": float(constraint.get("rhs", 0.0)),
                "operator": constraint.get("operator", "<="),
            }
    if factor_cost_lookup:
        return {
            "id": "media_cost_from_manifest",
            "coefficients": factor_cost_lookup,
            "rhs": None,
            "operator": "informational",
        }
    return None


def _find_total_carbon_constraint(
    constraints: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for constraint in constraints:
        if constraint.get("type") != "linear":
            continue
        cid = str(constraint.get("id", "")).lower()
        if "carbon" not in cid:
            continue
        return {
            "id": constraint["id"],
            "features": list(constraint.get("features") or []),
            "rhs": float(constraint.get("rhs", 0.0)),
            "operator": constraint.get("operator", "<="),
        }
    return None


def _enrich_candidate_row(
    row: dict[str, Any],
    inputs: list[dict[str, Any]],
    cost_constraint: dict[str, Any] | None,
    carbon_constraint: dict[str, Any] | None,
    nchoosek_constraints: list[dict[str, Any]],
) -> dict[str, Any]:
    factor_values: dict[str, float] = {}
    for spec in inputs:
        key = spec.get("key")
        if not key:
            continue
        value = row.get(key)
        if isinstance(value, (int, float)):
            factor_values[key] = float(value)

    cost_per_L = None
    cost_pct = None
    cost_ok = None
    if cost_constraint:
        cost_per_L = sum(
            factor_values.get(name, 0.0) * coeff
            for name, coeff in cost_constraint["coefficients"].items()
        )
        rhs = cost_constraint.get("rhs")
        if rhs is not None and rhs > 0:
            cost_pct = 100.0 * cost_per_L / rhs
            cost_ok = cost_per_L <= rhs + 1e-6

    carbon_total = None
    carbon_ok = None
    if carbon_constraint and carbon_constraint["features"]:
        carbon_total = sum(
            factor_values.get(name, 0.0) for name in carbon_constraint["features"]
        )
        carbon_ok = carbon_total <= carbon_constraint["rhs"] + 1e-6

    nchoosek_violations: list[str] = []
    for constraint in nchoosek_constraints:
        features = list(constraint.get("features") or [])
        max_count = int(constraint.get("max_count", len(features)))
        min_count = int(constraint.get("min_count", 0))
        active = sum(1 for name in features if abs(factor_values.get(name, 0.0)) > 1e-6)
        if active > max_count or active < min_count:
            nchoosek_violations.append(
                f"{constraint.get('id')} (active={active}, allowed=[{min_count}, {max_count}])"
            )

    feasible = all(
        flag is not False for flag in (cost_ok, carbon_ok)
    ) and not nchoosek_violations

    return {
        "run_id": row.get("run_id", ""),
        "factor_values": factor_values,
        "cost_per_L_usd": cost_per_L,
        "cost_pct_of_budget": cost_pct,
        "cost_ok": cost_ok,
        "carbon_total": carbon_total,
        "carbon_ok": carbon_ok,
        "nchoosek_violations": nchoosek_violations,
        "feasible": feasible,
        "raw": row,
    }


# ----- section renderers -----


def _section_header(ctx: dict[str, Any]) -> str:
    report = ctx["report"]
    campaign_id = html.escape(str(report.get("campaign_id") or "unnamed-campaign"))
    claim_level = html.escape(str(report.get("claim_level") or "unspecified"))
    non_claim = html.escape(str(report.get("non_claim") or NON_CLAIM))
    return f"""
<header>
  <h1>{campaign_id}</h1>
  <div class="claim">claim_level: <code>{claim_level}</code></div>
  <div class="non-claim" role="alert">
    <strong>Non-claim:</strong> {non_claim}
  </div>
</header>
"""


def _section_strategy_decision(ctx: dict[str, Any]) -> str:
    report = ctx["report"]
    route = report.get("route") or {}
    reasons = ", ".join(str(r) for r in route.get("reasons") or []) or "<em>none</em>"
    strategy = html.escape(str(report.get("strategy_kind") or "not_routed"))
    status = html.escape(str(report.get("adapter_status") or "unknown"))
    budget = html.escape(str(report.get("remaining_run_budget") or "n/a"))
    issues = report.get("issues") or []
    issues_html = ""
    if issues:
        items = "\n".join(f"<li>{html.escape(str(issue))}</li>" for issue in issues)
        issues_html = f"<div class='issues'><strong>Issues:</strong><ul>{items}</ul></div>"
    return f"""
<section id="strategy">
  <h2>Strategy decision</h2>
  <dl class="kv">
    <dt>Strategy kind</dt><dd><code>{strategy}</code></dd>
    <dt>Adapter status</dt><dd><code class="status-{status}">{status}</code></dd>
    <dt>Route reasons</dt><dd>{reasons}</dd>
    <dt>Remaining run budget</dt><dd>{budget}</dd>
  </dl>
  {issues_html}
</section>
"""


def _section_factor_table(ctx: dict[str, Any]) -> str:
    rows: list[str] = []
    for spec in ctx["inputs"]:
        key = html.escape(str(spec.get("key") or ""))
        ftype = html.escape(str(spec.get("type") or ""))
        if spec.get("type") == "continuous":
            range_text = f"[{spec.get('low', '?')} – {spec.get('high', '?')}]"
        elif spec.get("type") == "discrete":
            range_text = "{" + ", ".join(str(v) for v in spec.get("values") or []) + "}"
        elif spec.get("type") in {"categorical", "task"}:
            range_text = "{" + ", ".join(str(v) for v in spec.get("categories") or []) + "}"
        else:
            range_text = "n/a"
        rows.append(
            f"<tr><td><code>{key}</code></td><td>{ftype}</td><td>{html.escape(range_text)}</td></tr>"
        )
    table = "\n".join(rows) or "<tr><td colspan='3'><em>no factors</em></td></tr>"
    return f"""
<section id="factors">
  <h2>Factors ({len(ctx['inputs'])})</h2>
  <table>
    <thead><tr><th>Factor</th><th>Type</th><th>Range / values</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</section>
"""


def _section_constraint_summary(ctx: dict[str, Any]) -> str:
    rows: list[str] = []
    for c in ctx["constraints"]:
        cid = html.escape(str(c.get("id") or ""))
        ctype = html.escape(str(c.get("type") or ""))
        if c.get("type") == "linear":
            features = list(c.get("features") or [])
            coeffs = list(c.get("coefficients") or [])
            op = html.escape(str(c.get("operator") or "<="))
            rhs = html.escape(str(c.get("rhs") or ""))
            terms = " + ".join(
                f"{coeffs[i]:.4g}·{html.escape(features[i])}" for i in range(len(features))
            )
            detail = f"<code>{terms} {op} {rhs}</code>"
        elif c.get("type") == "nchoosek":
            features = ", ".join(html.escape(str(f)) for f in c.get("features") or [])
            detail = (
                f"min_count={c.get('min_count', 0)}, max_count={c.get('max_count', '?')}, "
                f"features = [{features}]"
            )
        else:
            detail = html.escape(json.dumps({k: v for k, v in c.items() if k not in {"id", "type"}}))
        rows.append(f"<tr><td><code>{cid}</code></td><td>{ctype}</td><td>{detail}</td></tr>")
    table = "\n".join(rows) or "<tr><td colspan='3'><em>no constraints</em></td></tr>"
    return f"""
<section id="constraints">
  <h2>Constraints ({len(ctx['constraints'])})</h2>
  <table>
    <thead><tr><th>ID</th><th>Type</th><th>Detail</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</section>
"""


def _section_candidate_design(ctx: dict[str, Any]) -> str:
    inputs = ctx["inputs"]
    rows = ctx["candidate_rows"]
    if not rows:
        return """
<section id="candidates">
  <h2>Candidate design (0 rows)</h2>
  <p><em>No candidate rows. Check the strategy decision section for issues.</em></p>
</section>
"""

    factor_keys = [spec.get("key") for spec in inputs if spec.get("key")]
    factor_header = "".join(f"<th><code>{html.escape(str(k))}</code></th>" for k in factor_keys)
    has_cost = ctx["cost_constraint"] is not None
    has_carbon = ctx["carbon_constraint"] is not None
    has_nchoosek = bool(ctx["nchoosek_constraints"])

    verification_headers = ""
    if has_carbon:
        verification_headers += "<th>Σ carbon</th>"
    if has_cost:
        verification_headers += "<th>$/L</th><th>% budget</th>"
    if has_nchoosek:
        verification_headers += "<th>NchooseK ok</th>"
    verification_headers += "<th>Feasible</th>"

    body_rows: list[str] = []
    for enriched in rows:
        run_id = html.escape(str(enriched["run_id"]))
        cells = "".join(
            f"<td>{_format_factor_value(enriched['factor_values'].get(k))}</td>"
            for k in factor_keys
        )
        verification_cells = ""
        if has_carbon:
            ct = enriched["carbon_total"]
            cls = "ok" if enriched["carbon_ok"] else "bad" if enriched["carbon_ok"] is False else ""
            verification_cells += f"<td class='{cls}'>{_fmt_number(ct)}</td>"
        if has_cost:
            cpl = enriched["cost_per_L_usd"]
            pct = enriched["cost_pct_of_budget"]
            cls = "ok" if enriched["cost_ok"] else "bad" if enriched["cost_ok"] is False else ""
            verification_cells += (
                f"<td class='{cls}'>${_fmt_number(cpl, decimals=4)}</td>"
                f"<td class='{cls}'>{_fmt_number(pct, decimals=1)}%</td>"
            )
        if has_nchoosek:
            nck_ok = not enriched["nchoosek_violations"]
            cls = "ok" if nck_ok else "bad"
            label = "✓" if nck_ok else "✗"
            verification_cells += f"<td class='{cls}'>{label}</td>"
        feasible_cls = "ok" if enriched["feasible"] else "bad"
        feasible_label = "feasible" if enriched["feasible"] else "infeasible"
        verification_cells += f"<td class='{feasible_cls}'>{feasible_label}</td>"
        body_rows.append(
            f"<tr><td><code>{run_id}</code></td>{cells}{verification_cells}</tr>"
        )

    body = "\n".join(body_rows)
    feasible_count = sum(1 for r in rows if r["feasible"])
    feasibility_summary = f"{feasible_count}/{len(rows)} rows feasible"
    return f"""
<section id="candidates">
  <h2>Candidate design ({len(rows)} rows) — {feasibility_summary}</h2>
  <table class="candidate-design">
    <thead><tr><th>Run</th>{factor_header}{verification_headers}</tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>
"""


def _section_provenance(ctx: dict[str, Any]) -> str:
    report = ctx["report"]
    manifest = ctx["manifest"]
    rows = [
        ("Campaign ID", report.get("campaign_id")),
        ("Adapter kind", report.get("adapter_kind")),
        ("Schema version", report.get("schema_version")),
        ("Rendered at (UTC)", ctx["rendered_at"]),
        ("Manifest claim level", manifest.get("claim_level") if manifest else None),
        ("Manifest authored", (manifest.get("provenance") or {}).get("authored_on") if manifest else None),
    ]
    body = "\n".join(
        f"<dt>{html.escape(str(label))}</dt><dd><code>{html.escape(str(value or 'n/a'))}</code></dd>"
        for label, value in rows
    )
    raw_json = html.escape(json.dumps(report, indent=2))
    return f"""
<section id="provenance">
  <h2>Provenance</h2>
  <dl class="kv">{body}</dl>
  <details>
    <summary>Raw report JSON</summary>
    <pre><code>{raw_json}</code></pre>
  </details>
</section>
"""


def _section_pipeline(ctx: dict[str, Any]) -> str:
    svg = _pipeline_svg.render_pipeline_svg(ctx["report"])
    return f"""
<section id="pipeline">
  <h2>What ran (BoFire routing pipeline)</h2>
  <p>Manifest enters at the left; the highlighted strategy box is the
  path this run took. Status banner reports the adapter outcome.</p>
  <div class="svg-wrap">{svg}</div>
</section>
"""


def _section_constraint_slice(ctx: dict[str, Any]) -> str:
    if not _charts.is_available():
        return ""
    if not ctx["manifest"]:
        return ""
    fig_html = _charts.render_constraint_slice(
        ctx["report"], ctx["manifest"], include_plotlyjs=True
    )
    if not fig_html:
        return ""
    return f"""
<section id="constraint-slice">
  <h2>Feasibility slice (constraint visualization)</h2>
  <p>2D slice through the constraint hull. Green = feasible under the
  declared total-carbon and cost-budget constraints with every other
  factor held at its floor (or midpoint for induction factors). Red =
  infeasible. The dashed line is the total-carbon boundary; the dotted
  line is the cost-budget boundary.</p>
  {fig_html}
</section>
"""


def _section_cost_stack(ctx: dict[str, Any]) -> str:
    if not _charts.is_available():
        return ""
    rows = ctx["report"].get("candidate_design") or []
    if not rows or not ctx["manifest"]:
        return ""
    fig_html = _charts.render_cost_stack(
        ctx["report"], ctx["manifest"], include_plotlyjs=False
    )
    if not fig_html:
        return ""
    return f"""
<section id="cost-stack">
  <h2>Per-candidate cost stack ($/L breakdown)</h2>
  <p>Each bar is one candidate row. Each segment is the
  <code>$/L</code> contribution from one media component, color-coded
  by category. The dashed line is the cost budget. Hover any segment
  to see the exact contribution.</p>
  {fig_html}
</section>
"""


def _section_factor_heatmap(ctx: dict[str, Any]) -> str:
    if not _charts.is_available():
        return ""
    rows = ctx["report"].get("candidate_design") or []
    if not rows or not ctx["manifest"]:
        return ""
    fig_html = _charts.render_factor_heatmap(
        ctx["report"], ctx["manifest"], include_plotlyjs=False
    )
    if not fig_html:
        return ""
    return f"""
<section id="factor-heatmap">
  <h2>Design coverage heatmap</h2>
  <p>Each column is a candidate; each row is a factor. Color is the
  factor value normalized to its declared box bounds (0 = floor, 1 =
  ceiling). Reveals coverage gaps and which factors the optimizer
  pushed to extremes versus held near the middle.</p>
  {fig_html}
</section>
"""


def _format_factor_value(value: Any) -> str:
    if value is None:
        return "<span class='dim'>—</span>"
    if isinstance(value, (int, float)):
        if abs(value) < 1e-6:
            return "<span class='dim'>0</span>"
        return _fmt_number(value)
    return html.escape(str(value))


def _fmt_number(value: Any, decimals: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if abs(value) >= 100:
            return f"{value:.{max(0, decimals - 1)}f}"
        return f"{value:.{decimals}f}"
    return str(value)


def _shell(*, body: str, title: str, jsonld: str) -> str:
    escaped_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      max-width: 1100px;
      margin: 2rem auto;
      padding: 0 1.5rem;
      line-height: 1.5;
      color: #1a1a1a;
      background: #fafafa;
    }}
    h1, h2 {{ font-weight: 600; }}
    h1 {{ margin: 0 0 .25rem; font-size: 1.4rem; }}
    h2 {{ margin: 2rem 0 .5rem; font-size: 1.1rem; border-bottom: 1px solid #ddd; padding-bottom: .25rem; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9em; }}
    pre {{ background: #f0f0f0; padding: .75rem; overflow-x: auto; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: .5rem 0; font-size: .85rem; }}
    th, td {{ border: 1px solid #ddd; padding: .25rem .5rem; text-align: left; }}
    th {{ background: #efefef; font-weight: 600; }}
    tr:nth-child(even) td {{ background: #f7f7f7; }}
    td.ok {{ background: #e7f5e7; color: #1a5d1a; font-weight: 500; }}
    td.bad {{ background: #ffe7e7; color: #8a1a1a; font-weight: 600; }}
    .non-claim {{
      background: #fff4ec;
      border-left: 4px solid #c44;
      padding: .5rem .75rem;
      margin: .75rem 0 1rem;
      font-size: .9rem;
    }}
    .claim {{ color: #555; font-size: .85rem; margin-bottom: .25rem; }}
    .dim {{ color: #888; }}
    dl.kv {{ display: grid; grid-template-columns: max-content 1fr; gap: .25rem 1rem; margin: .5rem 0 1rem; }} /* audit-skip: runpod_identifier CSS grid template, not a provider identifier */
    dl.kv dt {{ color: #666; }}
    dl.kv dd {{ margin: 0; }}
    .issues {{ background: #fff7e0; border-left: 4px solid #d99e00; padding: .5rem .75rem; margin: .5rem 0; }}
    details {{ margin-top: .5rem; }}
    details > summary {{ cursor: pointer; color: #555; font-size: .85rem; }}
    .status-executed {{ color: #1a5d1a; }}
    .status-not_available, .status-not_routed, .status-translation_blocked, .status-execution_failed {{ color: #8a1a1a; }}
    .svg-wrap {{ overflow-x: auto; padding: .5rem 0; }}
    .svg-wrap svg {{ max-width: 100%; height: auto; display: block; margin: 0 auto; }}
    section > p {{ color: #495057; font-size: .92rem; max-width: 60em; }}
  </style>
</head>
<body>
{body}
<script type="application/ld+json">
{jsonld}
</script>
</body>
</html>
"""
