"""Sampling-plan generator for fed-batch / perfusion campaigns.

Public API: :func:`compute_sampling_plan`, :func:`render_sampling_markdown`.

Reads the manifest's ``responses[]`` and an optional ``sampling_policy``
block, and emits a per-sample schedule plus totals (sample count, volume
removed, samples per response, samples per culture phase). The plan is
*planning support* — actual sampling burden depends on assay throughput,
robotics, and ELN scheduling that live outside this skill.

Inputs:

- ``responses[]`` with ``response_id``, ``assay_required``,
  ``measurement_type`` (``assayed`` / ``instrument`` / ``derived`` /
  ``clock``). Only ``assayed`` and ``instrument`` responses receive a
  schedule entry; ``derived`` and ``clock`` are skipped.
- Optional ``sampling_policy`` on the manifest, with shape:

  ```json
  {
    "run_duration_h": 48,
    "phases": [
      {"name": "lag", "start_h": 0, "end_h": 4},
      {"name": "log", "start_h": 4, "end_h": 24},
      {"name": "late_log", "start_h": 24, "end_h": 40},
      {"name": "stationary", "start_h": 40, "end_h": 48}
    ],
    "responses": [
      {
        "response_id": "titer_g_l",
        "frequency_h": 4,
        "active_window_h": [4, 48],
        "sample_volume_ml": 1.0
      }
    ]
  }
  ```

  When ``sampling_policy`` is absent, the skill uses heuristic defaults:
  ``run_duration_h = 48``, three phases (lag 0-4, active 4-40,
  stationary 40-48), every assayed response sampled every 4 hours
  starting at ``start_h = 4`` with ``sample_volume_ml = 1.0``.

Output is labeled ``claim_level: sampling_plan_planning``.
"""

from __future__ import annotations

from typing import Any, Iterable

CLAIM_LEVEL = "sampling_plan_planning"
NON_CLAIM = (
    "Sampling plan is a planning schedule. Actual sampling cadence depends "
    "on assay throughput, robotics availability, and operator judgment. "
    "Confirm volumes against working volume before locking the plan."
)

DEFAULT_FREQUENCY_H = 4.0
DEFAULT_SAMPLE_VOLUME_ML = 1.0
DEFAULT_RUN_DURATION_H = 48.0
DEFAULT_PHASES: list[dict[str, Any]] = [
    {"name": "lag", "start_h": 0.0, "end_h": 4.0},
    {"name": "active", "start_h": 4.0, "end_h": 40.0},
    {"name": "stationary", "start_h": 40.0, "end_h": 48.0},
]
SAMPLEABLE_MEASUREMENT_TYPES = frozenset({"assayed", "instrument"})


def compute_sampling_plan(
    manifest: dict[str, Any],
    *,
    run_duration_h: float | None = None,
    default_frequency_h: float = DEFAULT_FREQUENCY_H,
    default_sample_volume_ml: float = DEFAULT_SAMPLE_VOLUME_ML,
) -> dict[str, Any]:
    """Build a sampling schedule from the manifest's responses + policy."""
    policy = manifest.get("sampling_policy") if isinstance(manifest.get("sampling_policy"), dict) else {}
    duration = float(run_duration_h or policy.get("run_duration_h") or DEFAULT_RUN_DURATION_H)
    phases = _phases(policy, duration)
    response_settings = _response_settings(manifest, policy, duration, default_frequency_h, default_sample_volume_ml)

    samples: list[dict[str, Any]] = []
    sample_counter = 0
    warnings: list[str] = []

    for setting in response_settings:
        rid = setting["response_id"]
        freq = setting["frequency_h"]
        window_start, window_end = setting["active_window_h"]
        volume = setting["sample_volume_ml"]
        if freq <= 0:
            warnings.append(f"response_{rid}_frequency_h_must_be_positive_skipped")
            continue
        if window_end <= window_start:
            warnings.append(f"response_{rid}_active_window_invalid_skipped")
            continue
        steps: list[float] = []
        t = window_start
        while t <= window_end + 1e-9:
            steps.append(round(t, 6))
            t += freq
        for time_h in steps:
            sample_counter += 1
            phase = _phase_for_time(time_h, phases)
            samples.append(
                {
                    "sample_id": f"S{sample_counter:04d}",
                    "time_h": time_h,
                    "response_id": rid,
                    "phase": phase["name"] if phase else None,
                    "sample_volume_ml": volume,
                    "rationale": setting["rationale"],
                }
            )

    samples.sort(key=lambda s: (s["time_h"], s["sample_id"]))

    samples_per_response: dict[str, int] = {}
    samples_per_phase: dict[str, int] = {phase["name"]: 0 for phase in phases}
    samples_per_phase["unphased"] = 0
    total_volume = 0.0
    for sample in samples:
        samples_per_response[sample["response_id"]] = samples_per_response.get(sample["response_id"], 0) + 1
        phase_name = sample.get("phase") or "unphased"
        samples_per_phase[phase_name] = samples_per_phase.get(phase_name, 0) + 1
        total_volume += float(sample["sample_volume_ml"])

    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "run_duration_h": duration,
        "phases": phases,
        "responses": response_settings,
        "samples": samples,
        "totals": {
            "n_samples": len(samples),
            "total_volume_ml": round(total_volume, 4),
            "samples_per_response": samples_per_response,
            "samples_per_phase": samples_per_phase,
        },
        "warnings": warnings,
    }


