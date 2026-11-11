"""Frozen, immutable six-position capture; no generation or automatic retry."""

from __future__ import annotations

import argparse
import inspect
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from goal_takeover.instrumentation.activation_hooks import ResidualCapture
from goal_takeover.instrumentation.huggingface import transformer_block_names
from goal_takeover.models.loader import load_hugging_face_model
from goal_takeover.phase2.argument_recipient_672_train_readout import clean_commit
from goal_takeover.phase2.position_sweep_positions import (
    POSITIONS,
    canonical_prefix,
    context,
    resolve_positions,
    safe_path,
    verified_json,
    verify_manifest,
    write_report,
)
from goal_takeover.storage.run_writer import (
    ImmutableRunWriter,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


def load_model(config: dict) -> tuple:
    values = config["model"]
    return load_hugging_face_model(
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


def capture_condition(
    model: Any, tokenizer: Any, row: dict, prefix: dict, accounts: dict, spec: dict
) -> dict:
    import torch

    positions = resolve_positions(row, prefix, accounts, tokenizer, spec)
    maximum = getattr(getattr(model, "config", None), "max_position_embeddings", None)
    if maximum is not None and len(positions["input_ids"]) > maximum:
        raise ValueError("serialized input exceeds model context")
    names = transformer_block_names(model, block_path=spec["capture"]["block_path"])
    device = next(model.parameters()).device
    inputs = torch.tensor([positions["input_ids"]], dtype=torch.long, device=device)
    model.eval()
    indices = [positions["positions"][p]["token_index"] for p in POSITIONS]
    if indices[-3:] != list(range(inputs.shape[1] - 3, inputs.shape[1])):
        raise ValueError("S/G/D are not the final three input tokens")
    with torch.no_grad(), ResidualCapture(model, names, token_indices=indices) as captured:
        if "logits_to_keep" in inspect.signature(model.forward).parameters:
            output = model(input_ids=inputs, use_cache=False, logits_to_keep=3)
            logits = output.logits
            method = "logits_to_keep=3"
        else:
            # Bypass the causal-LM wrapper, so full-sequence vocabulary logits never exist.
            output = model.model(input_ids=inputs, use_cache=False, return_dict=True)
            logits = model.lm_head(output.last_hidden_state[:, -3:, :])
            method = "lm_head_last_three"
        if tuple(logits.shape[:2]) != (1, 3) or not torch.isfinite(logits).all():
            raise ValueError("invalid last-three logits")
        logprobs = torch.log_softmax(logits[0].float(), dim=-1)
        if not torch.isfinite(logprobs).all():
            raise ValueError("nonfinite log probabilities")
        records = {}
        for index, p in enumerate(("S", "G", "D")):
            values, token_ids = logprobs[index].topk(
                min(spec["capture"]["top_k"], logits.shape[-1])
            )
            records[p] = {
                "candidate_digits": {
                    key: float(logprobs[index, token])
                    for key, token in positions["digit_token_ids"].items()
                },
                "top_token_ids": token_ids.cpu().tolist(),
                "top_log_probabilities": values.cpu().tolist(),
            }
        records["S"]["gb_log_probability"] = float(
            logprobs[0, positions["positions"]["G"]["token_id"]]
        )
    tensors = {}
    for name, values in captured.values.items():
        if len(values) != 1 or tuple(values[0].shape[:2]) != (1, len(POSITIONS)):
            raise ValueError(f"residual capture shape/call count differs: {name}")
        tensor = values[0].to(torch.bfloat16).contiguous()
        if not torch.isfinite(tensor).all():
            raise ValueError(f"nonfinite residual: {name}")
        tensors[name] = tensor
    return {
        "positions": positions,
        "residuals": tensors,
        "logprobs": records,
        "logit_method": method,
    }


def environment() -> dict:
    import bitsandbytes
    import torch
    import transformers

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "bitsandbytes": bitsandbytes.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
    }


def validate_residual_schema(tensors: dict, model: Any) -> None:
    expected = {f"model.layers.{i}" for i in range(model.config.num_hidden_layers)}
    if set(tensors) != expected or any(
        tuple(t.shape) != (1, 6, model.config.hidden_size) for t in tensors.values()
    ):
        raise ValueError("residual model dimensions differ")


def gpu_preflight(config_path: Path) -> dict:
    import torch
    from safetensors.torch import load_file

    root, spec, config, rows, run_ids, accounts = context(config_path)
    commit = clean_commit(root)
    model, tokenizer = load_model(config)
    checks = []
    for row in rows[: spec["capture"]["preflight_condition_count"]]:
        run_id = run_ids[row["condition_id"]]
        prefix, _, manifest = canonical_prefix(root, run_id, row, spec)
        torch.cuda.reset_peak_memory_stats()
        start = time.monotonic()
        result = capture_condition(model, tokenizer, row, prefix, accounts, spec)
        torch.cuda.synchronize()
        validate_residual_schema(result["residuals"], model)
        bundle = root / "artifacts/runs" / run_id
        from goal_takeover.phase2.argument_recipient_672_features import _verified_artifact

        canonical = load_file(str(_verified_artifact(bundle, manifest, "residual.safetensors")))
        differences = {}
        for name, tensor in result["residuals"].items():
            current, old = tensor[:, 2:3, :].float(), canonical[name].float()
            if old.shape != current.shape or not torch.isfinite(old).all():
                raise ValueError("canonical comparison residual invalid")
            delta = current - old
            denominator = float(torch.linalg.vector_norm(old))
            differences[name] = {
                "max_absolute_difference": float(delta.abs().max()),
                "relative_l2_difference": float(torch.linalg.vector_norm(delta))
                / max(denominator, torch.finfo(torch.float32).tiny),
            }
        peak = torch.cuda.max_memory_allocated()
        if peak > spec["resources"]["maximum_gpu_memory_gib"] * 1024**3:
            raise RuntimeError("GPU memory ceiling exceeded")
        checks.append(
            {
                "condition_id": row["condition_id"],
                "differences": differences,
                "elapsed_seconds": time.monotonic() - start,
                "peak_gpu_memory_bytes": peak,
                "nonfinite": False,
                "logit_method": result["logit_method"],
            }
        )
    return write_report(
        root,
        "gpu-preflight",
        {
            "git_commit": commit,
            "status": "passed",
            "conditions": checks,
            "environment": environment(),
            "analysis_config_sha256": sha256_file(root / config_path),
            "spec_sha256": sha256_file(root / spec["spec"]),
        },
    )


def create_runtime_freeze(
    config_path: Path,
    tokenizer_report: Path,
    stem_report: Path,
    gpu_report: Path,
    environment_lock: Path,
    output_path: Path | None = None,
) -> Path:
    root, spec, config, *_ = context(config_path)
    commit = clean_commit(root)
    reports = [safe_path(root, p) for p in (tokenizer_report, stem_report, gpu_report)]
    loaded = [json.loads(p.read_text(encoding="utf-8")) for p in reports]
    config_sha, spec_sha = sha256_file(root / config_path), sha256_file(root / spec["spec"])
    if any(
        r.get("git_commit") != commit
        or r.get("analysis_config_sha256") != config_sha
        or r.get("spec_sha256") != spec_sha
        for r in loaded
    ):
        raise ValueError("preflight commit/config/spec differs")
    if loaded[0].get("status") != "passed" or loaded[2].get("status") != "passed":
        raise ValueError("tokenizer/GPU preflight did not pass")
    reports.append(safe_path(root, environment_lock))
    freeze = {
        "schema_version": 1,
        "status": "frozen",
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": commit,
        "design_freeze_sha256": sha256_file(root / config["references"]["design_freeze"]),
        "files_sha256": {p.relative_to(root).as_posix(): sha256_file(p) for p in reports},
        "model": config["model"],
        "resources": spec["resources"],
        "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0},
        "environment": loaded[2]["environment"],
        "analysis_config_sha256": config_sha,
        "spec_sha256": spec_sha,
    }
    output = safe_path(
        root,
        output_path or Path(f"artifacts/phase2-position-sweep-runtime-{commit[:7]}.freeze.json"),
    )
    with output.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json_bytes(freeze).decode("utf-8"))
    return output


