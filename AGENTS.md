# AGENTS.md

## Project purpose

This repository supports the graduation research described in
`docs/research_proposal.md`: temporal and geometric analysis of goal
representations in tool-using LLM agents under indirect prompt injection.

Read `docs/research_proposal.md` before making research-design changes. Treat it
as the canonical statement of the research questions. Record later deviations
and their evidence instead of silently changing the intended experiment.

## Current status

- The repository is at the pre-pilot scaffolding stage.
- The model and primary AgentDojo domain have not been selected.
- Files under `configs/**/example.yaml` are placeholders, not settled choices.
- There is not yet an end-to-end model runner or a validated AgentDojo adapter.

Do not present placeholder configurations or synthetic fixtures as research
results.

## Research invariants

- Start with one open-weight instruction model and one domain.
- Use deterministic decoding for the main internal-state comparison. Use
  stochastic decoding only for auxiliary attack-success-rate estimates.
- Do not compare seed-only repetitions as if their pre-divergence activations
  explained different outcomes.
- Keep semantic variants, stochastic repetitions, and close paraphrases in the
  same train/validation/test split. Prefer grouping by task and attack template.
- Track user-task success and attack success independently.
- Use these outcome groups:
  - A: no attack text and user task succeeds.
  - B: attack text exists, attack fails, and user task succeeds.
  - C: attack text exists and both attack and user task fail.
  - D: attacker-specified action occurs; user-task success is recorded
    separately.
- A clean run in which the user task fails is not A-D and must be retained as
  an explicit baseline failure or excluded with a documented rule.
- Goal-content readout, role readout, attention, and action logits are distinct
  measurements. Never claim that a readable goal was adopted merely because a
  probe score increased.
- Treat a Takeover Point as an observational candidate unless a controlled
  intervention supports a causal claim.
- Save the exact token index and token ID used at every processing stage.
- For multi-token tool names, compare whole-call sequence log probability, not
  only the first token.
- Fit calibration and preprocessing using training data only.

## Repository conventions

- Use English for code identifiers and configuration keys. Japanese is welcome
  in research-facing documentation.
- Put importable code under `src/goal_takeover/`; keep notebooks exploratory.
- Prefer configuration-driven experiments. Do not hard-code model, domain,
  layer, stage, decoding, or output paths in analysis code.
- Give conditions stable IDs and runs unique IDs. Preserve pair IDs for matched
  Resistant/Susceptible conditions.
- Every run should preserve the resolved configuration, Git commit, model and
  tokenizer revision, seed, decoding parameters, condition IDs, outcome flags,
  token positions, and checksums.
- Generated run directories are immutable. Derive a new run rather than editing
  old output in place.
- Keep raw and processed data separate. Processing code must not overwrite raw
  data.
- Never commit secrets, model weights, raw activations, attention tensors, or
  large run outputs. Store them externally and commit only manifests/checksums.
- Small, synthetic, non-sensitive test fixtures may be committed.
- Use paths relative to the repository in committed configs and manifests.

## Quality checks

Before completing a code change, run the checks relevant to the touched files:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
```

Once development dependencies are installed, also run:

```bash
ruff check .
ruff format --check .
pytest
```

Add tests for outcome classification, token-position selection, sequence
log-probability calculations, split leakage prevention, and any new schema or
data transformation. Numerical research code should test shapes, alignment,
missing values, and deterministic behavior.

## Safe change policy

- Preserve the dated proposal PDF as a fixed snapshot.
- Do not modify or delete existing research data without explicit user
  authorization.
- If a pilot result motivates a protocol change, document the date, evidence,
  affected hypotheses, and whether the change occurred before inspecting the
  final test set.
- Do not invent citations, experimental results, model capabilities, or
  AgentDojo compatibility. Verify unstable technical details before relying on
  them.
