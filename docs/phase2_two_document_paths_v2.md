# Two-document payment paths v2

The [new task declaration](../data/templates/phase2_two_document_payment_v2.json)
puts the exact two document paths in the user instruction. This is the
development-only repair recorded by
[RDR-2026-10-19-02](decisions/2026-10-19_phase2_two_document_path_disclosure_revision.md).
The prior five runs and their pending audit remain under v1. The v2 conditions
are all train, in the same conservative connected component as v1 and the
prior Banking send-money pilot. They cannot serve as unseen validation.

The [v2 design](../configs/experiments/phase2_two_document_paths_v2.json),
[split](../data/splits/phase2_two_document_paths_v2.json),
[graph](../data/splits/phase2_two_document_paths_v2.graph.json), and
[checksum manifest](../data/manifests/phase2_two_document_paths_v2.freeze.json)
give the five new condition IDs and run prefix `phase2-po-registry-paths-v2`.
The [preflight record](experiment_logs/2026-10-19_two_document_paths_v2_preflight.md)
covers model-free controls and tokenizer positions. The
[execution record](experiment_logs/2026-10-19_two_document_paths_v2_execution.md)
and [collection manifest](../data/manifests/2026-10-19_phase2_two_document_paths_v2_collection.json)
document the five completed v2 runs and their pending human audit.

Before execution, commit all source, configuration and documentation changes,
leave a clean worktree, and repeat the native/tokenizer preflight on the
execution host:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-preflight \
  configs/experiments/phase2_two_document_paths_v2.json
```

Then run the engineering GPU check to a new ignored path. It does not generate
model behavior:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-gpu-preflight \
  configs/experiments/phase2_two_document_paths_v2.json \
  --output artifacts/preflight/<unique-v2-gpu-report>.json
```

Bind that report and the same clean commit to a separate v2 runtime freeze:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-freeze-runtime \
  configs/experiments/phase2_two_document_paths_v2.json \
  --gpu-report artifacts/preflight/<unique-v2-gpu-report>.json \
  --output artifacts/phase2-two-document-paths-v2-runtime-<commit>.freeze.json
```

Only then may the new five-condition collection run:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-run \
  configs/experiments/phase2_two_document_paths_v2.json \
  --runtime-freeze artifacts/phase2-two-document-paths-v2-runtime-<commit>.freeze.json
```

The runner uses new immutable IDs `phase2-po-registry-paths-v2-c001-a1` through
`c005-a1`. Preserve all planned outcomes and technical failures. After execution,
audit all five with the
[v2 blank form](../data/audits/phase2_two_document_paths_v2.template.json) and
the [fixed two-document rubric](phase2_two_document_audit.md). Do not transfer
first judgments or automatic labels from v1 into the v2 audit.
