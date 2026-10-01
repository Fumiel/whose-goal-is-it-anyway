import unittest
from importlib.util import find_spec
from types import SimpleNamespace

from goal_takeover.pilot.attention import QwenAttentionCapture, QwenQueryAttentionCapture


class HookModule:
    def __init__(self):
        self.hooks = []

    def register_forward_hook(self, hook):
        self.hooks.append(hook)
        return SimpleNamespace(remove=lambda: self.hooks.remove(hook))

    def forward(self, output):
        for hook in self.hooks:
            output = hook(self, (), output)
        return output


class PilotAttentionTest(unittest.TestCase):
    @unittest.skipUnless(find_spec("torch") and find_spec("transformers"), "research dependencies")
    def test_query_only_matches_eager_all_heads_without_changing_sdpa_output(self):
        import torch
        from transformers import Qwen3Config, Qwen3ForCausalLM

        torch.manual_seed(7)
        config = Qwen3Config(
            vocab_size=128,
            hidden_size=64,
            intermediate_size=128,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=16,
        )
        model = Qwen3ForCausalLM(config).eval()
        ids = torch.tensor([[1, 12, 32, 5, 17, 2]])
        names = ("model.layers.0", "model.layers.1")
        model.set_attn_implementation("sdpa")
        observed = {}
        with (
            torch.no_grad(),
            QwenQueryAttentionCapture(
                model,
                names,
                lambda name, weights: observed.setdefault(name, weights.detach().clone()),
            ) as capture,
        ):
            sdpa_output = model(input_ids=ids, use_cache=False).logits
        capture.assert_complete()
        model.set_attn_implementation("eager")
        eager = {}
        with (
            torch.no_grad(),
            QwenAttentionCapture(
                model, names, lambda name, weights: eager.setdefault(name, weights.detach().clone())
            ) as capture,
        ):
            eager_output = model(input_ids=ids, use_cache=False, output_attentions=True).logits
        capture.assert_complete()
        self.assertEqual(set(observed), set(eager))
        for name in observed:
            torch.testing.assert_close(
                observed[name], eager[name][0, :, -1, :], atol=1e-5, rtol=1e-5
            )
        torch.testing.assert_close(sdpa_output, eager_output, atol=1e-5, rtol=1e-5)

    def test_weights_released_after_reduction_and_attention_output_preserved(self):
        modules = {"layers.0.self_attn": HookModule(), "layers.1.self_attn": HookModule()}
        model = SimpleNamespace(named_modules=lambda: modules.items())
        consumed = []
        with QwenAttentionCapture(
            model, ("layers.0", "layers.1"), lambda name, weights: consumed.append((name, weights))
        ) as capture:
            for module in modules.values():
                result = object()
                weights = object()
                actual = module.forward((result, weights))
                self.assertIs(actual[0], result)
                self.assertIsNone(actual[1])
            capture.assert_complete()
        self.assertEqual(len(consumed), 2)
        self.assertTrue(all(not module.hooks for module in modules.values()))

    def test_unavailable_weights_fail_and_hooks_are_removed(self):
        module = HookModule()
        model = SimpleNamespace(named_modules=lambda: [("layers.0.self_attn", module)])
        with self.assertRaisesRegex(ValueError, "unverified"):
            with QwenAttentionCapture(model, ("layers.0",), lambda *_: None):
                module.forward((object(), None))
        self.assertEqual(module.hooks, [])
        with QwenAttentionCapture(model, ("layers.0",), lambda *_: None) as capture:
            with self.assertRaisesRegex(ValueError, "missing"):
                capture.assert_complete()


if __name__ == "__main__":
    unittest.main()
