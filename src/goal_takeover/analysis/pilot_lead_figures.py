"""Render two descriptive figures from immutable pilot lead bundles.

Usage: PYTHONPATH=src python3 -m goal_takeover.analysis.pilot_lead_figures \
    artifacts/runs/banking-pilot-001-lead-status \
    docs/reports/figures
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from safetensors import safe_open

CAPTURE_COLUMNS = (
    "Initial\nresidual",
    "Tpre\nresidual",
    "Tpost\nresidual",
    "Tool end\nresidual",
    "Assistant start\nresidual",
    "IPI window\nresidual",
    "Last-query\nattention",
    "Actual-prefix\nscore",
    "Fixed-prefix\nscore",
)
POSITION_COLUMNS = {
    "Tpre": 1,
    "Tpost": 2,
    "Tend_tool": 3,
    "Tend_assistant": 4,
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_artifact(run_dir: Path, manifest: dict, relative_path: str) -> Path:
    entries = [item for item in manifest["artifacts"] if item["relative_path"] == relative_path]
    if len(entries) != 1:
        raise ValueError(f"Expected one manifest entry for {run_dir / relative_path}")
    path = run_dir / relative_path
    if not path.is_file():
        raise FileNotFoundError(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise ValueError(f"Checksum mismatch: {path}")
    return path


def capture_row(run: dict, manifest_paths: set[str]) -> np.ndarray:
    """Encode present actual residual/attention/score and diagnostic score."""
    row = np.zeros(len(CAPTURE_COLUMNS), dtype=np.uint8)
    for measurement in run["measurements"]:
        index = measurement["index"]
        scope = measurement["scope"]
        paths = {
            "residual": f"measurements/{index}/residual.safetensors",
            "attention": f"measurements/{index}/attention.json",
            "score": f"measurements/{index}/scores.json",
        }
        position_names = {item["name"] for item in measurement["positions"]["positions"]}
        if scope == "fixed_prefix_diagnostic":
            if paths["score"] in manifest_paths:
                row[8] = 4
            continue
        if scope != "actual":
            continue
        if paths["residual"] in manifest_paths:
            if index == 0 and "Tend_assistant" in position_names:
                row[0] = 1
            if measurement["positions"]["exposed"]:
                for name, column in POSITION_COLUMNS.items():
                    if name in position_names:
                        row[column] = 1
                intervention = set(measurement["positions"].get("intervention_token_indices", []))
                captured = set((measurement.get("activation") or {}).get("positions", []))
                if intervention and intervention <= captured:
                    row[5] = 1
        if paths["attention"] in manifest_paths and measurement["positions"]["exposed"]:
            row[6] = 2
        if paths["score"] in manifest_paths and measurement["positions"]["exposed"]:
            row[7] = 3
    return row


def cosine_distance_matrix(
    states: np.ndarray, positions: list[int], tpre: int
) -> tuple[np.ndarray, list[int]]:
    """Compare each saved token vector with Tpre at the same layer and prefix."""
    if states.ndim != 3 or states.shape[1] != len(positions):
        raise ValueError("Expected layers × captured positions × hidden dimensions")
    if len(set(positions)) != len(positions) or tpre not in positions:
        raise ValueError("Captured positions must be unique and include Tpre")
    after = [i for i, position in enumerate(positions) if position >= tpre]
    offsets = [positions[i] - tpre for i in after]
    if offsets != list(range(offsets[-1] + 1)):
        raise ValueError("Positions from Tpre through the last saved token must be continuous")
    vectors = np.asarray(states[:, after, :], dtype=np.float64)
    baseline = vectors[:, :1, :]
    norms = np.linalg.norm(vectors, axis=2) * np.linalg.norm(baseline, axis=2)
    if not np.all(np.isfinite(vectors)) or np.any(norms == 0):
        raise ValueError("Residual vectors must be finite and nonzero")
    similarity = np.sum(vectors * baseline, axis=2) / norms
    distance = np.clip(1.0 - similarity, 0.0, 2.0)
    distance[:, 0] = 0.0
    return distance, offsets


def render_coverage(matrix: np.ndarray, labels: list[str], output: Path) -> None:
    colors = ["#eef1f5", "#3664ad", "#168f8c", "#e49b34", "#9570b6"]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(np.arange(-0.5, 5.5), cmap.N)
    fig, ax = plt.subplots(figsize=(13.5, 8.3), constrained_layout=True)
    ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap=cmap, norm=norm)
    ax.set_xticks(range(len(CAPTURE_COLUMNS)), CAPTURE_COLUMNS, fontsize=10)
    ax.set_yticks(range(len(labels)), labels, fontsize=9)
    ax.tick_params(axis="both", length=0)
    ax.axhline(5.5, color="#526174", linewidth=1.5)
    ax.set_title("Pilot lead: saved measurements by condition", fontsize=15, pad=22)
    ax.set_xlabel("Measurement stored in the immutable bundle", labelpad=13)
    ax.set_ylabel("Execution order · task · condition", labelpad=11)
    ax.set_xticks(np.arange(-0.5, matrix.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, matrix.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.8)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.legend(
        handles=[
            Patch(color=colors[0], label="Not applicable / not saved"),
            Patch(color=colors[1], label="Residual state"),
            Patch(color=colors[2], label="Attention aggregate"),
            Patch(color=colors[3], label="Actual-prefix score"),
            Patch(color=colors[4], label="Fixed-prefix score"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        frameon=False,
        fontsize=9,
    )
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_distance(
    distance: np.ndarray, offsets: list[int], markers: dict[str, int], output: Path
) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 7), constrained_layout=True)
    image = ax.imshow(distance, aspect="auto", interpolation="nearest", cmap="viridis")
    ax.set_title("First IPI condition: residual-state distance from Tpre", fontsize=15, pad=20)
    ax.set_xlabel("Token offset from Tpre in the same actual prefix", labelpad=10)
    ax.set_ylabel("Transformer layer", labelpad=10)
    xticks = sorted(set([0, *range(0, len(offsets), 5), len(offsets) - 1]))
    ax.set_xticks(xticks, [str(offsets[i]) for i in xticks])
    ax.set_yticks(range(0, distance.shape[0], 5))
    for name, position in markers.items():
        if name == "Tpre":
            continue
        index = offsets.index(position - markers["Tpre"])
        ax.axvline(index, color="white", linestyle="--", linewidth=1.2, alpha=0.9)
        ax.text(index + 0.5, 0.3, name, color="white", rotation=90, va="top", fontsize=9)
    fig.colorbar(image, ax=ax, label="1 − cosine similarity to Tpre (same layer)", shrink=0.9)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    stage = read_json(args.stage_dir / "stage.json")
    if stage["stage"] != "lead" or len(stage["run_paths"]) != 18:
        raise ValueError("Expected the frozen 18-condition lead stage")
    repo_root = args.stage_dir.resolve().parents[2]
    rows, labels = [], []
    selected = None
    for order, relative_path in enumerate(stage["run_paths"], start=1):
        run_dir = repo_root / "artifacts" / relative_path
        manifest = read_json(run_dir / "manifest.json")
        run = read_json(require_artifact(run_dir, manifest, "run.json"))
        condition = read_json(require_artifact(run_dir, manifest, "condition.json"))
        if run["status"] != "completed" or run["condition_id"] != condition["condition_id"]:
            raise ValueError(f"Incomplete or misaligned run: {run_dir}")
        if stage["conditions"][order - 1]["condition_id"] != run["condition_id"]:
            raise ValueError(f"Stage order mismatch: {run_dir}")
        manifest_paths = set()
        for artifact in manifest["artifacts"]:
            path = artifact["relative_path"]
            if path.endswith(("/residual.safetensors", "/attention.json", "/scores.json")):
                require_artifact(run_dir, manifest, path)
                manifest_paths.add(path)
        rows.append(capture_row(run, manifest_paths))
        task = condition["user_task_id"].removeprefix("user_task_")
        labels.append(f"{order:02d}   task {task:<2}   {condition['condition_family'].upper()}")
        if selected is None and condition["condition_family"] == "ipi":
            selected = (run_dir, manifest, run)
    matrix = np.stack(rows)
    if selected is None:
        raise ValueError("No IPI condition found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    render_coverage(matrix, labels, args.output_dir / "pilot_lead_capture_coverage.png")

    run_dir, manifest, run = selected
    measurements = [
        item
        for item in run["measurements"]
        if item["scope"] == "actual" and item["positions"]["exposed"]
    ]
    if len(measurements) != 1:
        raise ValueError("Expected one exposed actual-prefix measurement")
    measurement = measurements[0]
    if not measurement["prefix_token_identity"]:
        raise ValueError("Prefix token identity check failed")
    index = measurement["index"]
    metadata = read_json(
        require_artifact(run_dir, manifest, f"measurements/{index}/activation.json")
    )
    tensor_path = require_artifact(run_dir, manifest, f"measurements/{index}/residual.safetensors")
    if metadata["prefix_id"] != measurement["prefix_id"]:
        raise ValueError("Activation prefix ID mismatch")
    markers = {item["name"]: item["token_index"] for item in measurement["positions"]["positions"]}
    for item in measurement["positions"]["positions"]:
        if metadata["token_ids"][item["token_index"]] != item["token_id"]:
            raise ValueError(f"Token ID mismatch at {item['name']}")
    layer_keys = sorted(metadata["layers"], key=lambda key: int(key.rsplit(".", 1)[1]))
    with safe_open(str(tensor_path), framework="pt", device="cpu") as tensors:
        states = np.stack(
            [tensors.get_tensor(key)[0].to(torch.float32).numpy() for key in layer_keys]
        )
    distance, offsets = cosine_distance_matrix(states, metadata["positions"], markers["Tpre"])
    for name in ("Tpost", "Tend_tool", "Tend_assistant"):
        if markers[name] - markers["Tpre"] not in offsets:
            raise ValueError(f"Missing selected position: {name}")
    render_distance(
        distance, offsets, markers, args.output_dir / "pilot_lead_residual_distance.png"
    )
    print(
        json.dumps(
            {
                "run_count": len(rows),
                "ipi_count": sum(label.endswith("IPI") for label in labels),
                "coverage_counts": (matrix != 0).sum(axis=0).tolist(),
                "figure2_run_id": run["run_id"],
                "figure2_prefix_id": measurement["prefix_id"],
                "figure2_layers": len(layer_keys),
                "figure2_offsets": [offsets[0], offsets[-1]],
                "figure2_distance_range": [float(distance.min()), float(distance.max())],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
