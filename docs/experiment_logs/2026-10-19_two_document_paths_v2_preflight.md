# 2026-10-19 two-document paths v2 preflight

The user instruction in the new development-only
[`v2` task](../../data/templates/phase2_two_document_payment_v2.json) names both
`purchase-order-742.txt` and `approved-payees.txt`. The five source-role variants
retain the v1 document texts, candidate `send_money` calls and evaluator rule.
Condition IDs and run namespace differ from v1. The
[RDR](../decisions/2026-10-19_phase2_two_document_path_disclosure_revision.md)
records why this revision followed inspection of the initial model runs.

On 2026-10-19, synthetic model-free controls passed six cases per condition.
Native AgentDojo Banking v1.2.2 model-free controls passed nine cases per
condition, 45 total, including both ordered document reads, authorized and
alternative transfers, missing and reversed reads, duplicate payment, wrong
amount, and forbidden side effect. These controls use declared tool calls and
do not measure model behavior.

The fixed Qwen3-8B tokenizer/native preflight passed all five new condition
IDs. It verified the local chat template and tool schema hashes, the declared
first-exposure boundary and token positions, the 4,096-token context ceiling,
and both complete candidate call sequences. Its design freeze SHA-256 was
`b81d07b527847cb06102294571b81c3191d23e6e2452f061cf08050a0b8a455c`.

No v2 GPU resource preflight, runtime freeze, model behavior run, or human audit
has been made at this point. An execution needs a clean code commit and a new
GPU report and runtime freeze from that same commit. The old v1 bundles and
pending human audit remain separate.
