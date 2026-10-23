# Argument recipient 96-condition development collection (2026-10-24)

The researcher approved the unchanged 24 task texts, four fictional account
values and REC/DON validation candidates. RDR-2026-10-24-01 fixed the resulting
96-condition execution design. This collection uses provisional Qwen3-8B int8
and AgentDojo Banking v1.2.2; the primary model and domain remain unselected.
No confirmatory test condition was run.

## Execution gates

- The final condition declaration, split and graph were regenerated from the
  approved draft and bound by
  [design checksums](../../data/manifests/phase2_argument_readout_96_v1.freeze.json).
- Native model-free preflight passed 960 actual-tool controls, and fixed Qwen
  tokenizer checks passed all 96 user-boundary positions and full candidate
  sequences. The small
  [preflight summary](../../data/manifests/phase2_argument_readout_96_v1_preflight.json)
  points to the externally stored full report.
- The clean execution commit was
  `b7e0244e07875733e17e34db9cab018dea9dcd21`. On the WSL RTX 5060 Ti,
  same-commit GPU preflight captured and scored the longest one-account and
  two-account prefixes. Peak GPU allocations/reservations were 11,079,254,016
  and 11,265,900,544 bytes, below the declared 12 GiB ceiling; residual
  artifacts were 15,338,608 bytes each, below 0.05 GiB. The full report is
  `artifacts/preflight/phase2-argument-recipient-96-v1-gpu-b7e0244.json`.
- `artifacts/phase2-argument-recipient-96-runtime-b7e0244.freeze.json` binds
  that report, source/config/schema checksums and the same clean commit.

## Raw collection and verification

One deterministic attempt was made for each fixed condition, in order, under
run IDs `phase2-argument-recipient-96-v1-c001-a1` through `c096-a1`. The raw
bundles are immutable under `artifacts/runs/`. There were 94 `completed` run
statuses, two `model_failure` statuses (c048 and c056), and no technical
failure. c048 referenced a missing transaction ID; c056 repeated missing
transaction IDs and reached the fixed eight-step limit. Both records were
retained without replacement. Execution status is not an audited user-task
success label.

Every bundle passed the argument-run JSON schema; planned run, condition,
split and group IDs; design/runtime/commit identity; all manifest artifact
lengths and SHA-256 checksums; first user-boundary exposure and selected
`Tpre`, `Tpost`, `Tend_assistant` positions; candidate-score presence; and
per-condition memory, wall-time and storage limits. The maximum observed GPU
peak was 11,345,592,320 bytes and the largest listed artifact total was
17,962,282 bytes. The
[collection manifest](../../data/manifests/phase2_argument_readout_96_v1_collection.json)
lists the 96 run IDs, condition IDs and raw manifest checksums. Raw artifacts,
full GPU report and runtime freeze are Git-ignored research records and must
remain unchanged.

## Next gate

Complete the planned human audit for all 96 runs, recording first judgments
and adjudications for user-task success, wrong-recipient transfers and side
effects. Preserve the automatic/native fields independently. Probe fitting
and REC/DON assessment remain separate work with the declared controls. This
collection alone does not test tool-output IPI, quotations/prohibitions or
simultaneous recipient candidates.
