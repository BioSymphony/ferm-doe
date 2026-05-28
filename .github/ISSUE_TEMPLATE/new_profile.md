---
name: New profile
about: Propose a new campaign profile
title: "[profile] "
labels: ["profile-proposal"]
---

## Profile name

Snake_case, descriptive, verb-or-noun-shaped (`scale_down_qualification`, `sequential_augmentation`, `confirmation`).

## When to use

Concrete scenarios. At least three.

## Required blocks

What manifest blocks become errors when absent under this profile? Keep this list short; required blocks should reflect structural inability to do what the profile claims.

## Advised blocks

What blocks emit warnings when absent? Most things go here.

## Advised inputs

What input files does this profile expect to consume?

## Advised expected artifacts

What outputs should the agent produce by default?

## Default DoE families

Which design families fit this profile? List 2-4.

## Profile-specific structural requirements

Anything else unique to this profile? E.g., `factor_hard_to_change_required`, `recapitulation_criterion_required`, `previous_wave_ref_required`.

## Public demo

Do you intend to ship a `examples/demo-<profile>-public/` campaign with this profile? If yes, sketch what it would show.

## Why not extend an existing profile

Why is this a new profile rather than a variant of `screening`, `optimization_rsm`, or `custom`?
