from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import random
import string

from models import GameState


@dataclass
class Room:
    room_id: str
    state: GameState = field(default_factory=GameState)
    p1_name: str | None = None
    p2_name: str | None = None
    status: str = "waiting"   # waiting / playing / finished
    pending_p1_move: str | None = None
    pending_p2_move: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_full(self) -> bool:
        return self.p1_name is not None and self.p2_name is not None

    def add_player(self, player_name: str) -> str:
        if self.p1_name is None:
            self.p1_name = player_name
            self.updated_at = datetime.utcnow()
            if self.is_full():
                self.status = "playing"
            return "p1"

        if self.p2_name is None:
            self.p2_name = player_name
            self.updated_at = datetime.utcnow()
            if self.is_full():
                self.status = "playing"
            return "p2"

        raise ValueError("房间已满。")

    def reset_game(self) -> None:
        self.state = GameState()
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.updated_at = datetime.utcnow()
        self.status = "playing" if self.is_full() else "waiting"

    def submit_move(self, seat: str, move_name: str) -> None:
        if seat == "p1":
            self.pending_p1_move = move_name
        elif seat == "p2":
            self.pending_p2_move = move_name
        else:
            raise ValueError("未知座位。")

        self.updated_at = datetime.utcnow()

    def clear_pending_moves(self) -> None:
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.updated_at = datetime.utcnow()

ROOMS: dict[str, Room] = {}


def generate_room_id(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        room_id = "".join(random.choice(alphabet) for _ in range(length))
        if room_id not in ROOMS:
            return room_id


def create_room(player_name: str) -> Room:
    room_id = generate_room_id()
    room = Room(room_id=room_id)
    room.add_player(player_name)
    ROOMS[room_id] = room
    return room


def get_room(room_id: str) -> Room | None:
    return ROOMS.get(room_id)


def join_room(room_id: str, player_name: str) -> tuple[Room, str]:
    room = get_room(room_id)
    if room is None:
        raise ValueError("房间不存在。")

    seat = room.add_player(player_name)
    return room, seat