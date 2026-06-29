from threading import Lock

from app.v1.models import GameState
from app.v2.models import GameStateV2
from app.v1.room_manager import cleanup_expired_rooms
from app.v1.matchmaking import cleanup_expired_match_state
from app.users import cleanup_unverified_accounts

CURRENT_STATE = GameState()
CURRENT_STATE_LOCK = Lock()
CURRENT_BATTLE_ID: str | None = None

# ── v2 本地模式全局状态 ──
CURRENT_STATE_V2: GameStateV2 = GameStateV2()
CURRENT_STATE_V2_LOCK = Lock()
CURRENT_BATTLE_ID_V2: str | None = None
CURRENT_ENGINE_V2 = None  # 持有当前引擎实例（用于步进式结算）


def run_periodic_cleanup() -> None:
    deleted_rooms = cleanup_expired_rooms()
    match_cleanup = cleanup_expired_match_state()
    deleted_users = cleanup_unverified_accounts()

    if deleted_rooms:
        print("[cleanup] deleted rooms:", deleted_rooms)

    if match_cleanup["removed_tokens"]:
        print("[cleanup] cleaned match tokens:", match_cleanup["removed_tokens"])

    if deleted_users:
        print("[cleanup] deleted unverified users:", deleted_users)

