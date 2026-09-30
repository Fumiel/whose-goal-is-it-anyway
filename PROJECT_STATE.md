# Project state

This file is the short operational entry point for humans and coding agents.
The research questions remain canonical in `docs/research_proposal.md`, and the
experimental procedure remains canonical in `docs/experimental_protocol.md`.

## Current phase

- Phase: `pre_pilot_scaffolding`
- Primary model: not selected
- Primary domain: not selected
- Provisional exploratory pilot: Qwen3-8B int8 on AgentDojo Banking v1.2.2;
  see `docs/decisions/2026-09-24_provisional_qwen3_8b_banking_pilot.md`.
- Confirmatory test set: not created or inspected
- Task allocation: use existing Banking families, including previously used
  selection/shakedown families, in fresh exploratory pilot runs. Design new
  semantic families alongside the pilot and assign connected components to
  development (training / validation) or held-out confirmatory test. See
  [RDR-2026-10-01-02](docs/decisions/2026-10-01_existing_tasks_pilot_new_families_test.md).
- Banking task inventory: all 16 native user tasks reviewed against the pinned
  AgentDojo 0.1.35 source on 2026-10-01; see
  [task candidates](docs/banking_task_candidates_2026-10-01.md). The conservative
  proposal has eight task families without composite task 15, before attack
  edges and prior-use exclusions. These are not validated independent clusters.
  Source-function no-op checks found utility positives for tasks 5 and 6;
  native-suite evaluator validation remains outstanding.
- End-to-end status: synthetic integration implemented; AgentDojo 0.1.35 API
  and three Banking v1.2.2 fixtures validated; Qwen3-8B int8 and Qwen3-4B BF16
  completed the three-fixture Windows GPU engineering shakedown on 2026-09-24.
  A subsequent WSL-side raw-bundle audit checked all eight bundles, including
  the technical failure; see `docs/experiment_logs/2026-09-24_shakedown_raw_audit.md`
  for measurements and verification limits. The runtime prefix checks passed,
  but the three consumer input sequences cannot be independently reconstructed
  from raw artifacts alone. The failure bundle lacks Git metadata and is not
  linked from the later successful runs.
- The first formal seven-condition selection execution produced 14 immutable
  bundles under `banking-selection-20260924-001`. Their checksums and scoring
  records were internally consistent, but the selection runner omitted final
  answers and raw generations. The required blind audit cannot be completed
  from those bundles. Both candidates were rerun with new IDs after the
  provenance-only runner correction; no primary model is selected.
- The corrected `banking-selection-20260924-002` produced 14 complete audit
  traces. The researcher completed a non-blind self-audit after seeing
  model-level aggregates. Both candidates failed the frozen selection gate:
  8B clean success was 3/5 and 4B was 2/5; the report selected no model.

## Current gate

Before starting new exploratory pilot runs:

1. The seven-condition Banking selection gate remains fixed. The current
   `configs/selection/integration_gate.freeze.json` records the corrected
   runner commit used for the completed rerun. The audit and report are complete;
   keep their failures and non-blind audit status visible.
2. Fix the pilot sample, stop and transition rules, and split exclusions before
   collecting new runs. The 8B/Banking combination is provisional only.
3. Keep all shakedown, candidate-selection, pilot, and tuning families and close
   variants out of confirmatory test. Existing families may be rerun for the
   exploratory pilot; old shakedown bundles remain engineering-only.
4. Before fixing the pilot sample, inventory task and attack relationships,
   prior-use relationships, and the resulting connected components. Report task
   families separately from the highest-level split/inference groups; the
   feasibility of 30 confirmatory clusters is unresolved. Keep tasks 5 and 6
   on hold for success-rate and main-analysis sampling until evaluator handling
   is specified. Audit task 11's recipient-insensitive utility before use, and
   record how new families will be designed and divided between development
   and confirmatory evaluation. Complete the graph, evaluator validation and
   final split by Phase 3; all new test families need not be finished before
   the pilot starts. See
   [RDR-2026-10-01-01](docs/decisions/2026-10-01_banking_task_feasibility_review.md)
   and [RDR-2026-10-01-02](docs/decisions/2026-10-01_existing_tasks_pilot_new_families_test.md).

A pre-gate, non-selection engineering shakedown is allowed only under
`RDR-2026-09-22-01`. It may be used for interface debugging and resource
measurement, but not for behavioral threshold setting or candidate ranking.
RDR-2026-10-01-02 partially revises the later family exclusion rule to allow
fresh pilot runs; it does not change the completed selection gate or permit
reuse of engineering bundles as research data.

## Stable entry points

- Fast checks: `make check-fast`
- Full checks after development dependencies are installed: `make check`
- Validate repository declarations: `make validate`
- Synthetic immutable-run dry run: `make dry-run`
- AgentDojo fixture preflight: `make agentdojo-preflight`
- Seven-condition selection preflight: `goal-takeover selection-preflight configs/selection/integration_gate.yaml`
- Windows GPU preflight: `make gpu-preflight`

## Known intentional gaps

- No selected primary model or formally adopted primary domain; the 8B/Banking
  pilot configuration is provisional.
- Qwen3-8B int8 and Qwen3-4B BF16 are evaluated selection candidates; neither
  has been adopted as the primary model.
- Both GPU shakedowns are engineering-only. The first formal selection run is
  incomplete for audit and must not be used for model adoption. The complete
  rerun and human review did not produce a passing candidate.
- No fitted action, argument, source-role, authority, or task-drift probe
- No frozen pilot sample or verified supply of independent unseen Banking
  clusters; native tasks 5 and 6 cannot yet support a meaningful clean-success
  count, and task 11 requires recipient-level audit.
- New development/test families, their AgentDojo compatibility and evaluator
  validation, and their final connected-component split are not implemented.
- No confirmatory data and no research result
