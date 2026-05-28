"""Nox lanes for BioSymphony Ferm DoE repository checks."""

from __future__ import annotations

import sys

import nox


nox.options.sessions = ["unit", "table_contracts", "tool_registry", "adaptive_backend_surface", "dossier_smoke"]


@nox.session(python=False)
def quick(session: nox.Session) -> None:
    """Fast local confidence lane for routine repo edits."""

    session.notify("unit")
    session.notify("table_contracts")
    session.notify("tool_registry")
    session.notify("adaptive_backend_surface")


@nox.session(python=False)
def public_release(session: nox.Session) -> None:
    """Run public-release scrub checks over the public-facing source areas."""

    session.run(sys.executable, "scripts/check_markdown_links.py", ".")
    session.run("make", "secret-scan-required", external=True)
    session.notify("release_check")


@nox.session(python="3.11")
def unit(session: nox.Session) -> None:
    """Run the stdlib/unit test suite."""

    session.install("-e", ".[dev]")
    session.run("python", "-m", "pytest", "tests", *session.posargs)


@nox.session(python="3.11")
def table_contracts(session: nox.Session) -> None:
    """Validate Frictionless-compatible CSV contracts with the stdlib validator."""

    session.install("-e", ".")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/table_contracts.py",
        "--out",
        ".runtime/validation/table-contracts-report.json",
    )


@nox.session(python="3.11")
def tool_registry(session: nox.Session) -> None:
    """Validate the curated external-tool registry."""

    session.install("-e", ".")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/tool_registry_check.py",
        "docs/tool-registry.json",
        "--out",
        ".runtime/validation/tool-registry-report.json",
        "--md-out",
        ".runtime/validation/tool-registry-summary.md",
    )


@nox.session(python="3.11")
def adaptive_backend_surface(session: nox.Session) -> None:
    """Validate the public adaptive-backend selection and fixture matrix."""

    session.install("-e", ".")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py",
        "docs/adaptive-backend-evaluation.json",
        "--out",
        ".runtime/validation/adaptive-backend-surface-report.json",
    )


@nox.session(python="3.11")
def adaptive_backend_live_imports(session: nox.Session) -> None:
    """Install optional adaptive backends and require live imports."""

    session.install("-e", ".[adaptive,backend-eval,entmoot,omlt,dev]")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py",
        "docs/adaptive-backend-evaluation.json",
        "--live-imports",
        "--out",
        ".runtime/validation/adaptive-backend-live-imports-report.json",
    )


@nox.session(python="3.11")
def dossier_smoke(session: nox.Session) -> None:
    """Compile a public demo dossier and run dossier/contract checks."""

    out_dir = ".runtime/dossier-smoke/xylanase"
    session.install("-e", ".[dev]")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py",
        "--manifest",
        "examples/demo-xylanase-public/campaign_manifest.json",
        "--out",
        out_dir,
        "--run-budget",
        "8",
    )
    session.run("python", "skills/biosymphony-ferm-doe/scripts/dossier_check.py", out_dir)
    session.run("python", "skills/biosymphony-ferm-doe/scripts/ferm_doe_contract_self_check.py", out_dir)


@nox.session(python="3.11")
def scale_bridge_dossier(session: nox.Session) -> None:
    """Compile and check the shake-flask to 2 L scale-bridge dossier."""

    out_dir = ".runtime/dossier-smoke/shakeflask-to-2l"
    session.install("-e", ".[dev]")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/compile_ferm_doe_dossier.py",
        "--manifest",
        "examples/demo-shakeflask-to-2l-bofire/campaign_manifest.json",
        "--out",
        out_dir,
    )
    session.run("python", "skills/biosymphony-ferm-doe/scripts/dossier_check.py", out_dir)
    session.run("python", "skills/biosymphony-ferm-doe/scripts/ferm_doe_contract_self_check.py", out_dir)


@nox.session(python="3.11")
def adaptive_smoke(session: nox.Session) -> None:
    """Run BoFire route/translation smokes without installing BoFire."""

    session.install("-e", ".[report]")
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/run_bofire_smoke.py",
        "--manifest",
        "examples/demo-media-cost-bofire/campaign_manifest.json",
        "--out-json",
        ".runtime/adaptive-smoke/media/bofire_strategy_report.json",
        "--out-html",
        ".runtime/adaptive-smoke/media/bofire_strategy_report.html",
        "--out-hashes",
        ".runtime/adaptive-smoke/media/artifact_hashes.json",
        "--budget",
        "12",
        "--seed",
        "42",
    )
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/run_bofire_smoke.py",
        "--manifest",
        "examples/demo-shakeflask-to-2l-bofire/campaign_manifest.json",
        "--results",
        "examples/demo-shakeflask-to-2l-bofire/inputs/historical_run_ledger.csv",
        "--out-json",
        ".runtime/adaptive-smoke/scale-bridge/bofire_strategy_report.json",
        "--out-html",
        ".runtime/adaptive-smoke/scale-bridge/bofire_strategy_report.html",
        "--out-hashes",
        ".runtime/adaptive-smoke/scale-bridge/artifact_hashes.json",
        "--budget",
        "2",
        "--seed",
        "42",
    )


