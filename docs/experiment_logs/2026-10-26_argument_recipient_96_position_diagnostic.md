# Recipient probe saved-position diagnostic (2026-10-26)

After inspecting the original REC/DON development result, the researcher asked
whether changing the residual capture position could explain weak probe
performance before collecting more conditions. This is a **post-result
exploratory analysis**, not an independent validation or a revision of the
original frozen probe. The 96 immutable runs, human audit, split, and original
probe output were left unchanged. No new model execution or test inspection
occurred.

The [analysis config](../../configs/analysis/phase2_argument_recipient_96_positions_diagnostic_v1.json)
references the exact original probe input and uses its 64 training and 32
REC/DON validation conditions, candidate labels, six layers, three C values,
train-only standardization, and candidate-wise linear logistic classifier.
The [new analysis code](../../src/goal_takeover/phase2/argument_position_diagnostic.py)
verifies each original run manifest and the raw files it reads. Its derived
[full report](../../artifacts/processed/phase2_argument_recipient_96_positions_diagnostic_v1/report.json)
records all 96 manifest hashes, exact selected token indices and IDs, all
validation scores, candidate and component AUROCs, and all layer/C settings.
The report SHA-256 is
`5b73f4c8e8de4c3a20e1909e9b606a255f5c922515379d40419062ded767fb91`.
The [small summary](../../results/2026-10-26_phase2_argument_recipient_96_positions_diagnostic_v1.json)
is tracked separately. Reproduce with:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_position_diagnostic \
  configs/analysis/phase2_argument_recipient_96_positions_diagnostic_v1.json \
  artifacts/runs artifacts/processed/a-new-derived-directory
```

All seven selected positions were saved at the first user-to-assistant boundary
for all 96 conditions, including the two retained model failures. `Tpre` is
the token before the declared recipient account, `Tpost` is its final token,
`post4/8/16` are the corresponding offsets, and `post_mean_0_8` averages the
nine residual vectors from `Tpost` through eight tokens later. The user
message's final content token was not among the saved positions: it was 36–108
tokens after `Tpost`. A first tool-return position is not available as one
complete, comparable 96-condition first-boundary set. Both were omitted.

The metric below is the four-candidate equal-weight AUROC among validation
conditions in which that candidate appears **anywhere in the complete user
instruction**. This keeps the evaluation rows matched across positions. At
early positions, a reference account can occur later in the prompt and not
yet be visible to the model. The original `Tend_assistant` result is reproduced
to three decimals.

| Position | Layer 8, C=1.0 | Post-hoc best over 18 settings |
| --- | ---: | ---: |
| `Tpre` | 0.523 | 0.531 |
| `Tpost` | 1.000 | 1.000 |
| `post4` | 0.828 | 0.883 |
| `post8` | 0.734 | 0.734 |
| `post16` | 0.813 | 0.813 |
| `post_mean_0_8` | 1.000 | 1.000 |
| `Tend_assistant` | 0.484 | 0.484 |

The original text TF-IDF comparator was 0.852 on this metric. `Tpost` and the
nearby positions were selected **using the condition's known positive
recipient account**. At `Tpost`, the selected token itself is part of that
account, so a probe can classify which of the four fixed accounts is present
without reading whether an arbitrary candidate is the recipient. The perfect
AUROC at `Tpost` and the window mean therefore demonstrates a strong local
account-identity signal under label-informed position selection. It does **not**
show that the prior final-boundary recipient-role probe was repaired, nor that
a goal was adopted. `Tpre` is only a before-account control. No new position
has been selected for the confirmatory experiment; the 0.80 development
criterion from the later learning-curve plan is not established by this
diagnostic.

The cause of the original final-boundary train/validation gap remains open.
A follow-up that tests recipient role at an earlier point would need a position
rule independent of the recipient label, with the same candidate's positive
and reference appearances available and exposure checked in each condition.
The old raw captures do not guarantee those matching reference-account spans.
