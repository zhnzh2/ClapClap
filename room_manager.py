from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import random
import string
from threading import RLock
from uuid import uuid4
import traceback

from models import GameState
from storage import load_all_rooms, save_room


@dataclass
class Room:
    room_id: str
    state: GameState = field(default_factory=GameState)
    p1_name: str | None = None
    p2_name: str | None = None
    p1_token: str | None = None
    p2_token: str | None = None
    status: str = "waiting"
    pending_p1_move: str | None = None
    pending_p2_move: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "state": self.state.to_dict(include_history=True),
            "p1_name": self.p1_name,
            "p2_name": self.p2_name,
            "p1_token": self.p1_token,
            "p2_token": self.p2_token,
            "status": self.status,
            "pending_p1_move": self.pending_p1_move,
            "pending_p2_move": self.pending_p2_move,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        room = cls(
            room_id=data["room_id"],
            p1_name=data.get("p1_name"),
            p2_name=data.get("p2_name"),
            p1_token=data.get("p1_token"),
            p2_token=data.get("p2_token"),
            status=data.get("status", "waiting"),
            pending_p1_move=data.get("pending_p1_move"),
            pending_p2_move=data.get("pending_p2_move"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        room.state = GameState.from_dict(data["state"])
        return room

    def is_full(self) -> bool:
        return self.p1_name is not None and self.p2_name is not None

    def add_player(self, player_name: str) -> tuple[str, str]:
        if self.p1_name is None:
            self.p1_name = player_name
            self.p1_token = uuid4().hex
            self.updated_at = datetime.utcnow()
            if self.is_full():
                self.status = "playing"
            return "p1", self.p1_token

        if self.p2_name is None:
            self.p2_name = player_name
            self.p2_token = uuid4().hex
            self.updated_at = datetime.utcnow()
            if self.is_full():
                self.status = "playing"
            return "p2", self.p2_token

        raise ValueError("房间已满。")

    def get_seat_by_token(self, player_token: str) -> str | None:
        if player_token == self.p1_token:
            return "p1"
        if player_token == self.p2_token:
            return "p2"
        return None

    def reset_game(self) -> None:
        self.state = GameState()
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.updated_at = datetime.utcnow()
        self.status = "playing" if self.is_full() else "waiting"
        self.persist()

    def submit_move(self, seat: str, move_name: str) -> None:
        if seat == "p1":
            self.pending_p1_move = move_name
        elif seat == "p2":
            self.pending_p2_move = move_name
        else:
            raise ValueError("未知座位。")

        self.updated_at = datetime.utcnow()
        self.persist()

    def clear_pending_moves(self) -> None:
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.updated_at = datetime.utcnow()
        self.persist()

    def persist(self) -> None:
        save_room(self.room_id, self.to_dict())

ROOMS: dict[str, Room] = {}
ROOMS_LOCK = RLock()
ROOM_RUNTIME_LOCKS: dict[str, RLock] = {}

def load_rooms_from_storage() -> None:
    persisted = load_all_rooms()
    with ROOMS_LOCK:
        ROOMS.clear()
        ROOM_RUNTIME_LOCKS.clear()

        for room_id, room_data in persisted.items():
            try:
                ROOMS[room_id] = Room.from_dict(room_data)
                ROOM_RUNTIME_LOCKS[room_id] = RLock()
            except Exception as exc:
                print(f"[load_rooms_from_storage] 跳过无法兼容的旧房间 {room_id}: {exc}")
                traceback.print_exc()

def generate_room_id(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        room_id = "".join(random.choice(alphabet) for _ in range(length))
        if room_id not in ROOMS:
            return room_id

def create_room(player_name: str) -> tuple[Room, str, str]:
    with ROOMS_LOCK:
        room_id = generate_room_id()
        room = Room(room_id=room_id)
        seat, token = room.add_player(player_name)
        ROOMS[room_id] = room
        ROOM_RUNTIME_LOCKS[room_id] = RLock()
        room.persist()
        return room, seat, token

def get_room(room_id: str) -> Room | None:
    with ROOMS_LOCK:
        return ROOMS.get(room_id)

def get_room_runtime_lock(room_id: str) -> RLock:
    with ROOMS_LOCK:
        if room_id not in ROOM_RUNTIME_LOCKS:
            ROOM_RUNTIME_LOCKS[room_id] = RLock()
        return ROOM_RUNTIME_LOCKS[room_id]

def join_room(room_id: str, player_name: str) -> tuple[Room, str, str]:
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room is None:
            raise ValueError("房间不存在。")

        seat, token = room.add_player(player_name)
        room.persist()
        return room, seat, token