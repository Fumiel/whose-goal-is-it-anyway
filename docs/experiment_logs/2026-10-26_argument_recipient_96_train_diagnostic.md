# Saved recipient probe: in-sample training diagnostic (2026-10-26)

After the weak REC/DON development validation was inspected, the researcher
requested an in-sample check of whether the already fitted probe ranks its
training conditions. This is a post-result diagnostic, not a change to the
original fit, split, frozen labels, or confirmatory protocol. No model was
refitted and no test set was created or inspected.

The new read-only scoring path is
`goal_takeover.phase2.argument_probe_train_diagnostic`. It reapplies the
saved `StandardScaler` and logistic-regression parameters to the same 64
training captures. It verifies the original input freeze, the raw run
manifests and selected token identities, then reproduces all 32 saved
validation decision scores for every candidate, layer, and C before writing
the new result. The original raw runs and fitted probe bundle were unchanged.

Run command:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_probe_train_diagnostic \
  configs/analysis/phase2_argument_recipient_96_probe_v1.json \
  artifacts/runs \
  artifacts/processed/phase2_argument_recipient_96_probe_v1 \
  artifacts/processed/phase2_argument_recipient_96_train_diagnostic_v2
```

For each candidate, the metric uses only rows where that account string has
appeared by `user_to_assistant/Tend_assistant`: positive when the condition
declares it as `send_money.recipient`, negative when it appears as the
reference account. Among the 64 training conditions this yields 16 positives
and 8 reference negatives per candidate. The matching REC/DON validation
metric has 8 positives and 4 reference negatives per candidate. These are
condition labels, not generated tool calls or human-audited outcomes.

| Candidate | Training AUROC, layer 8 / C=1.0 | REC/DON AUROC, same setting |
| --- | ---: | ---: |
| v1 | 1.000 | 0.469 |
| v2 | 1.000 | 0.563 |
| v3 | 1.000 | 0.313 |
| v4 | 1.000 | 0.594 |
| Four-candidate mean | **1.000** | **0.484** |

All four training AUROCs were 1.000 at every one of the 18 evaluated
layer/C combinations. The training value is resubstitution performance on
the data used to fit the same probe; it shows that the saved probes separate
those training labels, but does not show generalization or establish what
information the model represents. The gap to the independent REC/DON
validation is consistent with overfitting or a task-series distribution
shift; this comparison alone cannot distinguish them. The representative
layer/C setting is the earlier validation-grid maximum, not a newly selected
main-analysis probe.

The final immutable derived `report.json` is at
`artifacts/processed/phase2_argument_recipient_96_train_diagnostic_v2/` and
has SHA-256 `38fbbd9d6d1ea4f893e8ae2d66a338f62a2bcf4c6906c96aed3c2810fcfde74a`.
The same-byte initial diagnostic output at `...train_diagnostic_v1/` was
retained after a code-only change to derive expected row counts from the
original report. The [small result summary](../../results/2026-10-26_phase2_argument_recipient_96_train_diagnostic_v1.json)
points to the final v2 path. The original [validation fit log](2026-10-26_argument_recipient_96_probe_fit.md)
and its outputs remain unchanged.
