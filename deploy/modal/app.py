"""Modal endpoint for biosymphony-ferm-doe Bayesian-optimization follow-up.

Deploys the BoTorch ``plan_bo_wave2`` adapter as a serverless function on
Modal. CPU is the default and is fast enough for typical follow-up batches
(n_runs ≤ 200). Flip ``gpu="A10G"`` (or A100 for very large portfolios) on
the ``@app.function`` decorator when historical campaign portfolios push
n past ~1000.

Same Python module that ships in the package — adapters/botorch_wave2.py.
The deployment surface changes; the algorithm doesn't.

Deploy:

    modal deploy deploy/modal/app.py

Invoke (from any client that can speak HTTPS):

    curl -X POST https://your-app.modal.run/v1/plan-bo-wave2 \\
      -H "Content-Type: application/json" \\
      -H "Authorization: Bearer <runtime token>" \\
      -d '{ "manifest": {...}, "results": [...], "args": {...} }'

Or via Modal's Python SDK:

    plan_bo_wave2.remote(manifest, results, n_candidates=3)
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Any

from fastapi import Header, HTTPException
import modal

# Image: stdlib + torch + botorch + gpytorch. No CUDA needed for CPU mode.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.115,<1",
        "torch>=2.0,<3",
        "botorch>=0.9,<1",
        "gpytorch>=1.11,<2",
        "biosymphony-ferm-doe[botorch]==0.1.0a0",
    )
)

app = modal.App("biosymphony-ferm-doe-bo")

MAX_REQUEST_BYTES = 1_000_000
MAX_RESULT_ROWS = 1_000
MAX_CANDIDATES = 50
MAX_RESTARTS = 25
MAX_RAW_SAMPLES = 1_024


@app.function(
    image=image,
    cpu=2,
    memory=4096,
    timeout=300,
    secrets=[modal.Secret.from_name("biosymphony-ferm-doe-api")],
)
@modal.web_endpoint(method="POST")
def plan_bo_wave2_endpoint(payload: dict, authorization: str | None = Header(default=None)) -> dict:
    """Web endpoint wrapping the BoTorch follow-up planner.

    ``payload`` shape:

        {
          "manifest": {...},
          "results": [{"design_run_id": "D1", "x1": ..., "y": ...}, ...],
          "args": {
            "n_candidates": 3,
            "acquisition": "qei" | "qucb",
            "primary_response_id": "y",
            "seed": 0,
            "num_restarts": 10,
            "raw_samples": 256,
            "ucb_beta": 0.1
          }
        }
    """
    expected_token = os.environ.get("FERM_DOE_API_TOKEN", "")
    if not _authorized(authorization, expected_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    from biosymphony_ferm_doe.adapters import botorch_wave2

    manifest, results, args = _validated_payload(payload)

    return botorch_wave2.plan_bo_wave2(
        manifest,
        results,
        n_candidates=_bounded_int(args.get("n_candidates"), 3, minimum=1, maximum=MAX_CANDIDATES, field="args.n_candidates"),
        acquisition=args.get("acquisition", "qei"),
        primary_response_id=args.get("primary_response_id"),
        seed=_bounded_int(args.get("seed"), 0, minimum=0, maximum=2_147_483_647, field="args.seed"),
        num_restarts=_bounded_int(args.get("num_restarts"), 10, minimum=1, maximum=MAX_RESTARTS, field="args.num_restarts"),
        raw_samples=_bounded_int(args.get("raw_samples"), 256, minimum=16, maximum=MAX_RAW_SAMPLES, field="args.raw_samples"),
        ucb_beta=args.get("ucb_beta", 0.1),
    )


def _authorized(header_value: str | None, expected_token: str) -> bool:
    if not expected_token or not header_value:
        return False
    scheme, _, supplied = header_value.partition(" ")
    if scheme.lower() != "bearer" or not supplied:
        return False
    return hmac.compare_digest(supplied.strip(), expected_token)


def _validated_payload(payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object.")
    request_bytes = len(json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"))
    if request_bytes > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Request is too large.")
    manifest = payload.get("manifest")
    results = payload.get("results")
    args = payload.get("args") or {}
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=422, detail="manifest must be a JSON object.")
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise HTTPException(status_code=422, detail="results must be a list of JSON objects.")
    if len(results) > MAX_RESULT_ROWS:
        raise HTTPException(status_code=413, detail="Too many result rows for this public scaffold.")
    if not isinstance(args, dict):
        raise HTTPException(status_code=422, detail="args must be a JSON object when provided.")
    acquisition = args.get("acquisition", "qei")
    if acquisition not in {"qei", "qucb"}:
        raise HTTPException(status_code=422, detail="args.acquisition must be qei or qucb.")
    return manifest, results, args


def _bounded_int(value: Any, default: int, *, minimum: int, maximum: int, field: str) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{field} must be an integer.") from None
    if parsed < minimum or parsed > maximum:
        raise HTTPException(status_code=422, detail=f"{field} must be between {minimum} and {maximum}.")
    return parsed


# To run with GPU instead of CPU, copy the function above and apply:
#
#   @app.function(image=image, gpu="A10G", memory=8192, timeout=300)
#   @modal.web_endpoint(method="POST")
#   def plan_bo_wave2_endpoint_gpu(payload: dict) -> dict:
#       ...
#
# Modal mounts a CUDA-enabled torch automatically when gpu=... is set.
# The BoTorch adapter does not need code changes — torch picks GPU when
# the default device is CUDA. For our scale (n < 200) the GPU buys
# nothing; flip it on once you have campaign portfolios past n ~1000.
