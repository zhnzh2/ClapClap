"""Production inference guardrails for future ClapClap 1.0 AI models.

This module deliberately does not train models. It only validates deployable
model manifests and provides a safe fallback path to heuristic AI when no model
is available or the manifest does not match the current rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import random
from typing import Optional

from app.ai_env import validate_model_metadata
from app.v1.constants import Move
from app.v1.models import GameState

DEFAULT_MODEL_DIR = Path("models/ai/v1/deploy")


@dataclass(frozen=True)
class ModelRuntimeStatus:
    available: bool
    policy_type: str
    model_version: str | None = None
    reason: str | None = None
    manifest_path: str | None = None
    inference_adapter: str | None = None
    inference_timeout_ms: int = 100

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "policy_type": self.policy_type,
            "model_version": self.model_version,
            "reason": self.reason,
            "manifest_path": self.manifest_path,
            "inference_adapter": self.inference_adapter,
            "inference_timeout_ms": self.inference_timeout_ms,
        }


def _model_dir_from_env() -> Path:
    configured = os.environ.get("CLAPCLAP_AI_MODEL_DIR")
    return Path(configured) if configured else DEFAULT_MODEL_DIR


@lru_cache(maxsize=1)
def get_model_status() -> ModelRuntimeStatus:
    """Validate the deployable model manifest once per process."""
    manifest_path = _model_dir_from_env() / "manifest.json"
    if not manifest_path.exists():
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            reason="model_manifest_missing",
            manifest_path=str(manifest_path),
            inference_timeout_ms=_inference_timeout_ms(),
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            reason=f"model_manifest_unreadable:{exc.__class__.__name__}",
            manifest_path=str(manifest_path),
            inference_timeout_ms=_inference_timeout_ms(),
        )

    env_metadata = manifest.get("env_metadata")
    if not isinstance(env_metadata, dict) or not validate_model_metadata(env_metadata):
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            reason="model_metadata_mismatch",
            manifest_path=str(manifest_path),
            inference_timeout_ms=_inference_timeout_ms(),
        )

    weights_path = manifest.get("weights_path")
    if not isinstance(weights_path, str) or not (_model_dir_from_env() / weights_path).exists():
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_version=manifest.get("model_version"),
            reason="model_weights_missing",
            manifest_path=str(manifest_path),
            inference_adapter=manifest.get("inference_adapter"),
            inference_timeout_ms=_inference_timeout_ms(),
        )

    adapter = manifest.get("inference_adapter")
    if adapter != "sb3_maskable_ppo_v1":
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_version=manifest.get("model_version"),
            reason="model_inference_adapter_unimplemented",
            manifest_path=str(manifest_path),
            inference_adapter=adapter,
            inference_timeout_ms=_inference_timeout_ms(),
        )

    return ModelRuntimeStatus(
        available=False,
        policy_type="heuristic_fallback",
        model_version=manifest.get("model_version"),
        reason="model_inference_adapter_unimplemented",
        manifest_path=str(manifest_path),
        inference_adapter=adapter,
        inference_timeout_ms=_inference_timeout_ms(),
    )


def _inference_timeout_ms() -> int:
    raw = os.environ.get("CLAPCLAP_AI_INFERENCE_TIMEOUT_MS", "100")
    try:
        value = int(raw)
    except ValueError:
        return 100
    return max(1, value)


def policy_type_for_difficulty(difficulty: str) -> str:
    if difficulty == "easy":
        return "random"
    if difficulty == "hard":
        return get_model_status().policy_type
    return "heuristic"


def model_version_for_difficulty(difficulty: str) -> str | None:
    if difficulty != "hard":
        return None
    return get_model_status().model_version


def model_status_for_difficulty(difficulty: str) -> dict | None:
    if difficulty != "hard":
        return None
    return get_model_status().to_dict()


def select_model_move(
    state: GameState,
    controlled_player: int,
    rng: random.Random,
) -> Optional[Move]:
    """Return a model move when a production model is available.

    Real inference is intentionally not implemented yet. Until a validated model
    and inference adapter exist, callers must fall back to heuristic selection.
    """
    status = get_model_status()
    if not status.available:
        return None

    # Future hook: encode observation, apply action mask, run model with timeout.
    return None


def clear_model_status_cache() -> None:
    get_model_status.cache_clear()
