PYTHON ?= python3
EXAMPLE ?= examples/demo-xylanase-public

.PHONY: help test validate-demo validate-all assay-power-demo contract-check doctor inspect-demo catalog-demo brief-demo show-warnings \
        tool-registry-check adaptive-backend-surface table-contracts-check \
        bofire-smoke entmoot-smoke public-audit markdown-links secret-scan secret-scan-required \
        secret-scan-optional release-check \
        public-ready clean

help:
	@echo "BioSymphony Ferm DoE - common make targets"
	@echo ""
	@echo "  Sharing gate (run before opening a PR or publishing):"
	@echo "    make public-ready           release-check + required gitleaks scan"
	@echo "    make release-check          tests, validators, contract checks, public-release scan"
	@echo ""
	@echo "  Tests and validators:"
	@echo "    make test                   unittest discover under tests/"
	@echo "    make validate-all           validate every top-level public example"
	@echo "    make validate-demo          validate \$$EXAMPLE (default: examples/demo-xylanase-public)"
	@echo "    make contract-check         validate task-request template + compact dossier"
	@echo "    make tool-registry-check    validate docs/tool-registry.json"
	@echo "    make adaptive-backend-surface  validate docs/adaptive-backend-evaluation.json"
	@echo "    make table-contracts-check  validate CSV table contracts"
	@echo ""
	@echo "  Inspect a campaign:"
	@echo "    make doctor                 capability and adapter readiness report"
	@echo "    make inspect-demo           summarize the closed-loop demo campaign"
	@echo "    make catalog-demo           catalog every example campaign"
	@echo "    make brief-demo             build an agent kickoff brief"
	@echo "    make show-warnings          run the diagnostic-warnings walkthrough"
	@echo ""
	@echo "  Optional adapter smokes (use the matching pip extra):"
	@echo "    make bofire-smoke           BoFire DoEStrategy smoke (needs [bofire])"
	@echo "    make entmoot-smoke          ENTMOOT NChooseK smoke (needs [entmoot])"
	@echo ""
	@echo "  Public-safety scans:"
	@echo "    make public-audit           ferm-doe audit ."
	@echo "    make markdown-links         local Markdown link resolver"
	@echo "    make secret-scan            gitleaks (required for public-ready)"
	@echo "    make secret-scan-optional   gitleaks if installed; skip cleanly otherwise"
	@echo ""
	@echo "  Housekeeping:"
	@echo "    make clean                  remove build, cache, and runtime artifacts"

test:
	$(PYTHON) -m unittest discover -s tests

validate-demo:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate $(EXAMPLE)

validate-all:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-xylanase-public --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-scale-bridge-public --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-split-plot-fedbatch-public --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-warnings-walkthrough-public --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-pb-screening-public --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-media-cost-bofire --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-shakeflask-to-2l-bofire --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/engine-multi-arm-scale-transfer-public --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/reference-doe-custom-design --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/xylanase-wxz1-2012 --summary
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/yeast-isoprenoid-2l-fedbatch --summary

assay-power-demo:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli assay-power examples/demo-xylanase-public

doctor:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli doctor

inspect-demo:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli inspect-campaign examples/demo-pb-screening-public

catalog-demo:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli list-campaigns examples

brief-demo:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli agent-brief examples/demo-pb-screening-public --goal "Plan a safe follow-up fermentation DOE campaign."

contract-check:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate-task-request templates/task_request.template.json
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli check-dossier examples/demo-xylanase-public

tool-registry-check:
	PYTHONPATH=src $(PYTHON) skills/biosymphony-ferm-doe/scripts/tool_registry_check.py docs/tool-registry.json

adaptive-backend-surface:
	PYTHONPATH=src $(PYTHON) skills/biosymphony-ferm-doe/scripts/adaptive_backend_surface_check.py docs/adaptive-backend-evaluation.json

table-contracts-check:
	PYTHONPATH=src $(PYTHON) skills/biosymphony-ferm-doe/scripts/table_contracts.py

bofire-smoke:
	PYTHONPATH=src $(PYTHON) skills/biosymphony-ferm-doe/scripts/run_bofire_smoke.py \
		--manifest examples/demo-media-cost-bofire/campaign_manifest.json \
		--out-json /tmp/bofire-media-report.json \
		--out-html /tmp/bofire-media-report.html \
		--budget 12 --seed 42

