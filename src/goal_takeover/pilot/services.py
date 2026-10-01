"""GPU services, kept lazy so all orchestration tests can run without weights."""

from __future__ import annotations

from typing import Any

from goal_takeover.instrumentation.huggingface import HuggingFaceActivationExtractor
from goal_takeover.models.scoring import HuggingFaceTeacherForcedScorer
from goal_takeover.pilot.attention import QwenAttentionCapture
from goal_takeover.pilot.measurement import score_slots, validate_activation
from goal_takeover.pilot.plan import PilotPlan
from goal_takeover.pilot.preflight import create_session
from goal_takeover.runtime import (
    assert_model_has_no_cpu_offload,
    gpu_runtime_report,
    package_version,
)
from goal_takeover.selection import _load_model
from goal_takeover.shakedown import _make_backend, _save_activations


class HuggingFacePilotServices:
    """One evaluation model for generation, residuals, attention and scoring."""

    def __init__(self, plan: PilotPlan, runtime: dict[str, Any]) -> None:
        import torch

        self.torch = torch
        self.plan = plan
        self.runtime = runtime
        self.runtime_report = gpu_runtime_report()
        self.runtime_report["versions"] = {
            name: package_version(name)
            for name in (
                "agentdojo",
                "torch",
                "transformers",
                "accelerate",
                "bitsandbytes",
                "safetensors",
            )
        }
        torch.manual_seed(plan.config["experiment"]["seed"])
        torch.cuda.manual_seed_all(plan.config["experiment"]["seed"])
        self.model, self.tokenizer = _load_model(plan.model_config["model"])
        assert_model_has_no_cpu_offload(self.model)
        self.extractor = HuggingFaceActivationExtractor(
            self.model,
            block_path=plan.model_config["instrumentation"]["transformer_block_path"],
        )
        self.scorer = HuggingFaceTeacherForcedScorer(self.model, self.tokenizer)
        self.check_memory()

    def session(self, condition: dict[str, Any]) -> Any:
        return create_session(self.plan, condition)

    def backend(self, session: Any) -> Any:
        backend = _make_backend(
            model=self.model,
            tokenizer=self.tokenizer,
            session=session,
            model_config=self.plan.model_config,
            decoding=self.plan.config["decoding"],
        )
        if backend.template_sha256 != self.runtime["chat_template_sha256"]:
            raise ValueError("runtime chat template checksum mismatch")
        return backend

    def start_condition(self) -> None:
        self.torch.cuda.empty_cache()
        self.torch.cuda.reset_peak_memory_stats()

    def check_memory(self) -> int:
        peak = max(
            int(self.torch.cuda.max_memory_allocated()), int(self.torch.cuda.max_memory_reserved())
        )
        if peak > self.plan.config["resources"]["maximum_gpu_memory_gib"] * 2**30:
            raise RuntimeError("oom_or_resource_limit: peak GPU memory exceeds frozen ceiling")
        return peak

    def activation_bytes(self, record: Any) -> bytes:
        return _save_activations(record.values)

    def capture(
        self,
        prefix: Any,
        positions: tuple[int, ...],
        ranges: dict[str, tuple[int, ...]],
        *,
        full_attention: bool,
    ) -> tuple[Any, dict[str, Any], bytes | None]:
        record = self.extractor.capture(prefix, positions=positions)
        validate_activation(record, prefix, positions, self.extractor.module_names)
        self.check_memory()
        torch = self.torch
        device = next(self.model.parameters()).device
        ids = torch.tensor([prefix.token_ids], dtype=torch.long, device=device)
        metadata: dict[str, Any] = {
            "prefix_id": prefix.prefix_id,
            "prefix_token_ids": list(prefix.token_ids),
            "query_token_index": len(prefix.token_ids) - 1,
            "query_token_id": prefix.token_ids[-1],
            "aggregation": "sum_and_mean",
            "execution": "output_attentions_true_reduce_and_release_each_qwen_layer",
            "ranges": {
                name: {"token_indices": list(indices), "length": len(indices)}
                for name, indices in ranges.items()
            },
            "layers": {},
        }
        tensors = {}

        def consume(name: str, value: Any) -> None:
            if (
                value.ndim != 4
                or value.shape[0] != 1
                or tuple(value.shape[-2:]) != (len(prefix.token_ids), len(prefix.token_ids))
                or not bool(value.isfinite().all())
                or bool((value < 0).any())
            ):
                raise ValueError("attention shape or finite-value check failed")
            query = value[0, :, -1, :].float()
            metadata["layers"][name] = {
                name: {
                    "sum": query[:, list(indices)].sum(dim=-1).cpu().tolist(),
                    "mean": (
                        query[:, list(indices)].mean(dim=-1).cpu().tolist() if indices else None
                    ),
                }
                for name, indices in ranges.items()
            }
            if full_attention:
                tensors[name] = value.detach().cpu().contiguous()
            self.check_memory()

        with (
            torch.no_grad(),
            QwenAttentionCapture(self.model, self.extractor.module_names, consume) as attention,
        ):
            self.model(
                input_ids=ids,
                attention_mask=torch.ones_like(ids),
                use_cache=False,
                output_attentions=True,
            )
        attention.assert_complete()
        self.check_memory()
        if full_attention:
            from safetensors.torch import save

            full = save(tensors)
        else:
            full = None
        return record, metadata, full

    def score(self, prefix: Any, condition: dict[str, Any]) -> dict[str, Any]:
        result = score_slots(self.scorer, prefix, condition)
        for slot in result["slots"].values():
            for key in ("legitimate", "attack"):
                if (
                    len(prefix.token_ids) + len(slot[key]["token_ids"])
                    > self.plan.model_config["model"]["max_context_tokens"]
                ):
                    raise ValueError("candidate sequence exceeds configured context limit")
        self.check_memory()
        return result