@nox.session(python="3.11")
def adaptive_live(session: nox.Session) -> None:
    """Install heavy adaptive extras and run live optional-adapter tests."""

    session.install("-e", ".[bofire,report,dev]")
    session.run(
        "python",
        "-m",
        "unittest",
        "tests.test_optional_adapters.BofireMediaCostLiveExecutionTests",
        "-v",
    )
    session.run(
        "python",
        "skills/biosymphony-ferm-doe/scripts/run_bofire_smoke.py",
        "--manifest",
        "examples/demo-media-cost-bofire/campaign_manifest.json",
        "--out-json",
        ".runtime/adaptive-live/media/bofire_strategy_report.json",
        "--out-html",
        ".runtime/adaptive-live/media/bofire_strategy_report.html",
        "--out-hashes",
        ".runtime/adaptive-live/media/artifact_hashes.json",
        "--budget",
        "12",
        "--seed",
        "42",
        "--require-executed",
        "--require-candidates",
    )


@nox.session(python="3.11")
def release_check(session: nox.Session) -> None:
    """Run the stdlib public-release scanner over public-facing source areas."""

    session.install("-e", ".")
    session.run(
        "python",
        "-m",
        "biosymphony_ferm_doe.public_release",
        "README.md",
        "AGENTS.md",
        "pyproject.toml",
        "CHANGELOG.md",
        "NON_CLAIMS.md",
        "Makefile",
        "noxfile.py",
        ".gitignore",
        "BIOSAFETY.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CITATION.cff",
        ".github",
        "agents",
        "deploy",
        "scripts",
        "assets/images/biosymphony-agent-loop.svg",
        "docs/README.md",
        "docs/AGENT_QUICKSTART.md",
        "docs/USE_CASES.md",
        "docs/WORKFLOWS.md",
        "docs/PUBLIC_ADOPTION_PATH.md",
        "docs/PUBLIC_SECURITY_MODEL.md",
        "docs/RELEASE_READINESS_CHECKLIST.md",
        "docs/ISSUE_PACK_COOKBOOK.md",
        "docs/superpowers.md",
        "docs/diagrams",
        "docs/PUBLIC_RELEASE_PREP.md",
        "docs/TOOL_REGISTRY.md",
        "docs/SCALE_BRIDGE.md",
        "docs/SCALE_BRIDGE_METHODOLOGY.md",
        "docs/ADAPTIVE_WAVE2.md",
        "docs/CONTRACTS.md",
        "docs/DOE_FAMILIES.md",
        "docs/PROFILES.md",
        "docs/SWARMS_AND_EVIDENCE.md",
        "docs/BOFIRE_POSITIONING.md",
        "docs/BOFIRE_CONSTRAINT_PATTERNS.md",
        "docs/ENTMOOT_SWAP_DESIGN.md",
        "docs/COST_MODEL_REALISM_CHECK.md",
        "docs/dossier-generation.md",
        "docs/OPEN_DATA_PUBLICATION_STRATEGY.md",
        "docs/SIMULATOR_V2_SPEC.md",
        "docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md",
        "docs/adaptive-backend-evaluation.json",
        "docs/schemas",
        "schemas",
        "examples/demo-xylanase-public",
        "examples/demo-scale-bridge-public",
        "examples/demo-split-plot-fedbatch-public",
        "examples/demo-warnings-walkthrough-public",
        "examples/demo-pb-screening-public",
        "examples/demo-media-cost-bofire",
        "examples/demo-shakeflask-to-2l-bofire",
        "examples/entmoot-nchoosek-smoke",
        "examples/adaptive-backend-eval",
        "examples/engine-multi-arm-scale-transfer-public",
        "examples/reference-doe-custom-design",
        "examples/xylanase-wxz1-2012",
        "examples/yeast-isoprenoid-2l-fedbatch",
        "examples/starter-studies",
    )