entmoot-smoke:
	cd examples/entmoot-nchoosek-smoke && $(PYTHON) smoke.py

show-warnings:
	@echo "Diagnostic walkthrough (exits 0, surfaces warnings):"
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli validate examples/demo-warnings-walkthrough-public --summary

public-audit:
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli audit .

markdown-links:
	$(PYTHON) scripts/check_markdown_links.py .

secret-scan: secret-scan-required

secret-scan-required:
	@if ! command -v gitleaks >/dev/null 2>&1; then \
		echo "ERROR: gitleaks is required for public-ready secret scanning."; \
		echo "Install gitleaks or run 'make secret-scan-optional' only for local diagnostics."; \
		exit 2; \
	fi
	gitleaks detect --source . --no-banner --redact --verbose
	gitleaks dir . --no-banner --redact --verbose

secret-scan-optional:
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks detect --source . --no-banner --redact --verbose; \
		gitleaks dir . --no-banner --redact --verbose; \
	else \
		echo "gitleaks not installed; skipping optional local diagnostic secret scan."; \
	fi

release-check: test validate-all assay-power-demo contract-check tool-registry-check adaptive-backend-surface public-audit markdown-links
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli inspect-campaign examples/demo-pb-screening-public --out /tmp/biosymphony-inspect-demo.json
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli list-campaigns examples --out /tmp/biosymphony-campaign-catalog.json
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.cli agent-brief examples/demo-pb-screening-public --goal "Plan a safe follow-up fermentation DOE campaign." --out /tmp/biosymphony-agent-brief.json --md-out /tmp/biosymphony-agent-brief.md
	PYTHONPATH=src $(PYTHON) -m biosymphony_ferm_doe.public_release \
		README.md AGENTS.md pyproject.toml CHANGELOG.md NON_CLAIMS.md Makefile noxfile.py .gitignore \
		BIOSAFETY.md SECURITY.md CONTRIBUTING.md CITATION.cff .github agents deploy scripts \
		assets/images/biosymphony-agent-loop.svg assets/images/experiment-design-map.png \
		assets/images/scale-transfer-criteria.png assets/images/doe-family-selector.png \
		docs/README.md docs/AGENT_QUICKSTART.md docs/USE_CASES.md docs/WORKFLOWS.md docs/ORCHESTRATOR_BOUNDARY.md docs/PUBLIC_ADOPTION_PATH.md \
		docs/VISUAL_OVERVIEW.md docs/PUBLIC_SECURITY_MODEL.md docs/RELEASE_READINESS_CHECKLIST.md docs/ISSUE_PACK_COOKBOOK.md docs/superpowers.md \
		docs/diagrams docs/PUBLIC_RELEASE_PREP.md docs/TOOL_REGISTRY.md docs/SCALE_BRIDGE.md docs/SCALE_BRIDGE_METHODOLOGY.md \
		docs/ADAPTIVE_WAVE2.md docs/CONTRACTS.md docs/DOE_FAMILIES.md docs/PROFILES.md docs/SWARMS_AND_EVIDENCE.md \
		docs/BOFIRE_POSITIONING.md docs/BOFIRE_CONSTRAINT_PATTERNS.md docs/ENTMOOT_SWAP_DESIGN.md \
		docs/COST_MODEL_REALISM_CHECK.md docs/dossier-generation.md \
		docs/OPEN_DATA_PUBLICATION_STRATEGY.md docs/SIMULATOR_V2_SPEC.md \
		docs/BIOMANUFACTURING_ADAPTIVE_BACKENDS.md docs/adaptive-backend-evaluation.json docs/schemas schemas \
		docs/BACKEND_EVAL_FINDINGS.md docs/ADAPTER_DESIGN_NOTES.md \
		examples/demo-xylanase-public examples/demo-scale-bridge-public examples/demo-split-plot-fedbatch-public \
		examples/demo-warnings-walkthrough-public examples/demo-pb-screening-public \
		examples/demo-media-cost-bofire examples/demo-shakeflask-to-2l-bofire \
		examples/entmoot-nchoosek-smoke examples/adaptive-backend-eval examples/engine-multi-arm-scale-transfer-public \
		examples/reference-doe-custom-design examples/xylanase-wxz1-2012 examples/yeast-isoprenoid-2l-fedbatch \
		examples/starter-studies

public-ready: release-check secret-scan-required

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
	rm -rf build dist .runtime .nox
