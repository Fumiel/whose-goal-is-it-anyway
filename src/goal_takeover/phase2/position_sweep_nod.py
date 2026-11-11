"""Frozen D-free control, exact-input repeat, comparison and conditional reanalysis."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

from goal_takeover.phase2.argument_recipient_672_features import _verified_artifact  # noqa: E402
from goal_takeover.phase2.argument_recipient_672_selection_pointer import (  # noqa: E402
    PROBES,
    _cell_scores,
    pair_index,
    paired_accuracy,
    recipient_first_label,
)
from goal_takeover.phase2.argument_recipient_672_train_readout import (  # noqa: E402
    clean_commit,
    publish,
)
from goal_takeover.phase2.position_sweep_analysis import analyze, global_null  # noqa: E402
from goal_takeover.phase2.position_sweep_capture import (  # noqa: E402
    capture_files,
    completed_bundle,
    environment,
    forward_capture,
    load_model,
    validate_residual_schema,
    write_bundle,
)
from goal_takeover.phase2.position_sweep_positions import (  # noqa: E402
    POSITIONS,
    canonical_prefix,
    context,
    presentation_order,
    resolve_positions,
    safe_path,
    span_last_token,
    verified_json,
    verify_manifest,
    write_report,
)
from goal_takeover.storage.run_writer import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)

NOD_POSITIONS = POSITIONS[:-1]
REFERENCE_FILES = (
    "runtime_freeze",
    "collection_manifest",
    "analysis_report",
    "gpu_preflight_report",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run_id(prefix: str, canonical_id: str) -> str:
    if not prefix or Path(prefix).name != prefix or prefix in (".", ".."):
        raise ValueError("unsafe run prefix")
    return prefix + "-" + canonical_id.rsplit("-", 1)[1]


def nod_positions(resolved: dict) -> dict:
    value = copy.deepcopy(resolved)
    if value["position_order"] != list(POSITIONS) or set(value["positions"]) != set(POSITIONS):
        raise ValueError("expected six reference positions")
    if value["positions"]["D"]["token_index"] != len(value["input_ids"]) - 1:
        raise ValueError("D is not the last token")
    value["input_ids"] = value["input_ids"][:-1]
    value["positions"].pop("D")
    value["position_order"] = list(NOD_POSITIONS)
    value["position_rule_version"] = "position_sweep_nod_v1"
    value["input_token_count"] = len(value["input_ids"])
    value["continuation_text"] = value["continuation_text"][:-1]
    if [value["positions"][p]["token_index"] for p in ("S", "G")] != [
        len(value["input_ids"]) - 2,
        len(value["input_ids"]) - 1,
    ]:
        raise ValueError("S/G are not the final two tokens")
    return value


def repeat_condition_ids(rows: list[dict], pair_count: int = 5) -> list[str]:
    if any(r.get("split_candidate") != "train" for r in rows):
        raise ValueError("validation row rejected")
    # Pair completeness and invariant labels are checked by the caller with the accounts.
    tasks = sorted({r["draft_task_id"] for r in rows})[:pair_count]
    if len(tasks) != pair_count:
        raise ValueError("not enough repeat pairs")
    result = []
    for task in tasks:
        members = sorted(
            (r for r in rows if r["draft_task_id"] == task), key=lambda r: r["condition_id"]
        )
        if len(members) != 2:
            raise ValueError("repeat task is not a pair")
        result.extend(r["condition_id"] for r in members)
    return result


def verify_reference_files(root: Path, nod: dict, sweep: dict, config: dict) -> dict:
    hashes = {key: sha256_file(safe_path(root, nod["reference"][key])) for key in REFERENCE_FILES}
    runtime = read_json(root / nod["reference"]["runtime_freeze"])
    collection = read_json(root / nod["reference"]["collection_manifest"])
    analysis = read_json(root / nod["reference"]["analysis_report"])
    if (
        runtime.get("status") != "frozen"
        or runtime.get("model") != config["model"]
        or runtime.get("analysis_config_sha256") != sha256_file(root / nod["sweep_config"])
        or runtime.get("spec_sha256") != sha256_file(root / sweep["spec"])
        or collection.get("runtime_freeze_sha256") != hashes["runtime_freeze"]
        or collection.get("git_commit") != runtime["git_commit"]
        or analysis["provenance"].get("runtime_freeze_sha256") != hashes["runtime_freeze"]
        or runtime["files_sha256"].get(nod["reference"]["gpu_preflight_report"])
        != hashes["gpu_preflight_report"]
    ):
        raise ValueError("reference freeze/collection/report checksum or identity differs")
    for relative, digest in runtime["files_sha256"].items():
        if sha256_file(safe_path(root, relative)) != digest:
            raise ValueError("reference runtime checked file differs")
    report = safe_path(root, nod["reference"]["analysis_report"])
    manifest = read_json(report.parent / "manifest.json")
    item = manifest["artifacts"][report.name]
    if item["sha256"] != hashes["analysis_report"] or item["bytes"] != report.stat().st_size:
        raise ValueError("reference analysis manifest differs")
    return {"sha256": hashes, "runtime": runtime, "collection": collection, "analysis": analysis}


def load_plan(config_path: Path, runtime: Path | None = None, *, matching: bool = False) -> dict:
    root = Path.cwd().resolve()
    nod = read_json(safe_path(root, config_path))
    for key in ("spec", "sweep_config"):
        safe_path(root, nod[key])
    for key in REFERENCE_FILES:
        safe_path(root, nod["reference"][key])
    for key in ("nod_capture", "repeat_capture"):
        run_id(nod[key]["run_id_prefix"], "canonical-c001")
    for key in ("comparison", "reanalysis"):
        run_id(nod[key]["output_id"], "canonical-c001")
    if (
        nod["schema_version"] != 1
        or tuple(nod["nod_capture"]["positions"]) != NOD_POSITIONS
        or nod["nod_capture"]["logit_positions"] != ["S", "G"]
        or nod["repeat_capture"]["pair_order_key"] != "draft_task_id"
    ):
        raise ValueError("D-free configuration schema differs")
    root, sweep, config, rows, ids, accounts = context(
        Path(nod["sweep_config"]), runtime, matching=matching
    )
    refs = verify_reference_files(root, nod, sweep, config)
    indexed = {r["run_id"]: r for r in refs["collection"]["runs"]}
    expected = {
        run_id(nod["reference"]["capture_run_id_prefix"], ids[r["condition_id"]]) for r in rows
    }
    if len(indexed) != len(rows) or set(indexed) != expected:
        raise ValueError("reference collection IDs differ")
    plan = {
        "root": root,
        "nod": nod,
        "sweep": sweep,
        "config": config,
        "rows": rows,
        "run_ids": ids,
        "accounts": accounts,
        "reference": refs,
        "reference_rows": indexed,
        "config_path": config_path,
        "config_sha256": sha256_file(root / config_path),
        "spec_sha256": sha256_file(root / nod["spec"]),
        "sweep_config_sha256": sha256_file(root / nod["sweep_config"]),
    }
    plan["repeat_ids"] = repeat_condition_ids(rows, nod["repeat_capture"]["pair_count"])
    if runtime is not None:
        freeze = read_json(safe_path(root, runtime))
        validate_freeze(plan, freeze)
        plan["freeze"] = freeze
        plan["runtime"] = runtime.as_posix()
        plan["runtime_sha256"] = sha256_file(root / runtime)
    return plan


def validate_freeze(plan: dict, freeze: dict) -> None:
    expected = {
        "analysis_config_sha256": plan["config_sha256"],
        "spec_sha256": plan["spec_sha256"],
        "sweep_config_sha256": plan["sweep_config_sha256"],
        "reference_sha256": plan["reference"]["sha256"],
        "model": plan["config"]["model"],
        "resources": plan["nod"]["resources"],
        "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
    }
    if any(freeze.get(k) != v for k, v in expected.items()):
        raise ValueError("D-free freeze config/spec/reference/model/resources differ")


def validate_layout(resolved: dict, prefix: dict, row: dict, accounts: dict, names: tuple) -> None:
    ids, positions = resolved["input_ids"], resolved["positions"]
    if (
        resolved["position_order"] != list(names)
        or set(positions) != set(names)
        or resolved["input_token_count"] != len(ids)
        or resolved["prefix_token_count"] != len(prefix["token_ids"])
        or ids[: len(prefix["token_ids"])] != prefix["token_ids"]
        or positions["T"]["token_index"] != len(prefix["token_ids"]) - 1
    ):
        raise ValueError("capture input/prefix/position order differs")
    for name in names:
        index = positions[name]["token_index"]
        if not 0 <= index < len(ids) or positions[name]["token_id"] != ids[index]:
            raise ValueError("position token differs")
    for name, account in zip(("A1", "A2"), presentation_order(row, accounts), strict=True):
        start = prefix["text"].index(account)
        if (
            positions[name]["account"] != account
            or positions[name]["token_index"] != span_last_token(prefix, account)
            or positions[name]["character_span"] != [start, start + len(account)]
        ):
            raise ValueError("account span differs")
    logits = ("S", "G", "D") if "D" in names else ("S", "G")
    if [positions[p]["token_index"] for p in logits] != list(
        range(len(ids) - len(logits), len(ids))
    ):
        raise ValueError("logit positions differ")


def read_bundle(
    plan: dict, row: dict, prefix: dict, canonical_id: str, kind: str, *, tensors: bool = True
) -> dict:
    root, nod = plan["root"], plan["nod"]
    if row["split_candidate"] != "train":
        raise ValueError("validation row rejected")
    if kind == "reference":
        rid = run_id(nod["reference"]["capture_run_id_prefix"], canonical_id)
        runtime_sha = plan["reference"]["sha256"]["runtime_freeze"]
        commit = plan["reference"]["runtime"]["git_commit"]
        config_sha = plan["reference"]["runtime"]["analysis_config_sha256"]
        spec_sha = plan["reference"]["runtime"]["spec_sha256"]
        names = POSITIONS
    else:
        rid = run_id(nod[kind + "_capture"]["run_id_prefix"], canonical_id)
        runtime_sha, commit = plan["runtime_sha256"], plan["freeze"]["git_commit"]
        config_sha, spec_sha = plan["config_sha256"], plan["spec_sha256"]
        names = NOD_POSITIONS if kind == "nod" else POSITIONS
    bundle = safe_path(root, f"artifacts/runs/{rid}")
    manifest = verify_manifest(bundle)
    run = verified_json(bundle, manifest, "run.json")
    expected = {
        "run_id": rid,
        "condition_id": row["condition_id"],
        "pair_id": row["pair_id"],
        "status": "completed",
        "split": "train",
        "git_dirty": False,
        "git_commit": commit,
        "runtime_freeze_sha256": runtime_sha,
        "analysis_config_sha256": config_sha,
        "spec_sha256": spec_sha,
        "canonical_run_id": canonical_id,
        "canonical_manifest_sha256": sha256_file(
            root / "artifacts/runs" / canonical_id / "manifest.json"
        ),
        "model": plan["config"]["model"],
        "tokenizer_revision": plan["config"]["model"]["tokenizer_revision"],
    }
    if kind != "reference":
        reference_id = run_id(nod["reference"]["capture_run_id_prefix"], canonical_id)
        expected.update(
            capture_kind=kind,
            position_order=list(names),
            reference_run_id=reference_id,
            reference_manifest_sha256=plan["reference_rows"][reference_id]["manifest_sha256"],
        )
    if any(run.get(k) != v for k, v in expected.items()):
        raise ValueError(f"{rid}: capture provenance differs")
    condition = {k: v for k, v in row.items() if k != "account_block_position"}
    if verified_json(bundle, manifest, "condition.json") != condition:
        raise ValueError("capture condition differs")
    inputs = verified_json(bundle, manifest, "input.json")
    positions = verified_json(bundle, manifest, "positions.json")
    ids = inputs["token_ids"]
    if inputs["token_ids_sha256"] != sha256_bytes(canonical_json_bytes(ids)) or inputs[
        "canonical_prefix_sha256"
    ] != sha256_file(root / "artifacts/runs" / canonical_id / "prefix.json"):
        raise ValueError("capture input checksum differs")
    positions["input_ids"] = ids
    validate_layout(positions, prefix, row, plan["accounts"], names)
    digest = sha256_file(bundle / "manifest.json")
    if kind == "reference" and digest != plan["reference_rows"][rid]["manifest_sha256"]:
        raise ValueError("reference collection manifest differs")
    values = None
    if tensors:
        import torch
        from safetensors.torch import load_file

        values = load_file(str(bundle / "residual.safetensors"))
        dimensions = run["model_dimensions"]
        if dimensions["num_hidden_layers"] != max(
            plan["sweep"]["analysis"]["report_layers"]
        ) + 1 or set(values) != {
            f"model.layers.{i}" for i in range(dimensions["num_hidden_layers"])
        }:
            raise ValueError("residual layer grid differs")
        for tensor in values.values():
            if (
                tensor.shape != (1, len(names), dimensions["hidden_size"])
                or tensor.dtype != torch.bfloat16
                or not torch.isfinite(tensor).all()
            ):
                raise ValueError("residual shape/dtype/finite check failed")
    return {
        "run": run,
        "resolved": positions,
        "logprobs": verified_json(bundle, manifest, "logprobs.json"),
        "tensors": values,
        "manifest_sha256": digest,
        "bundle": bundle,
    }


def require_matching_input(resolved: dict, reference: dict) -> None:
    if resolved != reference:
        raise ValueError("recomputed positions/input differ from saved reference")


def nod_tokenizer_preflight(config_path: Path) -> dict:
    from transformers import AutoTokenizer

    from goal_takeover.models.qwen import chat_template_sha256

    plan = load_plan(config_path)
    config = plan["config"]["model"]
    tokenizer = AutoTokenizer.from_pretrained(
        config["name"],
        revision=config["tokenizer_revision"],
        trust_remote_code=config["trust_remote_code"],
    )
    for row in plan["rows"]:
        cid = plan["run_ids"][row["condition_id"]]
        prefix, _, _ = canonical_prefix(plan["root"], cid, row, plan["sweep"])
        saved = read_bundle(plan, row, prefix, cid, "reference", tensors=False)["resolved"]
        recomputed = resolve_positions(row, prefix, plan["accounts"], tokenizer, plan["sweep"])
        require_matching_input(recomputed, saved)
        require_matching_input(nod_positions(recomputed), nod_positions(saved))
    return write_report(
        plan["root"],
        "nod-tokenizer-preflight",
        {
            **report_identity(plan),
            "status": "passed",
            "condition_count": len(plan["rows"]),
            "checks": {
                "reference_prefix_and_positions_exact": True,
                "reference_manifest_and_freeze": True,
            },
            "repeat_condition_ids": plan["repeat_ids"],
            "repeat_selection": (
                "first five draft_task_id pairs, ascending; conditions ascending within pair"
            ),
            "tokenizer_revision": config["tokenizer_revision"],
            "chat_template_sha256": chat_template_sha256(tokenizer),
            "validation_rows_loaded": 0,
        },
    )


def report_identity(plan: dict) -> dict:
    return {
        "git_commit": clean_commit(plan["root"]),
        "analysis_config_sha256": plan["config_sha256"],
        "spec_sha256": plan["spec_sha256"],
        "sweep_config_sha256": plan["sweep_config_sha256"],
        "reference_sha256": plan["reference"]["sha256"],
    }


def capture_resolved(model, resolved: dict, sweep: dict) -> dict:
    names = resolved["position_order"]
    logits = [p for p in ("S", "G", "D") if p in names]
    value = forward_capture(
        model,
        resolved["input_ids"],
        [resolved["positions"][p]["token_index"] for p in names],
        logits,
        names,
        sweep["capture"]["block_path"],
        sweep["capture"]["top_k"],
        resolved["digit_token_ids"],
        resolved["positions"]["G"]["token_id"],
    )
    return {"positions": resolved, **value}


def nod_gpu_preflight(config_path: Path) -> dict:
    import torch

    plan = load_plan(config_path)
    identity = report_identity(plan)
    model, tokenizer = load_model(plan["config"])
    records = []
    for row in plan["rows"][: plan["nod"]["preflight_condition_count"]]:
        canonical_id = plan["run_ids"][row["condition_id"]]
        prefix, _, _ = canonical_prefix(plan["root"], canonical_id, row, plan["sweep"])
        reference = read_bundle(plan, row, prefix, canonical_id, "reference", tensors=False)
        recomputed = resolve_positions(row, prefix, plan["accounts"], tokenizer, plan["sweep"])
        require_matching_input(recomputed, reference["resolved"])
        torch.cuda.reset_peak_memory_stats()
        start = time.monotonic()
        result = capture_resolved(model, nod_positions(recomputed), plan["sweep"])
        torch.cuda.synchronize()
        validate_residual_schema(result["residuals"], model, len(NOD_POSITIONS))
        peak = torch.cuda.max_memory_allocated()
        if peak > plan["nod"]["resources"]["maximum_gpu_memory_gib"] * 1024**3:
            raise RuntimeError("GPU memory ceiling exceeded")
        records.append(
            {
                "condition_id": row["condition_id"],
                "elapsed_seconds": time.monotonic() - start,
                "peak_gpu_memory_bytes": peak,
                "nonfinite": False,
                "logit_method": result["logit_method"],
            }
        )
    return write_report(
        plan["root"],
        "nod-gpu-preflight",
        {**identity, "status": "passed", "conditions": records, "environment": environment()},
    )


def create_nod_runtime_freeze(
    config_path: Path,
    tokenizer_report: Path,
    gpu_report: Path,
    environment_lock: Path,
    output_path: Path | None = None,
) -> Path:
    plan = load_plan(config_path)
    identity = report_identity(plan)
    paths = [safe_path(plan["root"], p) for p in (tokenizer_report, gpu_report, environment_lock)]
    reports = [read_json(p) for p in paths[:2]]
    if any(
        r.get("status") != "passed" or any(r.get(k) != v for k, v in identity.items())
        for r in reports
    ):
        raise ValueError("D-free preflight identity or status differs")
    freeze = {
        **identity,
        "schema_version": 1,
        "status": "frozen",
        "created_at": datetime.now(UTC).isoformat(),
        "design_freeze_sha256": sha256_file(
            plan["root"] / plan["config"]["references"]["design_freeze"]
        ),
        "files_sha256": {p.relative_to(plan["root"]).as_posix(): sha256_file(p) for p in paths},
        "model": plan["config"]["model"],
        "resources": plan["nod"]["resources"],
        "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
        "environment": reports[1]["environment"],
    }
    validate_freeze(plan, freeze)
    relative = output_path or Path(
        f"artifacts/phase2-position-sweep-nod-runtime-{identity['git_commit'][:7]}.freeze.json"
    )
    path = safe_path(plan["root"], relative)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json_bytes(freeze).decode())
    return path


def jobs(plan: dict):
    indexed = {r["condition_id"]: r for r in plan["rows"]}
    return [("repeat", indexed[cid]) for cid in plan["repeat_ids"]] + [
        ("nod", r) for r in plan["rows"]
    ]


def capture_nod(config_path: Path, runtime_freeze: Path) -> list[Path]:
    import torch

    plan = load_plan(config_path, runtime_freeze, matching=True)
    identity = report_identity(plan)
    root, config, nod = plan["root"], plan["config"], plan["nod"]
    limits = nod["resources"]
    model = tokenizer = None
    paths, total = [], 0
    for number, (kind, row) in enumerate(jobs(plan), 1):
        canonical_id = plan["run_ids"][row["condition_id"]]
        rid = run_id(nod[kind + "_capture"]["run_id_prefix"], canonical_id)
        reference_id = run_id(nod["reference"]["capture_run_id_prefix"], canonical_id)
        names = NOD_POSITIONS if kind == "nod" else POSITIONS
        expected = {
            **identity,
            "schema_version": 1,
            "run_id": rid,
            "condition_id": row["condition_id"],
            "pair_id": row["pair_id"],
            "split": "train",
            "git_dirty": False,
            "runtime_freeze": runtime_freeze.as_posix(),
            "runtime_freeze_sha256": plan["runtime_sha256"],
            "canonical_run_id": canonical_id,
            "canonical_manifest_sha256": sha256_file(
                root / "artifacts/runs" / canonical_id / "manifest.json"
            ),
            "reference_run_id": reference_id,
            "reference_manifest_sha256": plan["reference_rows"][reference_id]["manifest_sha256"],
            "capture_kind": kind,
            "position_order": list(names),
            "model": config["model"],
            "tokenizer_revision": config["model"]["tokenizer_revision"],
            "seed": config["seed"],
            "decoding": plan["freeze"]["decoding"],
        }
        path = root / "artifacts/runs" / rid
        if completed_bundle(path, expected):
            total += bundle_bytes(path)
            paths.append(path)
            continue
        start, peak, result, failure = time.monotonic(), 0, None, None
        condition = {k: v for k, v in row.items() if k != "account_block_position"}
        run = {**expected, "status": "completed"}
        prefix_sha = ""
        try:
            prefix, condition, _ = canonical_prefix(root, canonical_id, row, plan["sweep"])
            prefix_sha = sha256_file(root / "artifacts/runs" / canonical_id / "prefix.json")
            reference = read_bundle(plan, row, prefix, canonical_id, "reference", tensors=False)
            if model is None:
                model, tokenizer = load_model(config)
            resolved = resolve_positions(row, prefix, plan["accounts"], tokenizer, plan["sweep"])
            require_matching_input(resolved, reference["resolved"])
            selected = nod_positions(resolved) if kind == "nod" else reference["resolved"]
            if len(selected["input_ids"]) > config["model"]["max_context_tokens"]:
                raise ValueError("serialized input exceeds configured context")
            torch.cuda.reset_peak_memory_stats()
            result = capture_resolved(model, selected, plan["sweep"])
            torch.cuda.synchronize()
            validate_residual_schema(result["residuals"], model, len(names))
            peak = torch.cuda.max_memory_allocated()
            dimensions = {
                "num_hidden_layers": model.config.num_hidden_layers,
                "hidden_size": model.config.hidden_size,
            }
            if dimensions != reference["run"]["model_dimensions"]:
                raise ValueError("reference model dimensions differ")
            run.update(model_dimensions=dimensions, logit_method=result["logit_method"])
            if peak > limits["maximum_gpu_memory_gib"] * 1024**3:
                raise RuntimeError("GPU memory ceiling exceeded")
            if time.monotonic() - start > limits["maximum_seconds_per_condition"]:
                raise RuntimeError("condition time ceiling exceeded")
        except Exception as exc:
            failure = exc
            if torch.cuda.is_initialized():
                peak = max(peak, torch.cuda.max_memory_allocated())
        run.update(elapsed_seconds=time.monotonic() - start, peak_gpu_memory_bytes=peak)
        resolved_config = {
            "nod": nod,
            "sweep": plan["sweep"],
            "model": config["model"],
            "seed": config["seed"],
            "decoding": plan["freeze"]["decoding"],
        }
        if failure is None:
            try:
                files = capture_files(condition, result, run, resolved_config, prefix_sha)
                maximum = min(
                    limits["maximum_storage_gib_per_condition"] * 1024**3,
                    limits["maximum_total_storage_gib"] * 1024**3 - total,
                )
                path = write_bundle(root / "artifacts", rid, files, maximum_bytes=maximum)
            except Exception as exc:
                failure = exc
        if failure is not None:
            run.update(
                status="technical_failure",
                exception_type=type(failure).__name__,
                failure_message=str(failure),
            )
            path = write_bundle(
                root / "artifacts",
                rid,
                capture_files(condition, None, run, resolved_config, prefix_sha),
            )
            raise RuntimeError(f"retained technical failure: {rid}") from failure
        total += bundle_bytes(path)
        paths.append(path)
        print(f"D-free capture {number}/{len(jobs(plan))}: {rid}", file=sys.stderr, flush=True)
    return paths


def bundle_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.iterdir() if p.is_file())


def load_records(plan: dict) -> list[dict]:
    records = []
    for row in plan["rows"]:
        canonical_id = plan["run_ids"][row["condition_id"]]
        prefix, _, manifest = canonical_prefix(plan["root"], canonical_id, row, plan["sweep"])
        reference = read_bundle(plan, row, prefix, canonical_id, "reference")
        nod = read_bundle(plan, row, prefix, canonical_id, "nod")
        require_matching_input(nod["resolved"], nod_positions(reference["resolved"]))
        if nod["run"]["model_dimensions"] != reference["run"]["model_dimensions"]:
            raise ValueError("D-free model dimensions differ")
        repeat = None
        if row["condition_id"] in plan["repeat_ids"]:
            repeat = read_bundle(plan, row, prefix, canonical_id, "repeat")
            require_matching_input(repeat["resolved"], reference["resolved"])
            if repeat["run"]["model_dimensions"] != reference["run"]["model_dimensions"]:
                raise ValueError("repeat model dimensions differ")
        import torch
        from safetensors.torch import load_file

        bundle = plan["root"] / "artifacts/runs" / canonical_id
        canonical = load_file(str(_verified_artifact(bundle, manifest, "residual.safetensors")))
        if set(canonical) != set(reference["tensors"]):
            raise ValueError("canonical residual layers differ")
        hidden = reference["run"]["model_dimensions"]["hidden_size"]
        if any(
            t.shape != (1, 1, hidden) or t.dtype != torch.bfloat16 or not torch.isfinite(t).all()
            for t in canonical.values()
        ):
            raise ValueError("canonical residual shape/dtype/finite differs")
        records.append(
            {
                "row": row,
                "prefix": prefix,
                "canonical_id": canonical_id,
                "canonical": canonical,
                "reference": reference,
                "nod": nod,
                "repeat": repeat,
            }
        )
    return records


def write_collection_manifest(config_path: Path, runtime_freeze: Path, output: Path) -> Path:
    plan = load_plan(config_path, runtime_freeze, matching=True)
    target = safe_path(plan["root"], output)
    if target.exists():
        raise FileExistsError(target)
    records = load_records(plan)
    items = []
    for record in records:
        for kind in ("repeat", "nod"):
            value = record[kind]
            if value is None:
                continue
            run = value["run"]
            items.append(
                {
                    k: run[k]
                    for k in (
                        "run_id",
                        "condition_id",
                        "pair_id",
                        "capture_kind",
                        "reference_run_id",
                        "reference_manifest_sha256",
                        "elapsed_seconds",
                        "peak_gpu_memory_bytes",
                    )
                }
                | {
                    "manifest_sha256": value["manifest_sha256"],
                    "bytes": bundle_bytes(value["bundle"]),
                }
            )
    limits = plan["nod"]["resources"]
    if any(
        r["bytes"] > limits["maximum_storage_gib_per_condition"] * 1024**3
        or r["elapsed_seconds"] > limits["maximum_seconds_per_condition"]
        or r["peak_gpu_memory_bytes"] > limits["maximum_gpu_memory_gib"] * 1024**3
        for r in items
    ):
        raise ValueError("capture resource ceiling exceeded")
    total = sum(i["bytes"] for i in items)
    if (
        len(items) != len(plan["rows"]) + len(plan["repeat_ids"])
        or total > limits["maximum_total_storage_gib"] * 1024**3
    ):
        raise ValueError("collection size or storage differs")
    report = {
        **report_identity(plan),
        "schema_version": 1,
        "status": "completed_verified",
        "created_at": datetime.now(UTC).isoformat(),
        "runtime_freeze": plan["runtime"],
        "runtime_freeze_sha256": plan["runtime_sha256"],
        "validation_rows_loaded": 0,
        "condition_count": len(plan["rows"]),
        "repeat_condition_count": len(plan["repeat_ids"]),
        "total_bytes": total,
        "runs": items,
        "files_sha256": plan["freeze"]["files_sha256"],
        "research_result": "post_result_train_only_technical_control_capture",
    }
    with target.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json_bytes(report).decode())
    return target


def compare_vectors(a_bf16, b_bf16) -> dict:
    import torch

    if (
        a_bf16.dtype != torch.bfloat16
        or b_bf16.dtype != torch.bfloat16
        or a_bf16.shape != b_bf16.shape
        or a_bf16.numel() == 0
        or not torch.isfinite(a_bf16).all()
        or not torch.isfinite(b_bf16).all()
    ):
        raise ValueError("comparison requires aligned finite bfloat16 vectors")
    a, b = a_bf16.float(), b_bf16.float()
    difference = a - b
    return {
        "bit_exact": bool(
            torch.equal(
                a_bf16.contiguous().view(torch.int16), b_bf16.contiguous().view(torch.int16)
            )
        ),
        "relative_l2": float(torch.linalg.vector_norm(difference))
        / max(float(torch.linalg.vector_norm(b)), torch.finfo(torch.float32).tiny),
        "max_absolute": float(difference.abs().max()),
    }


def compare_position(
    tensors_a: dict,
    positions_a: list[str],
    tensors_b: dict,
    positions_b: list[str],
    name: str,
    layer: str,
) -> dict:
    return compare_vectors(
        tensors_a[layer][0, positions_a.index(name)], tensors_b[layer][0, positions_b.index(name)]
    )


def aggregate_comparisons(cells: dict) -> dict:
    import numpy as np

    return {
        name: {
            "count": len(values),
            "bit_exact_count": sum(v["bit_exact"] for v in values),
            **{
                metric: {
                    "median": float(np.median([v[metric] for v in values])),
                    "maximum": max(v[metric] for v in values),
                }
                for metric in ("relative_l2", "max_absolute")
            },
        }
        for name, values in cells.items()
    }


def comparison_gate(repeat: dict, nod: dict) -> dict:
    exact = all(c["bit_exact_count"] == c["count"] for c in repeat.values())
    no_effect = exact and all(c["bit_exact_count"] == c["count"] for c in nod.values())
    widths = {name: c["relative_l2"]["maximum"] for name, c in repeat.items()}
    return {
        "reproducibility": "R-EXACT" if exact else "R-NOISE",
        "noise_width": widths,
        "nod_within_observed_noise_width": {
            name: c["relative_l2"]["maximum"] <= widths[name] for name, c in nod.items()
        },
        "d_effect": "1_no_effect" if no_effect else "pending_reanalysis",
        "reanalysis_required": not no_effect,
        "interpretation": "saved_residuals_only; local-wording caveats remain",
    }


def delta_label_readout(
    rows: list[dict], features: dict, accounts: dict, sweep_analysis: dict, comparison: dict
) -> dict:
    import numpy as np

    labels = np.asarray([recipient_first_label(row, accounts) for row in rows])
    pairs = pair_index(rows, labels)
    spec = {
        **sweep_analysis,
        "seed": comparison["delta_probe_seed"],
        "permutation_repeats": comparison["permutation_repeats"],
    }
    cells = {}
    for position, layers in spec["judged_layers"].items():
        for layer in layers:
            matrix = features[position][layer]
            zero = bool(np.all(matrix == 0))
            for probe in PROBES:
                name = f"{position}/layer{layer}/{probe}"
                cell = {
                    "position": position,
                    "layer": layer,
                    "probe": probe,
                    "judged": not zero,
                    "status": "no_difference" if zero else "computed",
                }
                if not zero:
                    values = _cell_scores(probe, rows, matrix, labels, "family", pairs, spec)
                    cell["paired_accuracy"] = paired_accuracy(pairs, labels, values)
                cells[name] = cell
    count = sum(c["judged"] for c in cells.values())
    null = global_null(rows, features, labels, pairs, cells, spec) if count else []
    for cell in cells.values():
        if cell["judged"]:
            cell["family_wise_p"] = (1 + sum(v >= cell["paired_accuracy"] for v in null)) / (
                1 + len(null)
            )
    return {
        "reported_only": True,
        "computed_cell_count": count,
        "cells": cells,
        "null_maxima": null,
        "settings": spec,
    }


def output_path(plan: dict, key: str) -> Path:
    path = safe_path(plan["root"], "artifacts/processed/" + plan["nod"][key]["output_id"])
    if path.exists():
        raise FileExistsError(f"immutable output already exists: {path}")
    return path


def provenance(plan: dict, records: list[dict]) -> dict:
    current = clean_commit(plan["root"])
    if current == plan["freeze"]["git_commit"]:
        raise ValueError("comparison/reanalysis requires a different commit from capture")
    return {
        **report_identity(plan),
        "git_dirty": False,
        "runtime_freeze_sha256": plan["runtime_sha256"],
        "capture_git_commit": plan["freeze"]["git_commit"],
        "validation_rows_loaded": 0,
        "research_result": "post_result_train_only_technical_control",
        "capture_manifest_sha256": {
            value["run"]["run_id"]: value["manifest_sha256"]
            for record in records
            for kind in ("reference", "nod", "repeat")
            if (value := record[kind]) is not None
        },
        "canonical_manifest_sha256": {
            r["canonical_id"]: sha256_file(
                plan["root"] / "artifacts/runs" / r["canonical_id"] / "manifest.json"
            )
            for r in records
        },
    }


def run_comparison(config_path: Path, runtime_freeze: Path) -> Path:
    import numpy as np

    plan = load_plan(config_path, runtime_freeze)
    output = output_path(plan, "comparison")
    if clean_commit(plan["root"]) == plan["freeze"]["git_commit"]:
        raise ValueError("comparison requires a different commit from capture")
    records = load_records(plan)
    prov = provenance(plan, records)
    comparisons = {"R": {}, "N": {}, "P": {}}
    per_condition = {}
    features = {
        p: {layer: [] for layer in plan["sweep"]["analysis"]["judged_layers"][p]}
        for p in NOD_POSITIONS
    }
    for record in records:
        ref, nod, repeat = record["reference"], record["nod"], record["repeat"]
        details = {"R": {}, "N": {}, "P": {}}
        for layer in ref["tensors"]:
            for name in NOD_POSITIONS:
                cell = name + "/" + layer
                value = compare_position(
                    nod["tensors"],
                    nod["resolved"]["position_order"],
                    ref["tensors"],
                    ref["resolved"]["position_order"],
                    name,
                    layer,
                )
                comparisons["N"].setdefault(cell, []).append(value)
                details["N"][cell] = value
                index = int(layer.rsplit(".", 1)[1])
                if index in features[name]:
                    a = ref["tensors"][layer][
                        0, ref["resolved"]["position_order"].index(name)
                    ].float()
                    b = nod["tensors"][layer][
                        0, nod["resolved"]["position_order"].index(name)
                    ].float()
                    features[name][index].append((a - b).numpy())
            value = compare_vectors(
                nod["tensors"][layer][0, nod["resolved"]["position_order"].index("T")],
                record["canonical"][layer][0, 0],
            )
            comparisons["P"].setdefault("T/" + layer, []).append(value)
            details["P"]["T/" + layer] = value
            if repeat is not None:
                for name in POSITIONS:
                    cell = name + "/" + layer
                    value = compare_position(
                        repeat["tensors"],
                        repeat["resolved"]["position_order"],
                        ref["tensors"],
                        ref["resolved"]["position_order"],
                        name,
                        layer,
                    )
                    comparisons["R"].setdefault(cell, []).append(value)
                    details["R"][cell] = value
        per_condition[record["row"]["condition_id"]] = details
    aggregated = {k: aggregate_comparisons(v) for k, v in comparisons.items()}
    gate = comparison_gate(aggregated["R"], aggregated["N"])
    matrices = {
        p: {layer: np.stack(v).astype(np.float32) for layer, v in layers.items()}
        for p, layers in features.items()
    }
    delta = delta_label_readout(
        plan["rows"],
        matrices,
        plan["accounts"],
        plan["sweep"]["analysis"],
        plan["nod"]["comparison"],
    )
    old_gpu = read_json(plan["root"] / plan["nod"]["reference"]["gpu_preflight_report"])
    two = {
        r["condition_id"]: {
            "canonical_to_ps001": r["differences"],
            "canonical_to_ps002": per_condition[r["condition_id"]]["P"],
            "ps001_to_ps002": {
                k: v for k, v in per_condition[r["condition_id"]]["N"].items() if k.startswith("T/")
            },
        }
        for r in old_gpu["conditions"]
    }
    return publish(
        output,
        {
            "report.json": canonical_json_bytes(
                {
                    "schema_version": 1,
                    "provenance": prov,
                    "report": {
                        **gate,
                        "comparisons": aggregated,
                        "per_condition": per_condition,
                        "delta_label_readout": delta,
                        "original_preflight_conditions": two,
                        "interpretation": (
                            "P and N are separate input changes, not additive proportions; "
                            "P is not rerun noise."
                        ),
                    },
                }
            )
        },
        kind="position_sweep_nod_comparison",
    )


def reanalysis_settings(original: dict, output_id: str, candidate: dict | None = None) -> dict:
    expected = copy.deepcopy(original)
    expected.update(report_only_positions=[], output_id=output_id)
    if candidate is not None and candidate != expected:
        raise ValueError("reanalysis changed settings beyond D/output ID")
    if sum(map(len, expected["judged_layers"].values())) * len(PROBES) != 42:
        raise ValueError("reanalysis must have 42 judged cells")
    return expected


def classify_reanalysis(old: dict, new: dict) -> dict:
    differences = []
    for p in NOD_POSITIONS:
        if (
            old["position_classifications"][p]["class"]
            != new["position_classifications"][p]["class"]
        ):
            differences.append("position_classifications/" + p)
    for key in ("rule", "mapping"):
        if old["hypothesis_mapping"][key] != new["hypothesis_mapping"][key]:
            differences.append("hypothesis_mapping/" + key)
    return {
        "d_effect": "3_classification_changed" if differences else "2_numeric_only",
        "changed_fields": differences,
    }


def load_comparison(plan: dict) -> tuple[dict, Path]:
    path = safe_path(
        plan["root"],
        "artifacts/processed/" + plan["nod"]["comparison"]["output_id"] + "/report.json",
    )
    manifest = read_json(path.parent / "manifest.json")
    if manifest.get("kind") != "position_sweep_nod_comparison":
        raise ValueError("comparison kind differs")
    item = manifest["artifacts"][path.name]
    if item["sha256"] != sha256_file(path) or item["bytes"] != path.stat().st_size:
        raise ValueError("comparison checksum differs")
    value = read_json(path)
    prov = value["provenance"]
    expected = {
        "analysis_config_sha256": plan["config_sha256"],
        "spec_sha256": plan["spec_sha256"],
        "sweep_config_sha256": plan["sweep_config_sha256"],
        "runtime_freeze_sha256": plan["runtime_sha256"],
        "reference_sha256": plan["reference"]["sha256"],
        "git_dirty": False,
        "validation_rows_loaded": 0,
    }
    if any(prov.get(k) != v for k, v in expected.items()):
        raise ValueError("comparison provenance differs")
    return value, path


def run_reanalysis(config_path: Path, runtime_freeze: Path) -> Path:
    import numpy as np

    plan = load_plan(config_path, runtime_freeze)
    output = output_path(plan, "reanalysis")
    comparison, path = load_comparison(plan)
    if not comparison["report"]["reanalysis_required"]:
        raise ValueError("reanalysis not required; stopping before fit")
    records = load_records(plan)
    prov = provenance(plan, records)
    # Bind exactly the bundles whose comparison requested this reanalysis.
    if prov["capture_manifest_sha256"] != comparison["provenance"]["capture_manifest_sha256"]:
        raise ValueError("comparison capture manifests differ")
    layers = plan["sweep"]["analysis"]["report_layers"]
    features = {
        p: {
            layer: np.stack(
                [
                    r["nod"]["tensors"][f"model.layers.{layer}"][
                        0, r["nod"]["resolved"]["position_order"].index(p)
                    ]
                    .float()
                    .numpy()
                    for r in records
                ]
            ).astype(np.float32)
            for layer in layers
        }
        for p in NOD_POSITIONS
    }
    settings = reanalysis_settings(
        plan["sweep"]["analysis"], plan["nod"]["reanalysis"]["output_id"]
    )
    report = analyze(
        plan["rows"],
        features,
        [r["prefix"]["text"] for r in records],
        [len(r["prefix"]["token_ids"]) for r in records],
        [r["nod"]["resolved"] for r in records],
        [r["nod"]["logprobs"] for r in records],
        plan["accounts"],
        settings,
        position_names=NOD_POSITIONS,
    )
    classification = classify_reanalysis(plan["reference"]["analysis"]["report"], report)
    classification["delta_has_significant_cell"] = any(
        c.get("family_wise_p", 1) < 0.05
        for c in comparison["report"]["delta_label_readout"]["cells"].values()
    )
    prov.update(
        reference_analysis_report_sha256=plan["reference"]["sha256"]["analysis_report"],
        comparison_report_sha256=sha256_file(path),
    )
    return publish(
        output,
        {
            "report.json": canonical_json_bytes(
                {
                    "schema_version": 1,
                    "provenance": prov,
                    "settings": settings,
                    "report": report,
                    "d_effect_classification": classification,
                }
            )
        },
        kind="position_sweep_nod_reanalysis",
    )


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
            "compare",
            "reanalyze",
        ),
    )
    parser.add_argument("config", type=Path)
    for key in ("tokenizer-report", "gpu-report", "environment-lock", "runtime-freeze", "output"):
        parser.add_argument("--" + key, type=Path)
    args = parser.parse_args()
    if args.command == "tokenizer-preflight":
        print(nod_tokenizer_preflight(args.config))
    elif args.command == "gpu-preflight":
        print(nod_gpu_preflight(args.config))
    elif args.command == "freeze":
        if any(v is None for v in (args.tokenizer_report, args.gpu_report, args.environment_lock)):
            parser.error("freeze requires both reports and environment lock")
        print(
            create_nod_runtime_freeze(
                args.config,
                args.tokenizer_report,
                args.gpu_report,
                args.environment_lock,
                args.output,
            )
        )
    else:
        if args.runtime_freeze is None:
            parser.error("command requires runtime freeze")
        if args.command == "capture":
            print(len(capture_nod(args.config, args.runtime_freeze)))
        elif args.command == "collection-manifest":
            if args.output is None:
                parser.error("collection-manifest requires output")
            print(write_collection_manifest(args.config, args.runtime_freeze, args.output))
        else:
            print(
                (run_comparison if args.command == "compare" else run_reanalysis)(
                    args.config, args.runtime_freeze
                )
            )


if __name__ == "__main__":
    main()
