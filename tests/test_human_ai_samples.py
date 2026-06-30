from __future__ import annotations

import json
import shutil
import unittest
import zipfile
from uuid import uuid4

from app.storage import DATA_DIR
from training.human_ai_samples import collect_samples, write_samples


class TestHumanAiSamples(unittest.TestCase):
    def test_collect_samples_from_export_zip_deduplicates(self):
        sample = {
            "schema": "clapclap-ai-human-battle-sample-v1",
            "battle_id": "20260630000000001",
            "round_num": 1,
            "human_seat": "p1",
            "ai_seat": "p2",
            "human_move": "QI",
            "ai_move": "SHIELD",
        }

        tmp_path = DATA_DIR / "test_human_ai_samples" / uuid4().hex
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            export_path = tmp_path / "export.zip"
            with zipfile.ZipFile(export_path, "w") as archive:
                archive.writestr(
                    "training/ai_battle_samples.jsonl",
                    json.dumps(sample, ensure_ascii=False) + "\n"
                    + json.dumps(sample, ensure_ascii=False) + "\n",
                )

            samples = collect_samples([export_path])
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["battle_id"], sample["battle_id"])

            output = tmp_path / "merged.jsonl"
            count = write_samples(samples, output)
            self.assertEqual(count, 1)
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 1)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
