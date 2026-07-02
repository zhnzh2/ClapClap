"""
RoomV2 多人房间测试。

席位号 1-based（1~max_players），退出不重排，空位复用。
"""

import pytest

from app.v2.room import (
    RoomV2,
    SeatV2,
    SpectatorV2,
    START_HOST,
    START_ALL_READY,
    START_FULL,
    ROOM_LOBBY,
    ROOM_PLAYING,
    ROOM_FINISHED,
)
from app.v2.room_manager import (
    create_room_v2,
    get_room_v2,
    join_room_v2,
    leave_room_v2,
    mark_seen_v2,
    mark_disconnected_v2,
    mark_reconnected_v2,
    cleanup_expired_rooms_v2,
    persist_room_v2,
    ROOMS_V2,
    ROOMS_V2_LOCK,
)
from app.v2.models import DecisionOption, DecisionRequest
from app.v2.state_api import get_room_v2_payload


class TestSeatV2:
    """SeatV2 数据模型测试。"""

    def test_create_seat(self):
        s = SeatV2(seat_index=1, username="alice", player_token="tok1", player_id="p1")
        assert s.seat_index == 1
        assert s.username == "alice"
        assert s.ready is False
        assert s.connected is True

    def test_to_dict_and_back(self):
        s = SeatV2(seat_index=3, username="bob", player_token="tok2", player_id="p3", ready=True)
        d = s.to_dict()
        s2 = SeatV2.from_dict(d)
        assert s2.seat_index == 3
        assert s2.username == "bob"
        assert s2.player_token == "tok2"
        assert s2.ready is True


class TestRoomV2Basic:
    """RoomV2 基本操作测试。"""

    def test_create_room(self):
        room, seat_index, token = create_room_v2("alice")
        assert room.room_id is not None
        assert len(room.room_id) == 6
        assert seat_index == 1                    # 1-based，最小可用
        assert token is not None
        assert room.player_count() == 1
        assert room.host_seat_index == 1
        assert room.status == ROOM_LOBBY

    def test_add_players_sequential(self):
        room, _, _ = create_room_v2("alice", max_players=4)

        si, _ = room.add_player("bob")
        assert si == 2
        si, _ = room.add_player("charlie")
        assert si == 3
        assert room.player_count() == 3

    def test_add_player_specific_seat(self):
        room, _, _ = create_room_v2("alice", max_players=4)

        si, _ = room.add_player("bob", requested_seat_index=4)
        assert si == 4
        # 自动分配下一个应该是 2
        si, _ = room.add_player("charlie")
        assert si == 2

    def test_add_player_seat_occupied(self):
        room, _, _ = create_room_v2("alice", max_players=4)
        room.add_player("bob", requested_seat_index=3)

        with pytest.raises(ValueError, match="已被占用"):
            room.add_player("charlie", requested_seat_index=3)

    def test_add_player_seat_out_of_range(self):
        room, _, _ = create_room_v2("alice", max_players=4)

        with pytest.raises(ValueError, match="席位号必须在"):
            room.add_player("bob", requested_seat_index=0)

        with pytest.raises(ValueError, match="席位号必须在"):
            room.add_player("bob", requested_seat_index=5)

    def test_add_until_full(self):
        room, _, _ = create_room_v2("alice", max_players=3)
        room.add_player("bob")
        room.add_player("charlie")
        assert room.is_full()

        with pytest.raises(ValueError, match="参战席位已满"):
            room.add_player("dave")

    def test_duplicate_username_rejected(self):
        room, _, _ = create_room_v2("alice")
        with pytest.raises(ValueError, match="已在参战席位中"):
            room.add_player("alice")

    def test_spectator(self):
        room, _, _ = create_room_v2("alice")
        tok = room.add_spectator("viewer1")
        assert tok is not None
        assert room.spectator_count() == 1

    def test_spectator_during_playing(self):
        """观战者应能在对局进行中加入。"""
        room, _, _ = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()
        assert room.status == ROOM_PLAYING

        tok = room.add_spectator("viewer1")
        assert tok is not None
        assert room.spectator_count() == 1

    def test_spectator_disabled(self):
        room, _, _ = create_room_v2("alice", allow_spectate=False)
        with pytest.raises(ValueError, match="不允许观战"):
            room.add_spectator("viewer1")


