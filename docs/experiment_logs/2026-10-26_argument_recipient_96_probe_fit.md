# Recipient content probe fit and development validation (2026-10-26)

The 96-run audit was complete with zero unresolved disagreements before this
fit. The [probe plan](../../configs/analysis/phase2_argument_recipient_96_probe_plan_v1.json)
fixed six layers (0, 8, 16, 24, 32, 35), the first `user_to_assistant`
`Tend_assistant` position, three regularization values, random-label controls,
and the missing-data rule. The
[input declaration](../../configs/analysis/phase2_argument_recipient_96_probe_v1.json)
and [freeze](../../data/manifests/phase2_argument_recipient_96_probe_v1.freeze.json)
bind all 96 approved conditions, the original split, audit, collection
manifests and condition-derived labels. The audit outcome is an eligibility
gate; it is not a probe teacher label.

The two `model_failure` runs, c048 and c056, have valid first-boundary
captures. The probe extractor now accepts those statuses when the selected
capture passes the same manifest, token, position, shape and finite-value
checks as completed runs. Both remain in the input; neither was rerun. All 96
features were usable for all six layers. Training used the 64 INV/REF/PRD/EXP
conditions; development validation used the independent REC and DON components
(16 conditions each). No test data were created or inspected.

The fit command was:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_probe \
  configs/analysis/phase2_argument_recipient_96_probe_v1.json \
  artifacts/runs artifacts/processed/phase2_argument_recipient_96_probe_v1
```

The immutable derived directory contains `report.json` (SHA-256
`fa7a3c91e56d89ba2cdda625cbdab5d29257641eb7e1b03e1e6f60342546540d`)
and `probe_parameters.npz` (SHA-256
`52d458b545a643ed353ad502b9a53e5dfdcb6fe77e1ba7f5c170beebbbd04d34`).
The small [curated summary](../../results/2026-10-26_phase2_argument_recipient_96_probe_v1.json)
records the exact spec hash and diagnostics.

## Development result

The declared primary diagnostic is candidate-wise AUROC among conditions where
that candidate's account string is present. At the highest mean AUROC among
the evaluated layer/C combinations (layer 8, C=1.0), the four-candidate mean
was 0.484, compared with 0.852 for the train-fitted TF-IDF baseline. Candidate
AUROCs were 0.469, 0.563, 0.313 and 0.594; baseline AUROCs were 0.813,
0.875, 0.813 and 0.906. This is an optimistic validation maximum over the
declared grid, not a selected final probe. No evaluated layer/C combination
exceeded the text baseline on the four-candidate mean. The full report retains
candidate, component, calibration, random-label and cluster-bootstrap
diagnostics; only two independent validation components make intervals coarse.

These results do not validate a recipient readout for tool-output IPI. The
quotation/prohibition, tool-output and dual-recipient controls remain required
before any use in the main argument-hijacking analysis. The weak development
performance motivates reassessing the probe and possibly narrowing claims,
with any design change and its timing recorded before confirmatory test.
