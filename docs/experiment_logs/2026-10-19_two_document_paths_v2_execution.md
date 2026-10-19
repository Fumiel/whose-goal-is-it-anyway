# 2026-10-19 two-document paths v2 execution

The five filename-disclosed development conditions were run under clean commit
`c36fc9c18bb641524de9fc1397c3bec8e7942ebf`, using a new GPU preflight
report and a separate same-commit runtime freeze. The native/tokenizer preflight
was repeated on the execution host before collection. The GPU report measured
the user-boundary and longest tool-return controls below the frozen 12 GiB
memory, 0.05 GiB residual storage, and 300-second per-condition ceilings.
Paths and SHA-256 digests are in the
[collection manifest](../../data/manifests/2026-10-19_phase2_two_document_paths_v2_collection.json).

The `phase2-two-document-run` command completed c001 through c005, one attempt
per condition, with no technical stop. Each immutable bundle passed full
artifact-size and SHA-256 verification and the Phase 2 `run.json` schema.
All five actual trajectories made successful `read_file` calls for
`purchase-order-742.txt` and then `approved-payees.txt`, with nonempty tool
responses. All five bundles record `actual_exposed_scored=true` and no actual
measurement missing reason. The peak recorded GPU allocation was
11,408,506,880 bytes; the longest condition took 55.91 seconds.

The [blank v2 audit handoff](../../artifacts/phase2-two-document-paths-v2-audit-blank-2026-10-19.json)
contains verified bundle-manifest checksums but no human judgments. All five
runs await human audit before any outcome report. The earlier v1 runs and their
separate pending audit remain unchanged. These v2 conditions are train-only and
share a conservative relationship component with v1 and the earlier Banking
pilot; they are not independent validation or confirmatory evidence.
