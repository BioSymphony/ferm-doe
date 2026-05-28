# Biosafety

This skill plans fermentation, cell culture, and upstream bioprocess campaigns in pre-experiment planning mode. It does not perform biosafety review, IBC oversight, or compliance certification. Operators remain responsible for their institutional biosafety processes.

## Scope

The skill's role: surface biosafety-relevant questions during planning and record the operator's answers in the manifest's `assumptions[]` block.

The operator's role: institutional biosafety review (IBC), compliance with national and local frameworks, organism risk classification, and the final go / no-go decision on whether to run the campaign.

## When the agent asks about biosafety

The agent surfaces a focused biosafety question when the manifest signals biorisk-relevant context. Routine industrial workhorse campaigns run without any biosafety prompt. Triggers:

- **Organism**: the host is outside the routine industrial workhorse set (E. coli K-12, S. cerevisiae, P. pastoris / K. phaffii, CHO-K1, HEK293, B. subtilis 168, common brewers' and bakers' yeast strains).
- **Genetic modification**: recombinant DNA is present, the campaign expresses heterologous proteins, or selection markers and resistance genes appear in the factor list.
- **Scale**: the campaign declares a scale-up endpoint beyond bench (`scale_context.to_scale.working_volume_l > ~100`).
- **Response targets**: the campaign measures phenotypes whose characterization is governed by the operator's IBC review.
- **Free-text signals**: manifest fields contain language indicating high-containment work, dual-use research of concern, or organisms on national select-agent and restricted-organism lists.

When any trigger fires, the agent asks one paragraph of questions about containment level, IBC approval status, and frameworks consulted. The agent records the answer in `assumptions[]` and proceeds. When no trigger fires, the agent stays silent on biosafety.

This list lives in this document rather than in validator code so contributors can propose additions via PR. The validator does not gate on biosafety status.

## Frameworks worth referencing

The skill does not embed compliance logic for any of these. They are pointers for operators planning campaigns that the heuristic above flags.

- WHO Laboratory Biosafety Manual, 4th edition
- NIH Guidelines for Research Involving Recombinant or Synthetic Nucleic Acid Molecules
- Biosafety in Microbiological and Biomedical Laboratories (BMBL), CDC and NIH
- NIH Policy for Oversight of Dual Use Research of Concern and Pathogens with Enhanced Pandemic Potential (2024)
- National select-agent and restricted-organism lists (e.g., CDC HHS, USDA APHIS, and equivalent national authorities)
- The operator's institutional biosafety committee (IBC) and applicable local jurisdiction rules

## Reporting biosafety concerns about this codebase

If a contribution introduces patterns that look like a biosafety problem (restricted organism names in public demos, agent prompts that discourage biosafety review, demos that model unsafe practice), please report it via GitHub's private vulnerability reporting flow described in [`SECURITY.md`](SECURITY.md) rather than as a public issue.

## See also

- [`NON_CLAIMS.md`](NON_CLAIMS.md) for the full list of scope boundaries.
- [`skills/biosymphony-ferm-doe/SKILL.md`](skills/biosymphony-ferm-doe/SKILL.md) for the agent loop, including the biosafety-relevant context step.
