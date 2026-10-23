# Recipient content 96-condition collection

The planned collection ran on 2026-10-24 under commit `b7e0244` and its
same-commit runtime freeze. All 96 raw bundles passed integrity checks; see
the [execution log](experiment_logs/2026-10-24_argument_recipient_96_collection.md)
and [manifest](../data/manifests/phase2_argument_readout_96_v1_collection.json).
The commands below document that execution and are not instructions to reuse
existing immutable run IDs.

The researcher approved the 24 task texts, four fictional accounts, and the
REC/DON development validation candidates on 2026-10-24. The separate
[decision](decisions/2026-10-24_argument_recipient_96_collection_freeze.md),
[condition declaration](../data/templates/phase2_argument_readout_96_v1.json),
[split](../data/splits/phase2_argument_readout_96_v1.json),
[graph](../data/splits/phase2_argument_readout_96_v1.graph.json),
[execution design](../configs/experiments/phase2_argument_readout_96_v1.json),
and [checksum manifest](../data/manifests/phase2_argument_readout_96_v1.freeze.json)
define this development-only collection. The source review draft remains
unchanged. No confirmatory test conditions are included.

The runner uses the native AgentDojo Banking task registered for each
condition. It captures all-layer residuals, attention aggregates and the two
full candidate-call scores at the first user-to-assistant boundary. Later
actual-trajectory boundaries retain their serialized prefixes, model output,
tool events and state changes without another residual capture. The conditions
are deterministic, one attempt each, with no outcome-based replacement.

## Execution gate

On the execution host, first verify the committed design, 960 native tool
controls and fixed-tokenizer alignment for all 96 conditions:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_collection \
  preflight configs/experiments/phase2_argument_readout_96_v1.json \
  --output artifacts/preflight/<new-native-tokenizer-report>.json
```

After all source, configuration and documentation changes are committed and
the worktree is clean, run GPU capture and candidate-scoring resource checks
on the longest one-account and two-account prefixes:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_collection \
  gpu-preflight configs/experiments/phase2_argument_readout_96_v1.json \
  --output artifacts/preflight/<new-gpu-report>.json
```

Create a runtime freeze tied to the same commit and GPU report:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_collection \
  freeze-runtime configs/experiments/phase2_argument_readout_96_v1.json \
  --gpu-report artifacts/preflight/<new-gpu-report>.json \
  --output artifacts/phase2-argument-recipient-96-runtime-<commit>.freeze.json
```

Only then collect the 96 new immutable bundles:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.argument_collection \
  run configs/experiments/phase2_argument_readout_96_v1.json \
  --runtime-freeze artifacts/phase2-argument-recipient-96-runtime-<commit>.freeze.json
```

The planned run IDs are `phase2-argument-recipient-96-v1-c001-a1` through
`c096-a1`. A model failure is preserved and the batch continues; a technical
failure is preserved and stops the batch. Re-execution or recovery requires
new IDs and a separate recorded decision. Existing raw bundles, including
failures, must remain unchanged.

All 96 executions require the planned human audit before an outcome report.
The probe's primary comparison uses each candidate's validation conditions
where its account string is present, with REC and DON as separate development
components. This set alone cannot validate readout behavior under tool-output
IPI, quotations, prohibitions or simultaneous recipient candidates.
