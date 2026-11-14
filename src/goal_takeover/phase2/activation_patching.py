"""Train-only, bidirectional single-site patching; capture is never implicit in preflight."""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import math
import os
import struct
import time
from collections import defaultdict
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

from goal_takeover.instrumentation.activation_hooks import (  # noqa: E402
    ResidualCapture,
    ResidualPatch,
)
from goal_takeover.instrumentation.huggingface import transformer_block_names  # noqa: E402
from goal_takeover.phase2 import position_sweep_nod as nod  # noqa: E402
from goal_takeover.phase2.argument_recipient_672_selection_pointer import (  # noqa: E402
    pair_index,
    recipient_first_label,
)
from goal_takeover.phase2.argument_recipient_672_train_readout import (  # noqa: E402
    clean_commit,
    publish,
)
from goal_takeover.phase2.position_sweep_capture import (  # noqa: E402
    completed_bundle,
    environment,
    load_model,
    write_bundle,
)
from goal_takeover.phase2.position_sweep_positions import (  # noqa: E402
    canonical_prefix,
    context,
    presentation_order,
    safe_path,
    verified_json,
    verify_manifest,
)
from goal_takeover.storage.run_writer import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)

POSITIONS = ("T", "S", "G")
DONOR_KINDS = ("matched", "self", "cross")
SERIALIZATION = "patching_recipient_first_v1"
VALIDATION = {
    "full_declaration_loaded_for_integrity": True,
    "validation_declaration_rows_loaded": 192,
    "validation_run_bundles_loaded": 0,
    "validation_rows_used": 0,
}


def require_train(rows: list[dict]) -> None:
    if not rows or any(row.get("split_candidate") != "train" for row in rows):
        raise ValueError("only nonempty train rows are allowed")


def read_config(path: Path) -> tuple[Path, dict]:
    root = Path.cwd().resolve()
    config = nod.read_json(safe_path(root, path))
    for key in ("spec", "sweep_config", "nod_config"):
        safe_path(root, config[key])
    for key in ("runtime_freeze", "collection_manifest", "candidate_report"):
        safe_path(root, config["reference"][key])
    for prefix in (
        config["reference"]["input_run_id_prefix"],
        config["patching"]["run_id_prefix"],
        config["analysis"]["output_id"],
        config["local_wording"]["output_id"],
    ):
        nod.run_id(prefix, "canonical-c001")
    patch, analysis = config["patching"], config["analysis"]
    if (
        config["schema_version"] != 1
        or patch["positions"] != list(POSITIONS)
        or patch["donor_kinds"] != list(DONOR_KINDS)
        or patch["candidate_scoring"] != "cached_token_by_token"
        or patch["replacement"] != "full_residual_block_output"
        or patch["serialization"] != SERIALIZATION
        or patch["layers"] != sorted(set(patch["layers"]))
        or not patch["layers"]
        or any(type(layer) is not int or not 0 <= layer <= 35 for layer in patch["layers"])
        or analysis["positive_control"]
        != {
            "position": "G",
            "layer": 35,
            "target": "full_vocabulary_next_token_log_probs",
            "comparison": "bitwise_donor_clean",
        }
        or analysis["positive_control"]["layer"] not in patch["layers"]
    ):
        raise ValueError("patching schema or fixed calculation contract differs")
    return root, config


def load_plan(path: Path, runtime: Path | None = None, *, matching: bool = False) -> dict:
    root, settings = read_config(path)
    # Reuse the old frozen declaration checks without changing any old module or record.
    source = nod.load_plan(
        Path(settings["nod_config"]), Path(settings["reference"]["runtime_freeze"])
    )
    _, sweep, config, rows, ids, accounts = context(
        Path(settings["sweep_config"]), runtime, matching=matching
    )
    require_train(rows)
    declaration = nod.read_json(root / config["references"]["declaration"])
    count = sum(row["split_candidate"] == "validation" for row in declaration["condition_specs"])
    if count != VALIDATION["validation_declaration_rows_loaded"]:
        raise ValueError("validation declaration count differs")
    if source["rows"] != rows or source["sweep"] != sweep:
        raise ValueError("D-free source and sweep declarations differ")
    reference = settings["reference"]
    hashes = {
        key: sha256_file(safe_path(root, reference[key]))
        for key in ("runtime_freeze", "collection_manifest", "candidate_report")
    }
    collection = nod.read_json(root / reference["collection_manifest"])
    report = nod.read_json(root / reference["candidate_report"])
    report_path = root / reference["candidate_report"]
    report_manifest = nod.read_json(report_path.parent / "manifest.json")
    report_entry = report_manifest["artifacts"][report_path.name]
    if (
        collection["runtime_freeze_sha256"] != hashes["runtime_freeze"]
        or collection["git_commit"] != source["freeze"]["git_commit"]
        or report["provenance"]["runtime_freeze_sha256"] != hashes["runtime_freeze"]
        or report_entry["sha256"] != hashes["candidate_report"]
        or report_entry["bytes"] != report_path.stat().st_size
    ):
        raise ValueError("D-free reference collection/report differs")
    indexed = {row["run_id"]: row for row in collection["runs"] if row["capture_kind"] == "nod"}
    expected = {nod.run_id(reference["input_run_id_prefix"], ids[r["condition_id"]]) for r in rows}
    if len(indexed) != len(rows) or set(indexed) != expected:
        raise ValueError("D-free source IDs differ")
    labels = [recipient_first_label(row, accounts) for row in rows]
    pairs = pair_index(rows, labels)
    plan = {
        "root": root,
        "settings": settings,
        "sweep": sweep,
        "config": config,
        "rows": rows,
        "run_ids": ids,
        "accounts": accounts,
        "labels": labels,
        "pairs": pairs,
        "donors": donor_table(rows, labels, pairs, accounts),
        "source": source,
        "source_rows": indexed,
        "reference_sha256": hashes,
        "analysis_config_sha256": sha256_file(root / path),
        "spec_sha256": sha256_file(root / settings["spec"]),
        "sweep_config_sha256": sha256_file(root / settings["sweep_config"]),
    }
    if runtime is not None:
        plan["freeze"] = nod.read_json(safe_path(root, runtime))
        plan["runtime"] = runtime.as_posix()
        plan["runtime_sha256"] = sha256_file(root / runtime)
        validate_freeze(plan, plan["freeze"])
    return plan


def identity(plan: dict) -> dict:
    return {
        "git_commit": clean_commit(plan["root"]),
        "git_dirty": False,
        **{
            key: plan[key]
            for key in (
                "analysis_config_sha256",
                "spec_sha256",
                "sweep_config_sha256",
                "reference_sha256",
            )
        },
        **VALIDATION,
    }


def report_path(plan: dict, kind: str) -> Path:
    commit = clean_commit(plan["root"])
    return plan["root"] / f"artifacts/phase2-activation-patching-{kind}-{commit[:7]}.json"


def write_report(path: Path, report: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json_bytes(report).decode())
    return report


def patching_call_text(sweep: dict, row: dict, account: str) -> str:
    require_train([row])
    call = row["expected_send_money"]
    if call["name"] != "send_money" or "recipient" not in call["arguments"]:
        raise ValueError("expected send_money recipient call")
    arguments = {"recipient": account}
    arguments.update(
        {key: call["arguments"][key] for key in sorted(call["arguments"]) if key != "recipient"}
    )
    payload = {"name": call["name"], "arguments": arguments}
    body = json.dumps(payload, ensure_ascii=False, sort_keys=False, separators=(", ", ": "))
    text = "<tool_call>\n" + body + "\n</tool_call><|im_end|>"
    if not text.startswith(sweep["capture"]["stem"] + account):
        raise ValueError("recipient-first call differs from frozen stem")
    expected = {**call, "arguments": {**call["arguments"], "recipient": account}}
    if json.loads(body) != expected:
        raise ValueError("call arguments lost during serialization")
    return text


