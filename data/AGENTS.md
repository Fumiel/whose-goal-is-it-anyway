# Data instructions

- Keep only small declarations, schemas, split assignments, audits, and artifact
  manifests in Git.
- Never commit secrets, personal data, model weights, raw activations, full
  attention tensors, or large run output.
- Raw runs live under `artifacts/runs/` and are immutable. Derived data lives
  under `artifacts/processed/`; processing must never overwrite raw runs.
- Keep task families, attack goal/style families, matched pairs, close
  paraphrases, and stochastic repetitions in the same split.
- Do not inspect confirmatory test outcomes before the Phase 3 freeze.
- Synthetic fixtures must be clearly labelled and must never be reported as
  research observations.
