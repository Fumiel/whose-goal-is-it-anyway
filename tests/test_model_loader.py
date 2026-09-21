import unittest

from goal_takeover.models.loader import load_hugging_face_model


class ModelLoaderTest(unittest.TestCase):
    def test_revisions_must_be_immutable_and_explicit(self) -> None:
        with self.assertRaises(ValueError):
            load_hugging_face_model("model", revision=None, tokenizer_revision=None)

    def test_only_declared_quantization_mode_is_accepted(self) -> None:
        with self.assertRaises(ValueError):
            load_hugging_face_model(
                "model",
                revision="abc",
                tokenizer_revision="abc",
                quantization="int4",
            )


if __name__ == "__main__":
    unittest.main()
