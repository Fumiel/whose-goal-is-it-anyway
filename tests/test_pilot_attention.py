import unittest
from types import SimpleNamespace

from goal_takeover.pilot.attention import QwenAttentionCapture


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
