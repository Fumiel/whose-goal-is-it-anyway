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
  A subsequent WSL-side raw-bundle audit checked all eight bundles, including
  the technical failure; see `docs/experiment_logs/2026-09-24_shakedown_raw_audit.md`
  for measurements and verification limits. The runtime prefix checks passed,
  but the three consumer input sequences cannot be independently reconstructed
  from raw artifacts alone. The failure bundle lacks Git metadata and is not
  linked from the later successful runs.

## Current gate

Before formally evaluating candidate models or domains:

1. The seven-condition Banking selection gate is frozen in
   `configs/selection/integration_gate.freeze.json` and the accompanying RDR.
   Run `selection-preflight` and the formal selection runner on the frozen clean
   commit before evaluating the candidate models.
2. Keep all candidate-selection and pilot families out of the confirmatory test
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
- Seven-condition selection preflight: `goal-takeover selection-preflight configs/selection/integration_gate.yaml`
- Windows GPU preflight: `make gpu-preflight`

## Known intentional gaps

- No selected primary model or formally adopted primary domain
- Qwen3-8B int8 and Qwen3-4B BF16 are shakedown candidates only
- Both GPU shakedowns are engineering-only; the formal seven-condition
  selection has not been executed
- No fitted action, argument, source-role, authority, or task-drift probe
- No confirmatory data and no research result
