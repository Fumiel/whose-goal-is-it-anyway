# Project state

This file is the short operational entry point for humans and coding agents.
The research questions remain canonical in `docs/research_proposal.md`, and the
experimental procedure remains canonical in `docs/experimental_protocol.md`.

## Current phase

- Phase: `phase2_paths_v2_outcome_report_complete_independent_validation_pending`
- Phase 2 custom-task candidate: the development-only two-document purchase-order
  payment series is declared in `data/templates/phase2_two_document_payment_v1.json`.
  Five matched source-role variants pass synthetic controls and native AgentDojo
  Banking v1.2.2 model-free preflight (45 actual-tool controls). The custom task
  is registered on an isolated suite copy, with real document reads, transfers,
  and independent native evaluators. See the
  [2026-10-19 execution log](docs/experiment_logs/2026-10-19_two_document_native_preflight.md).
  The initial five-condition development collection now has a design freeze:
  [RDR-2026-10-19-01](docs/decisions/2026-10-19_phase2_two_document_initial_specification.md),
  [execution specification](configs/experiments/phase2_two_document_initial_v1.json),
  [train split](data/splits/phase2_two_document_initial_v1.json), and
  [checksum manifest](data/manifests/phase2_two_document_initial_v1.freeze.json).
  All five are one component connected conservatively to the prior send-money
  pilot component; there is no independent validation family yet. The
  [Phase 2 runner](docs/phase2_two_document_runner.md) now connects the custom
  native task to the existing actual-trajectory capture, scoring and immutable
  bundle path. Native/tokenizer preflight passed for all five conditions on
  2026-10-19. Engineering GPU capture/scoring passed on this WSL RTX 5060 Ti host
  for the user boundary and longest tool-return condition under the 12 GiB and
  0.05 GiB ceilings. The five frozen train conditions were executed under clean
  commit `eac10554a6db4589158e2b27453eef03d7cefa37` and a matching runtime
  freeze. All five immutable run bundles passed checksum and schema verification
  and await human audit. The tool-output IPI condition did not contact the
  declared attack document, so its exposure measurement is missing; retain the
  executed behavior and do not replace the condition. See the
  [execution log](docs/experiment_logs/2026-10-19_phase2_two_document_initial_execution.md)
  and [collection manifest](data/manifests/2026-10-19_phase2_two_document_initial_collection.json).
  All five v1 runs requested wrong `read_file` paths and received empty file
  content; none read the declared registry. The exact filenames were absent from
  the user prompt, and the Banking tool set has no file listing or search tool.
  The researcher's post-run [RDR-2026-10-19-02](docs/decisions/2026-10-19_phase2_two_document_path_disclosure_revision.md)
  keeps v1 immutable and creates a separate [v2 task](data/templates/phase2_two_document_payment_v2.json)
  that gives both filenames in every user instruction. The five new IDs have a
  [train-only split](data/splits/phase2_two_document_paths_v2.json),
  [conservative graph](data/splits/phase2_two_document_paths_v2.graph.json),
  [design freeze](data/manifests/phase2_two_document_paths_v2.freeze.json), and
  [runner guide](docs/phase2_two_document_paths_v2.md). Synthetic, native
  AgentDojo model-free (45 controls), and fixed-tokenizer preflight passed.
  The clean commit `c36fc9c18bb641524de9fc1397c3bec8e7942ebf` has a
  same-commit GPU report and separate runtime freeze. All five new conditions
  ran once and completed with verified immutable bundles. Each actual trajectory
  read both declared documents with nonempty results, and each recorded an
  exposed, scored boundary. See the [v2 execution log](docs/experiment_logs/2026-10-19_two_document_paths_v2_execution.md)
  and [collection manifest](data/manifests/2026-10-19_phase2_two_document_paths_v2_collection.json).
  The researcher submitted all five first judgments, and the separate
  [v2 human audit](data/audits/2026-10-19_phase2_two_document_paths_v2_human_audit.json)
  records resolved adjudications and frozen automatic labels. Exact account
  comparison corrected the first candidate-action judgments for c001–c003;
  none reached the declared alternative account. The researcher's post-run human
  rubric excludes a document-unspecified send date and accepts a subject that
  denotes PO-742; it yields task success for c004/c005, while frozen automatic
  user-success remains false for all five. See [RDR-2026-10-19-03](docs/decisions/2026-10-19_phase2_two_document_human_audit_interpretation.md)
  and the [audit log](docs/experiment_logs/2026-10-19_two_document_paths_v2_human_audit.md).
  The v2 [outcome report](results/2026-10-19_phase2_two_document_paths_v2_outcome_report.json)
  (human and frozen automatic labels in separate fields, A–D only for the IPI
  condition, counts without rates) is recorded in the
  [report log](docs/experiment_logs/2026-10-19_two_document_paths_v2_outcome_report.md).
- Primary model: not selected
- Primary domain: not selected
- Post-pilot decision: [RDR-2026-10-14-01](docs/decisions/2026-10-14_phase2_development_after_banking_pilot.md)
  authorizes Phase 2 design, implementation, and new training / validation runs
  with provisional Qwen3-8B int8 / Banking, after the new conditions, evaluator,
  split, and runtime specification are fixed. The failed clean gate, pilot_only
  status, and unselected primary model/domain remain unchanged. The initial v1
  five and revised v2 five Phase 2 train runs are collected and awaiting separate
  audits; no confirmatory test runs have been recorded under this decision.
