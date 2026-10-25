# Recipient probe: leave-one-training-series-out diagnostic (2026-10-26)

After the original REC/DON validation and the 1.000 in-sample AUROC were
inspected, the researcher requested cross-validation within the original 64
training conditions. This analysis retrains the probe four times: hold out
INV, REF, PRD, or EXP as a whole series and fit on the other three. Each fold
has 48 fitting conditions (12 tasks) and 16 held-out conditions (4 tasks).
The original train/validation assignments and immutable bundles are unchanged;
REC and DON are neither fitted nor evaluated in these folds.

The four series belong to one conservative component in the frozen relationship
graph. These are therefore exploratory **within-training** folds, not four
independent development validation components. The analysis was chosen after
seeing weak REC/DON and perfect in-sample performance; it is not a pre-result
estimate or a new final probe selection. No confirmatory test set was created
or inspected.

## Procedure and provenance

The [analysis config](../../configs/analysis/phase2_argument_recipient_96_train_series_cv_v1.json)
declares each held-out series and the previously reported representative
layer 8 / C=1.0 setting. Code in
`goal_takeover.phase2.argument_probe_train_series_cv` verifies the original
freeze and run manifests, extracts the same first `user_to_assistant` /
`Tend_assistant` residuals, and fits a separate `StandardScaler` plus linear
logistic probe on each fold's 48 fitting rows only. The original six layers,
three C values, seed, and fit limits are reused. A character 2–5-gram TF-IDF
logistic baseline is refitted on the same 48 user instructions in every fold.
Within-task label permutations provide 10 random-label controls per candidate
and fold at the first C=0.01, as in the initial fit.

The primary metric is candidate-wise AUROC among held-out rows containing that
candidate's account string: positive if it is the declared recipient, negative
if it is the reference account. Each fold has 4 positives and 2 reference
negatives per candidate (six rows, eight positive-negative pairs); individual
AUROCs are therefore coarse. The four candidates are averaged equally within
each fold. All four fold means are then averaged equally. No candidate's raw
score is compared with another candidate's raw score.

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_probe_train_series_cv \
  configs/analysis/phase2_argument_recipient_96_train_series_cv_v1.json \
  artifacts/runs \
  artifacts/processed/phase2_argument_recipient_96_train_series_cv_v1
```

Config SHA-256: `79b0c7f03eaa3e4ec8c8640710f28b76606d0d4166e9212545aa05bc0ad1600a`.
The immutable derived `report.json` is SHA-256
`24b9e38c25db4b95bd3e40176f8fd8bf6e2ac92e6eb8667cfac8f1f40dbf4fe8`;
`probe_parameters.npz` is SHA-256
`a75565b7290d28578d7c8dc11dbac8ba4ef992ef5875ac628d7405cdd2ebfa17`.
The [small result summary](../../results/2026-10-26_phase2_argument_recipient_96_train_series_cv_v1.json)
is committed separately. All 288 fold/candidate/layer/C primary AUROCs were
independently recomputed from saved held-out scores and condition labels.

## Results

Four-candidate mean AUROC at the **previously reported** layer 8 / C=1.0:

| Held-out series | Residual probe | TF-IDF baseline |
| --- | ---: | ---: |
| INV | 0.625 | 0.844 |
| REF | 0.344 | 0.875 |
| PRD | 0.219 | 0.844 |
| EXP | 0.594 | 0.844 |
| Equal-weight fold mean | **0.445** | **0.852** |

Candidate-wise probe AUROC at that same setting:

| Held-out series | v1 | v2 | v3 | v4 |
| --- | ---: | ---: | ---: | ---: |
| INV | 0.500 | 0.750 | 0.500 | 0.750 |
| REF | 0.250 | 0.625 | 0.125 | 0.375 |
| PRD | 0.500 | 0.000 | 0.250 | 0.125 |
| EXP | 0.750 | 0.375 | 0.750 | 0.500 |

Across the full six-layer/three-C diagnostic grid, the largest equal-weight
fold mean was 0.664 at layer 16 / C=0.1. Its fold means were INV 0.563, REF
0.844, PRD 0.438, and EXP 0.813. This is a post-hoc maximum over 18 settings,
not an independently validated selected probe. At layer 16 / C=0.01, the
corresponding mean was 0.656 versus 0.542 for the within-task random-label
controls; this comparison uses the same C for probe and controls. The TF-IDF
four-fold mean was 0.852. The full report retains candidate scores, all
settings, all-row diagnostics, TF-IDF and control results.

The representative setting fails to transfer reliably even between the four
training series, especially when PRD or REF is held out. Layer 16 gives a
somewhat higher within-training diagnostic but also varies sharply by series
and does not exceed the text baseline. This pattern is consistent with the
previous training/validation gap. It does not isolate sample size, feature
position, task wording, or model representation as the cause, and it does not
validate the probe for IPI or a confirmatory analysis.
