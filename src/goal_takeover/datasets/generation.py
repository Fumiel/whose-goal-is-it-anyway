"""Deterministic identifiers for generated experimental conditions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def stable_condition_id(payload: Mapping[str, Any], *, prefix: str = "cond") -> str:
    """Hash canonical JSON so the same declared condition gets the same ID."""

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
