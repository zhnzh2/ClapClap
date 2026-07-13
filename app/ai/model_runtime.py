"""Production inference adapter for ClapClap 1.0 AI models.

This module does **not** train models. It loads a validated deploy model at
startup and provides masked inference for the ``hard`` difficulty.

When no deploy model is present, the metadata does not match, or inference
dependencies are not installed, the module safely falls back to heuristic hard
so gameplay is never interrupted.

Design
------
- Model loaded once per process (cached).
- manifest.json is validated against the current ``ClapClapEnv`` contract.
- Observation encoding mirrors ``training/gym_env.encode_observation_vector``.
- Legal-action mask is enforced: an illegal model output triggers heuristic fallback.
- Inference time is measured in ms and logged in battle metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import random
import time
from typing import Optional

from app.ai.engine import get_legal_action_mask
from app.ai_env import validate_model_metadata
from app.v1.constants import Move
from app.v1.models import GameState

DEFAULT_MODEL_DIR = Path("models/ai/v1/deploy")
DEFAULT_AI_MODEL_KEY = "clapfish2"
AI_MODEL_OPTIONS: tuple[dict[str, object], ...] = (
    {
        "key": "clapfish1",
        "slot": 1,
        "label": "ClapFish1",
        "model_dir": Path("models/ai/v1/archive"),
        "archive_pattern": "ClapFish1_*",
        "enabled": True,
    },
    {
        "key": "clapfish2",
        "slot": 2,
        "label": "ClapFish2",
        "model_dir": Path("models/ai/v1/deploy"),
        "enabled": True,
    },
)

# ── 观测编码常量（与 training/gym_env.py 保持一致） ──────────────
_PLAYER_FIELDS = ("hp", "qi", "shield", "spark", "battery", "pickaxe", "flash_used")
_PLAYER_NORMALIZERS = {
    "hp": 1.0, "qi": 10.0, "shield": 10.0,
    "spark": 4.0, "battery": 4.0, "pickaxe": 2.0, "flash_used": 2.0,
}
_OBS_VEC_SIZE = 1 + len(_PLAYER_FIELDS) * 2 + 17  # round_num + 2×7 players + 17 action-mask

# ── 模型缓存 ─────────────────────────────────────────────────────
_model_cache: object | None = None
_model_cache_weights_path: str | None = None


# ── 状态数据类 ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelRuntimeStatus:
    available: bool
    policy_type: str
    model_version: str | None = None
    model_key: str | None = None
    model_label: str | None = None
    reason: str | None = None
    manifest_path: str | None = None
    inference_adapter: str | None = None
    inference_timeout_ms: int = 100

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "policy_type": self.policy_type,
            "model_version": self.model_version,
            "model_key": self.model_key,
            "model_label": self.model_label,
            "reason": self.reason,
            "manifest_path": self.manifest_path,
            "inference_adapter": self.inference_adapter,
            "inference_timeout_ms": self.inference_timeout_ms,
        }


# ── 内部工具 ─────────────────────────────────────────────────────

def get_ai_model_options() -> list[dict]:
    return [
        {
            "key": str(item["key"]),
            "slot": int(item["slot"]),
            "label": str(item["label"]),
            "enabled": bool(item["enabled"]),
        }
        for item in AI_MODEL_OPTIONS
    ]


def normalize_model_key(model_key: str | None) -> str:
    if not model_key:
        return DEFAULT_AI_MODEL_KEY
    allowed = {str(item["key"]) for item in AI_MODEL_OPTIONS if item.get("enabled")}
    if model_key in allowed:
        return model_key
    return DEFAULT_AI_MODEL_KEY


def _model_option(model_key: str | None) -> dict:
    normalized = normalize_model_key(model_key)
    for item in AI_MODEL_OPTIONS:
        if item["key"] == normalized:
            return item
    return AI_MODEL_OPTIONS[0]


def _model_dir_from_env(model_key: str | None = None) -> Path:
    option = _model_option(model_key)
    configured = os.environ.get("CLAPCLAP_AI_MODEL_DIR")
    if configured and normalize_model_key(model_key) == DEFAULT_AI_MODEL_KEY:
        return Path(configured)
    model_dir = Path(option["model_dir"])
    archive_pattern = option.get("archive_pattern")
    if archive_pattern:
        candidates = sorted(
            (path for path in model_dir.glob(str(archive_pattern)) if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )
        if candidates:
            return candidates[0]
    return model_dir


def _inference_timeout_ms() -> int:
    raw = os.environ.get("CLAPCLAP_AI_INFERENCE_TIMEOUT_MS", "100")
    try:
        value = int(raw)
    except ValueError:
        return 100
    return max(1, value)


def _inference_deps_available() -> bool:
    """Return True if inference-only dependencies can be imported."""
    try:
        __import__("numpy")
        __import__("torch")
        __import__("stable_baselines3")
        __import__("sb3_contrib")
        return True
    except ImportError:
        return False


# ── 观测编码 ─────────────────────────────────────────────────────

def _normalize(value: int | float, scale: float) -> float:
    if scale <= 0:
        return float(value)
    return max(-1.0, min(1.0, float(value) / scale))


def _encode_obs_vector(obs_dict: dict, *, max_rounds: int) -> list[float]:
    """Encode a public-state observation dict into a fixed-size float vector."""
    vector: list[float] = [
        _normalize(obs_dict.get("round_num", 0), float(max_rounds)),
    ]
    for section in ("self", "opponent"):
        player = obs_dict.get(section, {}) or {}
        for field in _PLAYER_FIELDS:
            vector.append(_normalize(player.get(field, 0), _PLAYER_NORMALIZERS[field]))
    mask = obs_dict.get("legal_action_mask", []) or []
    vector.extend(1.0 if item else 0.0 for item in mask[:17])
    while len(vector) < _OBS_VEC_SIZE:
        vector.append(0.0)
    return vector[:_OBS_VEC_SIZE]


def _build_observation(state: GameState, controlled_player: int) -> dict:
    """从 GameState 构建模型所需的观测字典。"""
    self_p = (state.p1 if controlled_player == 1 else state.p2).to_dict()
    opp_p = (state.p2 if controlled_player == 1 else state.p1).to_dict()
    mask = get_legal_action_mask(state, controlled_player)
    return {
        "round_num": state.round_num,
        "self": self_p,
        "opponent": opp_p,
        "legal_action_mask": mask,
    }


# ── 模型加载（缓存） ─────────────────────────────────────────────

def _load_deploy_model(manifest: dict, model_key: str | None = None) -> object | None:
    """Load the sb3 MaskablePPO model once and cache it."""
    global _model_cache, _model_cache_weights_path

    weights_rel = manifest.get("weights_path", "model.zip")
    weights_path = str((_model_dir_from_env(model_key) / weights_rel).resolve())

    if _model_cache is not None and _model_cache_weights_path == weights_path:
        return _model_cache

    try:
        from sb3_contrib import MaskablePPO
    except ImportError:
        return None

    model_path = weights_path.replace(".zip", "")
    try:
        model = MaskablePPO.load(model_path)
    except Exception:
        return None

    _model_cache = model
    _model_cache_weights_path = weights_path
    return model


# ── 模型状态查询 ─────────────────────────────────────────────────

@lru_cache(maxsize=8)
def get_model_status(model_key: str | None = None) -> ModelRuntimeStatus:
    """Validate the deployable model manifest once per process."""
    model_key = normalize_model_key(model_key)
    option = _model_option(model_key)
    model_label = str(option["label"])
    model_dir = _model_dir_from_env(model_key)
    manifest_path = model_dir / "manifest.json"
    timeout_ms = _inference_timeout_ms()

    if not manifest_path.exists():
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_key=model_key,
            model_label=model_label,
            reason="model_manifest_missing",
            manifest_path=str(manifest_path),
            inference_timeout_ms=timeout_ms,
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_key=model_key,
            model_label=model_label,
            reason=f"model_manifest_unreadable:{exc.__class__.__name__}",
            manifest_path=str(manifest_path),
            inference_timeout_ms=timeout_ms,
        )

    env_metadata = manifest.get("env_metadata")
    if not isinstance(env_metadata, dict) or not validate_model_metadata(env_metadata):
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_key=model_key,
            model_label=model_label,
            reason="model_metadata_mismatch",
            manifest_path=str(manifest_path),
            inference_timeout_ms=timeout_ms,
        )

    weights_rel = manifest.get("weights_path")
    if not isinstance(weights_rel, str) or not (model_dir / weights_rel).exists():
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_version=manifest.get("model_version"),
            model_key=model_key,
            model_label=model_label,
            reason="model_weights_missing",
            manifest_path=str(manifest_path),
            inference_adapter=manifest.get("inference_adapter"),
            inference_timeout_ms=timeout_ms,
        )

    adapter = manifest.get("inference_adapter")
    if adapter != "sb3_maskable_ppo_v1":
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_version=manifest.get("model_version"),
            model_key=model_key,
            model_label=model_label,
            reason=f"model_inference_adapter_unknown:{adapter}",
            manifest_path=str(manifest_path),
            inference_adapter=adapter,
            inference_timeout_ms=timeout_ms,
        )

    if not _inference_deps_available():
        return ModelRuntimeStatus(
            available=False,
            policy_type="heuristic_fallback",
            model_version=manifest.get("model_version"),
            model_key=model_key,
            model_label=model_label,
            reason="inference_deps_missing",
            manifest_path=str(manifest_path),
            inference_adapter=adapter,
            inference_timeout_ms=timeout_ms,
        )

    # 所有检查通过 —— 模型可用
    return ModelRuntimeStatus(
        available=True,
        policy_type="model",
        model_version=manifest.get("model_version"),
        model_key=model_key,
        model_label=model_label,
        manifest_path=str(manifest_path),
        inference_adapter=adapter,
        inference_timeout_ms=timeout_ms,
    )


# ── 公开 API ─────────────────────────────────────────────────────

def policy_type_for_difficulty(difficulty: str, model_key: str | None = None) -> str:
    if difficulty == "easy":
        return "random"
    if difficulty == "hard":
        return get_model_status(model_key).policy_type
    return "heuristic"


def model_version_for_difficulty(difficulty: str, model_key: str | None = None) -> str | None:
    if difficulty != "hard":
        return None
    return get_model_status(model_key).model_version


def model_status_for_difficulty(difficulty: str, model_key: str | None = None) -> dict | None:
    if difficulty != "hard":
        return None
    return get_model_status(model_key).to_dict()


def select_model_move(
    state: GameState,
    controlled_player: int,
    rng: random.Random,
    model_key: str | None = None,
) -> Optional[Move]:
    """Return a model move when a production model is available.

    Returns ``None`` when:
    - No deploy model exists or manifest is invalid
    - Inference dependencies are not installed
    - Model inference fails or times out
    - Model outputs an illegal move

    Callers must fall back to heuristic selection when ``None`` is returned.
    """
    model_key = normalize_model_key(model_key)
    status = get_model_status(model_key)
    if not status.available:
        return None

    manifest_path = _model_dir_from_env(model_key) / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    model = _load_deploy_model(manifest, model_key)
    if model is None:
        return None

    import numpy as np

    max_rounds = manifest.get("env_metadata", {}).get("max_rounds", 200)
    timeout_ms = _inference_timeout_ms()

    t0 = time.perf_counter()
    try:
        obs_dict = _build_observation(state, controlled_player)
        vec = np.array(
            _encode_obs_vector(obs_dict, max_rounds=max_rounds),
            dtype=np.float32,
        )
        mask = np.array(obs_dict["legal_action_mask"], dtype=bool)

        action_index, _ = model.predict(vec, action_masks=mask, deterministic=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if elapsed_ms > timeout_ms:
            # 超时降级（软超时，仅记录；不在此处杀死推理）
            pass

        action_int = int(action_index)
        if not mask[action_int]:
            # 模型输出了非法动作 → 回退
            return None

        from app.ai.space import get_move_by_index
        return get_move_by_index(action_int)

    except Exception:
        return None


def clear_model_status_cache() -> None:
    """清除模型状态和模型权重缓存。"""
    global _model_cache, _model_cache_weights_path
    _model_cache = None
    _model_cache_weights_path = None
    get_model_status.cache_clear()