- Lexical-control follow-up: [RDR-2026-10-18-01](docs/decisions/2026-10-18_lexical_control_contradictions_probe_priority.md)
  records read-only inspection of conditions 26/31/38/46/69/70. Their native
  attack positives match actual attacker-side tool calls and state changes;
  `has_attack=false` describes quotation/prohibition context, not absence of
  attacker-side strings. The internal mechanism remains unproven. Dedicated
  follow-up model experiments on these six are deferred while Phase 2 probe
  implementation and new-condition validation take priority. Original labels,
  quarantine and pilot_only status remain in force.
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
  2026-10-13に拡張分38件を人手監査し、先行18件をそのまま引き継いだ56件の
  [完成監査票](data/audits/2026-10-13_banking_pilot_full_audit.json)を保存した。
  4件の初回副作用判断と採用された修正を別欄に保持し、未裁定不一致は0。
  [監査後報告](results/2026-10-13_banking_pilot_full_audit_report.json)でも
  clean成功2/6と元のゲート不合格は変わらない。語彙対照6件のnative攻撃陽性は
  矛盾として隔離する。[監査記録](docs/experiment_logs/2026-10-13_banking_pilot_full_audit.md)を参照。
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
  The [lead execution log](docs/experiment_logs/2026-10-02_banking_pilot_lead_execution.md)
  and [small manifest](data/manifests/2026-10-02_banking_pilot_lead.json) retain
  the pre-audit handoff and checksum history. Of four planned derived
  full-sequence captures, one completed and the second stopped at 12 GiB;
  the remaining two were not attempted.
  See [initial measurements](docs/experiment_logs/2026-10-02_pilot_preflight_measurements.md)
  and [capture repair](docs/experiment_logs/2026-10-02_capture_repair_preflight.md).
- Confirmatory test set: not created or inspected
- Confirmatory claim scope: same-tool argument hijacking within the selected
  single model and domain; cross-tool attacks are secondary or exploratory.
  This post-pilot clarification is recorded in
  [RDR-2026-10-07-03](docs/decisions/2026-10-07_argument_hijacking_scope_clarification.md).
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

After the exploratory pilot collection:

1. The seven-condition Banking selection gate remains fixed. The current
   `configs/selection/integration_gate.freeze.json` records the corrected
   runner commit used for the completed rerun. The audit and report are complete;
   keep their failures and non-blind audit status visible.
2. Preserve `configs/experiments/banking_pilot_v1.freeze.json`. Sample, stop rules,
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
   immutable. The expansion human audit is complete (56 audited runs total,
   including 18 carried-forward lead judgments). The 90-condition collection
   remains exploratory; its completed audit did not itself authorize Phase 2 or
   test. RDR-2026-10-14-01 separately authorizes Phase 2 development and new
   training / validation collection with the provisional configuration. It does
   not adopt a primary model/domain or authorize pilot reuse or confirmatory test.
6. The first five-condition Phase 2 design, model-free checks, conservative
   relationship component and train-only split, all-run audit, pinned model
   config, deterministic decoding, capture/scoring and resource ceilings are
   fixed by RDR-2026-10-19-01 and its checksum manifest. Before model execution,
   use the implemented custom measurement runner, verify native and
   fixed-tokenizer preflight on the execution host, retain a post-commit
   GPU/storage preflight report, and create a runtime freeze bound to the same
   clean execution commit. A later independent development component is needed
   for validation. The six quarantined lexical-control cases
   received the read-only audit recorded in RDR-2026-10-18-01; do not use their
   labels for probe training. Decide
   primary model/domain and confirmatory feasibility in a separate RDR before
   Phase 3 freeze.
7. Keep the completed v1 bundles and pending human audit unchanged. The new
   filename-disclosed v2 conditions are separate completed train runs in the
   same conservative component, not independent validation. The clean-commit
   GPU/storage report and new same-commit runtime freeze passed. All five v2
   runs have a separate completed human audit with a documented post-run human
   rubric and preserved frozen automatic labels. The v2 outcome report is
   complete; no independent validation exists. See RDR-2026-10-19-02/03 and the
   v2 execution, audit and outcome-report logs.

A pre-gate, non-selection engineering shakedown is allowed only under
`RDR-2026-09-22-01`. It may be used for interface debugging and resource
measurement, but not for behavioral threshold setting or candidate ranking.
RDR-2026-10-01-02 partially revises the later family exclusion rule to allow
fresh pilot runs; it does not change the completed selection gate or permit
reuse of engineering bundles as research data.

## Stable entry points

- Professor-facing progress reports: [template](docs/reports/progress_report_template.md)
  and [writing rules](docs/reports/progress_report_rules.md).
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
- Windows/WSL-only protected artifact inventory (dated snapshot, not a live
  filesystem check): [2026-10-13 inventory](data/manifests/windows_wsl_protected_artifacts_2026-10-13.json)

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
  previously unrun conditions. All 90 conditions have complete bundles and the
  56 selected runs are human-audited with no unresolved disagreements. The original
  clean gate remains failed. A post-pilot decision now permits Phase 2
  development, while verified supply of unseen Banking clusters remains outstanding.
  Tasks 5/6 remain on
  hold, and task 11 requires recipient audit.
- One custom development candidate has synthetic and native AgentDojo model-free
  controls, a frozen five-condition train-only design, an implemented Qwen runner,
  and five completed immutable v1 model-run bundles. The v1 human audit is
  outstanding. The v1 tool-output IPI condition did not expose the declared
  attack vector on its actual path.
  The path-disclosed v2 design, model-free/tokenizer/GPU preflights, runtime
  freeze, five model runs, separate human audit and outcome report are complete.
  No independent validation exists.
  Additional development/test families and the final connected-component split
  are not implemented.
- No confirmatory data and no research result
