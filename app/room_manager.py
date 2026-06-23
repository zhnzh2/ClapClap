from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import random
import string
from threading import RLock
from uuid import uuid4
import traceback

from app.models import GameState
from app.storage import load_all_rooms, load_room, save_room, delete_room

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
    reset_requested_by: str | None = None
    p1_last_seen_at: datetime | None = None
    p2_last_seen_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # 聊天记录: [{"timestamp": "...", "sender": "...", "message": "..."}, ...]
    chat_messages: list[dict] = field(default_factory=list)
    # 对局记录 ID
    battle_id: str | None = None
    # 规则版本
    rule_version: str = "1.0"

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
            "reset_requested_by": self.reset_requested_by,
            "p1_last_seen_at": self.p1_last_seen_at.isoformat() if self.p1_last_seen_at else None,
            "p2_last_seen_at": self.p2_last_seen_at.isoformat() if self.p2_last_seen_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "chat_messages": self.chat_messages,
            "battle_id": self.battle_id,
            "rule_version": self.rule_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        def _ensure_utc(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        room = cls(
            room_id=data["room_id"],
            p1_name=data.get("p1_name"),
            p2_name=data.get("p2_name"),
            p1_token=data.get("p1_token"),
            p2_token=data.get("p2_token"),
            status=data.get("status", "waiting"),
            pending_p1_move=data.get("pending_p1_move"),
            pending_p2_move=data.get("pending_p2_move"),
            reset_requested_by=data.get("reset_requested_by"),
            p1_last_seen_at=_ensure_utc(datetime.fromisoformat(data["p1_last_seen_at"]) if data.get("p1_last_seen_at") else None),
            p2_last_seen_at=_ensure_utc(datetime.fromisoformat(data["p2_last_seen_at"]) if data.get("p2_last_seen_at") else None),
            created_at=_ensure_utc(datetime.fromisoformat(data["created_at"])),
            chat_messages=data.get("chat_messages", []),
            battle_id=data.get("battle_id"),
            updated_at=_ensure_utc(datetime.fromisoformat(data["updated_at"])),
            rule_version=data.get("rule_version", "1.0"),
        )
        room.state = GameState.from_dict(data["state"])
        return room

    def is_full(self) -> bool:
        return self.p1_name is not None and self.p2_name is not None

    def add_player(self, player_name: str) -> tuple[str, str]:
        if self.p1_name is None:
            self.p1_name = player_name
            self.p1_token = uuid4().hex
            self.p1_last_seen_at = datetime.now(timezone.utc)
            self.updated_at = datetime.now(timezone.utc)
            if self.is_full():
                self.status = "playing"
            return "p1", self.p1_token

        if self.p2_name is None:
            self.p2_name = player_name
            self.p2_token = uuid4().hex
            self.p2_last_seen_at = datetime.now(timezone.utc)
            self.updated_at = datetime.now(timezone.utc)
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

    def mark_seen(self, seat: str) -> None:
        now = datetime.now(timezone.utc)

        if seat == "p1":
            self.p1_last_seen_at = now
        elif seat == "p2":
            self.p2_last_seen_at = now

        self.updated_at = now
        self.persist()

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self.persist()

    def is_seat_online(self, seat: str, *, ttl_seconds: int = 20) -> bool:
        now = datetime.now(timezone.utc)

        if seat == "p1":
            last_seen = self.p1_last_seen_at
        elif seat == "p2":
            last_seen = self.p2_last_seen_at
        else:
            return False

        if last_seen is None:
            return False

        return (now - last_seen).total_seconds() <= ttl_seconds

    def get_online_status_payload(self) -> dict:
        return {
            "p1_online": self.is_seat_online("p1"),
            "p2_online": self.is_seat_online("p2"),
        }

    def request_reset(self, seat: str) -> tuple[bool, str]:
        if self.reset_requested_by is None:
            self.reset_requested_by = seat
            self.updated_at = datetime.now(timezone.utc)
            self.persist()
            return False, f"{seat} 已发起重置请求，等待另一方确认。"

        if self.reset_requested_by == seat:
            return False, "你已经发起过重置请求，正在等待另一方确认。"

        self.state = GameState()
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.reset_requested_by = None
        self.updated_at = datetime.now(timezone.utc)
        self.status = "playing" if self.is_full() else "waiting"
        self.persist()
        return True, "双方已确认，房间对局已重置。"

    def clear_reset_request(self) -> None:
        self.reset_requested_by = None
        self.updated_at = datetime.now(timezone.utc)
        self.persist()

    def is_expired(self, *, waiting_minutes: int = 180, finished_minutes: int = 360) -> bool:
        now = datetime.now(timezone.utc)

        if self.status == "finished":
            return self.updated_at < now - timedelta(minutes=finished_minutes)

        if self.status == "waiting":
            return self.updated_at < now - timedelta(minutes=waiting_minutes)

        no_one_online = (not self.is_seat_online("p1", ttl_seconds=120)) and (not self.is_seat_online("p2", ttl_seconds=120))
        very_old = self.updated_at < now - timedelta(hours=12)
        return no_one_online and very_old

    def reset_game(self) -> None:
        self.state = GameState()
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.reset_requested_by = None
        self.updated_at = datetime.now(timezone.utc)
        self.status = "playing" if self.is_full() else "waiting"
        self.persist()

    def submit_move(self, seat: str, move_name: str) -> None:
        if seat == "p1":
            self.pending_p1_move = move_name
        elif seat == "p2":
            self.pending_p2_move = move_name
        else:
            raise ValueError("未知座位。")

        self.reset_requested_by = None
        self.updated_at = datetime.now(timezone.utc)
        self.persist()

    def cancel_submitted_move(self, seat: str) -> tuple[bool, str]:
        if seat == "p1":
            if self.pending_p1_move is None:
                return False, "你当前还没有已提交的动作。"
            if self.pending_p2_move is not None:
                return False, "对方已经提交，当前回合已进入结算，不能撤回。"

            self.pending_p1_move = None
        elif seat == "p2":
            if self.pending_p2_move is None:
                return False, "你当前还没有已提交的动作。"
            if self.pending_p1_move is not None:
                return False, "对方已经提交，当前回合已进入结算，不能撤回。"

            self.pending_p2_move = None
        else:
            raise ValueError("未知座位。")

        self.updated_at = datetime.now(timezone.utc)
        self.persist()
        return True, "已撤回本回合提交动作。"

    def clear_pending_moves(self) -> None:
        self.pending_p1_move = None
        self.pending_p2_move = None
        self.updated_at = datetime.now(timezone.utc)
        self.persist()

    def add_chat_message(self, sender: str, message: str) -> dict:
        """添加一条聊天消息。返回消息 dict。发送者和观战者均可发言。"""
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        msg = {
            "timestamp": ts,
            "sender": sender,
            "message": message,
        }
        self.chat_messages.append(msg)
        self.persist()
        return msg

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

def create_room(player_name: str, rule_version: str = "1.0") -> tuple[Room, str, str]:
    with ROOMS_LOCK:
        room_id = generate_room_id()
        room = Room(room_id=room_id, rule_version=rule_version)
        seat, token = room.add_player(player_name)
        ROOMS[room_id] = room
        ROOM_RUNTIME_LOCKS[room_id] = RLock()
        room.persist()
        return room, seat, token

def get_room(room_id: str) -> Room | None:
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room is not None:
            return room

    room_data = load_room(room_id)
    if room_data is None:
        return None

    try:
        restored_room = Room.from_dict(room_data)
    except Exception as exc:
        print(f"[get_room] 恢复房间 {room_id} 失败: {exc}")
        traceback.print_exc()
        return None

    with ROOMS_LOCK:
        existing = ROOMS.get(room_id)
        if existing is not None:
            return existing

        ROOMS[room_id] = restored_room
        ROOM_RUNTIME_LOCKS.setdefault(room_id, RLock())
        return restored_room

def get_room_runtime_lock(room_id: str) -> RLock:
    with ROOMS_LOCK:
        if room_id not in ROOM_RUNTIME_LOCKS:
            ROOM_RUNTIME_LOCKS[room_id] = RLock()
        return ROOM_RUNTIME_LOCKS[room_id]
    
def cleanup_expired_rooms() -> list[str]:
    deleted_room_ids: list[str] = []

    with ROOMS_LOCK:
        room_ids = list(ROOMS.keys())

        for room_id in room_ids:
            room = ROOMS.get(room_id)
            if room is None:
                continue

            if not room.is_expired():
                continue

            ROOMS.pop(room_id, None)
            ROOM_RUNTIME_LOCKS.pop(room_id, None)
            delete_room(room_id)
            deleted_room_ids.append(room_id)

    return deleted_room_ids

def join_room(room_id: str, player_name: str) -> tuple[Room, str, str]:
    room = get_room(room_id)
    if room is None:
        raise ValueError("房间不存在。")

    with ROOMS_LOCK:
        seat, token = room.add_player(player_name)
        room.persist()
        return room, seat, token
    
def delete_room_by_id(room_id: str) -> None:
    with ROOMS_LOCK:
        ROOMS.pop(room_id, None)
        ROOM_RUNTIME_LOCKS.pop(room_id, None)
        delete_room(room_id)