def verify_sweep_freeze(
    root: Path, config_path: Path, spec: dict, config: dict, runtime: Path
) -> dict:
    freeze = json.loads(safe_path(root, runtime).read_text(encoding="utf-8"))
    if (
        freeze.get("analysis_config_sha256") != sha256_file(root / config_path)
        or freeze.get("spec_sha256") != sha256_file(root / spec["spec"])
        or freeze.get("model") != config["model"]
        or freeze.get("resources") != spec["resources"]
        or freeze.get("decoding") != {"do_sample": False, "temperature": 0.0, "top_p": 1.0}
    ):
        raise ValueError("position sweep freeze config/spec/model/resources differ")
    return freeze


def capture_files(
    condition: dict, result: dict | None, run: dict, resolved: dict, prefix_sha: str
) -> dict[str, bytes]:
    files = {
        "condition.json": canonical_json_bytes(condition),
        "run.json": canonical_json_bytes(run),
        "resolved_config.json": canonical_json_bytes(resolved),
    }
    if result is not None:
        from safetensors.torch import save

        positions = dict(result["positions"])
        ids = positions.pop("input_ids")
        files.update(
            {
                "positions.json": canonical_json_bytes(positions),
                "input.json": canonical_json_bytes(
                    {
                        "token_ids": ids,
                        "token_ids_sha256": sha256_bytes(canonical_json_bytes(ids)),
                        "canonical_prefix_sha256": prefix_sha,
                    }
                ),
                "logprobs.json": canonical_json_bytes(result["logprobs"]),
                "residual.safetensors": save(result["residuals"]),
            }
        )
    return files


