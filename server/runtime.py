import time
from dataclasses import dataclass, field
from threading import Lock

from app.v1.models import GameState
from app.v2.models import GameStateV2
from app.v1.room_manager import cleanup_expired_rooms
from app.v1.matchmaking import cleanup_expired_match_state
from app.users import cleanup_unverified_accounts

CURRENT_STATE = GameState()
CURRENT_STATE_LOCK = Lock()
CURRENT_BATTLE_ID: str | None = None

# ── AI 对战独立状态 ──
# 不能复用 CURRENT_STATE，否则会和 /local 本地双人模式串局。
# AI_SESSIONS 进一步按用户隔离，避免多用户同时访问 /v1/ai 时共享同一局。
AI_STATE = GameState()
AI_STATE_LOCK = Lock()
CURRENT_AI_BATTLE_ID: str | None = None
AI_SESSION_TTL_SECONDS = 60 * 60 * 6


@dataclass
class AISession:
    state: GameState = field(default_factory=GameState)
    battle_id: str | None = None
    difficulty: str | None = None
    human_seat: str | None = None
    ai_seat: str | None = None
    policy_type: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()


AI_SESSIONS: dict[str, AISession] = {}


def get_ai_session_key(user: dict) -> str:
    """Return the per-user AI session key used by /v1/api/ai/*."""
    uid = user.get("uid")
    if uid is not None:
        return f"uid:{uid}"
    username = user.get("username") or "anonymous"
    return f"username:{username}"


def cleanup_ai_sessions(now: float | None = None) -> int:
    """Remove stale AI sessions and return the number of removed entries."""
    if now is None:
        now = time.time()
    expired = [
        key for key, session in AI_SESSIONS.items()
        if now - session.updated_at > AI_SESSION_TTL_SECONDS
    ]
    for key in expired:
        AI_SESSIONS.pop(key, None)
    return len(expired)


def get_ai_session(session_key: str) -> AISession:
    cleanup_ai_sessions()
    session = AI_SESSIONS.get(session_key)
    if session is None:
        session = AISession()
        AI_SESSIONS[session_key] = session
    session.touch()
    return session


def reset_ai_session(session_key: str) -> AISession:
    session = AISession()
    AI_SESSIONS[session_key] = session
    return session


def clear_ai_sessions() -> None:
    """Test helper: clear per-user AI state and legacy compatibility fields."""
    global AI_STATE, CURRENT_AI_BATTLE_ID
    AI_SESSIONS.clear()
    AI_STATE = GameState()
    CURRENT_AI_BATTLE_ID = None

# ── v2 本地模式全局状态 ──
CURRENT_STATE_V2: GameStateV2 = GameStateV2()
CURRENT_STATE_V2_LOCK = Lock()
CURRENT_BATTLE_ID_V2: str | None = None
CURRENT_ENGINE_V2 = None  # 持有当前引擎实例（用于步进式结算）


def run_periodic_cleanup() -> None:
    deleted_rooms = cleanup_expired_rooms()
    match_cleanup = cleanup_expired_match_state()
    deleted_users = cleanup_unverified_accounts()
    with AI_STATE_LOCK:
        deleted_ai_sessions = cleanup_ai_sessions()

    if deleted_rooms:
        print("[cleanup] deleted rooms:", deleted_rooms)

    if match_cleanup["removed_tokens"]:
        print("[cleanup] cleaned match tokens:", match_cleanup["removed_tokens"])

    if deleted_users:
        print("[cleanup] deleted unverified users:", deleted_users)

    if deleted_ai_sessions:
        print("[cleanup] deleted AI sessions:", deleted_ai_sessions)

