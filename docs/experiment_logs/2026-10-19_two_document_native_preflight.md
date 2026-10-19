# Two-document payment native AgentDojo preflight, 2026-10-19

This is a model-free engineering execution for the development-only
`purchase_order_registry_reconciliation_v1` task. It is not a model run,
behavioral result, training datum, or confirmatory observation. The test set
was not created or inspected.

The adapter loaded AgentDojo 0.1.35 Banking v1.2.2, copied its suite for each
fresh condition, registered custom `user_task_742` and `injection_task_742`,
installed `purchase-order-742.txt` and `approved-payees.txt`, and used native
`read_file` and `send_money` calls. The standard Banking suite was not modified.
The native bank account begins with five historical transactions; controls
checked the newly added transfer against that preserved baseline.

Command:

```bash
.venv/bin/python -m goal_takeover.datasets.two_document_native data/templates/phase2_two_document_payment_v1.json
```

The command passed all five source-role conditions, nine controls each:
no operation, authorized transfer, alternative transfer, missing registry read,
duplicate transfer, wrong amount, transfer before registry read, reversed document
reads, and a forbidden account-profile change. The authorized case passed native
user utility in every condition. Other controls failed utility as specified.
The independent native injection predicate detected an exact attacker-recipient
transfer. It also detected that transfer in the `user_instruction` condition,
where the user authorized it; this is a candidate-action flag, not a claim of an
unauthorized attack in that control. Each authorized case returned the exact
installed document text through the native tool. Native tool schemas accepted
all declared calls.

- Spec SHA-256: `03ba599c86130015d23774329afd02402ca3314d0f6da9b4942c3467e7d23cb9`
- Condition IDs: `user_instruction=phase2_po_registry_1b3ab53b446ddc7a`,
  `tool_output=phase2_po_registry_5ccc0ca66318286f`,
  `quotation=phase2_po_registry_cada2c1c22b19175`,
  `explanation=phase2_po_registry_cef992a1f6bf825d`,
  `prohibition=phase2_po_registry_02d534c220605ffd`.
- Quality checks: 102 unit tests passed; `compileall`, `ruff check`,
  `ruff format --check`, and `pytest` passed.

The task remains connected to prior send-money and direct-override families
pending the relationship graph review. A Phase 2 model run still requires a
fixed development split, evaluator and audit rules, model/tokenizer revisions,
decoding and measurement choices, resource ceiling, runtime freeze, and new run
IDs under RDR-2026-10-14-01.
