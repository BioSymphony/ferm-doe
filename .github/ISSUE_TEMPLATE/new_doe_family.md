---
name: New DoE family
about: Propose a new design family
title: "[family] "
labels: ["family-proposal"]
---

## Family name

Snake_case (`d_optimal_with_blocks`, `mixture_process_combined`, etc.).

## When to use

What problem does this family solve that the current set does not?

## Reference

Standard reference (Montgomery, Jones & Nachtsheim, Cornell, Box-Hunter-Hunter, etc.). DOI or canonical link.

## Minimum-runs formula

Closed form if computable; "user_declared" if it depends on parameters the schema does not carry.

## Required structural fields

Resolution? Alias structure? Mixture components? Hard-to-change factors? Previous wave reference?

## Replication / center-point expectations

What does a well-formed instance of this family include?

## Statistical claim level

What `doe.claim` value should default for this family: `exact`, `adapter_backed`, `approximate`, or `heuristic`?

## Validator behavior

What checks would the validator run against a manifest declaring this family? Each check id and severity (warning vs error).

## Adapter

If a DoE adapter (statsmodels, pyDOE3, custom) generates this family today, link it. If not, note that.
