"""Atomic writer for immutable raw run directories."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


class ImmutableRunWriter:
    """Write into a temporary directory and atomically publish one new run."""

    def __init__(self, artifact_root: str | Path, run_id: str) -> None:
        if not _RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("run_id contains unsafe characters or is too long")
        self.run_id = run_id
        self.runs_root = Path(artifact_root) / "runs"
        self.final_path = self.runs_root / run_id
        self._temporary_path = self.runs_root / f".{run_id}.tmp-{uuid.uuid4().hex}"
        self._committed = False
        self._written: dict[str, dict[str, Any]] = {}

    def __enter__(self) -> ImmutableRunWriter:
        self.runs_root.mkdir(parents=True, exist_ok=True)
        if self.final_path.exists():
            raise FileExistsError(f"immutable run already exists: {self.final_path}")
        self._temporary_path.mkdir()
        return self

    def _resolve_relative(self, relative_path: str) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("artifact path must be a safe relative path")
        target = self._temporary_path / relative
        if target.exists():
            raise FileExistsError(f"artifact already written: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_bytes(self, relative_path: str, content: bytes, *, kind: str) -> dict[str, Any]:
        target = self._resolve_relative(relative_path)
        target.write_bytes(content)
        record = {
            "artifact_id": f"{self.run_id}:{relative_path}",
            "run_id": self.run_id,
            "kind": kind,
            "relative_path": relative_path,
            "external_uri": None,
            "sha256": sha256_bytes(content),
            "bytes": len(content),
            "shape": None,
            "dtype": None,
        }
        self._written[relative_path] = record
        return dict(record)

    def write_json(self, relative_path: str, value: Any, *, kind: str) -> dict[str, Any]:
        return self.write_bytes(relative_path, canonical_json_bytes(value), kind=kind)

    def commit(self) -> Path:
        if self._committed:
            raise RuntimeError("run writer has already been committed")
        if self.final_path.exists():
            raise FileExistsError(f"immutable run already exists: {self.final_path}")
        manifest = {
            "schema_version": 1,
            "run_id": self.run_id,
            "artifacts": [self._written[key] for key in sorted(self._written)],
        }
        manifest_path = self._temporary_path / "manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        os.rename(self._temporary_path, self.final_path)
        self._committed = True
        return self.final_path

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self._committed and self._temporary_path.exists():
            shutil.rmtree(self._temporary_path)
