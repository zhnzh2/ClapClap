"""Offline training entrypoint skeleton for ClapClap 1.0 AI.

The production web app must not import or run this module. It is intentionally
kept under training/ and only imports heavyweight RL dependencies when a real
training run is requested.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_env import ClapClapEnv, validate_model_metadata


def build_training_manifest(args: argparse.Namespace) -> dict:
    env = ClapClapEnv(
        ai_player=1,
        max_rounds=args.max_rounds,
        history_window=args.history_window,
        seed=args.seed,
    )
    metadata = env.metadata()
    return {
        "manifest_version": "clapclap-ai-model-manifest-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "MaskablePPO",
        "model_version": args.model_version,
        "inference_adapter": "sb3_maskable_ppo_v1",
        "status": "dry_run" if args.dry_run else "training_requested",
        "env_metadata": metadata,
        "training": {
            "seed": args.seed,
            "total_timesteps": args.total_timesteps,
            "opponent_pool": ["random"],
            "seat_randomization": True,
            "max_rounds": args.max_rounds,
            "history_window": args.history_window,
        },
        "evaluation": {
            "required_command": (
                "python scripts/evaluate_ai.py --matrix --games 500 "
                "--seed 20260630 --max-rounds 120 --summary"
            )
        },
    }


def _ensure_training_dependencies_available() -> None:
    missing: list[str] = []
    for package in ("gymnasium", "torch", "stable_baselines3", "sb3_contrib"):
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        raise SystemExit(
            "Training dependencies are not installed: "
            + ", ".join(missing)
            + ". Install with: pip install -r requirements-train.txt"
        )


def write_manifest(output_dir: Path, manifest: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "manifest.json"
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ClapClap 1.0 AI with Maskable PPO.")
    parser.add_argument("--output-dir", type=Path, default=Path("models/ai/v1/dev"))
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--total-timesteps", type=int, default=100_000)
    parser.add_argument("--model-version", default="dev")
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--history-window", type=int, default=4)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only write the model manifest and validate metadata; do not train.",
    )
    args = parser.parse_args()

    if args.total_timesteps <= 0:
        raise SystemExit("--total-timesteps must be greater than 0")
    if args.max_rounds <= 0:
        raise SystemExit("--max-rounds must be greater than 0")
    if args.history_window < 0:
        raise SystemExit("--history-window cannot be negative")

    manifest = build_training_manifest(args)
    if not validate_model_metadata(manifest["env_metadata"]):
        raise SystemExit("Generated env metadata does not match current ClapClapEnv contract.")

    path = write_manifest(args.output_dir, manifest)

    if args.dry_run:
        print(f"dry-run manifest written: {path}")
        return

    _ensure_training_dependencies_available()
    raise SystemExit(
        "Real MaskablePPO training is not implemented yet. "
        "The environment contract and manifest are ready; implement the Gymnasium wrapper next."
    )


if __name__ == "__main__":
    main()
