# Source-code instructions

- Keep importable experiment code in this package and keep notebooks
  exploratory.
- Do not hard-code model, domain, layer, token position, decoding, split, or
  artifact paths.
- Preserve exact serialized prefixes, token IDs, token positions, revisions,
  checksums, and resolved configuration at every run.
- Keep action readout, argument readout, source-role readout, authority score,
  attention, and tool-call preference as separate measurements.
- New transformations need tests for shapes, alignment, missing values, and
  deterministic behavior.
- Real model and benchmark adapters must fail explicitly when compatibility has
  not been verified; synthetic adapters must be labelled as test-only.