def write_bundle(
    artifact_root: Path, run_id: str, files: dict[str, bytes], *, maximum_bytes: float | None = None
) -> Path:
    with ImmutableRunWriter(artifact_root, run_id) as writer:
        for name, content in files.items():
            writer.write_bytes(name, content, kind="position_sweep")
        if maximum_bytes is not None and writer.projected_size_bytes() > maximum_bytes:
            raise RuntimeError("storage ceiling exceeded, including manifest")
        return writer.commit()


def completed_bundle(bundle: Path, expected: dict) -> bool:
    if not bundle.exists():
        return False
    manifest = verify_manifest(bundle)
    run = verified_json(bundle, manifest, "run.json")
    if run.get("status") != "completed":
        raise ValueError("retained failure: retry requires a new run ID prefix")
    if any(run.get(k) != value for k, value in expected.items()):
        raise ValueError("existing bundle provenance differs")
    return True


def capture(config_path: Path, runtime_freeze: Path) -> list[Path]:
    import torch

    root, spec, config, rows, run_ids, accounts = context(
        config_path, runtime_freeze, matching=True
    )
    freeze = verify_sweep_freeze(root, config_path, spec, config, runtime_freeze)
    commit = clean_commit(root)
    base = {
        "schema_version": 1,
        "git_commit": commit,
        "git_dirty": False,
        "split": "train",
        "runtime_freeze": runtime_freeze.as_posix(),
        "runtime_freeze_sha256": sha256_file(root / runtime_freeze),
        "analysis_config_sha256": freeze["analysis_config_sha256"],
        "spec_sha256": freeze["spec_sha256"],
        "model": config["model"],
        "tokenizer_revision": config["model"]["tokenizer_revision"],
        "seed": config["seed"],
        "decoding": freeze["decoding"],
    }
    model = tokenizer = None
    paths, total = [], 0
    for row in rows:
        cid = row["condition_id"]
        canonical_id = run_ids[cid]
        run_id = spec["capture"]["run_id_prefix"] + "-" + canonical_id.rsplit("-", 1)[1]
        bundle = root / "artifacts/runs" / run_id
        expected = {
            **base,
            "run_id": run_id,
            "condition_id": cid,
            "canonical_run_id": canonical_id,
            "canonical_manifest_sha256": sha256_file(
                root / "artifacts/runs" / canonical_id / "manifest.json"
            ),
        }
        if completed_bundle(bundle, expected):
            total += sum(p.stat().st_size for p in bundle.iterdir() if p.is_file())
            paths.append(bundle)
            continue
        # Initialization follows all frozen-plan checks; errors are retained for this condition.
        start = time.monotonic()
        result = None
        prefix_sha = ""
        condition = {k: v for k, v in row.items() if k != "account_block_position"}
        run = {**expected, "pair_id": row["pair_id"], "status": "completed"}
        failure = None
        peak = 0
        try:
            if model is None:
                model, tokenizer = load_model(config)
            prefix, condition, _ = canonical_prefix(root, canonical_id, row, spec)
            prefix_sha = sha256_file(root / "artifacts/runs" / canonical_id / "prefix.json")
            torch.cuda.reset_peak_memory_stats()
            result = capture_condition(model, tokenizer, row, prefix, accounts, spec)
            torch.cuda.synchronize()
            validate_residual_schema(result["residuals"], model)
            peak = torch.cuda.max_memory_allocated()
            run.update(
                logit_method=result["logit_method"],
                model_dimensions={
                    "num_hidden_layers": model.config.num_hidden_layers,
                    "hidden_size": model.config.hidden_size,
                },
            )
            if result["positions"]["input_token_count"] > config["model"]["max_context_tokens"]:
                raise ValueError("serialized input exceeds configured context")
            limits = spec["resources"]
            if peak > limits["maximum_gpu_memory_gib"] * 1024**3:
                raise RuntimeError("GPU memory ceiling exceeded")
            if time.monotonic() - start > limits["maximum_seconds_per_condition"]:
                raise RuntimeError("condition time ceiling exceeded")
        except Exception as exc:
            failure = exc
            if torch.cuda.is_initialized():
                peak = max(peak, torch.cuda.max_memory_allocated())
        run.update(elapsed_seconds=time.monotonic() - start, peak_gpu_memory_bytes=peak)
        resolved = {
            "sweep": spec,
            "model": config["model"],
            "decoding": freeze["decoding"],
            "seed": config["seed"],
        }
        try:
            files = capture_files(condition, result, run, resolved, prefix_sha)
            size = sum(map(len, files.values()))
            limits = spec["resources"]
            if (
                size > limits["maximum_storage_gib_per_condition"] * 1024**3
                or total + size > limits["maximum_total_storage_gib"] * 1024**3
            ):
                raise RuntimeError("storage ceiling exceeded")
        except Exception as exc:
            failure = failure or exc
        if failure is not None:
            run.update(
                status="technical_failure",
                exception_type=type(failure).__name__,
                failure_message=str(failure),
            )
            # A small diagnostic failure bundle also works after OOM/serialization failures.
            files = capture_files(condition, None, run, resolved, prefix_sha)
        if failure is None:
            maximum_bytes = min(
                limits["maximum_storage_gib_per_condition"] * 1024**3,
                limits["maximum_total_storage_gib"] * 1024**3 - total,
            )
            try:
                path = write_bundle(root / "artifacts", run_id, files, maximum_bytes=maximum_bytes)
            except Exception as exc:
                failure = exc
                run.update(
                    status="technical_failure",
                    exception_type=type(exc).__name__,
                    failure_message=str(exc),
                )
                path = write_bundle(
                    root / "artifacts",
                    run_id,
                    capture_files(condition, None, run, resolved, prefix_sha),
                )
        else:
            path = write_bundle(root / "artifacts", run_id, files)
        paths.append(path)
        if failure is not None:
            raise RuntimeError(f"retained technical failure: {run_id}") from failure
        total += sum(p.stat().st_size for p in paths[-1].iterdir() if p.is_file())
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gpu-preflight", "freeze", "capture"))
    parser.add_argument("config", type=Path)
    for option in (
        "tokenizer-report",
        "stem-report",
        "gpu-report",
        "environment-lock",
        "runtime-freeze",
    ):
        parser.add_argument("--" + option, type=Path)
    args = parser.parse_args()
    if args.command == "gpu-preflight":
        print(gpu_preflight(args.config))
    elif args.command == "freeze":
        values = [args.tokenizer_report, args.stem_report, args.gpu_report, args.environment_lock]
        if any(v is None for v in values):
            parser.error("freeze requires all reports and environment lock")
        print(create_runtime_freeze(args.config, *values))
    else:
        if args.runtime_freeze is None:
            parser.error("capture requires --runtime-freeze")
        print(len(capture(args.config, args.runtime_freeze)))


if __name__ == "__main__":
    main()
