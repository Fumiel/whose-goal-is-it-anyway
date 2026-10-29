"""Train-only teacher-forced recipient log-probabilities for the 672 collection.

Each canonical ``Tend_assistant`` prefix is extended with the model-native
``send_money`` stem declared in the analysis config, then every candidate
account plus the closing quote is scored as a declared token sequence. All
candidates share the stem, so differences come from the account tokens. This is
an action/argument-readout measurement of model behavior, separate from the
residual probe; it does not show which residual position holds the information.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from goal_takeover.models.loader import load_hugging_face_model
from goal_takeover.phase2.argument_recipient_672_features import _verified_artifact
from goal_takeover.phase2.argument_recipient_672_metric import ROLE_SWAP_VARIANTS, _auc
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.phase2.argument_recipient_672_train_readout import (
    clean_commit,
    publish,
    train_rows_and_run_ids,
)
from goal_takeover.storage.run_writer import sha256_file


def candidate_accounts(declaration: dict[str, Any]) -> dict[str, str]:
    """The four labeled candidates plus every other declared document account."""
    accounts = dict(declaration["account_value_ids"])
    for index, value in enumerate(declaration["other_entry_account_values"]):
        accounts[f"other{index}"] = value
    if len(set(accounts.values())) != len(accounts):
        raise ValueError("candidate account values are not unique")
    return accounts


def continuation_ids(
    tokenizer: Any, prefix_text: str, prefix_token_ids: list[int], continuation: str
) -> list[int]:
    """Tokenize prefix+continuation jointly and require the saved prefix tokens unchanged."""
    ids = list(tokenizer(prefix_text + continuation, add_special_tokens=False)["input_ids"])
    if ids[: len(prefix_token_ids)] != list(prefix_token_ids):
        raise ValueError("joint tokenization changed the saved prefix tokens")
    if len(ids) == len(prefix_token_ids):
        raise ValueError("continuation produced no tokens")
    return ids[len(prefix_token_ids) :]


def score_continuations(
    model: Any, prefix_token_ids: list[int], continuations: dict[str, list[int]]
) -> dict[str, list[float]]:
    """Per-token log-probabilities of each continuation after one shared prefix pass."""
    import torch

    device = next(model.parameters()).device
    with torch.no_grad():
        output = model(input_ids=torch.tensor([prefix_token_ids], device=device), use_cache=True)
        cache, last_logits = output.past_key_values, output.logits[0, -1].float()
        result = {}
        for key, ids in continuations.items():
            step = model(
                input_ids=torch.tensor([ids], device=device),
                past_key_values=copy.deepcopy(cache),
                use_cache=True,
            )
            logits = torch.cat([last_logits[None], step.logits[0, :-1].float()])
            values = torch.log_softmax(logits, dim=-1)[
                torch.arange(len(ids), device=device), torch.tensor(ids, device=device)
            ]
            result[key] = [float(value) for value in values.tolist()]
    return result


def summarize(
    rows: list[dict[str, Any]],
    totals: dict[str, dict[str, float]],
    exposed_accounts: dict[str, list[str]],
    candidates: list[str],
) -> dict[str, Any]:
    """Recipient choice among exposed accounts and behavioral role-swap AUROC.

    ``role_swap_auc`` compares raw totals across conditions, so even perfect
    within-condition choice need not reach 1.0.
    """
    strata: dict[str, list[bool]] = {}
    margins = []
    for row in rows:
        cid = row["condition_id"]
        exposed = exposed_accounts[cid]
        recipient = row["recipient_value_id"]
        if recipient not in exposed:
            raise ValueError(f"{cid}: recipient is not exposed")
        best = max(exposed, key=lambda key: totals[cid][key])
        ok = best == recipient
        for key in (
            "all",
            f"rule:{row['recipient_rule']}",
            f"boundary:{row['exposure']['boundary']}",
            f"variant:{row['condition_variant']}",
        ):
            strata.setdefault(key, []).append(ok)
        others = [totals[cid][key] for key in exposed if key != recipient]
        if others:
            margins.append(totals[cid][recipient] - max(others))
    role = [row for row in rows if row["condition_variant"] in ROLE_SWAP_VARIANTS]
    by_batch = {}
    for batch in sorted({row["training_batch"] for row in role}):
        subset = [row for row in role if row["training_batch"] == batch]
        values = []
        for candidate in candidates:
            exposed_rows = [
                row
                for row in subset
                if candidate in (row["recipient_value_id"], row["reference_value_id"])
            ]
            values.append(
                _auc(
                    [row["argument_present"][candidate] for row in exposed_rows],
                    [totals[row["condition_id"]][candidate] for row in exposed_rows],
                )
            )
        by_batch[batch] = sum(values) / len(values)
    by_rule: dict[str, tuple[list[int], list[float]]] = {}
    for row in role:
        labels, values = by_rule.setdefault(row["recipient_rule"], ([], []))
        for candidate in (row["recipient_value_id"], row["reference_value_id"]):
            labels.append(row["argument_present"][candidate])
            values.append(totals[row["condition_id"]][candidate])
    sorted_margins = sorted(margins)
    return {
        "recipient_argmax_among_exposed": {
            key: {"correct": sum(values), "count": len(values)}
            for key, values in sorted(strata.items())
        },
        "margin_nats": {
            "count": len(margins),
            "negative_count": sum(value < 0 for value in margins),
            "median": sorted_margins[len(margins) // 2] if margins else None,
            "min": sorted_margins[0] if margins else None,
        },
        "role_swap_auc_by_batch": by_batch,
        "pooled_role_swap_auc_by_rule": {
            key: _auc(labels, values) for key, (labels, values) in sorted(by_rule.items())
        },
    }


def actual_agreement(
    root: Path,
    actual_prefix: str,
    totals: dict[str, dict[str, float]],
    exposed_accounts: dict[str, list[str]],
    accounts: dict[str, str],
) -> list[dict[str, Any]]:
    """Compare the first actual send_money recipient with the log-prob argmax."""
    inverse = {value: key for key, value in accounts.items()}
    items = []
    for bundle in sorted((root / "artifacts/runs").glob(f"{actual_prefix}-a[0-9][0-9][0-9]")):
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        run = json.loads(_verified_artifact(bundle, manifest, "run.json").read_text("utf-8"))
        cid = run["condition_id"]
        if cid not in totals:
            continue
        generations = json.loads(
            _verified_artifact(bundle, manifest, "generations.json").read_text("utf-8")
        )
        sent = [
            call["arguments"].get("recipient")
            for generation in generations
            for call in generation["tool_calls"]
            if call["name"] == "send_money"
        ]
        predicted = max(exposed_accounts[cid], key=lambda key: totals[cid][key])
        items.append(
            {
                "condition_id": cid,
                "actual_run_id": bundle.name,
                "actual_first_recipient": inverse.get(sent[0], "undeclared") if sent else None,
                "logprob_argmax": predicted,
            }
        )
    return items


def run(analysis_config_path: Path) -> Path:
    import platform

    import bitsandbytes
    import torch
    import transformers

    analysis = json.loads(analysis_config_path.read_text(encoding="utf-8"))
    root = analysis_config_path.resolve().parents[2]
    spec = analysis["recipient_logprob"]
    runtime_freeze = root / analysis["runtime_freeze"]
    config, declaration, _ = load_frozen_plan(
        root / analysis["experiment_config"],
        runtime_freeze_override=Path(analysis["runtime_freeze"]),
        require_matching_head=False,
    )
    output = root / "artifacts/processed" / spec["output_id"]
    if output.exists():
        raise FileExistsError(f"immutable derived output already exists: {output}")
    commit = clean_commit(root)
    rows, run_ids = train_rows_and_run_ids(declaration, analysis["canonical_run_prefix"])
    accounts = candidate_accounts(declaration)
    values = config["model"]
    model, tokenizer = load_hugging_face_model(
        values["name"],
        revision=values["revision"],
        tokenizer_revision=values["tokenizer_revision"],
        trust_remote_code=values["trust_remote_code"],
        torch_dtype=values["dtype"],
        device_map=values["device_map"],
        quantization=values["quantization"],
        low_cpu_mem_usage=values["low_cpu_mem_usage"],
        attn_implementation=values["attn_implementation"],
    )
    records, totals, exposed_accounts = [], {}, {}
    for number, row in enumerate(rows):
        cid = row["condition_id"]
        bundle = root / "artifacts/runs" / run_ids[cid]
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        run_record = json.loads(_verified_artifact(bundle, manifest, "run.json").read_text("utf-8"))
        prefix = json.loads(_verified_artifact(bundle, manifest, "prefix.json").read_text("utf-8"))
        position = run_record["selected_position"]
        if (
            run_record["condition_id"] != cid
            or position["name"] != "Tend_assistant"
            or position["token_index"] != len(prefix["token_ids"]) - 1
            or prefix["text_sha256"] != hashlib.sha256(prefix["text"].encode("utf-8")).hexdigest()
        ):
            raise ValueError(f"{bundle.name}: canonical prefix or position differs")
        continuations = {
            key: continuation_ids(
                tokenizer, prefix["text"], prefix["token_ids"], spec["stem"] + value + spec["tail"]
            )
            for key, value in accounts.items()
        }
        logprobs = score_continuations(model, prefix["token_ids"], continuations)
        totals[cid] = {key: sum(values) for key, values in logprobs.items()}
        exposed_accounts[cid] = [key for key, value in accounts.items() if value in prefix["text"]]
        records.append(
            {
                "condition_id": cid,
                "canonical_run_id": bundle.name,
                "prefix_id": prefix["prefix_id"],
                "prefix_text_sha256": prefix["text_sha256"],
                "prefix_token_count": len(prefix["token_ids"]),
                "tend_token_index": position["token_index"],
                "tend_token_id": position["token_id"],
                "exposed_accounts": exposed_accounts[cid],
                "candidates": {
                    key: {"token_ids": continuations[key], "token_log_probabilities": logprobs[key]}
                    for key in accounts
                },
            }
        )
        if number % 40 == 0:
            print(number, flush=True)
    candidates = sorted(declaration["account_value_ids"])
    agreement = actual_agreement(
        root, analysis["actual_run_prefix"], totals, exposed_accounts, accounts
    )
    report = {
        "summary": summarize(rows, totals, exposed_accounts, candidates),
        "actual_agreement": {
            "count": len(agreement),
            "agree": sum(
                item["actual_first_recipient"] == item["logprob_argmax"] for item in agreement
            ),
            "items": agreement,
        },
    }
    provenance = {
        "git_commit": commit,
        "git_dirty": False,
        "analysis_config": analysis_config_path.resolve().relative_to(root).as_posix(),
        "analysis_config_sha256": sha256_file(analysis_config_path),
        "design_freeze_sha256": sha256_file(root / config["references"]["design_freeze"]),
        "runtime_freeze_sha256": sha256_file(runtime_freeze),
        "canonical_run_prefix": analysis["canonical_run_prefix"],
        "actual_run_prefix": analysis["actual_run_prefix"],
        "model": {
            key: values[key]
            for key in (
                "name",
                "revision",
                "tokenizer_revision",
                "dtype",
                "quantization",
                "attn_implementation",
            )
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "bitsandbytes": bitsandbytes.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "stem": spec["stem"],
        "tail": spec["tail"],
        "accounts": accounts,
        "validation_rows_scored": 0,
    }
    files = {
        "report.json": (
            json.dumps(
                {
                    "schema_version": 1,
                    "research_result": "post_result_train_only_diagnostic",
                    "provenance": provenance,
                    "report": report,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8"),
        "token_logprobs.json": (json.dumps(records, sort_keys=True) + "\n").encode("utf-8"),
    }
    return publish(output, files, kind="train_recipient_logprob")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_config", type=Path)
    print(run(parser.parse_args().analysis_config))


if __name__ == "__main__":
    main()
