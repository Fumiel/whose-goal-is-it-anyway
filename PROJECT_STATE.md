# Project state

This file is the short operational entry point for humans and coding agents.
The research questions remain canonical in `docs/research_proposal.md`, and the
experimental procedure remains canonical in `docs/experimental_protocol.md`.

## Current phase

- Phase: `exploratory_pilot_post_lead`
- Primary model: not selected
- Primary domain: not selected
- Provisional exploratory pilot: Qwen3-8B int8 on AgentDojo Banking v1.2.2;
  see `docs/decisions/2026-09-24_provisional_qwen3_8b_banking_pilot.md`.
- Initial pilot sample: frozen by RDR-2026-10-01-03. Tasks 14/0/3/4/2/12,
  four task families, maximum 90 conditions (6 clean / 72 IPI / 12 controls),
  with an 18-condition lead stage. The declared relationship graph has one
  connected component; all conditions are pilot_only and test-excluded.
  See [pilot preparation](docs/banking_pilot_v1.md). The lead 18 conditions ran
  on 2026-10-06. Audited strict clean success was 2/6, so the frozen lead gate
  failed; 18 audits and 12 fixed-prefix diagnostics were complete, with no
  technical failures or unresolved disagreements. The immutable lead report is
  `artifacts/pilot-lead-report-2026-10-06.json`. RDR-2026-10-07-01 authorizes
  the remaining 72 as a post-result exploratory continuation, without changing
  the failed gate or task 12's baseline-failure label. This is 60 IPI and 12
  lexical controls, with no additional clean conditions. Continuation ran under
  commit `b7df23f41b47b0eae529ebe261d46d41ab29701c` and stopped at condition
  51 when actual capture exceeded the frozen 12 GiB GPU ceiling. At that stop,
  50 conditions were complete, one was a technical failure, and 39 were not run.
  See [technical stop log](docs/experiment_logs/2026-10-07_post_gate_continuation_technical_stop.md).
  RDR-2026-10-07-02は保存済み51番prefixでのGPU工学計測を根拠に、12 GiB上限を
  維持したCUDAキャッシュ解放と、旧失敗を保持する51～90の専用再開経路を決定した。
  code commit `9fa8985ace6642e466f334524054cad61656675b`と新runtime freezeで
  51番の新試行と52～90を完了した。全90条件はcompleted、総attemptは91。
  recovery stageは`awaiting_human_audit`、追加の技術停止はない。
  [再開実行記録](docs/experiment_logs/2026-10-07_pilot_gpu_recovery_execution.md)を参照。
- Pilot runner: implemented with separate actual-trajectory/fixed-prefix paths,
  immutable partial failures, native/strict labels, checksummed audits and staged
  gates. Synthetic orchestration tests cover all 90 conditions. On 2026-10-02,
  native model-free controls passed for all 90 conditions after a pilot-only YAML
  escaping fix; fixed-tokenizer positions passed for all 90 native fixed prefixes.
  The installed Transformers `sdpa` path does not provide Attention weights,
  and full `eager` Attention exceeded the 12 GiB ceiling. RDR-2026-10-02-01
  specifies last-query recomputation, a 16/16 IPI window, score-only fixed
  diagnostics and four separate derived full-sequence residual captures.
  Engineering GPU checks of the revised path passed. Task 14's pre-pilot
  suspicion review was approved on 2026-10-02 for transaction ID 4, with a
  strict rubric fixed in `data/audits/2026-10-02_task14_password_suspicion_review.json`.
  The lead-stage runtime freeze is recorded separately under
  `artifacts/pilot-runtime.freeze.json`; the continuation and recovery each used
  a separate runtime freeze tied to their execution code.
  See [initial measurements](docs/experiment_logs/2026-10-02_pilot_preflight_measurements.md)
  and [capture repair](docs/experiment_logs/2026-10-02_capture_repair_preflight.md).
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

Before the post-gate exploratory continuation:

1. The seven-condition Banking selection gate remains fixed. The current
   `configs/selection/integration_gate.freeze.json` records the corrected
   runner commit used for the completed rerun. The audit and report are complete;
   keep their failures and non-blind audit status visible.
2. Verify `configs/experiments/banking_pilot_v1.freeze.json`. Sample, stop rules,
   audit specification and pilot exclusions are frozen. Native model-free controls,
   fixed-prefix token-position checks and basic GPU preflight passed on 2026-10-02.
   Attention capture and detailed-save resource choices are documented by
   RDR-2026-10-02-01 and implemented for preflight. Task 14 human review is
   approved using the [evidence packet](docs/experiment_logs/2026-10-02_task14_preexecution_review_packet.md)
   and [fixed rubric](data/audits/2026-10-02_task14_password_suspicion_review.json).
   The chosen token-position/capture rules and runtime code/config checksums
   are frozen separately in `artifacts/pilot-runtime.freeze.json`.
   The 8B/Banking combination is provisional only.
3. Keep all shakedown, candidate-selection, pilot, and tuning families and close
   variants out of confirmatory test. Existing families may be rerun for the
   exploratory pilot; old shakedown bundles remain engineering-only.
4. The initial pilot inventory has four task families and one connected
   component, with prior-use/test exclusions retained. Report task families
   separately from the highest-level split/inference groups; the
   feasibility of 30 confirmatory clusters is unresolved. Keep tasks 5 and 6
   on hold for success-rate and main-analysis sampling until evaluator handling
   is specified. Audit task 11's recipient-insensitive utility before use, and
   record how new families will be designed and divided between development
   and confirmatory evaluation. Complete the graph, evaluator validation and
   final split by Phase 3; all new test families need not be finished before
   the pilot starts. See
   [RDR-2026-10-01-01](docs/decisions/2026-10-01_banking_task_feasibility_review.md)
   and [RDR-2026-10-01-02](docs/decisions/2026-10-01_existing_tasks_pilot_new_families_test.md).
5. Preserve the 2026-10-06 lead report's failed gate and all six clean labels.
   The post-gate continuation stopped at condition 51 under the frozen GPU ceiling;
   RDR-2026-10-07-02 authorized the separate recovery stage, which completed
   condition 51 as a2 and the 39 previously unrun conditions. Old bundles remain
   immutable. Expansion human audit is outstanding. The 90-condition collection
   remains exploratory and does not automatically authorize Phase 2 or test.

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
- Offline pilot freeze verification: `PYTHONPATH=src python3 -m goal_takeover.datasets.pilot_sample configs/experiments/banking_pilot_v1.freeze.json`
- Pilot native preflight: `goal-takeover pilot-preflight configs/experiments/banking_pilot_v1.yaml`
- Pilot runner/report/audit commands and runtime freeze contract: [runner usage](docs/pilot_runner.md)
- Derived pilot detail capture: `goal-takeover pilot-detail-capture configs/experiments/banking_pilot_detail_v1.yaml --run-prefix <pilot-prefix>` after the lead stage
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
- Pilot lead stage completed with 2/6 strict clean success and a failed frozen
  continuation gate. The authorized post-gate exploratory continuation recorded
  32 new completions and stopped at condition 51 due to the 12 GiB GPU ceiling;
  the separately authorized recovery collected condition 51 as a2 and the 39
  previously unrun conditions. All 90 conditions have complete bundles; expansion
  audit and verified supply of unseen Banking clusters remain outstanding.
  Tasks 5/6 remain on
  hold, and task 11 requires recipient audit.
- New development/test families, their AgentDojo compatibility and evaluator
  validation, and their final connected-component split are not implemented.
- No confirmatory data and no research result