class TestRoomV2SeatReuse:
    """席位复用测试。"""

    def test_seat_reuse_after_leave(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)
        room.add_player("bob")            # seat 2
        room.add_player("charlie")        # seat 3

        # bob 退出，席位 2 空出
        room.remove_player(tok1)          # alice (seat 1) 退出
        # 现在 seats 中有 bob(2), charlie(3)

        # 新玩家应分配到最小空位 1
        si, _ = room.add_player("dave")
        assert si == 1

    def test_seat_not_renumbered_after_leave(self):
        room, _, _ = create_room_v2("alice", max_players=4)
        _, tok2 = room.add_player("bob")         # seat 2
        _, tok3 = room.add_player("charlie")     # seat 3

        # alice (seat 1) 退出
        room.remove_player(room.seats[0].player_token)

        # bob 和 charlie 的席位号不变
        assert room.get_seat_by_token(tok2).seat_index == 2
        assert room.get_seat_by_token(tok3).seat_index == 3

    def test_host_transfer_on_leave(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)
        _, tok2 = room.add_player("bob", requested_seat_index=4)     # seat 4
        _, tok3 = room.add_player("charlie", requested_seat_index=2)  # seat 2

        assert room.host_seat_index == 1
        assert room.is_host(tok1)

        # 房主（seat 1）退出 → 房主转给最小席位号的剩余玩家（seat 2, charlie）
        new_host, _ = room.remove_player(tok1)
        assert new_host == tok3
        assert room.host_seat_index == 2
        assert room.is_host(tok3)


class TestRoomV2ChangeSeat:
    """换位测试。"""

    def test_change_seat(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)
        _, tok2 = room.add_player("bob")  # seat 2

        # alice 从 seat 1 换到 seat 3
        room.change_seat(tok1, 3)
        assert room.get_seat_by_token(tok1).seat_index == 3
        assert room.get_seat_by_token(tok1).player_id == "p3"
        # 房主席位号跟随
        assert room.host_seat_index == 3

    def test_change_seat_occupied(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)
        room.add_player("bob")  # seat 2

        with pytest.raises(ValueError, match="已被占用"):
            room.change_seat(tok1, 2)

    def test_change_seat_out_of_range(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)

        with pytest.raises(ValueError, match="席位号必须在"):
            room.change_seat(tok1, 0)

        with pytest.raises(ValueError, match="席位号必须在"):
            room.change_seat(tok1, 5)

    def test_change_seat_only_in_lobby(self):
        room, _, tok1 = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()

        with pytest.raises(ValueError, match="对局已开始"):
            room.change_seat(tok1, 2)

    def test_change_seat_same_seat_noop(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)
        # 换到当前席位，不应报错
        room.change_seat(tok1, 1)
        assert room.get_seat_by_token(tok1).seat_index == 1


