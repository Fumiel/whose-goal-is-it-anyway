# Generated artifacts

This is the single Git-ignored root for generated experiment artifacts.

```text
artifacts/
├── runs/<run_id>/          # immutable raw run bundles
├── processed/<dataset_id>/ # reproducible features and probe inputs
└── analyses/<analysis_id>/ # analysis execution outputs
```

Every raw run must contain a resolved configuration, exact serialized prefix
and token IDs, outcome flags, score details, artifact checksums, and provenance.
Large files may be stored externally when their URI, shape, dtype, byte count,
and SHA-256 checksum remain traceable from a committed manifest.

Only this README is tracked under `artifacts/`.
