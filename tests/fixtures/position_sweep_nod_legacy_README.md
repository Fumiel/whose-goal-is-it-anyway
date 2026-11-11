# Synthetic legacy fixtures for the D-free refactor

These files contain only synthetic test data, not model runs or research results.
They were generated before changing the existing capture/analysis functions, at
commit `3f97be1` (the documentation-only review commit).

- `position_sweep_nod_legacy_analysis.json`: canonical JSON from the unchanged
  `analyze(*NumericalTest.data())` in `test_position_sweep_analysis.py`. It uses
  six positions, one synthetic layer, 26 permutations and two bootstrap samples.
- `position_sweep_nod_legacy_capture.json`: output of unchanged `capture_condition`
  with the CPU-only `synthetic_model`, `SyntheticTokenizer`, the first synthetic
  pair member and `torch.manual_seed(71)`. Tensors are serialized as float lists.

The new tests compare canonical bytes with these saved results and also verify
that removing report-only D leaves the shared five positions and nulls unchanged.
