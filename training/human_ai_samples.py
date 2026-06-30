"""Utilities for collecting human-vs-AI samples exported from the web UI.

The exported ZIP contains ``training/ai_battle_samples.jsonl``.  These samples
are not a replacement for self-play PPO, but they are useful for later behavior
cloning, evaluation sets, and opening-book analysis.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Iterable

SAMPLE_PATH_IN_ZIP = "training/ai_battle_samples.jsonl"
DEFAULT_OUTPUT = Path("training/data/human_ai_samples.jsonl")


def _sample_key(sample: dict) -> tuple:
    return (
        sample.get("battle_id"),
        sample.get("round_num"),
        sample.get("human_seat"),
        sample.get("ai_seat"),
        sample.get("human_move"),
        sample.get("ai_move"),
    )


def _iter_jsonl_lines(text: str) -> Iterable[dict]:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        if isinstance(data, dict):
            yield data


def iter_samples_from_path(path: Path) -> Iterable[dict]:
    """Yield exported AI training samples from a ZIP or JSONL file."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as archive:
            if SAMPLE_PATH_IN_ZIP not in archive.namelist():
                return
            text = archive.read(SAMPLE_PATH_IN_ZIP).decode("utf-8")
            yield from _iter_jsonl_lines(text)
        return

    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        yield from _iter_jsonl_lines(path.read_text(encoding="utf-8"))


def collect_samples(inputs: Iterable[Path]) -> list[dict]:
    """Collect and de-duplicate samples while preserving first-seen order."""
    seen: set[tuple] = set()
    samples: list[dict] = []
    for input_path in inputs:
        for sample in iter_samples_from_path(input_path):
            key = _sample_key(sample)
            if key in seen:
                continue
            seen.add(key)
            samples.append(sample)
    return samples


def write_samples(samples: Iterable[dict], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8", newline="\n") as fh:
        for sample in samples:
            fh.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")))
            fh.write("\n")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge exported ClapClap human-vs-AI training samples."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Export ZIP or JSONL files.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSONL path. Default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    samples = collect_samples(args.inputs)
    count = write_samples(samples, args.output)
    print(f"wrote {count} samples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
