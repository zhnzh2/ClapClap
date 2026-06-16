from threading import Lock

from app.models import GameState
from app.room_manager import cleanup_expired_rooms
from app.matchmaking import cleanup_expired_match_state
from app.users import cleanup_unverified_accounts

CURRENT_STATE = GameState()
CURRENT_STATE_LOCK = Lock()


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

