from __future__ import annotations

from app.constants import ATTACK_MOVES, DEFENSE_MOVES, Move, RESOURCE_MOVES, TRICK_MOVES
from app.game import GameEngine
from app.models import GameState

def get_move_catalog() -> list[dict]:
    result: list[dict] = []

    for move in Move:
        if move in RESOURCE_MOVES:
            category = "resource"
        elif move in ATTACK_MOVES:
            category = "attack"
        elif move in DEFENSE_MOVES:
            category = "defense"
        elif move in TRICK_MOVES:
            category = "trick"
        else:
            category = "unknown"

        result.append(
            {
                "name": move.name,
                "label": move.value,
                "category": category,
            }
        )

    return result

def get_legal_moves(state: GameState, player_index: int) -> list[str]:
    player = state.p1 if player_index == 1 else state.p2

    legal_moves: list[str] = []
    for move in Move:
        if GameEngine.can_afford(player, move):
            legal_moves.append(move.name)

    return legal_moves

def get_game_state_payload(state: GameState, include_history: bool = True) -> dict:
    payload = state.to_dict(include_history=include_history)
    payload["legal_moves"] = {
        "p1": get_legal_moves(state, 1),
        "p2": get_legal_moves(state, 2),
    }
    payload["move_catalog"] = get_move_catalog()
    return payload

def create_new_game_payload() -> dict:
    state = GameState()
    return get_game_state_payload(state, include_history=True)

def apply_round_and_get_payload(state: GameState, p1_move: Move, p2_move: Move) -> dict:
    GameEngine.resolve_round(state, p1_move, p2_move)
    return get_game_state_payload(state, include_history=True)

def parse_move_name(name: str) -> Move:
    try:
        return Move[name]
    except KeyError as exc:
        raise ValueError(f"未知动作名: {name}") from exc
    
def get_room_payload(room) -> dict:
    return {
        "room_id": room.room_id,
        "status": room.status,
        "p1_name": room.p1_name,
        "p2_name": room.p2_name,
        "is_full": room.is_full(),
        "pending_p1_move": room.pending_p1_move,
        "pending_p2_move": room.pending_p2_move,
        "game": get_game_state_payload(room.state, include_history=True),
        "reset_requested_by": room.reset_requested_by,
        "online_status": room.get_online_status_payload(),
        "chat_messages": getattr(room, "chat_messages", []),
        "battle_id": getattr(room, "battle_id", None),
        "rule_version": getattr(room, "rule_version", "1.0"),
    }