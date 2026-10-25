# Phase 2 recipient argument probe implementation

For the research design, data, training, validation and interpretation in one
place, see the [Japanese end-to-end account](phase2_argument_probe_end_to_end_2026-10-26.md).

The development implementation is `goal_takeover.phase2.argument_probe`. It
reads completed immutable run bundles and creates a new directory of derived
probe parameters and validation diagnostics. It does not run the model or
change raw bundles. The initial research fit and its limits are recorded in
[the 2026-10-26 fit log](experiment_logs/2026-10-26_argument_recipient_96_probe_fit.md).

## Input contract

Run with:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_probe \
  path/to/frozen_probe_input.json artifacts/runs artifacts/processed/new-probe-id
```

The input JSON must contain:

- `status`: `frozen_research` for research data or `synthetic_fixture` for
  engineering tests. Research mode also requires `design_freeze_path` and its
  `design_freeze_sha256`. The referenced JSON must contain
  `probe_declaration_sha256`, the SHA-256 of canonical JSON for
  `candidate_values`, `feature_specs`, `conditions`, `fit` and `missing_policy` (sorted keys,
  compact separators, UTF-8). This binds the probe input declaration to the
  separate freeze file.
- `candidate_values`: stable candidate IDs to exact account strings.
- `feature_specs`: distinct `feature_id` values with `layer`, `boundary`,
  `position_name`, and `position_rule_version`. Each feature selects one actual
  trajectory boundary per condition. Layer and position selection remain
  research decisions to make using the independent development validation.
- `conditions`: one record per run with a valid capture, including a retained
  `model_failure` run when its selected capture passes all checks, with `condition_id`, `run_id`,
  `split`, `component_id`, `task_template_id`, `user_instruction`, and
  `argument_present`. Optional `pair_id` and `paraphrase_family_id` are checked
  for train/validation leakage when supplied. `argument_present` has one binary
  label per candidate; several candidates may be positive at once.
- `fit`: positive `regularization_c` values, `max_iter`, `seed`,
  `calibration_bins`, `random_label_repeats`, and
  `cluster_bootstrap_repeats`.
- `missing_policy`: `exclude_with_reason`. The report retains every missing
  feature's condition, run, feature ID and reason.

Research mode requires a frozen condition and split declaration, and the
design-freeze file checksum is verified. The initial 96-condition
[input declaration](../configs/analysis/phase2_argument_recipient_96_probe_v1.json)
and [freeze](../data/manifests/phase2_argument_recipient_96_probe_v1.freeze.json)
were built from the audited collection. The earlier review draft remains separate.

## Checks and outputs

The loader verifies raw artifact checksums; accepted run status, condition and split
IDs; raw condition labels and prompt; relationship component; prefix and token
IDs; position rule; residual layer, shape, dtype and finiteness. This first
implementation is limited to user-instruction recipient content: a positive
condition label is used only after its account string appears within the
declared user instruction by the selected token position. Missing positions
and pre-exposure positives are counted by
reason. A position or token identity mismatch is an error.

Every feature and regularization candidate is fit on training rows only with
`StandardScaler` and a linear logistic probe for each account. The output keeps
continuous validation decision scores, probabilities, candidate and component
counts, AUC for all rows and lexical-present rows, balanced accuracy at score
zero, Brier score, ECE bins, a TF-IDF text baseline and within-task random-label
controls. It also reports lexical-present selectivity against those controls
and a component-resampled AUC interval when at least two validation components
are available. With only two components, that interval is necessarily coarse.
These probabilities are raw logistic outputs, not a separately fitted
calibration transform. No layer, threshold, score transformation or calibration
method is automatically selected by this implementation.

The new output directory contains `report.json` and
`probe_parameters.npz`. The report stores row-level token identity and input
checksums without copying residual tensors. `score_saved_probe` reloads the
saved normalization and linear coefficients to reproduce a decision score.
The directory must not already exist; reruns need a new derived ID.

The initial 96 user-instruction conditions alone cannot establish probe
validity for tool-output IPI, quoted or prohibited recipients, or two
simultaneous recipient candidates. Those controls are required separately by
RDR-2026-10-22-03 and the experimental protocol before using this readout in
the main analysis.
