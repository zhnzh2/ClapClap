"""
ClapClap 2.0 多人房间数据模型。

与 1.0 Room (app/room_manager.py) 完全独立。
以「玩家席位列表 + 观战者列表」替代 p1/p2 双人假设。

席位规则：
  - 席位号从 1 开始，最大为 max_players（默认 6，即 1~6）
  - 加入时自动分配最小可用席位号，也可指定
  - 退出后席位号保留（不重排），空位可被新加入者复用
  - lobby 阶段允许自由换位
  - 房主退出后只转移房主，席位号不变
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.v2.constants import MAX_PLAYERS, MIN_PLAYERS
from app.v2.models import GameStateV2, PlayerStateV2

# ── 开始条件常量 ──
START_HOST = "host"              # 房主手动开始
START_ALL_READY = "all_ready"    # 全员准备后自动开始
START_FULL = "full"              # 满员自动开始

# ── 房间状态常量 ──
ROOM_LOBBY = "lobby"             # 大厅（等待开始）
ROOM_PLAYING = "playing"         # 对局进行中
ROOM_FINISHED = "finished"       # 对局已结束

# ── 玩家离开原因 ──
LEAVE_QUIT = "quit"              # 主动退出
LEAVE_SURRENDER = "surrender"    # 投降
LEAVE_DISCONNECT = "disconnect"  # 断线


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ═══════════════════════════════════════════════════════════════
# 参战席位
# ═══════════════════════════════════════════════════════════════

@dataclass
class SeatV2:
    """一个参战席位。席位号从 1 开始，player_id 为 "p1"~"pN"。"""

    seat_index: int                      # 席位号（1-based，1~max_players）
    username: str                        # 显示名
    player_token: str                    # 身份令牌（用于 API 认证）
    player_id: str = ""                  # 对局内标识（如 "p1", "p2"），加入时自动分配
    ready: bool = False                  # 是否已准备
    last_seen_at: datetime | None = None # 最后在线时间
    connected: bool = True               # 当前是否已连接（Socket.IO 心跳）

    def to_dict(self) -> dict:
        return {
            "seat_index": self.seat_index,
            "username": self.username,
            "player_token": self.player_token,
            "player_id": self.player_id,
            "ready": self.ready,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "connected": self.connected,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SeatV2":
        last_seen = None
        if data.get("last_seen_at"):
            try:
                last_seen = _ensure_utc(datetime.fromisoformat(data["last_seen_at"]))
            except (ValueError, TypeError):
                pass

        return cls(
            seat_index=data.get("seat_index", 1),
            username=data.get("username", ""),
            player_token=data.get("player_token", ""),
            player_id=data.get("player_id", ""),
            ready=data.get("ready", False),
            last_seen_at=last_seen,
            connected=data.get("connected", True),
        )


# ═══════════════════════════════════════════════════════════════
# 观战者
# ═══════════════════════════════════════════════════════════════

@dataclass
class SpectatorV2:
    """一个观战者。可在任意阶段加入（包括对局进行中）。"""

    username: str
    spectator_token: str
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "spectator_token": self.spectator_token,
            "joined_at": self.joined_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpectatorV2":
        joined_at = datetime.now(timezone.utc)
        if data.get("joined_at"):
            try:
                joined_at = _ensure_utc(datetime.fromisoformat(data["joined_at"]))
            except (ValueError, TypeError):
                pass

        return cls(
            username=data.get("username", ""),
            spectator_token=data.get("spectator_token", ""),
            joined_at=joined_at,
        )


# ═══════════════════════════════════════════════════════════════
# 多人房间
# ═══════════════════════════════════════════════════════════════

@dataclass
class RoomV2:
    """2.0 多人房间。

    席位号 1~max_players，退出不重排，空位可复用。
    """

    room_id: str
    rule_version: str = "2.0"

    # ── 席位 ──
    seats: list[SeatV2] = field(default_factory=list)
    spectators: list[SpectatorV2] = field(default_factory=list)

    # ── 房主 ──
    host_seat_index: int = 1              # 当前房主的席位号

    # ── 房间配置 ──
    max_players: int = MAX_PLAYERS        # 参战人数上限（默认 6）
    min_players: int = MIN_PLAYERS        # 最少开始人数（默认 2）
    start_condition: str = START_HOST     # 开始条件
    allow_spectate: bool = True           # 是否允许观战
    public: bool = False                  # 是否公开（显示在房间列表）
    password: str | None = None           # 房间密码（None = 无密码）

    # ── 状态 ──
    status: str = ROOM_LOBBY              # lobby / playing / finished

    # ── 对局状态（开始对局时创建） ──
    game_state: GameStateV2 | None = None

    # ── 重赛投票 ──
    rematch_votes: dict[str, bool] = field(default_factory=dict)  # {player_token: vote}

    # ── 聊天 ──
    chat_messages: list[dict] = field(default_factory=list)

    # ── 时间戳 ──
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 对局记录 ──
    battle_id: str | None = None

    # ═══════════════════════════════════════════════════════
    # 席位辅助
    # ═══════════════════════════════════════════════════════

    def _occupied_seats(self) -> set[int]:
        """当前已占用的席位号集合。"""
        return {s.seat_index for s in self.seats}

    def _smallest_available_seat(self) -> int | None:
        """最小可用席位号（1~max_players）。满员返回 None。"""
        occupied = self._occupied_seats()
        for i in range(1, self.max_players + 1):
            if i not in occupied:
                return i
        return None

    # ═══════════════════════════════════════════════════════
    # 玩家管理
    # ═══════════════════════════════════════════════════════

    def add_player(self, username: str, requested_seat_index: int | None = None) -> tuple[int, str]:
        """加入参战席位。返回 (seat_index, player_token)。

        默认自动分配最小可用席位号；也可通过 requested_seat_index 指定。
        """
        if self.is_full():
            raise ValueError("参战席位已满。")

        if self.status != ROOM_LOBBY:
            raise ValueError("对局已开始，不能加入参战席位。")

        # 检查是否已在席位中
        for s in self.seats:
            if s.username == username:
                raise ValueError("你已在参战席位中。")

        # 确定席位号
        if requested_seat_index is not None:
            if requested_seat_index < 1 or requested_seat_index > self.max_players:
                raise ValueError(f"席位号必须在 1~{self.max_players} 之间。")
            if requested_seat_index in self._occupied_seats():
                raise ValueError(f"席位 {requested_seat_index} 已被占用。")
            seat_index = requested_seat_index
        else:
            seat_index = self._smallest_available_seat()
            if seat_index is None:
                raise ValueError("参战席位已满。")

        player_token = uuid4().hex

        seat = SeatV2(
            seat_index=seat_index,
            username=username,
            player_token=player_token,
            player_id=f"p{seat_index}",
            last_seen_at=datetime.now(timezone.utc),
            connected=True,
        )
        self.seats.append(seat)
        self.updated_at = datetime.now(timezone.utc)
        return seat_index, player_token

    def add_spectator(self, username: str) -> str:
        """加入观战。返回 spectator_token。

        观战者可在任意阶段加入（lobby / playing / finished）。
        """
        if not self.allow_spectate:
            raise ValueError("本房间不允许观战。")

        # 检查是否已在观战中
        for s in self.spectators:
            if s.username == username:
                raise ValueError("你已在观战中。")

        spectator_token = uuid4().hex
        spec = SpectatorV2(
            username=username,
            spectator_token=spectator_token,
        )
        self.spectators.append(spec)
        self.updated_at = datetime.now(timezone.utc)
        return spectator_token

    def change_seat(self, player_token: str, new_seat_index: int) -> None:
        """更换席位号。仅限 lobby 阶段。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            raise ValueError("身份无效。")

        if self.status != ROOM_LOBBY:
            raise ValueError("对局已开始，不能更换席位。")

        if new_seat_index < 1 or new_seat_index > self.max_players:
            raise ValueError(f"席位号必须在 1~{self.max_players} 之间。")

        if new_seat_index == seat.seat_index:
            return  # 没变，不需要操作

        if new_seat_index in self._occupied_seats():
            raise ValueError(f"席位 {new_seat_index} 已被占用。")

        old_seat_index = seat.seat_index
        seat.seat_index = new_seat_index
        seat.player_id = f"p{new_seat_index}"

        # 如果是房主换位，更新房主席位号
        if old_seat_index == self.host_seat_index:
            self.host_seat_index = new_seat_index

        self.updated_at = datetime.now(timezone.utc)

    def remove_player(self, player_token: str) -> tuple[str | None, str]:
        """移除玩家（退出/断线/投降）。席位号保留，不重排。

        返回 (new_host_token | None, leave_type)。
        """
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            # 可能是观战者
            spec = self.get_spectator_by_token(player_token)
            if spec is None:
                raise ValueError("身份无效。")
            self.spectators.remove(spec)
            self.updated_at = datetime.now(timezone.utc)
            return None, LEAVE_QUIT

        leave_type = LEAVE_QUIT
        if self.status == ROOM_PLAYING:
            leave_type = LEAVE_SURRENDER

        was_host = (seat.seat_index == self.host_seat_index)

        # 移除席位（不重排）
        self.seats = [s for s in self.seats if s.player_token != player_token]

        # 如果对局进行中且玩家存活，标记死亡
        if self.game_state is not None and leave_type == LEAVE_SURRENDER:
            player = self.game_state.get_player(seat.player_id)
            if player is not None and player.is_alive():
                from app.v2.constants import DEATH_SURRENDER
                player.mark_dead(
                    self.game_state.round_num,
                    DEATH_SURRENDER,
                )
                alive = self.game_state.alive_players()
                if len(alive) <= 1:
                    self.game_state.winner = alive[0].player_id if alive else ""
                    self.game_state.assign_ranks()

        # 房主转移：只转移房主，不重排席位
        new_host_token = None
        if was_host:
            if self.seats:
                # 转移到席位号最小的剩余参战者
                smallest = min(self.seats, key=lambda s: s.seat_index)
                self.host_seat_index = smallest.seat_index
                new_host_token = smallest.player_token
            else:
                self.host_seat_index = -1

        self.updated_at = datetime.now(timezone.utc)

        # 清除该玩家的重赛投票
        self.rematch_votes.pop(player_token, None)

        return new_host_token, leave_type

    # ═══════════════════════════════════════════════════════
    # 查找
    # ═══════════════════════════════════════════════════════

    def get_seat_by_token(self, player_token: str) -> SeatV2 | None:
        for s in self.seats:
            if s.player_token == player_token:
                return s
        return None

    def get_seat_by_index(self, seat_index: int) -> SeatV2 | None:
        for s in self.seats:
            if s.seat_index == seat_index:
                return s
        return None

    def get_seat_by_player_id(self, player_id: str) -> SeatV2 | None:
        """根据 player_id 查找席位。"""
        for s in self.seats:
            if s.player_id == player_id:
                return s
        return None

    def get_spectator_by_token(self, token: str) -> SpectatorV2 | None:
        for s in self.spectators:
            if s.spectator_token == token:
                return s
        return None

    def get_seat_by_username(self, username: str) -> SeatV2 | None:
        for s in self.seats:
            if s.username == username:
                return s
        return None

    # ═══════════════════════════════════════════════════════
    # 就绪与开始
    # ═══════════════════════════════════════════════════════

    def set_ready(self, player_token: str, ready: bool) -> None:
        """设置玩家的准备状态。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            raise ValueError("身份无效。")

        if self.status != ROOM_LOBBY:
            raise ValueError("对局已开始，不能更改准备状态。")

        seat.ready = ready
        self.updated_at = datetime.now(timezone.utc)

    def all_players_ready(self) -> bool:
        """所有参战者是否都已准备。"""
        if not self.seats:
            return False
        return all(s.ready for s in self.seats)

    def is_full(self) -> bool:
        """参战席位是否已满。"""
        return len(self.seats) >= self.max_players

    def can_start(self) -> bool:
        """当前是否可以开始对局。"""
        if self.status != ROOM_LOBBY:
            return False

        if len(self.seats) < self.min_players:
            return False

        if self.start_condition == START_ALL_READY:
            return self.all_players_ready()

        if self.start_condition == START_FULL:
            return self.is_full()

        # START_HOST: 房主手动开始，只需满足最低人数
        return True

    def player_count(self) -> int:
        return len(self.seats)

    def spectator_count(self) -> int:
        return len(self.spectators)

    # ═══════════════════════════════════════════════════════
    # 对局生命周期
    # ═══════════════════════════════════════════════════════

    def start_game(self) -> GameStateV2:
        """开始对局：锁定参战名单，创建 GameStateV2。"""
        if not self.can_start():
            raise ValueError("当前不满足开始条件。")

        # 构建 PlayerStateV2 列表（按席位号排序）
        sorted_seats = sorted(self.seats, key=lambda s: s.seat_index)
        players: list[PlayerStateV2] = []
        for seat in sorted_seats:
            p = PlayerStateV2(
                player_id=seat.player_id,
                seat_index=seat.seat_index,
                username=seat.username,
            )
            players.append(p)

        self.game_state = GameStateV2(
            players=players,
            max_players=self.max_players,
            rule_version=self.rule_version,
        )
        self.status = ROOM_PLAYING
        self.updated_at = datetime.now(timezone.utc)

        return self.game_state

    def submit_move(self, player_token: str, _move_name: str) -> None:
        """提交本回合动作（仅标记提交状态，实际结算由 room_service 触发）。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            raise ValueError("身份无效。")

        if self.status != ROOM_PLAYING:
            raise ValueError("对局尚未开始。")

        if self.game_state is None:
            raise ValueError("对局状态异常。")

        player = self.game_state.get_player(seat.player_id)
        if player is None:
            raise ValueError("找不到你的对局状态。")

        if not player.is_alive():
            raise ValueError("你已淘汰，不能提交动作。")

        if player.move_submitted:
            raise ValueError("你本回合已经提交过动作。")

        player.pending_move = _move_name
        player.move_submitted = True
        self.updated_at = datetime.now(timezone.utc)

    def all_moves_submitted(self) -> bool:
        """所有存活玩家是否都已提交本回合动作。"""
        if self.game_state is None:
            return False
        return self.game_state.all_moves_submitted()

    def clear_round_state(self) -> None:
        """清除回合临时状态（结算后调用）。"""
        self.updated_at = datetime.now(timezone.utc)

    # ═══════════════════════════════════════════════════════
    # 重赛
    # ═══════════════════════════════════════════════════════

    def vote_rematch(self, player_token: str, vote: bool) -> tuple[bool, str]:
        """重赛投票。返回 (did_trigger, message)。"""
        if self.status != ROOM_FINISHED:
            return False, "对局尚未结束，不能发起重赛。"

        seat = self.get_seat_by_token(player_token)
        if seat is None:
            return False, "只有参战者才能投票重赛。"

        self.rematch_votes[player_token] = vote
        self.updated_at = datetime.now(timezone.utc)

        if not vote:
            self.rematch_votes = {}
            return False, f"{seat.username} 拒绝了重赛。"

        all_voted_yes = all(
            self.rematch_votes.get(s.player_token, False)
            for s in self.seats
        )

        if all_voted_yes:
            self._reset_for_rematch()
            return True, "全员同意，重新开始对局！"

        return False, f"{seat.username} 同意重赛（{sum(1 for v in self.rematch_votes.values() if v)}/{len(self.seats)}）。"

    def _reset_for_rematch(self) -> None:
        """重置对局状态以开始新一局。保留参战名单和房主。"""
        self.game_state = None
        self.status = ROOM_LOBBY
        self.rematch_votes = {}
        self.battle_id = None

        for s in self.seats:
            s.ready = False

        self.updated_at = datetime.now(timezone.utc)

    # ═══════════════════════════════════════════════════════
    # 在线状态
    # ═══════════════════════════════════════════════════════

    def mark_seen(self, player_token: str) -> None:
        """标记玩家在线。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            return

        now = datetime.now(timezone.utc)
        seat.last_seen_at = now
        seat.connected = True
        self.updated_at = now

    def mark_disconnected(self, player_token: str) -> None:
        """标记玩家断开连接。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            return
        seat.connected = False
        self.updated_at = datetime.now(timezone.utc)

    def mark_reconnected(self, player_token: str) -> None:
        """标记玩家重新连接。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            return
        seat.connected = True
        seat.last_seen_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def is_seat_online(self, seat_index: int, *, ttl_seconds: int = 20) -> bool:
        """检查某个席位是否在线。"""
        seat = self.get_seat_by_index(seat_index)
        if seat is None:
            return False
        if seat.last_seen_at is None:
            return False
        now = datetime.now(timezone.utc)
        return (now - seat.last_seen_at).total_seconds() <= ttl_seconds

    def get_online_status(self) -> dict[int, bool]:
        """获取所有席位的在线状态。"""
        return {s.seat_index: self.is_seat_online(s.seat_index) for s in self.seats}

    # ═══════════════════════════════════════════════════════
    # 聊天
    # ═══════════════════════════════════════════════════════

    def add_chat_message(self, sender: str, message: str) -> dict:
        """添加一条聊天消息。"""
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        msg = {
            "timestamp": ts,
            "sender": sender,
            "message": message,
        }
        self.chat_messages.append(msg)
        self.updated_at = now
        return msg

    # ═══════════════════════════════════════════════════════
    # 过期清理
    # ═══════════════════════════════════════════════════════

    def is_expired(self, *, waiting_minutes: int = 180, finished_minutes: int = 360) -> bool:
        """检查房间是否过期。"""
        now = datetime.now(timezone.utc)

        if self.status == ROOM_FINISHED:
            return self.updated_at < now - timedelta(minutes=finished_minutes)

        if self.status == ROOM_LOBBY:
            return self.updated_at < now - timedelta(minutes=waiting_minutes)

        # playing 状态：全部离线 + 很久没更新
        no_one_online = all(
            not self.is_seat_online(s.seat_index, ttl_seconds=120)
            for s in self.seats
        )
        very_old = self.updated_at < now - timedelta(hours=12)
        return no_one_online and very_old

    # ═══════════════════════════════════════════════════════
    # 房主
    # ═══════════════════════════════════════════════════════

    def is_host(self, player_token: str) -> bool:
        """检查是否是房主。"""
        seat = self.get_seat_by_token(player_token)
        if seat is None:
            return False
        return seat.seat_index == self.host_seat_index

    def transfer_host(self, new_player_token: str) -> None:
        """手动转移房主。"""
        seat = self.get_seat_by_token(new_player_token)
        if seat is None:
            raise ValueError("目标玩家不在参战席位中。")
        self.host_seat_index = seat.seat_index
        self.updated_at = datetime.now(timezone.utc)

    # ═══════════════════════════════════════════════════════
    # 序列化
    # ═══════════════════════════════════════════════════════

    def persist(self) -> None:
        """持久化到 SQLite。"""
        from app.storage import save_room
        save_room(self.room_id, self.to_dict())

    def to_dict(self) -> dict:
        data = {
            "room_id": self.room_id,
            "rule_version": self.rule_version,
            "seats": [s.to_dict() for s in self.seats],
            "spectators": [s.to_dict() for s in self.spectators],
            "host_seat_index": self.host_seat_index,
            "max_players": self.max_players,
            "min_players": self.min_players,
            "start_condition": self.start_condition,
            "allow_spectate": self.allow_spectate,
            "public": self.public,
            "password": self.password,
            "status": self.status,
            "rematch_votes": self.rematch_votes,
            "chat_messages": self.chat_messages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "battle_id": self.battle_id,
        }

        if self.game_state is not None:
            data["game_state"] = self.game_state.to_dict(include_history=True)

        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RoomV2":
        seats_data = data.get("seats", [])
        seats = [SeatV2.from_dict(sd) for sd in seats_data]

        spectators_data = data.get("spectators", [])
        spectators = [SpectatorV2.from_dict(sd) for sd in spectators_data]

        game_state = None
        if "game_state" in data and data["game_state"] is not None:
            try:
                game_state = GameStateV2.from_dict(data["game_state"])
            except Exception:
                game_state = None

        created_at = datetime.now(timezone.utc)
        if data.get("created_at"):
            try:
                created_at = _ensure_utc(datetime.fromisoformat(data["created_at"]))
            except (ValueError, TypeError):
                pass

        updated_at = datetime.now(timezone.utc)
        if data.get("updated_at"):
            try:
                updated_at = _ensure_utc(datetime.fromisoformat(data["updated_at"]))
            except (ValueError, TypeError):
                pass

        return cls(
            room_id=data["room_id"],
            rule_version=data.get("rule_version", "2.0"),
            seats=seats,
            spectators=spectators,
            host_seat_index=data.get("host_seat_index", 1),
            max_players=data.get("max_players", MAX_PLAYERS),
            min_players=data.get("min_players", MIN_PLAYERS),
            start_condition=data.get("start_condition", START_HOST),
            allow_spectate=data.get("allow_spectate", True),
            public=data.get("public", False),
            password=data.get("password"),
            status=data.get("status", ROOM_LOBBY),
            game_state=game_state,
            rematch_votes=data.get("rematch_votes", {}),
            chat_messages=data.get("chat_messages", []),
            created_at=created_at,
            updated_at=updated_at,
            battle_id=data.get("battle_id"),
        )