def account_remainder_ids(
    tokenizer: Any, sweep: dict, row: dict, account: str, *, prefix: dict
) -> list[int]:
    call = patching_call_text(sweep, row, account)
    stem = sweep["capture"]["stem"]
    gb = sweep["capture"]["gb_text"]
    if not account.startswith(gb):
        raise ValueError("candidate does not start with common GB text")
    base_text = prefix["text"] + stem + gb
    base = list(tokenizer(base_text, add_special_tokens=False)["input_ids"])
    if base[: len(prefix["token_ids"])] != prefix["token_ids"]:
        raise ValueError("joint tokenization changed canonical prefix")
    full = tokenizer(prefix["text"] + call, add_special_tokens=False, return_offsets_mapping=True)
    end = len(prefix["text"] + stem + account)
    indices = [
        i
        for i, (start, stop) in enumerate(full["offset_mapping"])
        if stop > len(base_text) and start < end and stop > start
    ]
    if (
        list(full["input_ids"][: len(base)]) != base
        or not indices
        or indices[0] != len(base)
        or full["offset_mapping"][indices[-1]][1] != end
        or any(full["offset_mapping"][i][1] > end for i in indices)
    ):
        raise ValueError("account boundary is inside a token or prefix changed")
    result = list(full["input_ids"][len(base) : indices[-1] + 1])
    short = list(tokenizer(prefix["text"] + stem + account, add_special_tokens=False)["input_ids"])
    if short != base + result:
        raise ValueError("account-only and complete call tokenization differ")
    return result


def donor_table(rows: list[dict], labels: Any, pairs: list, accounts: dict) -> dict:
    require_train(rows)
    if len(labels) != len(rows) or len({r["condition_id"] for r in rows}) != len(rows):
        raise ValueError("donor row/label alignment differs")
    table = {}
    covered = []
    orders = [presentation_order(row, accounts) for row in rows]
    for first, second in pairs:
        if labels[first] == labels[second] or orders[first] != orders[second]:
            raise ValueError("matched pair labels/order differ")
        covered.extend((first, second))
        for recipient, donor in ((first, second), (second, first)):
            row = rows[recipient]
            candidates = sorted(
                (
                    other
                    for i, other in enumerate(rows)
                    if other["family_id"] != row["family_id"]
                    and labels[i] == labels[donor]
                    and orders[i] == orders[recipient]
                ),
                key=lambda other: other["draft_condition_id"],
            )
            if not candidates:
                raise ValueError(f"{row['condition_id']}: no cross donor")
            index = int(sha256_bytes(row["draft_condition_id"].encode("utf-8")), 16) % len(
                candidates
            )
            table[row["condition_id"]] = {
                "matched": rows[donor]["condition_id"],
                "self": row["condition_id"],
                "cross": candidates[index]["condition_id"],
            }
    if sorted(covered) != list(range(len(rows))):
        raise ValueError("donor pairs do not partition rows")
    return table


def read_input(plan: dict, row: dict) -> dict:
    require_train([row])
    canonical_id = plan["run_ids"][row["condition_id"]]
    prefix, condition, _ = canonical_prefix(plan["root"], canonical_id, row, plan["sweep"])
    source = nod.read_bundle(plan["source"], row, prefix, canonical_id, "nod", tensors=False)
    rid = nod.run_id(plan["settings"]["reference"]["input_run_id_prefix"], canonical_id)
    if source["manifest_sha256"] != plan["source_rows"][rid]["manifest_sha256"]:
        raise ValueError("D-free input manifest differs from collection")
    resolved = source["resolved"]
    positions = {name: resolved["positions"][name] for name in POSITIONS}
    ids = resolved["input_ids"]
    t, s, g = (positions[name]["token_index"] for name in POSITIONS)
    if (
        t != len(prefix["token_ids"]) - 1
        or s != len(ids) - 2
        or g != len(ids) - 1
        or g - t != 17
        or any(
            positions[name]["token_id"] != ids[positions[name]["token_index"]] for name in POSITIONS
        )
    ):
        raise ValueError("T/S/G input alignment differs")
    return {
        "row": row,
        "condition": condition,
        "prefix": prefix,
        "source_run_id": rid,
        "source_manifest_sha256": source["manifest_sha256"],
        "input_ids": ids,
        "positions": positions,
        "t_index": t,
        "g_index": g,
        "digit_token_ids": resolved["digit_token_ids"],
        "source": source,
    }


def prepare_input(plan: dict, row: dict, tokenizer: Any) -> dict:
    item = read_input(plan, row)
    accounts = presentation_order(row, plan["accounts"])
    remainders = {
        name: account_remainder_ids(tokenizer, plan["sweep"], row, account, prefix=item["prefix"])
        for name, account in zip(("first", "second"), accounts, strict=True)
    }
    base = tokenizer(
        item["prefix"]["text"] + item["source"]["resolved"]["continuation_text"],
        add_special_tokens=False,
    )["input_ids"]
    if list(base) != item["input_ids"] or remainders["first"][0] == remainders["second"][0]:
        raise ValueError("saved input or discriminating token differs")
    item.update(
        accounts=dict(zip(("first", "second"), accounts, strict=True)),
        remainders=remainders,
        serialization=SERIALIZATION,
        call_text_sha256={
            name: sha256_bytes(
                (item["prefix"]["text"] + patching_call_text(plan["sweep"], row, account)).encode()
            )
            for name, account in zip(("first", "second"), accounts, strict=True)
        },
    )
    return item


def patching_tokenizer_preflight(config_path: Path) -> dict:
    from transformers import AutoTokenizer

    plan = load_plan(config_path)
    target = report_path(plan, "tokenizer-preflight")
    if target.exists():
        raise FileExistsError(target)
    config = plan["config"]["model"]
    tokenizer = AutoTokenizer.from_pretrained(
        config["name"],
        revision=config["tokenizer_revision"],
        trust_remote_code=config["trust_remote_code"],
        local_files_only=True,
    )
    common = None
    rows = []
    for row in plan["rows"]:
        item = prepare_input(plan, row, tokenizer)
        suffix = item["input_ids"][item["t_index"] + 1 :]
        if common is not None and common != suffix:
            raise ValueError("17 post-T tokens are not common")
        common = suffix
        rows.append(
            {
                "condition_id": row["condition_id"],
                "source_run_id": item["source_run_id"],
                "source_manifest_sha256": item["source_manifest_sha256"],
                "remainder_lengths": {k: len(v) for k, v in item["remainders"].items()},
            }
        )
    return write_report(
        target,
        {
            **identity(plan),
            "status": "passed",
            "condition_count": len(rows),
            "common_post_t_ids": common,
            "donors": plan["donors"],
            "conditions": rows,
            "serialization": SERIALIZATION,
        },
    )


def tensor_bytes(value: Any) -> bytes:
    import torch

    return value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()


def tensor_record(value: Any) -> dict:
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "sha256": sha256_bytes(tensor_bytes(value)),
    }


def compare_distributions(current: Any, donor: Any) -> dict:
    import torch

    if (
        current.shape != donor.shape
        or current.dtype != torch.float32
        or donor.dtype != torch.float32
    ):
        raise ValueError("distribution shape/dtype differs")
    if not torch.isfinite(current).all() or not torch.isfinite(donor).all():
        raise ValueError("nonfinite next-token distribution")
    return {
        "current": tensor_record(current),
        "donor": tensor_record(donor),
        "bit_exact": tensor_bytes(current) == tensor_bytes(donor),
        "maximum_absolute_difference": float((current - donor).abs().max()),
    }


