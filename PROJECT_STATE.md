# Project state

This file is the short operational entry point for humans and coding agents.
The research questions remain canonical in `docs/research_proposal.md`, and the
experimental procedure remains canonical in `docs/experimental_protocol.md`.

## Current phase

- Phase: `pre_pilot_scaffolding`
- Primary model: not selected
- Primary domain: not selected
- Confirmatory test set: not created or inspected
- End-to-end status: synthetic integration implemented; AgentDojo 0.1.35 API
  and three Banking v1.2.2 fixtures validated; Qwen3-8B int8 and Qwen3-4B BF16
  completed the three-fixture Windows GPU engineering shakedown on 2026-09-24.
  See `docs/experiment_logs/` for user-reported measurements and verification
  limits.

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
- AgentDojo fixture preflight: `make agentdojo-preflight`
- Windows GPU preflight: `make gpu-preflight`

## Known intentional gaps

- No selected primary model or formally adopted primary domain
- Qwen3-8B int8 and Qwen3-4B BF16 are shakedown candidates only
- Both GPU shakedowns are engineering-only; the formal integration gate
  and candidate-selection sample are not frozen
- No fitted action, argument, source-role, authority, or task-drift probe
- No confirmatory data and no research result