class TestRoomV2Ready:
    """准备状态测试。"""

    def test_set_ready(self):
        room, _, tok1 = create_room_v2("alice")
        room.add_player("bob")

        room.set_ready(tok1, True)
        assert room.get_seat_by_token(tok1).ready is True

        room.set_ready(tok1, False)
        assert room.get_seat_by_token(tok1).ready is False

    def test_all_ready(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")

        assert not room.all_players_ready()
        room.set_ready(tok1, True)
        room.set_ready(tok2, True)
        assert room.all_players_ready()

    def test_cant_ready_after_start(self):
        room, _, tok1 = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()

        with pytest.raises(ValueError, match="对局已开始"):
            room.set_ready(tok1, False)


class TestRoomV2Start:
    """开始对局测试。"""

    def test_can_start_host_mode(self):
        room, _, _ = create_room_v2("alice", min_players=2, start_condition=START_HOST)
        room.add_player("bob")
        assert room.can_start()

    def test_cannot_start_insufficient_players(self):
        room, _, _ = create_room_v2("alice", min_players=3)
        room.add_player("bob")
        assert not room.can_start()
        assert room.player_count() == 2

        with pytest.raises(ValueError, match="不满足开始条件"):
            room.start_game()

    def test_start_game_creates_game_state(self):
        room, _, _ = create_room_v2("alice")
        room.add_player("bob")
        room.add_player("charlie", requested_seat_index=3)

        gs = room.start_game()
        assert room.status == ROOM_PLAYING
        assert room.game_state is not None
        assert len(gs.players) == 3
        # 玩家按席位号排序
        assert gs.players[0].username == "alice"
        assert gs.players[0].player_id == "p1"
        assert gs.players[1].username == "bob"
        assert gs.players[1].player_id == "p2"
        assert gs.players[2].username == "charlie"
        assert gs.players[2].player_id == "p3"


class TestRoomV2SubmitMove:
    """提交动作测试。"""

    def test_submit_move(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "PO")
        p1 = room.game_state.get_player("p1")
        assert p1.move_submitted
        assert p1.pending_move == "PO"

    def test_cannot_submit_twice(self):
        room, _, tok1 = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "PO")
        with pytest.raises(ValueError, match="已经提交过动作"):
            room.submit_move(tok1, "QI")

    def test_all_moves_submitted(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        _, tok3 = room.add_player("charlie")
        _, tok4 = room.add_player("dave")
        room.start_game()

        assert not room.all_moves_submitted()
        room.submit_move(tok1, "QI")
        room.submit_move(tok2, "QI")
        assert not room.all_moves_submitted()
        room.submit_move(tok3, "QI")
        room.submit_move(tok4, "QI")
        assert room.all_moves_submitted()

    def test_dead_player_cannot_submit(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.game_state.get_player("p2").mark_dead(1, "normal")

        with pytest.raises(ValueError, match="已淘汰"):
            room.submit_move(tok2, "QI")


class TestRoomV2CancelMove:
    """撤回动作测试 —— 阶段 B。"""

    # ── 模型层单元测试 ──

    def test_cancel_submitted_move_basic(self):
        """提交动作 → 撤回 → pending_move 清空、move_submitted 为 False。"""
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "QI")
        p1 = room.game_state.get_player("p1")
        assert p1.move_submitted
        assert p1.pending_move == "QI"

        success, msg = room.cancel_submitted_move(tok1)
        assert success
        assert "已撤回" in msg
        assert not p1.move_submitted
        assert p1.pending_move is None

    def test_cancel_then_submit_again(self):
        """撤回后可以再次提交动作。"""
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "QI")
        room.cancel_submitted_move(tok1)
        # 再次提交不应报错
        room.submit_move(tok1, "PO")
        assert room.game_state.get_player("p1").pending_move == "PO"

    def test_cancel_when_not_submitted(self):
        """未提交时撤回应返回 False 和错误消息。"""
        room, _, tok1 = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()

        success, msg = room.cancel_submitted_move(tok1)
        assert not success
        assert "没有已提交" in msg or "未提交" in msg

    def test_cancel_after_settlement_begins(self):
        """进入结算后（phase 不是 waiting_moves）撤回应返回 False。"""
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "QI")
        room.submit_move(tok2, "QI")

        # 模拟进入结算阶段
        room.game_state.phase = "speed_layer"

        success, msg = room.cancel_submitted_move(tok1)
        assert not success
        assert "已经进入结算" in msg or "不能撤回" in msg

    def test_dead_player_cannot_cancel(self):
        """死亡玩家不能撤回动作。"""
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok2, "QI")
        room.game_state.get_player("p2").mark_dead(1, "normal")

        success, msg = room.cancel_submitted_move(tok2)
        assert not success

    def test_cancel_one_player_does_not_affect_others(self):
        """P1 撤回不影响 P2 已提交状态。"""
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "QI")
        room.submit_move(tok2, "PO")

        # P1 撤回
        room.cancel_submitted_move(tok1)

        # P2 仍然已提交
        p2 = room.game_state.get_player("p2")
        assert p2.move_submitted
        assert p2.pending_move == "PO"

        # all_moves_submitted 应回到 False
        assert not room.all_moves_submitted()

    def test_cancel_then_resubmit_all_triggers_settlement(self):
        """P1 撤回后再提交，全部提交后 all_moves_submitted 回到 True。"""
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        _, tok3 = room.add_player("charlie")
        room.start_game()

        room.submit_move(tok1, "QI")
        room.submit_move(tok2, "QI")
        room.submit_move(tok3, "QI")
        assert room.all_moves_submitted()

        # P1 撤回 → 不再全部提交
        room.cancel_submitted_move(tok1)
        assert not room.all_moves_submitted()

        # P1 重新提交 → 恢复全部提交
        room.submit_move(tok1, "QI")
        assert room.all_moves_submitted()

    def test_cancel_invalid_token(self):
        """非法 token 撤回应返回 False。"""
        room, _, tok1 = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()

        success, msg = room.cancel_submitted_move("bad-token")
        assert not success
        assert "身份无效" in msg

    def test_cancel_spectator(self):
        """观战者不能撤回动作。"""
        room, _, _ = create_room_v2("alice")
        room.add_player("bob")
        room.start_game()

        spec_token = room.add_spectator("viewer")
        success, msg = room.cancel_submitted_move(spec_token)
        assert not success
        assert "身份无效" in msg


