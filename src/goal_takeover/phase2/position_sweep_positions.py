"""Label-blind positions and model-free checks for the train-only position sweep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from goal_takeover.phase2.argument_recipient_672_features import _verified_artifact
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.phase2.argument_recipient_672_selection_pointer import (
    pair_index,
    pointer_indices,
    presentation_text,
    recipient_first_label,
    with_block_position,
)
from goal_takeover.phase2.argument_recipient_672_train_readout import (
    clean_commit,
    train_rows_and_run_ids,
)
from goal_takeover.storage.run_writer import canonical_json_bytes, sha256_bytes, sha256_file

POSITIONS = ("A1", "A2", "T", "S", "G", "D")


def safe_path(root: Path, relative: str | Path) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe repository path: {relative}")
    resolved = root / path
    if not resolved.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repository: {relative}")
    return resolved


def read_config(path: Path) -> tuple[Path, dict]:
    root = Path.cwd().resolve()
    path = safe_path(root, path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("spec", "experiment_config", "canonical_runtime_freeze"):
        safe_path(root, spec[key])
    for value in (
        spec["canonical_run_prefix"],
        spec["actual_run_prefix"],
        spec["capture"]["run_id_prefix"],
        spec["analysis"]["output_id"],
    ):
        if Path(value).name != value or value in {".", ".."}:
            raise ValueError("unsafe output ID")
    if spec["schema_version"] != 1 or tuple(spec["capture"]["positions"]) != POSITIONS:
        raise ValueError("position sweep schema or position order differs")
    return root, spec


def context(path: Path, runtime: Path | None = None, *, matching: bool = False) -> tuple:
    root, spec = read_config(path)
    runtime = runtime or Path(spec["canonical_runtime_freeze"])
    safe_path(root, runtime)
    config, declaration, _ = load_frozen_plan(
        safe_path(root, spec["experiment_config"]),
        runtime_freeze_override=runtime,
        require_matching_head=matching,
    )
    rows, run_ids = train_rows_and_run_ids(declaration, spec["canonical_run_prefix"])
    rows = with_block_position(rows, declaration["task_specs"])
    rows = [rows[i] for i in pointer_indices(rows)]
    accounts = declaration["account_value_ids"]
    if (
        len(rows) != 240
        or len(pair_index(rows, [recipient_first_label(r, accounts) for r in rows])) != 120
    ):
        raise ValueError("expected 240 train rows / 120 pairs")
    return root, spec, config, rows, run_ids, accounts


def verified_json(bundle: Path, manifest: dict, name: str) -> Any:
    return json.loads(_verified_artifact(bundle, manifest, name).read_text(encoding="utf-8"))


def verify_manifest(bundle: Path) -> dict:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest["run_id"] != bundle.name:
        raise ValueError("manifest run ID differs")
    for entry in manifest["artifacts"]:
        safe_path(bundle, entry["relative_path"])
        _verified_artifact(bundle, manifest, entry["relative_path"])
    return manifest


def canonical_prefix(root: Path, run_id: str, row: dict, spec: dict) -> tuple[dict, dict, dict]:
    if row["split_candidate"] != "train":
        raise ValueError("validation row rejected")
    bundle = safe_path(root, f"artifacts/runs/{run_id}")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest["run_id"] != run_id:
        raise ValueError("canonical manifest ID differs")
    run = verified_json(bundle, manifest, "run.json")
    prefix = verified_json(bundle, manifest, "prefix.json")
    condition = verified_json(bundle, manifest, "condition.json")
    position = run["selected_position"]
    ids = prefix["token_ids"]
    if (
        run["condition_id"] != row["condition_id"]
        or run["run_id"] != run_id
        or run["status"] != "completed"
        or run["split"] != "train"
        or run["git_dirty"] is not False
        or position["name"] != "Tend_assistant"
        or position["token_index"] != len(ids) - 1
        or not ids
        or position["token_id"] != ids[-1]
        or prefix["text_sha256"] != sha256_bytes(prefix["text"].encode("utf-8"))
        or run["runtime_freeze_sha256"] != sha256_file(root / spec["canonical_runtime_freeze"])
        or condition
        != {key: value for key, value in row.items() if key != "account_block_position"}
    ):
        raise ValueError(f"{run_id}: canonical prefix or provenance differs")
    if len(prefix["offsets"]) != len(ids) or any(
        item["token_index"] != i
        or item["token_id"] != ids[i]
        or not 0 <= item["start"] <= item["end"] <= len(prefix["text"])
        for i, item in enumerate(prefix["offsets"])
    ):
        raise ValueError("canonical offsets differ")
    return prefix, condition, manifest


def presentation_order(row: dict, accounts: dict) -> tuple[str, str]:
    text = presentation_text(row)
    values = [accounts[row[key]] for key in ("recipient_value_id", "reference_value_id")]
    if len(set(values)) != 2 or any(text.count(v) != 1 for v in values):
        raise ValueError("accounts must each occur exactly once")
    return tuple(sorted(values, key=text.index))


def span_last_token(prefix: dict, account: str) -> int:
    text = prefix["text"]
    if text.count(account) != 1:
        raise ValueError("account must occur exactly once in prefix")
    start = text.index(account)
    indices = [
        o["token_index"]
        for o in prefix["offsets"]
        if o["end"] > o["start"] and o["end"] > start and o["start"] < start + len(account)
    ]
    if not indices:
        raise ValueError("account has no overlapping tokens")
    return max(indices)


def first_digit(account: str) -> str:
    if not account.startswith("GB") or len(account) < 3 or account[2] not in "0123456789":
        raise ValueError("expected a GB account followed by an ASCII digit")
    return account[2]


def call_continuation_ids(
    tokenizer: Any, prefix: dict, stem: str, gb_text: str, digit: str
) -> dict:
    stages = [list(prefix["token_ids"])]
    for suffix in (stem, stem + gb_text, stem + gb_text + digit):
        ids = list(tokenizer(prefix["text"] + suffix, add_special_tokens=False)["input_ids"])
        previous = stages[-1]
        if ids[: len(previous)] != previous or len(ids) <= len(previous):
            raise ValueError("joint tokenization changed prefix or produced no continuation")
        stages.append(ids)
    if len(stages[2]) != len(stages[1]) + 1 or len(stages[3]) != len(stages[2]) + 1:
        raise ValueError("GB and digit must each be one token")
    return {
        "input_ids": stages[3],
        "S": len(stages[1]) - 1,
        "G": len(stages[2]) - 1,
        "D": len(stages[3]) - 1,
    }


def resolve_positions(row: dict, prefix: dict, accounts: dict, tokenizer: Any, spec: dict) -> dict:
    first, second = presentation_order(row, accounts)
    if prefix["text"].index(first) >= prefix["text"].index(second):
        raise ValueError("prefix order differs from presentation order")
    capture = spec["capture"]
    continuations = {
        key: call_continuation_ids(
            tokenizer, prefix, capture["stem"], capture["gb_text"], first_digit(value)
        )
        for key, value in accounts.items()
    }
    selected = continuations[row["recipient_value_id"]]
    ids = selected["input_ids"]
    indices = {
        "A1": span_last_token(prefix, first),
        "A2": span_last_token(prefix, second),
        "T": len(prefix["token_ids"]) - 1,
        **{p: selected[p] for p in ("S", "G", "D")},
    }
    result = {
        "position_rule_version": "position_sweep_v1",
        "position_order": list(POSITIONS),
        "input_ids": ids,
        "positions": {},
        "prefix_token_count": len(prefix["token_ids"]),
        "input_token_count": len(ids),
        "continuation_text": capture["stem"]
        + capture["gb_text"]
        + first_digit(accounts[row["recipient_value_id"]]),
        "digit_token_ids": {key: v["input_ids"][-1] for key, v in continuations.items()},
    }
    for name, index in indices.items():
        offset = prefix["offsets"][index] if index < len(prefix["token_ids"]) else None
        result["positions"][name] = {
            "token_index": index,
            "token_id": ids[index],
            "decoded": tokenizer.decode([ids[index]]),
            "offset": {k: offset[k] for k in ("start", "end")} if offset else None,
        }
    for name, value in (("A1", first), ("A2", second)):
        start = prefix["text"].index(value)
        result["positions"][name].update(account=value, character_span=[start, start + len(value)])
    # Continuation offsets are local to the serialized full input, including special tokens.
    encoded = tokenizer(
        prefix["text"] + result["continuation_text"],
        add_special_tokens=False,
        return_offsets_mapping=True,
    )
    if list(encoded["input_ids"]) != ids:
        raise ValueError("offset tokenization differs")
    for name in ("S", "G", "D"):
        start, end = encoded["offset_mapping"][indices[name]]
        result["positions"][name]["offset"] = {"start": start, "end": end}
    return result


def validate_tokenizations(rows: list[dict], resolved: list[dict], accounts: dict) -> dict:
    if len(rows) != len(resolved) or not rows:
        raise ValueError("unaligned tokenizer checks")
    common = None
    for row, value in zip(rows, resolved, strict=True):
        presentation_order(row, accounts)
        p = value["positions"]
        tokens = (p["S"]["token_id"], p["G"]["token_id"])
        if common is not None and tokens != common:
            raise ValueError("S/G tokens differ across conditions")
        common = tokens
        digits = value["digit_token_ids"]
        if digits[row["recipient_value_id"]] == digits[row["reference_value_id"]]:
            raise ValueError("paired accounts do not diverge after GB")
    pairs = pair_index(rows, [recipient_first_label(r, accounts) for r in rows])
    for a, b in pairs:
        for name in ("A1", "A2"):
            if (
                resolved[a]["positions"][name]["account"]
                != resolved[b]["positions"][name]["account"]
            ):
                raise ValueError("pair presentation accounts differ")
    return {
        "prefix_stable": True,
        "single_token_GB_and_digit": True,
        "common_S_G": True,
        "distinct_digits": True,
        "accounts_once": True,
        "pair_accounts_match": True,
        "prefix_order_matches": True,
    }


def write_report(root: Path, kind: str, report: dict) -> dict:
    path = root / f"artifacts/phase2-position-sweep-{kind}-{report['git_commit'][:7]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json_bytes(report).decode("utf-8"))
    return report


def tokenizer_preflight(config_path: Path) -> dict:
    from transformers import AutoTokenizer

    from goal_takeover.models.qwen import chat_template_sha256

    root, spec, config, rows, run_ids, accounts = context(config_path)
    commit = clean_commit(root)
    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["name"],
        revision=config["model"]["tokenizer_revision"],
        trust_remote_code=config["model"]["trust_remote_code"],
    )
    values = [
        resolve_positions(
            r,
            canonical_prefix(root, run_ids[r["condition_id"]], r, spec)[0],
            accounts,
            tokenizer,
            spec,
        )
        for r in rows
    ]
    checks = validate_tokenizations(rows, values, accounts)
    return write_report(
        root,
        "tokenizer-preflight",
        {
            "status": "passed",
            "git_commit": commit,
            "checks": checks,
            "condition_count": len(rows),
            "tokenizer_revision": config["model"]["tokenizer_revision"],
            "chat_template_sha256": chat_template_sha256(tokenizer),
            "common_tokens": {p: values[0]["positions"][p] for p in ("S", "G")},
            "analysis_config_sha256": sha256_file(root / config_path),
            "spec_sha256": sha256_file(root / spec["spec"]),
            "validation_rows_loaded": 0,
        },
    )


def stem_statistics(generations_by_run: dict[str, list[dict]], stem: str) -> dict:
    expected = stem.split("<tool_call>", 1)[-1].lstrip("\n")
    count = matched = 0
    mismatched, absent = [], []
    for run_id, generations in generations_by_run.items():
        seen = False
        for generation in generations:
            text = generation["raw_text"]
            if text is not None and "send_money" in text:
                seen = True
                count += 1
                if expected in text:
                    matched += 1
                elif run_id not in mismatched:
                    mismatched.append(run_id)
        if not seen:
            absent.append(run_id)
    return {
        "send_money_generations": count,
        "matching_generations": matched,
        "mismatching_run_ids": mismatched,
        "no_send_money_run_ids": absent,
        "mismatch_fraction": (count - matched) / count if count else None,
    }


def stem_preflight(config_path: Path) -> dict:
    root, spec = read_config(config_path)
    commit = clean_commit(root)
    generations = {}
    for number in range(1, spec["actual_run_count"] + 1):
        run_id = f"{spec['actual_run_prefix']}-a{number:03d}"
        bundle = root / "artifacts/runs" / run_id
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        if manifest["run_id"] != run_id:
            raise ValueError("actual run ID differs")
        generations[run_id] = verified_json(bundle, manifest, "generations.json")
    return write_report(
        root,
        "stem-preflight",
        {
            "git_commit": commit,
            "status": "recorded",
            "analysis_config_sha256": sha256_file(root / config_path),
            "spec_sha256": sha256_file(root / spec["spec"]),
            **stem_statistics(generations, spec["capture"]["stem"]),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tokenizer-preflight", "stem-preflight"))
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    print(
        (tokenizer_preflight if args.command == "tokenizer-preflight" else stem_preflight)(
            args.config
        )
    )


if __name__ == "__main__":
    main()
