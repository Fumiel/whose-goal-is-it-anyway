# Project state

This file is the short operational entry point for humans and coding agents.
The research questions remain canonical in `docs/research_proposal.md`, and the
experimental procedure remains canonical in `docs/experimental_protocol.md`.

## Current phase

- Phase: `pre_pilot_scaffolding`
- Primary model: not selected
- Primary domain: not selected
- Confirmatory test set: not created or inspected
- End-to-end status: synthetic integration implemented; real-model and
  AgentDojo adapters are not yet validated

## Current gate

Before formally evaluating candidate models or domains:

1. Fill and freeze `configs/selection/integration_gate.yaml`.
2. Record candidate revisions and the frozen gate in a new RDR.
3. Keep all candidate-selection and pilot families out of the confirmatory test
   split.

A pre-gate, non-selection engineering shakedown is allowed only under
`RDR-2026-09-22-01`. It may be used for interface debugging and resource
measurement, but not for behavioral threshold setting or candidate ranking.

## Stable entry points

- Fast checks: `make check-fast`
- Full checks after development dependencies are installed: `make check`
- Validate repository declarations: `make validate`
- Synthetic immutable-run dry run: `make dry-run`

## Known intentional gaps

- No selected Hugging Face model revision
- No validated AgentDojo domain adapter
- No fitted action, argument, source-role, authority, or task-drift probe
- No confirmatory data and no research result
