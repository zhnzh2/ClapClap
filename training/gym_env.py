"""Optional Gymnasium adapter for ClapClap 1.0 AI training.

This module is safe to import without Gymnasium installed. The actual Gym env is
created only through `make_gymnasium_env()`, which checks training dependencies
at call time.
"""

from __future__ import annotations

from typing import Any

from app.ai.space import ACTION_SPACE_SIZE
from app.ai_env import ClapClapEnv

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover - depends on optional training deps
    gym = None
    spaces = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - depends on optional training deps
    np = None


PLAYER_FIELDS = ("hp", "qi", "shield", "spark", "battery", "pickaxe", "flash_used")
PLAYER_NORMALIZERS = {
    "hp": 1.0,
    "qi": 10.0,
    "shield": 10.0,
    "spark": 4.0,
    "battery": 4.0,
    "pickaxe": 2.0,
    "flash_used": 2.0,
}
OBSERVATION_VECTOR_SIZE = 1 + len(PLAYER_FIELDS) * 2 + ACTION_SPACE_SIZE


def _normalize(value: int | float, scale: float) -> float:
    if scale <= 0:
        return float(value)
    return max(-1.0, min(1.0, float(value) / scale))


def encode_observation_vector(observation: dict, *, max_rounds: int) -> list[float]:
    """Encode the public-state observation into a stable numeric vector."""
    vector: list[float] = [
        _normalize(observation.get("round_num", 0), float(max_rounds)),
    ]
    for section in ("self", "opponent"):
        player = observation.get(section, {}) or {}
        for field in PLAYER_FIELDS:
            vector.append(_normalize(player.get(field, 0), PLAYER_NORMALIZERS[field]))
    mask = observation.get("legal_action_mask", []) or []
    vector.extend(1.0 if item else 0.0 for item in mask[:ACTION_SPACE_SIZE])
    while len(vector) < OBSERVATION_VECTOR_SIZE:
        vector.append(0.0)
    return vector[:OBSERVATION_VECTOR_SIZE]


def _require_training_dependencies() -> None:
    missing = []
    if gym is None or spaces is None:
        missing.append("gymnasium")
    if np is None:
        missing.append("numpy")
    if missing:
        raise RuntimeError(
            "Training dependencies are not installed: "
            + ", ".join(missing)
            + ". Install with: pip install -r requirements-train.txt"
        )


def make_gymnasium_env(**env_kwargs: Any):
    """Create a Gymnasium-compatible env for MaskablePPO training."""
    _require_training_dependencies()

    class ClapClapGymEnv(gym.Env):  # type: ignore[union-attr]
        metadata = {"render_modes": []}

        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            self.core = ClapClapEnv(**kwargs)
            self.action_space = spaces.Discrete(ACTION_SPACE_SIZE)
            self.observation_space = spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(OBSERVATION_VECTOR_SIZE,),
                dtype=np.float32,
            )

        def reset(self, *, seed: int | None = None, options: dict | None = None):
            ai_player = None
            if options and options.get("randomize_seat"):
                ai_player = self.core.rng.choice((1, 2))
            observation = self.core.reset(seed=seed, ai_player=ai_player)
            return self._vector(observation), {"metadata": observation["metadata"]}

        def step(self, action: int):
            result = self.core.step(int(action))
            return (
                self._vector(result.observation),
                result.reward,
                result.terminated,
                result.truncated,
                result.info,
            )

        def action_masks(self):
            return np.array(self.core.legal_action_mask(), dtype=bool)

        def _vector(self, observation: dict):
            return np.array(
                encode_observation_vector(observation, max_rounds=self.core.max_rounds),
                dtype=np.float32,
            )

    return ClapClapGymEnv(**env_kwargs)
