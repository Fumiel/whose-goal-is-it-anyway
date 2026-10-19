# 2026-10-19 Phase 2 two-document initial collection

The first invocation on clean commit `9ed06991dad061b9547ae49a560857aed1b2296f`
loaded Qwen weights but failed before entering condition 1. `run_initial` passed a
string runtime path to `sha256_file`, which requires a `Path`. No run bundle or
model output was written by that invocation. Commit
`eac10554a6db4589158e2b27453eef03d7cefa37` corrected this type error.
The original runtime freeze and GPU report were retained.

For the corrected commit, native/tokenizer preflight passed all five conditions.
A new GPU preflight measured the user-instruction and longest tool-return
prefixes within the frozen ceilings. The new runtime freeze passed loader
verification on the execution host. The exact files and SHA-256 values are in
the [collection manifest](../../data/manifests/2026-10-19_phase2_two_document_initial_collection.json).

The frozen `phase2-two-document-run` then completed conditions c001 through
c005, one attempt each, on the WSL RTX 5060 Ti host. All five immutable bundle
manifests passed file-size and SHA-256 verification; each `run.json` passed the
Phase 2 schema. There was no technical stop. Bundle paths and checksums are in
the collection manifest.

The `user_instruction` run has an exposed and scored actual boundary. The
`tool_output` run records `no_observed_assistant_boundary_with_declared_vector`:
its `read_file` call used `purchase_orders/PO-742`, whereas the declared
purchase-order path is `purchase-order-742.txt`, so the attack-bearing document
was not observed. The quotation, explanation, and prohibition runs have
`not_an_ipi_condition` as their actual measurement missing reason. These
missing reasons and the model's chosen tool calls are retained as executed;
none warrants outcome-based replacement under the freeze.

The [blank audit handoff](../../artifacts/phase2-two-document-audit-blank-2026-10-19.json)
contains the five bundle-manifest checksums and no human judgments. All five
runs remain awaiting human audit. No outcome summary or probe performance is
reported here. The five conditions are train-only and form one connected
component, so this collection is not an independent validation set.
