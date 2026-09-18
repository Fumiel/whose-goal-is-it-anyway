import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from goal_takeover.storage.run_writer import ImmutableRunWriter


class RunWriterTest(unittest.TestCase):
    def test_writer_publishes_checksums_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with ImmutableRunWriter(root, "run-001") as writer:
                writer.write_json("resolved_config.json", {"seed": 0}, kind="config")
                path = writer.commit()

            content = (path / "resolved_config.json").read_bytes()
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            record = manifest["artifacts"][0]
            self.assertEqual(record["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(record["relative_path"], "resolved_config.json")

            with self.assertRaises(FileExistsError):
                with ImmutableRunWriter(root, "run-001"):
                    pass

    def test_unsafe_relative_artifact_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with ImmutableRunWriter(temporary_directory, "run-002") as writer:
                with self.assertRaises(ValueError):
                    writer.write_bytes("../escape.bin", b"x", kind="test")


if __name__ == "__main__":
    unittest.main()