def _float_bits(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite scalar")
        return {"float64_bytes": struct.pack(">d", value).hex()}
    if isinstance(value, dict):
        return {key: _float_bits(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_float_bits(item) for item in value]
    return value


def records_exact(first: dict, second: dict) -> bool:
    return _float_bits(first) == _float_bits(second)


class ForwardStats:
    """Synchronized forward timings; other work remains in condition wall time."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)
        self.seconds: dict[str, float] = defaultdict(float)

    def call(self, model: Any, kind: str, **kwargs: Any) -> Any:
        import torch

        device = next(model.parameters()).device
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        start = time.monotonic()
        output = model(**kwargs)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        self.counts[kind] += 1
        self.seconds[kind] += time.monotonic() - start
        return output

    def record(self) -> dict:
        return {"forward_counts": dict(self.counts), "forward_seconds": dict(self.seconds)}


CAST_WARNING_LOGGER = "bitsandbytes.autograd._functions"
CAST_WARNING_PREFIX = "MatMul8bitLt: inputs will be cast from"


class RepeatedCastWarningFilter(logging.Filter):
    """Pass the first bitsandbytes dtype-cast warning per argument set; count the rest.

    Only this message is limited. Other warnings and errors pass unchanged, and the
    cast itself (computation dtype) is untouched because this filters log records only.
    """

    def __init__(self) -> None:
        super().__init__()
        self.seen: set[tuple] = set()
        self.suppressed = 0

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno > logging.WARNING or not str(record.msg).startswith(CAST_WARNING_PREFIX):
            return True
        key = (str(record.msg), tuple(str(arg) for arg in (record.args or ())))
        if key in self.seen:
            self.suppressed += 1
            return False
        self.seen.add(key)
        return True

    def record(self) -> dict:
        return {
            "logger": CAST_WARNING_LOGGER,
            "message_prefix": CAST_WARNING_PREFIX,
            "first_occurrences_emitted": len(self.seen),
            "repeats_suppressed": self.suppressed,
        }


class limited_cast_warning:  # noqa: N801 - used as a context manager
    """Attach the filter to the bitsandbytes logger only for the enclosed run."""

    def __enter__(self) -> RepeatedCastWarningFilter:
        self.filter = RepeatedCastWarningFilter()
        logging.getLogger(CAST_WARNING_LOGGER).addFilter(self.filter)
        return self.filter

    def __exit__(self, *_exc: object) -> None:
        logging.getLogger(CAST_WARNING_LOGGER).removeFilter(self.filter)


MEMINFO_KEYS = ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
STATUS_KEYS = ("VmRSS", "VmHWM", "VmSwap")
VMSTAT_KEYS = ("pswpin", "pswpout", "pgmajfault")


def _kib_fields(text: str, keys: tuple[str, ...]) -> dict:
    found = {}
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        if name in keys and rest.split():
            found[f"{name}_kib"] = int(rest.split()[0])
    return found


def host_resources(proc: Path = Path("/proc")) -> dict:
    """Diagnostic host snapshot; read-only, never used for scoring or gating."""
    snapshot: dict[str, Any] = {"recorded_at": datetime.now(UTC).isoformat()}
    readers = {
        "meminfo": lambda t: _kib_fields(t, MEMINFO_KEYS),
        "self/status": lambda t: _kib_fields(t, STATUS_KEYS),
        "vmstat": lambda t: {
            k: int(v)
            for k, _, v in (line.partition(" ") for line in t.splitlines())
            if k in VMSTAT_KEYS
        },
        "pressure/memory": lambda t: {
            line.split()[0]: {
                k: float(v) for k, v in (f.split("=") for f in line.split()[1:]) if k != "total"
            }
            for line in t.splitlines()
            if line.split()
        },
    }
    for name, parse in readers.items():
        try:
            snapshot[name.replace("/", "_")] = parse((proc / name).read_text())
        except (OSError, ValueError):
            snapshot[name.replace("/", "_")] = None
    return snapshot


def resource_line(snapshot: dict) -> str:
    memory = snapshot.get("meminfo") or {}
    try:
        available = memory["MemAvailable_kib"] / 1024**2
        swap = (memory["SwapTotal_kib"] - memory["SwapFree_kib"]) / 1024**2
    except KeyError:
        return "host memory unavailable"
    return f"RAM available {available:.2f} GiB, swap used {swap:.2f} GiB"


def start_progress(progress: dict | None, stage: str, cell_count: int) -> ForwardStats:
    """Reset a mutable progress record so a failure handler can report partial work."""
    stats = ForwardStats()
    if progress is not None:
        progress.clear()
        progress.update(
            stage=stage,
            stats=stats,
            started_monotonic=time.monotonic(),
            started_at=datetime.now(UTC).isoformat(),
            host_at_start=host_resources(),
            cell_count=cell_count,
            cells_completed=0,
            last_completed_cell=None,
            groups=[],
        )
    return stats


def progress_record(progress: dict | None) -> dict | None:
    """JSON-safe view of partial progress; elapsed time is measured at failure."""
    if not progress:
        return None
    record = {
        key: value
        for key, value in progress.items()
        if key not in ("stats", "started_monotonic", "group_monotonic")
    }
    record["elapsed_seconds_at_failure"] = time.monotonic() - progress["started_monotonic"]
    record["timing"] = progress["stats"].record()
    return record


def crop_cache(cache: Any, length: int) -> None:
    cache.crop(length)
    if cache.get_seq_length() != length:
        raise ValueError("cache crop failed")


def prefix_cache(
    model: Any, input_ids: list[int], t_index: int, *, stats: ForwardStats | None = None
) -> Any:
    import torch

    if not 0 < t_index < len(input_ids):
        raise ValueError("invalid T for prefix cache")
    stats = stats or ForwardStats()
    args = {
        "input_ids": torch.tensor([input_ids[:t_index]], device=next(model.parameters()).device),
        "use_cache": True,
    }
    # Prefix logits are unused; avoiding a full-prefix vocabulary tensor is essential.
    if "logits_to_keep" in inspect.signature(model.forward).parameters:
        args["logits_to_keep"] = 1
    with torch.no_grad():
        cache = stats.call(model, "prefix", **args).past_key_values
    if cache.get_seq_length() != t_index or not callable(getattr(cache, "crop", None)):
        raise ValueError("model does not expose a restorable prefix cache")
    return cache


def run_suffix(
    model: Any,
    cache: Any,
    input_ids: list[int],
    t_index: int,
    g_index: int,
    patch: tuple | None = None,
    capture_names: list[str] | None = None,
    *,
    stats: ForwardStats | None = None,
) -> dict:
    import torch

    if cache.get_seq_length() != t_index or not 0 <= t_index < g_index < len(input_ids):
        raise ValueError("suffix cache/positions differ")
    stats = stats or ForwardStats()
    device = next(model.parameters()).device
    indices = [0, g_index - t_index - 1, g_index - t_index]
    with torch.no_grad(), ExitStack() as stack:
        if patch is not None:
            module, position, vector = patch
            if position not in POSITIONS:
                raise ValueError("patch position outside T/S/G")
            stack.enter_context(
                ResidualPatch(
                    model, module, indices[POSITIONS.index(position)], vector.to(device=device)
                )
            )
        captured = (
            stack.enter_context(ResidualCapture(model, capture_names, token_indices=indices))
            if capture_names is not None
            else None
        )
        output = stats.call(
            model,
            "suffix",
            input_ids=torch.tensor([input_ids[t_index : g_index + 1]], device=device),
            use_cache=True,
            past_key_values=cache,
        )
    if output.past_key_values is not cache or cache.get_seq_length() != g_index + 1:
        raise ValueError("model replaced or misaligned mutable suffix cache")
    if output.logits.shape[:2] != (1, g_index - t_index + 1):
        raise ValueError("suffix must retain all logits")
    residuals = {}
    if captured is not None:
        for name, values in captured.values.items():
            if (
                len(values) != 1
                or values[0].shape[:2] != (1, len(POSITIONS))
                or not torch.isfinite(values[0]).all()
            ):
                raise ValueError("captured residual shape/count/finite differs")
            residuals[name] = values[0]
    return {"logits": output.logits, "residuals": residuals}


def score_candidates(
    model: Any,
    cache: Any,
    g_logits: Any,
    remainders: dict[str, list[int]],
    g_length: int,
    *,
    stats: ForwardStats | None = None,
) -> dict:
    import torch

    stats = stats or ForwardStats()
    if list(remainders) != ["first", "second"] or cache.get_seq_length() != g_length:
        raise ValueError("candidate order or G cache differs")
    initial = torch.log_softmax(g_logits.float(), dim=-1)
    scores = {}
    device = next(model.parameters()).device
    with torch.no_grad():
        for name, ids in remainders.items():
            if not ids:
                raise ValueError("empty candidate remainder")
            values = [float(initial[ids[0]])]
            try:
                for previous, target in zip(ids[:-1], ids[1:], strict=True):
                    output = stats.call(
                        model,
                        "token",
                        input_ids=torch.tensor([[previous]], device=device),
                        use_cache=True,
                        past_key_values=cache,
                    )
                    if output.past_key_values is not cache or output.logits.shape[:2] != (1, 1):
                        raise ValueError("incremental candidate output differs")
                    logprobs = torch.log_softmax(output.logits[0, 0].float(), dim=-1)
                    if not torch.isfinite(logprobs).all():
                        raise ValueError("nonfinite candidate distribution")
                    values.append(float(logprobs[target]))
            finally:
                crop_cache(cache, g_length)
            if not all(math.isfinite(value) for value in values):
                raise ValueError("nonfinite candidate score")
            scores[name] = {
                "token_ids": list(ids),
                "token_log_probabilities": values,
                "log_probability": sum(values),
            }
    return scores


def evaluate(
    model: Any,
    cache: Any,
    item: dict,
    plan: dict,
    *,
    patch: tuple | None = None,
    capture_names: list[str] | None = None,
    stats: ForwardStats | None = None,
) -> dict:
    import torch

    t, g = item["t_index"], item["g_index"]
    try:
        with torch.no_grad():
            result = run_suffix(
                model, cache, item["input_ids"], t, g, patch, capture_names, stats=stats
            )
            logprobs = torch.log_softmax(result["logits"][0].float(), dim=-1)
            if not torch.isfinite(logprobs).all():
                raise ValueError("nonfinite suffix distribution")
            distribution = logprobs[-1].detach().cpu().clone()
            tokens = item["input_ids"][t + 1 : g + 1]
            stem = float(
                logprobs[:-1, :]
                .gather(1, torch.tensor(tokens, device=logprobs.device)[:, None])
                .sum()
            )
            candidates = score_candidates(
                model, cache, result["logits"][0, -1], item["remainders"], g + 1, stats=stats
            )
            first, second = (candidates[key]["log_probability"] for key in ("first", "second"))
            digits = {
                key: float(distribution[value]) for key, value in item["digit_token_ids"].items()
            }
            top_values, top_ids = distribution.topk(
                min(plan["settings"]["patching"]["top_k"], len(distribution))
            )
            first_digit, second_digit = (
                item["remainders"][name][0] for name in ("first", "second")
            )
            maximum = max(first, second)
            record = {
                "candidates": candidates,
                "ld": first - second,
                "candidate_log_mass": maximum
                + math.log(math.exp(first - maximum) + math.exp(second - maximum)),
                "candidate_digits": digits,
                "digit_margin": float(distribution[first_digit] - distribution[second_digit]),
                "g_distribution": tensor_record(distribution),
                "top_token_ids": top_ids.tolist(),
                "top_log_probabilities": top_values.tolist(),
                "stem_log_likelihood": {"T": stem, "S": float(logprobs[-2, item["input_ids"][g]])},
                "scalar_storage_dtype": "float64",
            }
            return {
                "record": record,
                "distribution": distribution,
                "residuals": result["residuals"],
            }
    finally:
        crop_cache(cache, t)


def raw_changes(clean: dict, patched: dict, position: str, analysis: dict) -> dict:
    mass = patched["candidate_log_mass"] - clean["candidate_log_mass"]
    stem = (
        None
        if position == "G"
        else patched["stem_log_likelihood"][position] - clean["stem_log_likelihood"][position]
    )
    reasons = []
    if mass < analysis["disrupt_log_mass_threshold"]:
        reasons.append("candidate_mass")
    if stem is not None and stem < analysis["disrupt_stem_log_likelihood_threshold"]:
        reasons.append("stem_likelihood")
    return {
        "log_mass_change": mass,
        "stem_log_likelihood_change": stem,
        "disrupted": bool(reasons),
        "disruption_reasons": reasons,
    }


def model_names(model: Any, plan: dict) -> list[str]:
    names = transformer_block_names(model, block_path=plan["sweep"]["capture"]["block_path"])
    if any(layer >= len(names) for layer in plan["settings"]["patching"]["layers"]):
        raise ValueError("configured patch layer exceeds model")
    return list(names)


def clean_condition(
    model: Any, item: dict, plan: dict, names: list[str], progress: dict | None = None
) -> dict:
    import torch

    stats = start_progress(progress, "donor_clean", 1)
    start = time.monotonic()
    cache = prefix_cache(model, item["input_ids"], item["t_index"], stats=stats)
    result = evaluate(model, cache, item, plan, capture_names=names, stats=stats)
    for tensor in result["residuals"].values():
        if tensor.dtype != torch.bfloat16 or tensor.shape != (
            1,
            len(POSITIONS),
            model.config.hidden_size,
        ):
            raise ValueError("normal capture dtype/shape differs; no implicit conversion")
    if progress is not None:
        progress.update(cells_completed=1, last_completed_cell="clean")
    result.update(elapsed_seconds=time.monotonic() - start, timing=stats.record())
    return result


def intervene_condition(
    model: Any,
    item: dict,
    plan: dict,
    normals: dict,
    names: list[str],
    progress: dict | None = None,
) -> dict:
    cid = item["row"]["condition_id"]
    layers = plan["settings"]["patching"]["layers"]
    stats = start_progress(
        progress, "interventions", len(DONOR_KINDS) * len(POSITIONS) * len(layers)
    )
    start = time.monotonic()
    cache = prefix_cache(model, item["input_ids"], item["t_index"], stats=stats)
    entries, vectors = {}, {}
    positive = None
    groups = progress["groups"] if progress is not None else []
    for kind in DONOR_KINDS:
        donor = plan["donors"][cid][kind]
        group_start = time.monotonic()
        groups.append({"donor_kind": kind, "started_at": datetime.now(UTC).isoformat()})
        for position in POSITIONS:
            for layer in plan["settings"]["patching"]["layers"]:
                module = names[layer]
                vector = normals[donor]["residuals"][module][0, POSITIONS.index(position)]
                patched = evaluate(
                    model, cache, item, plan, patch=(module, position, vector), stats=stats
                )
                record = patched["record"]
                exact = records_exact(record, normals[cid]["record"]) if kind == "self" else None
                if kind == "self" and not exact:
                    raise RuntimeError(f"self patch mismatch: {position}/{layer}")
                key = f"{kind}/{position}/layer{layer}"
                if kind != "self":
                    vectors[key] = vector.contiguous()
                entries[key] = {
                    "donor_condition_id": donor,
                    "donor_run_id": nod.run_id(
                        plan["settings"]["patching"]["run_id_prefix"], plan["run_ids"][donor]
                    ),
                    "position": position,
                    "layer": layer,
                    "module_name": module,
                    "hook_point": "block_output_residual",
                    "vector": tensor_record(vector),
                    "result": record,
                    "self_exact": exact,
                    **raw_changes(
                        normals[cid]["record"], record, position, plan["settings"]["analysis"]
                    ),
                }
                control = plan["settings"]["analysis"]["positive_control"]
                if (
                    kind == "matched"
                    and position == control["position"]
                    and layer == control["layer"]
                ):
                    positive = {
                        "donor_condition_id": donor,
                        **compare_distributions(
                            patched["distribution"], normals[donor]["distribution"]
                        ),
                    }
                if progress is not None:
                    progress["cells_completed"] += 1
                    progress["last_completed_cell"] = key
        groups[-1].update(
            finished_at=datetime.now(UTC).isoformat(), seconds=time.monotonic() - group_start
        )
    repeated = evaluate(model, cache, item, plan, stats=stats)["record"]
    if not records_exact(repeated, normals[cid]["record"]):
        raise RuntimeError("normal recheck differs from first pass")
    if progress is not None:
        progress["last_completed_cell"] = "clean_recheck"
    return {
        "clean": normals[cid]["record"],
        "interventions": entries,
        "clean_recheck": repeated,
        "positive_control": positive,
        "vectors": vectors,
        "elapsed_seconds": time.monotonic() - start,
        "timing": stats.record(),
        "group_timing": groups,
    }


def check_resources(limits: dict, seconds: float, peak: int) -> None:
    if peak > limits["maximum_gpu_memory_gib"] * 1024**3:
        raise RuntimeError("GPU memory ceiling exceeded")
    if seconds > limits["maximum_seconds_per_condition"]:
        raise RuntimeError("condition time ceiling exceeded")


def patching_gpu_preflight(config_path: Path) -> dict:
    with limited_cast_warning() as warnings_filter:
        return _patching_gpu_preflight(config_path, warnings_filter)


def _patching_gpu_preflight(config_path: Path, warnings_filter: RepeatedCastWarningFilter) -> dict:
    import torch
    from safetensors.torch import load_file

    plan = load_plan(config_path)
    target = report_path(plan, "gpu-preflight")
    if target.exists():
        raise FileExistsError(target)
    report = {
        **identity(plan),
        "status": "running",
        "conditions": [],
        "additional_donor_conditions": [],
        "donors": plan["donors"],
    }
    model = None
    progress: dict = {}
    try:
        model, tokenizer = load_model(plan["config"])
        model.eval()
        torch.manual_seed(plan["settings"]["patching"]["seed"])
        names = model_names(model, plan)
        selected = plan["rows"][: plan["settings"]["preflight_condition_count"]]
        ids = {row["condition_id"] for row in selected}
        needed = ids | {donor for cid in ids for donor in plan["donors"][cid].values()}
        normals, items, peaks = {}, {}, {}
        for row in plan["rows"]:
            cid = row["condition_id"]
            if cid not in needed:
                continue
            report.update(active_condition_id=cid, active_stage="donor_clean")
            item = prepare_input(plan, row, tokenizer)
            items[cid] = item
            torch.cuda.reset_peak_memory_stats()
            normals[cid] = clean_condition(model, item, plan, names, progress)
            peaks[cid] = torch.cuda.max_memory_allocated()
            check_resources(
                plan["settings"]["resources"], normals[cid]["elapsed_seconds"], peaks[cid]
            )
            if cid not in ids:
                report["additional_donor_conditions"].append(
                    {
                        "condition_id": cid,
                        "elapsed_seconds": normals[cid]["elapsed_seconds"],
                        **normals[cid]["timing"],
                    }
                )
        for row in selected:
            cid = row["condition_id"]
            report.update(active_condition_id=cid, active_stage="interventions")
            item, normal = items[cid], normals[cid]
            saved = load_file(str(item["source"]["bundle"] / "residual.safetensors"))
            comparisons = {
                f"{p}/{name}": nod.compare_vectors(
                    normal["residuals"][name][0, i],
                    saved[name][0, item["source"]["resolved"]["position_order"].index(p)],
                )
                for i, p in enumerate(POSITIONS)
                for name in names
            }
            old_digits = item["source"]["logprobs"]["G"]["candidate_digits"]
            new_digits = normal["record"]["candidate_digits"]
            digit_comparison = {
                "bit_exact": records_exact(new_digits, old_digits),
                "maximum_absolute_difference": max(
                    abs(new_digits[k] - old_digits[k]) for k in old_digits
                ),
            }
            torch.cuda.reset_peak_memory_stats()
            result = intervene_condition(model, item, plan, normals, names, progress)
            peak = max(peaks[cid], torch.cuda.max_memory_allocated())
            wall = normal["elapsed_seconds"] + result["elapsed_seconds"]
            host_end = host_resources()
            check = {
                "condition_id": cid,
                "elapsed_seconds": wall,
                "donor_clean_seconds": normal["elapsed_seconds"],
                "intervention_seconds": result["elapsed_seconds"],
                "clean_timing": normal["timing"],
                "intervention_timing": result["timing"],
                "intervention_group_timing": result["group_timing"],
                "host_resources": {"start": progress["host_at_start"], "end": host_end},
                "peak_gpu_memory_bytes": peak,
                "self_exact_count": sum(
                    entry["self_exact"] is True for entry in result["interventions"].values()
                ),
                "positive_control": result["positive_control"],
                "reference_residual_comparisons": comparisons,
                "reference_digit_comparison": digit_comparison,
            }
            # Repetition is engineering-only overhead, separate from the main-run budget.
            module = names[24]
            vector = normals[plan["donors"][cid]["matched"]]["residuals"][module][0, 0]
            repeat_start = time.monotonic()
            cache = prefix_cache(model, item["input_ids"], item["t_index"])
            first = evaluate(model, cache, item, plan, patch=(module, "T", vector))["record"]
            second = evaluate(model, cache, item, plan, patch=(module, "T", vector))["record"]
            check.update(
                cache_repeat_exact=records_exact(first, second),
                extra_repeat_seconds=time.monotonic() - repeat_start,
            )
            report["conditions"].append(check)
            if not check["cache_repeat_exact"] or not result["positive_control"]["bit_exact"]:
                raise RuntimeError("cache repeat or positive control mismatch")
            check_resources(plan["settings"]["resources"], wall, peak)
            print(
                f"GPU preflight {len(report['conditions'])}/{len(selected)}: "
                f"{wall:.1f}s, {peak / 1024**3:.3f} GiB; {resource_line(host_end)}",
                flush=True,
            )
        report.update(
            status="passed",
            estimated_capture_seconds=max(c["elapsed_seconds"] for c in report["conditions"])
            * len(plan["rows"]),
        )
    except Exception as exc:
        report.update(status="failed", exception_type=type(exc).__name__, failure_message=str(exc))
        report["failure_diagnostics"] = {
            "failed_at": datetime.now(UTC).isoformat(),
            "progress": progress_record(progress),
            "host_resources_at_failure": host_resources(),
        }
        if torch.cuda.is_initialized():
            report["failure_peak_gpu_memory_bytes"] = torch.cuda.max_memory_allocated()
        raise
    finally:
        report["log_filter"] = warnings_filter.record()
        if model is not None:
            report["environment"] = environment()
        write_report(target, report)
    return report


def validate_freeze(plan: dict, freeze: dict) -> None:
    expected = {
        key: plan[key]
        for key in (
            "analysis_config_sha256",
            "spec_sha256",
            "sweep_config_sha256",
            "reference_sha256",
        )
    }
    expected.update(
        model=plan["config"]["model"],
        resources=plan["settings"]["resources"],
        decoding={"do_sample": False, "temperature": 0.0, "top_p": 1.0},
    )
    if any(freeze.get(key) != value for key, value in expected.items()):
        raise ValueError("patching freeze config/spec/reference/model/resources differs")


def create_patching_runtime_freeze(
    config_path: Path, tokenizer_report: Path, gpu_report: Path, environment_lock: Path
) -> Path:
    plan = load_plan(config_path)
    ident = identity(plan)
    paths = [
        safe_path(plan["root"], path) for path in (tokenizer_report, gpu_report, environment_lock)
    ]
    for path in paths[:2]:
        report = nod.read_json(path)
        if report.get("status") != "passed" or any(report.get(k) != v for k, v in ident.items()):
            raise ValueError("preflight identity or status differs")
    freeze = {
        **ident,
        "schema_version": 1,
        "status": "frozen",
        "created_at": datetime.now(UTC).isoformat(),
        "design_freeze_sha256": sha256_file(
            plan["root"] / plan["config"]["references"]["design_freeze"]
        ),
        "files_sha256": {p.relative_to(plan["root"]).as_posix(): sha256_file(p) for p in paths},
        "model": plan["config"]["model"],
        "resources": plan["settings"]["resources"],
        "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
        "environment": nod.read_json(paths[1])["environment"],
    }
    validate_freeze(plan, freeze)
    target = report_path(plan, "runtime").with_suffix(".freeze.json")
    write_report(target, freeze)
    return target


def capture_identity(plan: dict, row: dict, *, commit: str | None = None) -> dict:
    cid = row["condition_id"]
    source_id = nod.run_id(
        plan["settings"]["reference"]["input_run_id_prefix"], plan["run_ids"][cid]
    )
    return {
        **identity(plan),
        "git_commit": commit or plan["freeze"]["git_commit"],
        "schema_version": 1,
        "run_id": nod.run_id(plan["settings"]["patching"]["run_id_prefix"], plan["run_ids"][cid]),
        "condition_id": cid,
        "pair_id": row["pair_id"],
        "split": "train",
        "runtime_freeze": plan["runtime"],
        "runtime_freeze_sha256": plan["runtime_sha256"],
        "source_run_id": source_id,
        "source_manifest_sha256": plan["source_rows"][source_id]["manifest_sha256"],
        "model": plan["config"]["model"],
        "tokenizer_revision": plan["config"]["model"]["tokenizer_revision"],
        "seed": plan["settings"]["patching"]["seed"],
        "decoding": plan["freeze"]["decoding"],
        "cache_method": "DynamicCache.crop",
        "candidate_scoring": plan["settings"]["patching"]["candidate_scoring"],
        "serialization": SERIALIZATION,
    }


def bundle_files(
    plan: dict,
    row: dict,
    run: dict,
    item: dict | None = None,
    normal: dict | None = None,
    result: dict | None = None,
) -> dict[str, bytes]:
    files = {
        "condition.json": canonical_json_bytes(
            {k: v for k, v in row.items() if k != "account_block_position"}
        ),
        "run.json": canonical_json_bytes(run),
        "resolved_config.json": canonical_json_bytes(
            {
                "patching": plan["settings"],
                "sweep": plan["sweep"],
                "model": plan["config"]["model"],
                "seed": run["seed"],
                "decoding": run["decoding"],
                "cache_method": run["cache_method"],
            }
        ),
    }
    if result is not None and item is not None and normal is not None:
        from safetensors.torch import save

        results = {
            key: result[key]
            for key in ("clean", "interventions", "clean_recheck", "positive_control")
        }
        files.update(
            {
                "input.json": canonical_json_bytes(
                    {
                        "token_ids": item["input_ids"],
                        "token_ids_sha256": sha256_bytes(canonical_json_bytes(item["input_ids"])),
                        "source_run_id": item["source_run_id"],
                        "source_manifest_sha256": item["source_manifest_sha256"],
                    }
                ),
                "positions.json": canonical_json_bytes(
                    {
                        key: item[key]
                        for key in (
                            "positions",
                            "t_index",
                            "g_index",
                            "accounts",
                            "remainders",
                            "serialization",
                            "call_text_sha256",
                        )
                    }
                ),
                "donors.json": canonical_json_bytes(plan["donors"][row["condition_id"]]),
                "results.json": canonical_json_bytes(results),
                "clean_residual.safetensors": save(normal["residuals"]),
                "patch_vectors.safetensors": save(result["vectors"]),
            }
        )
    return files


def capture_patching(config_path: Path, runtime_freeze: Path) -> list[Path]:
    """Explicit full capture command. Neither preflight calls this function."""
    with limited_cast_warning() as warnings_filter:
        return _capture_patching(config_path, runtime_freeze, warnings_filter)


def _capture_patching(
    config_path: Path, runtime_freeze: Path, warnings_filter: RepeatedCastWarningFilter
) -> list[Path]:
    import torch

    plan = load_plan(config_path, runtime_freeze, matching=True)
    base = {row["condition_id"]: capture_identity(plan, row) for row in plan["rows"]}
    limits = plan["settings"]["resources"]
    completed, paths, total = set(), [], 0
    for row in plan["rows"]:
        cid = row["condition_id"]
        path = plan["root"] / "artifacts/runs" / base[cid]["run_id"]
        if completed_bundle(path, base[cid]):
            completed.add(cid)
            paths.append(path)
            total += sum(p.stat().st_size for p in path.iterdir() if p.is_file())
    if len(completed) == len(plan["rows"]):
        return paths
    items, normals, peaks = {}, {}, {}
    row = plan["rows"][0]
    stage = "donor_clean"
    progress: dict = {}
    measured: dict = {}
    last_bundle_at = None
    try:
        model, tokenizer = load_model(plan["config"])
        model.eval()
        torch.manual_seed(plan["settings"]["patching"]["seed"])
        names = model_names(model, plan)
        for row in plan["rows"]:
            cid = row["condition_id"]
            items[cid] = prepare_input(plan, row, tokenizer)
            measured.clear()
            torch.cuda.reset_peak_memory_stats()
            normals[cid] = clean_condition(model, items[cid], plan, names, progress)
            peaks[cid] = torch.cuda.max_memory_allocated()
            measured.update(
                donor_clean_seconds=normals[cid]["elapsed_seconds"],
                peak_gpu_memory_bytes=peaks[cid],
            )
            check_resources(limits, normals[cid]["elapsed_seconds"], peaks[cid])
            print(
                f"{datetime.now(UTC).isoformat()} donor clean {len(normals)}/"
                f"{len(plan['rows'])}: {cid} {normals[cid]['elapsed_seconds']:.1f}s; "
                f"{resource_line(host_resources())}",
                flush=True,
            )
        stage = "interventions"
        for row in plan["rows"]:
            cid = row["condition_id"]
            if cid in completed:
                continue
            measured.clear()
            torch.cuda.reset_peak_memory_stats()
            result = intervene_condition(model, items[cid], plan, normals, names, progress)
            wall = normals[cid]["elapsed_seconds"] + result["elapsed_seconds"]
            peak = max(peaks[cid], torch.cuda.max_memory_allocated())
            measured.update(
                elapsed_seconds=wall,
                donor_clean_seconds=normals[cid]["elapsed_seconds"],
                intervention_seconds=result["elapsed_seconds"],
                peak_gpu_memory_bytes=peak,
            )
            host_end = host_resources()
            check_resources(limits, wall, peak)
            run = {
                **base[cid],
                "status": "completed",
                "model_dimensions": {
                    "num_hidden_layers": len(names),
                    "hidden_size": model.config.hidden_size,
                },
                "elapsed_seconds": wall,
                "peak_gpu_memory_bytes": peak,
                "donor_clean_seconds": normals[cid]["elapsed_seconds"],
                "intervention_seconds": result["elapsed_seconds"],
                "clean_timing": normals[cid]["timing"],
                "intervention_timing": result["timing"],
                "intervention_group_timing": result["group_timing"],
                "host_resources": {"start": progress["host_at_start"], "end": host_end},
                "log_filter_cumulative": warnings_filter.record(),
            }
            maximum = min(
                limits["maximum_storage_gib_per_condition"] * 1024**3,
                limits["maximum_total_storage_gib"] * 1024**3 - total,
            )
            path = write_bundle(
                plan["root"] / "artifacts",
                run["run_id"],
                bundle_files(plan, row, run, items[cid], normals[cid], result),
                maximum_bytes=maximum,
            )
            paths.append(path)
            total += sum(p.stat().st_size for p in path.iterdir() if p.is_file())
            last_bundle_at = datetime.now(UTC).isoformat()
            print(
                f"{last_bundle_at} Captured {len(paths)}/{len(plan['rows'])}: "
                f"{run['run_id']} {wall:.1f}s, {peak / 1024**3:.3f} GiB; "
                f"{resource_line(host_end)}",
                flush=True,
            )
    except Exception as exc:
        cid = row["condition_id"]
        failure = {
            **base[cid],
            "status": "technical_failure",
            "failure_stage": stage,
            "exception_type": type(exc).__name__,
            "failure_message": str(exc),
            "peak_gpu_memory_bytes": (
                torch.cuda.max_memory_allocated() if torch.cuda.is_initialized() else 0
            ),
            # Diagnostics only: no intervention results are retained for a failed condition.
            "diagnostics": {
                "failed_at": datetime.now(UTC).isoformat(),
                "measured_before_check": dict(measured) or None,
                "donor_clean_seconds": (
                    normals[cid]["elapsed_seconds"] if cid in normals else None
                ),
                "progress": progress_record(progress if progress.get("stage") == stage else None),
                "last_completed_bundle_at": last_bundle_at,
                "host_resources_at_failure": host_resources(),
                "log_filter_cumulative": warnings_filter.record(),
            },
        }
        # An existing completed bundle cannot be repurposed as a failure on resume.
        rid = failure["run_id"]
        if (plan["root"] / "artifacts/runs" / rid).exists():
            rid += "-donor-failure-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
            failure.update(run_id=rid, attempted_run_id=base[cid]["run_id"])
        write_bundle(plan["root"] / "artifacts", rid, bundle_files(plan, row, failure))
        raise RuntimeError(f"retained technical failure: {rid}") from exc
    return paths


def pair_effects(
    clean_ld: dict, patched_ld: dict, pairs: list, labels: Any, delta_minimum: float
) -> dict:
    included, excluded = [], []
    for first, second in pairs:
        x, y = (first, second) if labels[first] == 1 else (second, first)
        if labels[x] != 1 or labels[y] != 0:
            raise ValueError("pair labels do not flip")
        delta = clean_ld[x] - clean_ld[y]
        forward = patched_ld[y] - clean_ld[y]
        backward = clean_ld[x] - patched_ld[x]
        values = {
            "pair": [x, y],
            "delta": delta,
            "raw_change_x_to_y": forward,
            "raw_change_y_to_x": -backward,
        }
        if not all(math.isfinite(v) for v in (delta, forward, backward)):
            raise ValueError("nonfinite pair effects")
        if delta < delta_minimum:
            excluded.append({**values, "reason": "small_or_reversed_delta"})
        else:
            included.append(
                {
                    **values,
                    "ne_x_to_y": forward / delta,
                    "ne_y_to_x": backward / delta,
                    "ne_pair": (forward + backward) / (2 * delta),
                }
            )
    return {"included": included, "excluded": excluded}


def bootstrap_mean(
    rows: list[dict], effects: list[dict], *, repeats: int, seed: int
) -> list[float] | None:
    import numpy as np

    if not effects:
        return None
    grouped = defaultdict(list)
    for effect in effects:
        series = rows[effect["pair"][0]]["semantic_series_id"]
        grouped[series].append(effect["ne_pair"])
    groups = [grouped[name] for name in sorted(grouped)]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(repeats):
        indices = rng.choice(len(groups), size=len(groups), replace=True)
        values = [value for index in indices for value in groups[index]]
        means.append(sum(values) / len(values))
    return [float(v) for v in np.percentile(means, [2.5, 97.5])]


def classify_cell(cell: dict, analysis: dict) -> str:
    if cell["eligible_pairs"] == 0:
        return "undefined"
    if cell["median_log_mass_change"] < analysis["disrupt_log_mass_threshold"] or (
        cell["median_stem_log_likelihood_change"] is not None
        and cell["median_stem_log_likelihood_change"]
        < analysis["disrupt_stem_log_likelihood_threshold"]
    ):
        return "P-DISRUPT"
    strong = analysis["strong"]
    if (
        cell["mean"] >= strong["mean_minimum"]
        and cell["interval"][0] >= strong["interval_lower_minimum"]
        and all(
            value >= strong["direction_mean_minimum"] for value in cell["direction_means"].values()
        )
        and sum(value > 0 for value in cell["family_means"].values())
        >= strong["family_positive_minimum"]
        and all(
            cell["source_role_means"].get(role, 0) > 0 for role in strong["source_roles_positive"]
        )
    ):
        return "P-STRONG"
    return "P-PARTIAL" if cell["interval"][0] > 0 else "P-NONE"


def cell_statistics(
    rows: list[dict],
    effects: dict,
    clean: dict,
    patched: dict,
    position: str,
    analysis: dict,
    donor_clean: dict,
) -> dict:
    import numpy as np

    require_train(rows)
    eligible = effects["included"]
    if not eligible:
        return {"class": "undefined", "eligible_pairs": 0, "excluded_pairs": effects["excluded"]}
    families, roles = defaultdict(list), defaultdict(list)
    changes, agreement = [], []
    role_names = {"user_instruction": "user", "tool_output_document": "tool"}
    for effect in eligible:
        x, y = effect["pair"]
        families[rows[x]["family_id"]].append(effect["ne_pair"])
        roles[role_names[rows[x]["source_role"]]].append(effect["ne_pair"])
        for index in (x, y):
            changes.append(raw_changes(clean[index], patched[index], position, analysis))
            current, donor = patched[index]["ld"], donor_clean[index]["ld"]
            agreement.append(current != 0 and donor != 0 and (current > 0) == (donor > 0))
    count = len(eligible)
    result = {
        "eligible_pairs": count,
        "excluded_pairs": effects["excluded"],
        "mean": sum(v["ne_pair"] for v in eligible) / count,
        "interval": bootstrap_mean(
            rows, eligible, repeats=analysis["bootstrap_repeats"], seed=analysis["bootstrap_seed"]
        ),
        "direction_means": {
            direction: sum(v[direction] for v in eligible) / count
            for direction in ("ne_x_to_y", "ne_y_to_x")
        },
        "family_means": {
            key: sum(values) / len(values) for key, values in sorted(families.items())
        },
        "source_role_means": {
            key: sum(values) / len(values) for key, values in sorted(roles.items())
        },
        "median_log_mass_change": float(np.median([v["log_mass_change"] for v in changes])),
        "median_stem_log_likelihood_change": None
        if position == "G"
        else float(np.median([v["stem_log_likelihood_change"] for v in changes])),
        "disrupted_count": sum(v["disrupted"] for v in changes),
        "disrupted_fraction": sum(v["disrupted"] for v in changes) / len(changes),
        "disruption_reasons": {
            reason: sum(reason in v["disruption_reasons"] for v in changes)
            for reason in ("candidate_mass", "stem_likelihood")
        },
        "donor_sign_agreement_rate": sum(agreement) / len(agreement),
        "mean_digit_margin_change": sum(
            patched[i]["digit_margin"] - clean[i]["digit_margin"]
            for effect in eligible
            for i in effect["pair"]
        )
        / (2 * count),
        "pair_effects": eligible,
    }
    result["class"] = classify_cell(result, analysis)
    return result


def map_patching(
    cells: dict,
    health_ok: bool,
    positive_ok: bool,
    middle_max: int = 24,
    late_min: int = 28,
    cross_half_ratio: float = 0.5,
) -> dict:
    shallowest = {
        p: min(
            (
                cell["layer"]
                for cell in cells.values()
                if cell["position"] == p and cell["class"] == "P-STRONG"
            ),
            default=None,
        )
        for p in POSITIONS
    }
    output = {"shallowest_strong_layers": shallowest, "evidence_cells": []}
    if (
        not health_ok
        or not positive_ok
        or all(cell["class"] == "undefined" for cell in cells.values())
    ):
        return {
            **output,
            "rule": 0,
            "mapping": "held",
            "reason": "health_or_positive_control"
            if not health_ok or not positive_ok
            else "no_eligible_pairs",
        }
    evidence_positions = []
    if shallowest["T"] is not None and shallowest["T"] <= middle_max:
        rule, mapping, evidence_positions = 1, "H2_consistent", ["T"]
    elif any(shallowest[p] is not None and shallowest[p] <= middle_max for p in ("S", "G")):
        rule, mapping = 2, "H3_consistent"
        evidence_positions = [
            p for p in ("S", "G") if shallowest[p] is not None and shallowest[p] <= middle_max
        ]
    elif any(layer is not None and layer >= late_min for layer in shallowest.values()):
        rule, mapping = 3, "late_layer_only_no_mapping"
    elif all(layer is None for layer in shallowest.values()):
        rule, mapping = 4, "no_strong_single_site_effect"
    else:
        raise ValueError("uncovered patching mapping combination")
    output.update(rule=rule, mapping=mapping)
    for position in evidence_positions:
        key = f"{position}/layer{shallowest[position]}"
        cell = cells[key]
        cross = cell["cross"]
        ratio = cross["mean"] / cell["mean"]
        description = (
            "cross_disrupted_interpretation_held"
            if cross["class"] == "P-DISRUPT"
            else (
                "same_accounts_order_cross_context_ge_half"
                if ratio >= cross_half_ratio
                else "selected_cross_context_lt_half"
            )
        )
        output["evidence_cells"].append(
            {"cell": key, "cross_to_matched_mean_ratio": ratio, "cross_description": description}
        )
    if rule == 2:
        output["description"] = (
            "T middle layers did not meet the strong-effect criterion; S/G middle layers did. "
            "Partial or late-layer T effects are not excluded."
        )
    if rule == 4:
        output["description"] = (
            "No tested single-site intervention met the strong-effect criterion; "
            "partial effects are reported separately."
        )
    return output


def read_capture(plan: dict, row: dict) -> dict:
    import torch
    from safetensors.torch import load_file

    expected = capture_identity(plan, row)
    path = plan["root"] / "artifacts/runs" / expected["run_id"]
    if not completed_bundle(path, expected):
        raise FileNotFoundError(path)
    manifest = verify_manifest(path)
    condition = verified_json(path, manifest, "condition.json")
    if condition != {k: v for k, v in row.items() if k != "account_block_position"}:
        raise ValueError("patch condition differs")
    item = read_input(plan, row)
    inputs = verified_json(path, manifest, "input.json")
    if inputs != {
        "token_ids": item["input_ids"],
        "token_ids_sha256": sha256_bytes(canonical_json_bytes(item["input_ids"])),
        "source_run_id": item["source_run_id"],
        "source_manifest_sha256": item["source_manifest_sha256"],
    }:
        raise ValueError("patch input provenance differs")
    if verified_json(path, manifest, "donors.json") != plan["donors"][row["condition_id"]]:
        raise ValueError("patch donor table differs")
    positions = verified_json(path, manifest, "positions.json")
    if (
        positions["positions"] != item["positions"]
        or positions["t_index"] != item["t_index"]
        or positions["g_index"] != item["g_index"]
        or positions["serialization"] != SERIALIZATION
    ):
        raise ValueError("patch positions differ")
    if positions["accounts"] != dict(
        zip(("first", "second"), presentation_order(row, plan["accounts"]), strict=True)
    ):
        raise ValueError("patch account order differs")
    results = verified_json(path, manifest, "results.json")
    run = verified_json(path, manifest, "run.json")
    vectors = load_file(str(path / "patch_vectors.safetensors"))
    residuals = load_file(str(path / "clean_residual.safetensors"))
    dimensions = item["source"]["run"]["model_dimensions"]
    if run["model_dimensions"] != dimensions:
        raise ValueError("patch model dimensions differ from reference")
    modules = {
        f"{plan['sweep']['capture']['block_path']}.{layer}"
        for layer in range(dimensions["num_hidden_layers"])
    }
    if set(residuals) != modules or any(
        value.shape != (1, len(POSITIONS), dimensions["hidden_size"])
        or value.dtype != torch.bfloat16
        or not torch.isfinite(value).all()
        for value in residuals.values()
    ):
        raise ValueError("saved clean residual grid/shape/dtype/finite differs")
    expected_keys = {
        f"{kind}/{p}/layer{layer}"
        for kind in DONOR_KINDS
        for p in POSITIONS
        for layer in plan["settings"]["patching"]["layers"]
    }
    if set(results["interventions"]) != expected_keys or set(vectors) != {
        key for key in expected_keys if not key.startswith("self/")
    }:
        raise ValueError("patch cell/vector grid incomplete")
    if any(
        vector.shape != (dimensions["hidden_size"],)
        or vector.dtype != torch.bfloat16
        or not torch.isfinite(vector).all()
        for vector in vectors.values()
    ):
        raise ValueError("saved patch vector shape/dtype/finite differs")
    for record in (
        results["clean"],
        results["clean_recheck"],
        *(entry["result"] for entry in results["interventions"].values()),
    ):
        _float_bits(record)
        for name, candidate in record["candidates"].items():
            if (
                candidate["token_ids"] != positions["remainders"][name]
                or len(candidate["token_log_probabilities"]) != len(candidate["token_ids"])
                or candidate["log_probability"] != sum(candidate["token_log_probabilities"])
            ):
                raise ValueError("saved candidate sequence/score alignment differs")
    return {
        "results": results,
        "vectors": vectors,
        "residuals": residuals,
        "positions": positions,
        "manifest_sha256": sha256_file(path / "manifest.json"),
        "run": run,
    }


def analyze(config_path: Path, runtime_freeze: Path) -> Path:
    plan = load_plan(config_path, runtime_freeze)
    target = plan["root"] / "artifacts/processed" / plan["settings"]["analysis"]["output_id"]
    if target.exists():
        raise FileExistsError(target)
    if clean_commit(plan["root"]) == plan["freeze"]["git_commit"]:
        raise ValueError("analysis requires a commit separate from capture")
    bundles = {row["condition_id"]: read_capture(plan, row) for row in plan["rows"]}
    rows, analysis = plan["rows"], plan["settings"]["analysis"]
    clean = {i: bundles[row["condition_id"]]["results"]["clean"] for i, row in enumerate(rows)}
    health = {"self_exact": True, "clean_recheck_exact": True, "positive_control_exact": True}
    for index, row in enumerate(rows):
        cid = row["condition_id"]
        bundle = bundles[cid]
        result = bundle["results"]
        health["clean_recheck_exact"] &= records_exact(result["clean"], result["clean_recheck"])
        positive_donor = plan["donors"][cid]["matched"]
        positive = result["positive_control"]
        health["positive_control_exact"] &= (
            positive["bit_exact"]
            and positive["current"] == bundles[positive_donor]["results"]["clean"]["g_distribution"]
            and positive["donor_condition_id"] == positive_donor
            and positive["current"] == positive["donor"]
        )
        for key, entry in result["interventions"].items():
            kind, position, layer_text = key.split("/")
            layer = int(layer_text.removeprefix("layer"))
            donor = plan["donors"][cid][kind]
            if (
                entry["donor_condition_id"] != donor
                or entry["donor_run_id"]
                != nod.run_id(plan["settings"]["patching"]["run_id_prefix"], plan["run_ids"][donor])
                or entry["position"] != position
                or entry["layer"] != layer
                or entry["module_name"] != f"{plan['sweep']['capture']['block_path']}.{layer}"
                or entry["hook_point"] != "block_output_residual"
            ):
                raise ValueError("saved donor provenance differs")
            vector = bundles[donor]["residuals"][entry["module_name"]][0, POSITIONS.index(position)]
            if entry["vector"] != tensor_record(vector) or (
                kind != "self" and tensor_bytes(bundle["vectors"][key]) != tensor_bytes(vector)
            ):
                raise ValueError("saved donor vector differs")
            changes = raw_changes(clean[index], entry["result"], position, analysis)
            if any(entry[k] != v for k, v in changes.items()):
                raise ValueError("saved disruption flags differ")
            if kind == "self":
                health["self_exact"] &= entry["self_exact"] is True and records_exact(
                    clean[index], entry["result"]
                )
    cells = {}
    for position in POSITIONS:
        for layer in plan["settings"]["patching"]["layers"]:
            kinds = {}
            for kind in ("matched", "cross"):
                patched = {
                    i: bundles[row["condition_id"]]["results"]["interventions"][
                        f"{kind}/{position}/layer{layer}"
                    ]["result"]
                    for i, row in enumerate(rows)
                }
                effects = pair_effects(
                    {i: v["ld"] for i, v in clean.items()},
                    {i: v["ld"] for i, v in patched.items()},
                    plan["pairs"],
                    plan["labels"],
                    analysis["delta_minimum_nats"],
                )
                donor_clean = {
                    i: bundles[plan["donors"][row["condition_id"]][kind]]["results"]["clean"]
                    for i, row in enumerate(rows)
                }
                kinds[kind] = cell_statistics(
                    rows, effects, clean, patched, position, analysis, donor_clean
                )
            cells[f"{position}/layer{layer}"] = {
                "position": position,
                "layer": layer,
                **kinds["matched"],
                "cross": kinds["cross"],
            }
    mapping = map_patching(
        cells,
        health["self_exact"] and health["clean_recheck_exact"],
        health["positive_control_exact"],
        analysis["middle_layer_maximum"],
        analysis["late_layer_minimum"],
        analysis["cross_half_ratio"],
    )
    report = {
        "provenance": {
            **identity(plan),
            "runtime_freeze_sha256": plan["runtime_sha256"],
            "capture_commit": plan["freeze"]["git_commit"],
            "bundle_manifest_sha256": {
                cid: bundle["manifest_sha256"] for cid, bundle in bundles.items()
            },
            "research_result": "post_result_train_only_exploratory_intervention",
        },
        "health": health,
        "cells": cells,
        "hypothesis_mapping": mapping,
        "limitations": [
            "post-result train-only; no attack or independent validation",
            "whole-vector sufficiency does not establish necessity, "
            "a probe direction, or first decision time",
            "cross fixes both account identity and order",
            "uncorrected exploratory cell intervals",
        ],
    }
    return publish(
        target, {"report.json": canonical_json_bytes(report)}, kind="activation_patching"
    )


def write_collection_manifest(config_path: Path, runtime_freeze: Path, output: Path) -> Path:
    plan = load_plan(config_path, runtime_freeze)
    target = safe_path(plan["root"], output)
    if target.exists():
        raise FileExistsError(target)
    items = []
    for row in plan["rows"]:
        expected = capture_identity(plan, row)
        path = plan["root"] / "artifacts/runs" / expected["run_id"]
        if not completed_bundle(path, expected):
            raise FileNotFoundError(path)
        manifest = verify_manifest(path)
        run = verified_json(path, manifest, "run.json")
        items.append(
            {
                "run_id": run["run_id"],
                "condition_id": row["condition_id"],
                "pair_id": row["pair_id"],
                "manifest_sha256": sha256_file(path / "manifest.json"),
                "elapsed_seconds": run["elapsed_seconds"],
                "peak_gpu_memory_bytes": run["peak_gpu_memory_bytes"],
                "bytes": sum(p.stat().st_size for p in path.iterdir() if p.is_file()),
            }
        )
    report = {
        **identity(plan),
        "git_commit": plan["freeze"]["git_commit"],
        "created_at": datetime.now(UTC).isoformat(),
        "runtime_freeze": plan["runtime"],
        "runtime_freeze_sha256": plan["runtime_sha256"],
        "condition_count": len(items),
        "runs": items,
        "total_bytes": sum(row["bytes"] for row in items),
        "research_result": "post_result_train_only_exploratory_intervention_capture",
    }
    write_report(target, report)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "tokenizer-preflight",
            "gpu-preflight",
            "freeze",
            "capture",
            "collection-manifest",
            "analyze",
        ),
    )
    parser.add_argument("config", type=Path)
    for name in ("runtime-freeze", "tokenizer-report", "gpu-report", "environment-lock", "output"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.command == "tokenizer-preflight":
        report = patching_tokenizer_preflight(args.config)
        print(f"Tokenizer preflight: {report['status']}; {report['condition_count']} conditions")
    elif args.command == "gpu-preflight":
        report = patching_gpu_preflight(args.config)
        print(f"GPU preflight: {report['status']}; {len(report['conditions'])} conditions")
    elif args.command == "freeze":
        if any(
            value is None
            for value in (args.tokenizer_report, args.gpu_report, args.environment_lock)
        ):
            parser.error("freeze requires tokenizer/GPU reports and environment lock")
        print(
            create_patching_runtime_freeze(
                args.config, args.tokenizer_report, args.gpu_report, args.environment_lock
            )
        )
    else:
        if args.runtime_freeze is None:
            parser.error("this command requires --runtime-freeze")
        if args.command == "capture":
            print(len(capture_patching(args.config, args.runtime_freeze)))
        elif args.command == "analyze":
            print(analyze(args.config, args.runtime_freeze))
        else:
            if args.output is None:
                parser.error("collection-manifest requires --output")
            print(write_collection_manifest(args.config, args.runtime_freeze, args.output))


if __name__ == "__main__":
    main()