class TestRoomV2CancelMoveAPI:
    """撤回动作 HTTP API 集成测试。"""

    def setup_method(self):
        with ROOMS_V2_LOCK:
            ROOMS_V2.clear()

    def test_cancel_step_api_success(self):
        """cancel-step API 成功返回 ok=True 和正确的 room payload。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"csl_a_{uid}", "test", verified="1")
            users.register(f"csl_b_{uid}", "test", verified="1")
            token_a = users.login(f"csl_a_{uid}", "test")["session_token"]
            token_b = users.login(f"csl_b_{uid}", "test")["session_token"]

        client = app.test_client()

        # 创建房间
        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        data = resp.get_json()
        assert data["ok"]
        room_id = data["room"]["room_id"]
        pt_a = data["player_token"]

        # 加入
        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        # 准备 + 开始
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 提交动作
        resp = client.post(f"/v2/api/rooms/{room_id}/step",
                           json={"player_token": pt_a, "move_name": "QI"})
        assert resp.get_json()["ok"]

        # 撤回动作
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": pt_a})
        data = resp.get_json()
        assert data["ok"]
        assert "已撤回" in data["message"]
        assert data["room"] is not None
        # requester 视角下自己的 pending_move 应为空
        own_player = _find_player_in_payload(data["room"]["game"]["players"], "p1")
        assert own_player is not None
        assert own_player["pending_move"] is None

    def test_cancel_step_then_submit_again(self):
        """撤回后可以再次提交动作。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"csa_a_{uid}", "test", verified="1")
            users.register(f"csa_b_{uid}", "test", verified="1")
            token_a = users.login(f"csa_a_{uid}", "test")["session_token"]
            token_b = users.login(f"csa_b_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]
        pt_a = resp.get_json()["player_token"]

        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 提交 → 撤回 → 再提交（使用合法动作 SHIELD）
        client.post(f"/v2/api/rooms/{room_id}/step",
                    json={"player_token": pt_a, "move_name": "QI"})
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": pt_a})
        assert resp.get_json()["ok"]

        resp = client.post(f"/v2/api/rooms/{room_id}/step",
                           json={"player_token": pt_a, "move_name": "SHIELD"})
        assert resp.get_json()["ok"]

    def test_cancel_step_settlement_blocked(self):
        """进入结算后 cancel-step 返回错误。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"csb_a_{uid}", "test", verified="1")
            users.register(f"csb_b_{uid}", "test", verified="1")
            token_a = users.login(f"csb_a_{uid}", "test")["session_token"]
            token_b = users.login(f"csb_b_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]
        pt_a = resp.get_json()["player_token"]

        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 双方提交 → 触发结算
        client.post(f"/v2/api/rooms/{room_id}/step",
                    json={"player_token": pt_a, "move_name": "QI"})
        client.post(f"/v2/api/rooms/{room_id}/step",
                    json={"player_token": pt_b, "move_name": "QI"})

        # 进入结算后尝试撤回
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": pt_a})
        data = resp.get_json()
        assert not data["ok"]
        assert resp.status_code == 400
        assert "已经进入结算" in data["error"] or "不能撤回" in data["error"]

    def test_cancel_step_invalid_token(self):
        """非法 player_token 返回 400。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"cst_a_{uid}", "test", verified="1")
            token_a = users.login(f"cst_a_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]
        pt_a = resp.get_json()["player_token"]

        # 加入另一个玩家然后开始
        from app import users as u2
        import uuid as uu
        uid2 = str(uu.uuid4().hex[:8])
        with app.app_context():
            u2.register(f"cst_b_{uid2}", "test", verified="1")
            token_b = u2.login(f"cst_b_{uid2}", "test")["session_token"]

        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 空 token
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": ""})
        assert resp.status_code == 400

        # 错误 token
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": "bad-token-xxxx"})
        data = resp.get_json()
        assert not data["ok"]
        assert resp.status_code == 400

    def test_cancel_step_spectator_blocked(self):
        """观战者提交 cancel-step 返回 400。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"css_a_{uid}", "test", verified="1")
            users.register(f"css_b_{uid}", "test", verified="1")
            users.register(f"css_s_{uid}", "test", verified="1")
            token_a = users.login(f"css_a_{uid}", "test")["session_token"]
            token_b = users.login(f"css_b_{uid}", "test")["session_token"]
            token_s = users.login(f"css_s_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]
        pt_a = resp.get_json()["player_token"]

        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        # 观战者加入
        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": True},
                           headers={"X-Session-Token": token_s})
        spec_token = resp.get_json()["spectator_token"]

        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 观战者尝试撤回
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": spec_token})
        data = resp.get_json()
        assert not data["ok"]
        assert resp.status_code == 400
        assert "身份无效" in data["error"]

    def test_cancel_step_api_payload_has_own_pending_move_cleared(self):
        """cancel-step 成功返回的 room payload 中，requester 的 pending_move 为空。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"cpp_a_{uid}", "test", verified="1")
            users.register(f"cpp_b_{uid}", "test", verified="1")
            token_a = users.login(f"cpp_a_{uid}", "test")["session_token"]
            token_b = users.login(f"cpp_b_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]
        pt_a = resp.get_json()["player_token"]

        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # A 提交动作
        client.post(f"/v2/api/rooms/{room_id}/step",
                    json={"player_token": pt_a, "move_name": "QI"})

        # A 撤回
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": pt_a})
        data = resp.get_json()
        assert data["ok"]

        # 验证 room payload 中 p1 的 pending_move 已清空
        players = data["room"]["game"]["players"]
        p1 = _find_player_in_payload(players, "p1")
        assert p1 is not None
        assert p1["pending_move"] is None

    def test_cancel_step_dead_player_blocked(self):
        """死亡玩家不能通过 API 撤回动作。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"cdd_a_{uid}", "test", verified="1")
            users.register(f"cdd_b_{uid}", "test", verified="1")
            token_a = users.login(f"cdd_a_{uid}", "test")["session_token"]
            token_b = users.login(f"cdd_b_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]
        pt_a = resp.get_json()["player_token"]

        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        pt_b = resp.get_json()["player_token"]

        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 将 P2 标记为死亡
        room = get_room_v2(room_id)
        room.game_state.get_player("p2").mark_dead(1, "normal")
        room.game_state.get_player("p1").pending_move = "QI"
        room.game_state.get_player("p1").move_submitted = True
        persist_room_v2(room)

        # 死亡玩家尝试撤回 → 应被拒绝
        resp = client.post(f"/v2/api/rooms/{room_id}/cancel-step",
                           json={"player_token": pt_b})
        data = resp.get_json()
        assert not data["ok"]
        assert resp.status_code == 400
        assert "已淘汰" in data["error"]


def _find_player_in_payload(players, player_id):
    """在 room payload 的 players 列表中按 player_id 查找。"""
    for p in players:
        if p.get("player_id") == player_id:
            return p
    return None


class TestRoomV2Rematch:
    """重赛投票测试。"""

    def test_rematch_vote_all_yes(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()
        room.game_state.winner = "p1"
        room.status = ROOM_FINISHED

        triggered, msg = room.vote_rematch(tok1, True)
        assert not triggered
        triggered, msg = room.vote_rematch(tok2, True)
        assert triggered
        assert room.status == ROOM_LOBBY
        assert room.game_state is None

    def test_rematch_one_rejects(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()
        room.game_state.winner = "p1"
        room.status = ROOM_FINISHED

        room.vote_rematch(tok1, True)
        triggered, msg = room.vote_rematch(tok2, False)
        assert not triggered
        assert room.rematch_votes == {}


class TestRoomV2Serialization:
    """序列化往返测试。"""

    def test_to_dict_and_back_empty(self):
        room, _, _ = create_room_v2("alice")
        room.add_player("bob")

        d = room.to_dict()
        room2 = RoomV2.from_dict(d)
        assert room2.room_id == room.room_id
        assert room2.player_count() == 2
        assert room2.host_seat_index == 1

    def test_to_dict_and_back_with_game(self):
        room, _, _ = create_room_v2("alice")
        room.add_player("bob")
        room.add_player("charlie")
        room.start_game()

        d = room.to_dict()
        room2 = RoomV2.from_dict(d)
        assert room2.status == ROOM_PLAYING
        assert room2.game_state is not None
        assert len(room2.game_state.players) == 3

    def test_to_dict_and_back_after_seat_reuse(self):
        room, _, tok1 = create_room_v2("alice", max_players=4)
        room.add_player("bob")       # seat 2
        room.add_player("charlie")   # seat 3
        room.remove_player(tok1)     # seat 1 vacated
        room.add_player("dave")      # should take seat 1

        d = room.to_dict()
        room2 = RoomV2.from_dict(d)
        assert room2.player_count() == 3
        assert room2.get_seat_by_username("dave").seat_index == 1
        assert room2.get_seat_by_username("bob").seat_index == 2
        assert room2.get_seat_by_username("charlie").seat_index == 3


class TestRoomV2Manager:
    """room_manager 集成测试。"""

    def setup_method(self):
        with ROOMS_V2_LOCK:
            ROOMS_V2.clear()

    def test_create_and_get(self):
        room, seat_index, token = create_room_v2("alice")
        assert seat_index == 1
        room2 = get_room_v2(room.room_id)
        assert room2 is not None
        assert room2.room_id == room.room_id

    def test_join_room(self):
        room, _, _ = create_room_v2("alice", max_players=3)
        room2, seat_index, token = join_room_v2(room.room_id, "bob")
        assert seat_index == 2
        assert room2.player_count() == 2

    def test_join_with_specific_seat(self):
        room, _, _ = create_room_v2("alice", max_players=4)
        _, seat_index, _ = join_room_v2(room.room_id, "bob", seat_index=4)
        assert seat_index == 4

    def test_join_as_spectator(self):
        room, _, _ = create_room_v2("alice")
        room2, seat_index, token = join_room_v2(room.room_id, "viewer", as_spectator=True)
        assert seat_index == -1
        assert room2.spectator_count() == 1

    def test_join_full_room(self):
        room, _, _ = create_room_v2("alice", max_players=2)
        join_room_v2(room.room_id, "bob")

        with pytest.raises(ValueError, match="参战席位已满"):
            join_room_v2(room.room_id, "charlie")

    def test_join_nonexistent(self):
        with pytest.raises(ValueError, match="房间不存在"):
            join_room_v2("NOEXIST", "alice")

    def test_leave_room(self):
        room, _, _ = create_room_v2("alice")
        _, _, tok2 = join_room_v2(room.room_id, "bob")

        leave_room_v2(room.room_id, tok2)
        room = get_room_v2(room.room_id)
        assert room.player_count() == 1

    def test_persist_and_load(self):
        room, _, _ = create_room_v2("alice")
        room.add_player("bob")
        persist_room_v2(room)

        from app.storage import load_room
        data = load_room(room.room_id)
        assert data is not None
        assert data["rule_version"] == "2.0"
        assert len(data["seats"]) == 2
        assert data["host_seat_index"] == 1

    def test_cleanup_expired(self):
        from datetime import datetime, timedelta, timezone

        room, _, _ = create_room_v2("alice")
        room_id = room.room_id
        room.updated_at = datetime.now(timezone.utc) - timedelta(hours=4)
        persist_room_v2(room)

        deleted = cleanup_expired_rooms_v2()
        assert room_id in deleted
        assert get_room_v2(room_id) is None


class TestRoomV2ProtocolPayload:
    """Step 6 协议载荷测试。"""

    def setup_method(self):
        with ROOMS_V2_LOCK:
            ROOMS_V2.clear()

    def test_room_payload_hides_unrevealed_moves_from_broadcast(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()

        room.submit_move(tok1, "QI")
        room.submit_move(tok2, "SHIELD")

        broadcast_payload = get_room_v2_payload(room)
        broadcast_players = {
            p["player_id"]: p for p in broadcast_payload["game"]["players"]
        }
        assert broadcast_players["p1"]["pending_move"] is None
        assert broadcast_players["p2"]["pending_move"] is None

        own_payload = get_room_v2_payload(room, requester_token=tok1)
        own_players = {
            p["player_id"]: p for p in own_payload["game"]["players"]
        }
        assert own_players["p1"]["pending_move"] == "QI"
        assert own_players["p2"]["pending_move"] is None

    def test_room_payload_does_not_expose_private_tokens(self):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()
        room.status = ROOM_FINISHED
        room.vote_rematch(tok1, True)

        payload = get_room_v2_payload(room, requester_token=tok2)

        assert tok1 not in payload["rematch_votes"]
        assert tok2 not in payload["rematch_votes"]
        assert payload["rematch_votes"] == {"p1": True}

    def test_socket_room_state_is_emitted_per_private_identity(self, monkeypatch):
        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()
        room.submit_move(tok1, "QI")

        emitted = []

        def fake_emit(event, payload, to=None):
            emitted.append((event, payload, to))

        from server import socket_events_v2

        monkeypatch.setattr(socket_events_v2.socketio, "emit", fake_emit)
        socket_events_v2.emit_room_v2_state(room.room_id)

        assert [item[2] for item in emitted] == [
            f"{room.room_id}:player:{tok1}",
            f"{room.room_id}:player:{tok2}",
        ]

        first_payload = emitted[0][1]["room"]["game"]["players"]
        second_payload = emitted[1][1]["room"]["game"]["players"]
        assert {p["player_id"]: p for p in first_payload}["p1"]["pending_move"] == "QI"
        assert {p["player_id"]: p for p in first_payload}["p2"]["pending_move"] is None
        assert {p["player_id"]: p for p in second_payload}["p1"]["pending_move"] is None

    def test_step6_routes_are_under_v2_room_api_prefix(self):
        from server.app import app

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        assert "/v2/api/rooms/<room_id>/decision" in rules
        assert "/v2/api/rooms/<room_id>/decisions" in rules

        client = app.test_client()
        response = client.get("/v2/api/rooms/NOEXIST/decisions")
        assert response.status_code == 404
        assert response.get_json()["error_code"] == "ROOM_NOT_FOUND"

    def test_pending_decisions_endpoint_filters_by_player_token(self):
        from server.app import app

        room, _, tok1 = create_room_v2("alice")
        _, tok2 = room.add_player("bob")
        room.start_game()
        room.game_state.current_decision_requests = [
            DecisionRequest(
                decision_id="target_p1_9",
                decision_type="target_select",
                speed_layer=9,
                player_id="p1",
                options=[DecisionOption(option_id="p2", label="Bob")],
            ),
            DecisionRequest(
                decision_id="target_p2_9",
                decision_type="target_select",
                speed_layer=9,
                player_id="p2",
                options=[DecisionOption(option_id="p1", label="Alice")],
            ),
        ]

        client = app.test_client()
        public_response = client.get(f"/v2/api/rooms/{room.room_id}/decisions")
        public_data = public_response.get_json()
        assert public_response.status_code == 200
        assert public_data["decision_requests"] == []
        assert len(public_data["decision_requests_summary"]) == 2
        assert "options" not in public_data["decision_requests_summary"][0]

        own_response = client.get(
            f"/v2/api/rooms/{room.room_id}/decisions",
            query_string={"player_token": tok1},
        )
        own_data = own_response.get_json()
        assert own_response.status_code == 200
        assert [r["player_id"] for r in own_data["decision_requests"]] == ["p1"]
        assert own_data["decision_requests"][0]["options"][0]["option_id"] == "p2"

        invalid_response = client.get(
            f"/v2/api/rooms/{room.room_id}/decisions",
            query_string={"player_token": "bad-token"},
        )
        assert invalid_response.status_code == 403
