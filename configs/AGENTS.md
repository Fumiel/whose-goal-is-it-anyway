# Configuration instructions

- Treat `docs/research_proposal.md` and `docs/experimental_protocol.md` as the
  source of truth for scientific choices.
- Files with `status: placeholder` or `status: synthetic_example_only` are not
  selected research settings.
- Keep model, tokenizer, domain, layer, position, decoding, split, and storage
  choices in configuration rather than analysis code.
- Do not fill selection thresholds after inspecting candidate results. Freeze
  them first and record the decision in `docs/decisions/`.
- Paths committed here must be relative to the repository.
- Update configuration validation tests whenever a key is added or renamed.
