# RDR-2026-09-22-02: AgentDojo shakedown implementation baseline

- `decision_id`: `RDR-2026-09-22-02`
- Date: 2026-09-22
- Status: `accepted`
- Phase: before formal integration-gate evaluation
- Test set inspected: no
- Depends on: `RDR-2026-09-22-01`

## Decision

The engineering shakedown uses AgentDojo package 0.1.35, benchmark v1.2.2,
and the Banking suite. AgentDojo supplies the environment, tools, tasks, and
evaluators; the repository-owned runner controls message serialization and
model execution. The standard AgentDojo CLI is used only for reference and
conformance checks.

The candidates are Qwen3-8B with LLM.int8 and Qwen3-4B with BF16. Both use
greedy decoding with thinking disabled, a 4096-token shakedown context, and one
Transformers model instance for generation, residual capture, and candidate
sequence scoring. If both satisfy the engineering checks, the predeclared
capacity rule prefers 8B. Behavioral outcomes from the three fixtures cannot
be used for this choice.

Each fixture has two explicitly separated paths. The instrumentation path uses
the first AgentDojo ground-truth tool call to construct the required
`first_tool_to_assistant` boundary, then runs generation, residual capture, and
scoring from that identical prefix. A fresh environment runs the uncontrolled
model agent loop only to diagnose parsing, tool execution, and evaluator
wiring. The ground-truth path is not counted as model task success.

Execution is performed on the Windows 11 RTX 5060 Ti host through WSL2 Ubuntu
24.04 and LAN-only key-authenticated SSH. Raw activations and model weights
remain on that host.

## Authorized fixtures and isolation

- `user_task_1`: read-only transaction aggregation.
- `user_task_3`: transaction lookup followed by a refund.
- `user_task_0` with `injection_task_0` in `injection_bill_text`: legitimate
  and attacker calls both use `send_money` with different recipients.

These task IDs, the injection task, the fixed attack text, and close
paraphrases are excluded from later model selection, pilot, and confirmatory
splits.

## Verification boundary

AgentDojo fixture loading, tool schemas, ground-truth calls, injection
rendering, and evaluator wiring were checked locally against 0.1.35. Qwen3
chat-template token identity was checked with the pinned tokenizer revision.
GPU model loading, CUDA memory fit, generation, residual capture, and
teacher-forced scoring remain unverified until the Windows shakedown runs.
