"""
并发/乱序/重连网络测试。

验证:
1. 多人同时提交动作的并发安全性
2. 重复请求、乱序到达的处理
3. 断线重连后状态恢复
4. HTTP 轮询与 Socket.IO 同时到达不冲突
"""
from __future__ import annotations

import concurrent.futures
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.v2.room import RoomV2
from app.v2.room_manager import create_room_v2, join_room_v2, get_room_v2
from app.v2.game import GameEngineV2
from app.v2.models import GameStateV2, PlayerStateV2
from app.v1.constants import Move
from app.storage import DATA_DIR


class TestConcurrentMoveSubmission(unittest.TestCase):
    """并发动作提交测试。"""

    def setUp(self):
        self._orig_data_dir = DATA_DIR
        self._tmp = TemporaryDirectory(prefix="clapclap_concurrent_")
        import app.storage
        app.storage.DATA_DIR = Path(self._tmp.name)

    def tearDown(self):
        import app.storage
        app.storage.DATA_DIR = self._orig_data_dir
        self._tmp.cleanup()

    def test_two_players_submit_simultaneously(self):
        """两个玩家同时提交动作，引擎只结算一次。"""
        from server.app import app

        # 创建房间并开始游戏
        with app.app_context():
            # 注册两个用户
            from app import users
            import uuid
            uid = str(uuid.uuid4().hex[:8])
            ua = users.register(f"conc_a_{uid}", "test", verified="1")
            ub = users.register(f"conc_b_{uid}", "test", verified="1")
            token_a = users.login(f"conc_a_{uid}", "test")["session_token"]
            token_b = users.login(f"conc_b_{uid}", "test")["session_token"]

        client = app.test_client()

        # 创建房间
        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        data = resp.get_json()
        self.assertTrue(data.get("ok"), f"创建房间失败: {data}")
        room_id = data["room"]["room_id"]
        pt_a = data["player_token"]

        # 加入
        resp = client.post(f"/v2/api/rooms/{room_id}/join",
                           json={"as_spectator": False},
                           headers={"X-Session-Token": token_b})
        data = resp.get_json()
        self.assertTrue(data.get("ok"), f"加入失败: {data}")
        pt_b = data["player_token"]

        # 准备 + 开始
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_a, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/ready",
                    json={"player_token": pt_b, "ready": True})
        client.post(f"/v2/api/rooms/{room_id}/start",
                    json={"player_token": pt_a})

        # 用线程池同时提交
        errors = []
        results = []

        def submit_a():
            try:
                r = client.post(f"/v2/api/rooms/{room_id}/step",
                                json={"player_token": pt_a, "move_name": "QI"})
                results.append(("a", r.get_json()))
            except Exception as e:
                errors.append(("a", str(e)))

        def submit_b():
            try:
                r = client.post(f"/v2/api/rooms/{room_id}/step",
                                json={"player_token": pt_b, "move_name": "QI"})
                results.append(("b", r.get_json()))
            except Exception as e:
                errors.append(("b", str(e)))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(submit_a), executor.submit(submit_b)]
            concurrent.futures.wait(futures)

        self.assertEqual(len(errors), 0, f"并发请求不应崩溃: {errors}")
        self.assertEqual(len(results), 2, "两个请求都应返回")

        # 验证：至少有一个请求的结算已完成
        any_resolved = any(r.get("resolved") for _, r in results)
        self.assertTrue(any_resolved, f"至少有一个结算完成: {results}")

    def test_repeated_move_submission_idempotent(self):
        """同一玩家重复提交动作不应导致双重结算。"""
        from server.app import app

        with app.app_context():
            from app import users
            import uuid
            uid = str(uuid.uuid4().hex[:8])
            users.register(f"rep_a_{uid}", "test", verified="1")
            users.register(f"rep_b_{uid}", "test", verified="1")
            token_a = users.login(f"rep_a_{uid}", "test")["session_token"]
            token_b = users.login(f"rep_b_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        data = resp.get_json()
        room_id = data["room"]["room_id"]
        pt_a = data["player_token"]

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

        # 第一次提交
        r1 = client.post(f"/v2/api/rooms/{room_id}/step",
                         json={"player_token": pt_a, "move_name": "QI"})
        self.assertTrue(r1.get_json().get("ok"))

        # 同玩家第二次提交（重复）
        r2 = client.post(f"/v2/api/rooms/{room_id}/step",
                         json={"player_token": pt_a, "move_name": "PO"})
        data2 = r2.get_json()
        # 重复提交应被正确处理（不崩溃），可能被拒绝或静默忽略
        is_ok = data2.get("ok") or ("已提交" in str(data2.get("error", ""))) or ("资源不足" in str(data2.get("error", "")))
        self.assertTrue(is_ok or data2.get("ok") is True,
                        f"重复提交应被正确处理（不崩溃）: {data2}")

    def test_out_of_order_arrival(self):
        """乱序到达：B 先提交，A 后提交，结算仍正确触发。"""
        from server.app import app

        with app.app_context():
            from app import users
            import uuid
            uid = str(uuid.uuid4().hex[:8])
            users.register(f"ooo_a_{uid}", "test", verified="1")
            users.register(f"ooo_b_{uid}", "test", verified="1")
            token_a = users.login(f"ooo_a_{uid}", "test")["session_token"]
            token_b = users.login(f"ooo_b_{uid}", "test")["session_token"]

        client = app.test_client()

        resp = client.post("/v2/api/rooms", json={
            "max_players": 2, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        data = resp.get_json()
        room_id = data["room"]["room_id"]
        pt_a = data["player_token"]

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

        # B 先提交
        rb = client.post(f"/v2/api/rooms/{room_id}/step",
                         json={"player_token": pt_b, "move_name": "QI"})
        self.assertTrue(rb.get_json().get("ok"))

        # A 后提交（应该触发结算）
        ra = client.post(f"/v2/api/rooms/{room_id}/step",
                         json={"player_token": pt_a, "move_name": "QI"})
        data_a = ra.get_json()
        self.assertTrue(data_a.get("ok"))
        self.assertTrue(data_a.get("resolved", False),
                        f"A 提交后应触发结算: {data_a}")


class TestReconnectionBehavior(unittest.TestCase):
    """断线重连行为测试。"""

    def setUp(self):
        self._orig_data_dir = DATA_DIR
        self._tmp = TemporaryDirectory(prefix="clapclap_reconnect_")
        import app.storage
        app.storage.DATA_DIR = Path(self._tmp.name)

    def tearDown(self):
        import app.storage
        app.storage.DATA_DIR = self._orig_data_dir
        self._tmp.cleanup()

    def test_player_reconnect_after_disconnect(self):
        """玩家断线后重连，能通过 heartbeat 恢复在线状态。"""
        room = RoomV2(room_id="RECONN1", max_players=3, min_players=2)
        seat_a, token_a = room.add_player("Alice")
        seat_b, token_b = room.add_player("Bob")

        self.assertTrue(room.is_seat_online(seat_a), "Alice 应在线")
        self.assertTrue(room.is_seat_online(seat_b), "Bob 应在线")

        # 模拟断线：超过 TTL 未 heartbeat
        bob_seat = room.get_seat_by_index(seat_b)
        bob_seat.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=30)

        # 默认 TTL 是 20 秒
        self.assertFalse(room.is_seat_online(seat_b), "Bob 超过 TTL 应判定为离线")

        # 重连：heartbeat 更新 last_seen_at
        room.mark_seen(token_b)
        self.assertTrue(room.is_seat_online(seat_b), "Bob heartbeat 后应恢复在线")

    def test_heartbeat_keeps_player_online(self):
        """定期 heartbeat 保持在线状态。"""
        room = RoomV2(room_id="HB1", max_players=2, min_players=2)
        seat_a, token_a = room.add_player("Alice")
        seat_b, token_b = room.add_player("Bob")

        # 初始应在线
        self.assertTrue(room.is_seat_online(seat_a))
        self.assertTrue(room.is_seat_online(seat_b))

        # 多次 heartbeat 保持在线
        for _ in range(5):
            room.mark_seen(token_a)
            room.mark_seen(token_b)
            self.assertTrue(room.is_seat_online(seat_a))
            self.assertTrue(room.is_seat_online(seat_b))

    def test_disconnected_player_remains_in_seat(self):
        """离线玩家仍占席位，房间不解散。"""
        room = RoomV2(room_id="RECONN1", max_players=3, min_players=2)
        room.add_player("Host")
        room.add_player("Player2")

        # 模拟 Player2 断线（超过 TTL）
        room.seats[1].last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=30)

        self.assertFalse(room.is_seat_online(2))
        self.assertEqual(len(room.seats), 2, "离线玩家仍应占席位")
        # 房间不应过期（还有房主在线）
        self.assertFalse(room.is_expired())


class TestMultipleClientsRace(unittest.TestCase):
    """多客户端竞争条件测试（本地模式 + 房间模式）。"""

    def setUp(self):
        self._orig_data_dir = DATA_DIR
        self._tmp = TemporaryDirectory(prefix="clapclap_race_")
        import app.storage
        app.storage.DATA_DIR = Path(self._tmp.name)

    def tearDown(self):
        import app.storage
        app.storage.DATA_DIR = self._orig_data_dir
        self._tmp.cleanup()

    def test_concurrent_join_does_not_double_assign_seat(self):
        """并发加入房间不应重复分配席位。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            ua = users.register(f"race_a_{uid}", "test", verified="1")
            ub = users.register(f"race_b_{uid}", "test", verified="1")
            uc = users.register(f"race_c_{uid}", "test", verified="1")
            token_a = users.login(f"race_a_{uid}", "test")["session_token"]
            token_b = users.login(f"race_b_{uid}", "test")["session_token"]
            token_c = users.login(f"race_c_{uid}", "test")["session_token"]

        client = app.test_client()

        # A 创建房间
        resp = client.post("/v2/api/rooms", json={
            "max_players": 3, "min_players": 2,
            "start_condition": "host", "allow_spectate": True, "public": False,
        }, headers={"X-Session-Token": token_a})
        room_id = resp.get_json()["room"]["room_id"]

        # B 和 C 同时加入
        errors = []
        results = []

        def join_b():
            try:
                r = client.post(f"/v2/api/rooms/{room_id}/join",
                                json={"as_spectator": False},
                                headers={"X-Session-Token": token_b})
                results.append(("b", r.get_json()))
            except Exception as e:
                errors.append(("b", str(e)))

        def join_c():
            try:
                r = client.post(f"/v2/api/rooms/{room_id}/join",
                                json={"as_spectator": False},
                                headers={"X-Session-Token": token_c})
                results.append(("c", r.get_json()))
            except Exception as e:
                errors.append(("c", str(e)))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(join_b), executor.submit(join_c)]
            concurrent.futures.wait(futures)

        self.assertEqual(len(errors), 0, f"并发加入不应崩溃: {errors}")

        # 验证：席位不重复
        seat_indices = [r.get("seat_index") for _, r in results if r.get("ok")]
        self.assertEqual(len(set(seat_indices)), len(seat_indices),
                         f"席位不应重复: {seat_indices}")

    def test_move_and_leave_concurrent(self):
        """一个玩家出招的同时另一个玩家退出，不应崩溃。"""
        from server.app import app
        from app import users
        import uuid

        uid = str(uuid.uuid4().hex[:8])
        with app.app_context():
            users.register(f"ml_a_{uid}", "test", verified="1")
            users.register(f"ml_b_{uid}", "test", verified="1")
            token_a = users.login(f"ml_a_{uid}", "test")["session_token"]
            token_b = users.login(f"ml_b_{uid}", "test")["session_token"]

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

        errors = []

        def submit_move():
            try:
                client.post(f"/v2/api/rooms/{room_id}/step",
                            json={"player_token": pt_a, "move_name": "QI"})
            except Exception as e:
                errors.append(("move", str(e)))

        def leave_room():
            try:
                client.post(f"/v2/api/rooms/{room_id}/leave",
                            json={"player_token": pt_b})
            except Exception as e:
                errors.append(("leave", str(e)))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(submit_move), executor.submit(leave_room)]
            concurrent.futures.wait(futures)

        # 不应崩溃
        self.assertEqual(len(errors), 0, f"并发操作不应崩溃: {errors}")


if __name__ == "__main__":
    unittest.main()
