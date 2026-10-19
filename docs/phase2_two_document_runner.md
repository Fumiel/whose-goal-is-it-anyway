# Phase 2 two-document Qwen runner

The [design freeze](../data/manifests/phase2_two_document_initial_v1.freeze.json)
and [RDR-2026-10-19-01](decisions/2026-10-19_phase2_two_document_initial_specification.md)
define five development-only train conditions. The custom task is registered on
an isolated AgentDojo Banking suite. This runner preserves actual generations,
tool events, state checksums, exact serialized prefixes, selected residuals,
Attention span aggregates, full candidate-sequence scores and partial technical
failures in immutable raw bundles. It does not convert any prior pilot run into
training data.

## Checks before collection

Use the execution WSL environment with the pinned local Qwen3-8B revision and
AgentDojo 0.1.35. The native/tokenizer check loads no model weights:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-preflight \
  configs/experiments/phase2_two_document_initial_v1.json
```

It checks all 45 native evaluator controls, five condition IDs and their order,
the local tokenizer and chat template, actual Qwen prefix positions at the user
or purchase-order return boundary, tool schema checksum, 4,096-token context
ceiling, and complete canonical candidate sequences.

The engineering GPU check loads Qwen but does not generate model behavior:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-gpu-preflight \
  configs/experiments/phase2_two_document_initial_v1.json \
  --output artifacts/preflight/<new-unique-name>.json
```

It captures the user-boundary control and the longest matched-content tool
return (`explanation`), then scores both declared `send_money` candidate
sequences at each exact prefix. The run must stay within 12 GiB GPU memory,
0.05 GiB residual storage and 300 seconds per measured condition. Save its
unmodified JSON report and checksum. An earlier engineering measurement on
2026-10-19 used this WSL RTX 5060 Ti host: the user control peaked at
11,035,213,824 bytes with 18,877,560 residual bytes; the explanation control
peaked at 11,179,917,312 bytes with 21,236,864 residual bytes. That first
report preceded the final code commit and is not an execution runtime freeze.

After all code and documentation are committed and the worktree is clean,
repeat the GPU check with a new report name. Bind that report and the clean
commit into a **new** ignored runtime freeze:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-freeze-runtime \
  configs/experiments/phase2_two_document_initial_v1.json \
  --gpu-report artifacts/preflight/<new-unique-name>.json \
  --output artifacts/phase2-two-document-runtime.freeze.json
```

The freeze records hashes of the design, all importable source and schemas,
the model/domain configs, Qwen chat template, native tool schema and GPU
report. The loader rejects changed code, dirty Git state, a different GPU
software stack or a report from another commit before loading model weights.
Do not overwrite a runtime freeze used for execution; create a new one if the
code or environment changes.

## Collection

Once the runtime freeze has been validated, collect only the five frozen train
conditions:

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.cli \
  phase2-two-document-run \
  configs/experiments/phase2_two_document_initial_v1.json \
  --runtime-freeze artifacts/phase2-two-document-runtime.freeze.json
```

The command checks all run IDs for collisions before loading Qwen. It writes
`artifacts/runs/phase2-po-registry-initial-v1-c001-a1` through `c005-a1` as
immutable bundles, stopping on a technical failure. Model parse/tool failures
remain behavioral failures and are not regenerated. The five runs require
human review before any outcome report. The `user_instruction` control can
legitimately transfer to the alternative account: candidate action occurrence,
native security flag, user authorization and IPI attack success are separate.
The quotation, explanation and prohibition controls retain any candidate-action
positives as anomalies outside the ordinary A–D grouping.

The tokenizer/native check and GPU check are engineering evidence only. Neither
is a model behavior result or independent validation group.