def render_sampling_markdown(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Sampling plan")
    lines.append("")
    lines.append(f"- Claim level: `{plan['claim_level']}`")
    lines.append(f"- Run duration: `{plan['run_duration_h']} h`")
    lines.append(f"- Phases: " + ", ".join(f"`{p['name']}` ({p['start_h']}–{p['end_h']} h)" for p in plan["phases"]))
    lines.append("")
    totals = plan["totals"]
    lines.append(f"- Total samples: `{totals['n_samples']}`")
    lines.append(f"- Total volume drawn: `{totals['total_volume_ml']} mL`")
    lines.append("")
    lines.append("## Samples per response")
    lines.append("")
    lines.append("| Response | Frequency h | Window | Volume mL | n_samples |")
    lines.append("|---|---|---|---|---|")
    for setting in plan["responses"]:
        n = totals["samples_per_response"].get(setting["response_id"], 0)
        window = setting["active_window_h"]
        lines.append(
            f"| `{setting['response_id']}` | {setting['frequency_h']} | "
            f"{window[0]}–{window[1]} h | {setting['sample_volume_ml']} | {n} |"
        )
    lines.append("")
    lines.append("## Schedule preview (first 20)")
    lines.append("")
    lines.append("| sample_id | time_h | response | phase | volume_mL |")
    lines.append("|---|---|---|---|---|")
    for sample in plan["samples"][:20]:
        lines.append(
            f"| `{sample['sample_id']}` | {sample['time_h']} | `{sample['response_id']}` | "
            f"`{sample.get('phase', '-')}` | {sample['sample_volume_ml']} |"
        )
    if len(plan["samples"]) > 20:
        lines.append(f"| ... | | | | ({len(plan['samples']) - 20} more rows) |")
    lines.append("")
    if plan["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        for warn in plan["warnings"]:
            lines.append(f"- `{warn}`")
        lines.append("")
    lines.append(f"> {plan['non_claim']}")
    lines.append("")
    return "\n".join(lines)


# =====================================================================
# Helpers
# =====================================================================


def _phases(policy: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    declared = policy.get("phases")
    if isinstance(declared, list) and declared:
        out: list[dict[str, Any]] = []
        for entry in declared:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or "phase"
            start = float(entry.get("start_h", 0.0))
            end = float(entry.get("end_h", duration))
            out.append({"name": name, "start_h": start, "end_h": end})
        return out
    if duration >= DEFAULT_RUN_DURATION_H:
        return [
            {"name": "lag", "start_h": 0.0, "end_h": 4.0},
            {"name": "active", "start_h": 4.0, "end_h": max(duration - 8.0, 4.0)},
            {"name": "stationary", "start_h": max(duration - 8.0, 4.0), "end_h": duration},
        ]
    if duration >= 12.0:
        return [
            {"name": "lag", "start_h": 0.0, "end_h": min(2.0, duration / 4.0)},
            {"name": "active", "start_h": min(2.0, duration / 4.0), "end_h": duration},
        ]
    return [{"name": "active", "start_h": 0.0, "end_h": duration}]


def _response_settings(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    duration: float,
    default_frequency_h: float,
    default_sample_volume_ml: float,
) -> list[dict[str, Any]]:
    declared_per_response = {
        item.get("response_id"): item
        for item in (policy.get("responses") or [])
        if isinstance(item, dict) and item.get("response_id")
    }
    out: list[dict[str, Any]] = []
    for response in manifest.get("responses") or []:
        if not isinstance(response, dict):
            continue
        rid = response.get("response_id")
        if not rid:
            continue
        measurement = str(response.get("measurement_type", "")).lower()
        if measurement and measurement not in SAMPLEABLE_MEASUREMENT_TYPES:
            continue
        if not measurement and not response.get("assay_required"):
            continue
        decl = declared_per_response.get(rid, {})
        freq = float(decl.get("frequency_h", default_frequency_h))
        window = decl.get("active_window_h")
        if isinstance(window, list) and len(window) == 2:
            active_window = (float(window[0]), float(window[1]))
        else:
            active_window = (4.0, duration) if duration > 4.0 else (0.0, duration)
        volume = float(decl.get("sample_volume_ml", default_sample_volume_ml))
        rationale = "policy_declared" if rid in declared_per_response else f"default_frequency_{freq:g}h_for_{measurement or 'assayed'}_response"
        out.append(
            {
                "response_id": rid,
                "frequency_h": freq,
                "active_window_h": [active_window[0], active_window[1]],
                "sample_volume_ml": volume,
                "rationale": rationale,
                "measurement_type": measurement or "assayed",
            }
        )
    return out


def _phase_for_time(time_h: float, phases: list[dict[str, Any]]) -> dict[str, Any] | None:
    for phase in phases:
        if phase["start_h"] - 1e-9 <= time_h <= phase["end_h"] + 1e-9:
            return phase
    return None


__all__ = ["compute_sampling_plan", "render_sampling_markdown", "CLAIM_LEVEL", "NON_CLAIM"]
