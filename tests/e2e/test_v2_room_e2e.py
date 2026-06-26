"""
ClapClap 2.0 多人房间 E2E 测试。

覆盖流程：创建房间 → 加入 → 准备 → 开始 → 出招 → 结算 → 对局结束 → 回放。

需要: pip install playwright requests && playwright install chromium
运行: python -m pytest tests/e2e/ -v
"""
from __future__ import annotations

import json
import time

import pytest
import requests


# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════

def _guest_login(server: str) -> tuple[requests.Session, dict, str]:
    """访客登录，返回 (session, user, token)。"""
    sess = requests.Session()
    resp = sess.post(f"{server}/api/auth/guest", json={})
    data = resp.json()
    assert data.get("ok"), f"访客登录失败: {data}"
    token = data["session_token"]
    sess.headers["X-Session-Token"] = token
    return sess, data["user"], token


def _create_room(server: str, auth_sess: requests.Session, max_players: int = 4) -> tuple[str, str]:
    """创建 v2 房间，返回 (room_id, player_token)。"""
    resp = auth_sess.post(f"{server}/api/v2/rooms", json={
        "max_players": max_players,
        "min_players": 2,
        "start_condition": "host",
        "allow_spectate": True,
        "public": False,
    })
    data = resp.json()
    assert data.get("ok"), f"创建房间失败: {data}"
    return data["room"]["room_id"], data["player_token"]


def _join_room(server: str, auth_sess: requests.Session, room_id: str,
               seat_index: int | None = None) -> str:
    """加入 v2 房间，返回 player_token。"""
    body = {"as_spectator": False}
    if seat_index is not None:
        body["seat_index"] = seat_index
    resp = auth_sess.post(f"{server}/api/v2/rooms/{room_id}/join", json=body)
    data = resp.json()
    assert data.get("ok"), f"加入房间失败: {data}"
    return data["player_token"]


def _ready_up(server: str, room_id: str, player_token: str) -> None:
    resp = requests.post(f"{server}/api/v2/rooms/{room_id}/ready", json={
        "player_token": player_token, "ready": True,
    })
    data = resp.json()
    assert data.get("ok"), f"准备失败: {data}"


def _start_game(server: str, room_id: str, player_token: str) -> None:
    resp = requests.post(f"{server}/api/v2/rooms/{room_id}/start", json={
        "player_token": player_token,
    })
    data = resp.json()
    assert data.get("ok"), f"开始失败: {data}"


def _submit_move(server: str, room_id: str, player_token: str, move_name: str) -> dict:
    resp = requests.post(f"{server}/api/v2/rooms/{room_id}/step", json={
        "player_token": player_token,
        "move_name": move_name,
    })
    data = resp.json()
    assert data.get("ok"), f"出招失败: {data}"
    return data


def _handle_decisions(server: str, room_id: str, player_token: str) -> dict:
    """如果结算需要决策，自动用默认值提交。"""
    resp = requests.get(f"{server}/api/v2/rooms/{room_id}/decisions",
                        params={"player_token": player_token})
    data = resp.json()
    if not data.get("ok") or not data.get("decision_requests"):
        return data

    # 为每个决策请求选第一个有效选项
    decisions = {}
    for req in data["decision_requests"]:
        pid = req.get("player_id", "")
        dtype = req.get("decision_type", "")
        options = req.get("options", [])
        valid = [o for o in options if o.get("is_valid", True)]
        if dtype == "target_select":
            split = req.get("split_count", 1)
            targets = []
            for i in range(split):
                targets.append(valid[i % len(valid)].get("option_id", ""))
            decisions[pid] = targets
        else:
            decisions[pid] = valid[0].get("option_id", "") if valid else ""

    resp = requests.post(f"{server}/api/v2/rooms/{room_id}/decision", json={
        "player_token": player_token,
        "decisions": decisions,
    })
    return resp.json()


def _get_room_state(server: str, room_id: str) -> dict:
    resp = requests.get(f"{server}/api/v2/rooms/{room_id}")
    return resp.json()


# ═══════════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════════

class TestV2RoomLifecycleE2E:
    """2.0 房间完整生命周期 E2E 测试（API 级别）。"""

    def test_two_player_full_game_flow(self, server):
        """两人完整对局：创建 → 加入 → 准备 → 开始 → 出招 → 结算 → 结束 → 回放。"""
        # ── 登录 ──
        sess_a, user_a, _ = _guest_login(server)
        sess_b, user_b, _ = _guest_login(server)

        # ── 创建/加入房间 ──
        room_id, token_a = _create_room(server, sess_a, max_players=2)
        token_b = _join_room(server, sess_b, room_id)

        # ── 准备 ──
        _ready_up(server, room_id, token_a)
        _ready_up(server, room_id, token_b)

        # ── 开始 ──
        _start_game(server, room_id, token_a)

        # ── 出招 + 结算多回合 ──
        max_rounds = 30
        round_count = 0
        battle_id = None

        for _ in range(max_rounds):
            room = _get_room_state(server, room_id)
            if not room.get("ok"):
                break
            room_data = room.get("room", room)
            status = room_data.get("status", "")
            if status == "finished":
                battle_id = room_data.get("battle_id")
                break

            # 提交动作
            res_a = _submit_move(server, room_id, token_a, "QI")
            res_b = _submit_move(server, room_id, token_b, "QI")

            # 处理决策
            if not res_a.get("resolved"):
                _handle_decisions(server, room_id, token_a)
            if not res_b.get("resolved"):
                _handle_decisions(server, room_id, token_b)

            round_count += 1

        assert round_count > 0, "至少应进行了一回合"
        assert battle_id is not None, "对局结束应有 battle_id"

        # ── 验证回放页可访问 ──
        resp = requests.get(f"{server}/v2/record/{battle_id}")
        assert resp.status_code == 200, f"回放页应返回 200，实际 {resp.status_code}"
        assert "2.0 对局回放" in resp.text, "回放页应包含标题"

        # ── 验证回放 API 返回完整数据 ──
        resp = sess_a.get(f"{server}/api/battles/{battle_id}")
        battle_data = resp.json()
        assert battle_data.get("ok"), f"回放 API 失败: {battle_data}"
        battle = battle_data["battle"]
        assert battle.get("rule_version") == "2.0"
        assert len(battle.get("rounds", [])) == round_count, \
            f"回合数: 预期={round_count} 实际={len(battle.get('rounds', []))}"
        assert "final_result" in battle
        assert "rankings" in battle.get("final_result", {})

    def test_three_player_with_different_moves(self, server):
        """三人不同出招对局。"""
        sess_a, user_a, _ = _guest_login(server)
        sess_b, user_b, _ = _guest_login(server)
        sess_c, user_c, _ = _guest_login(server)

        room_id, token_a = _create_room(server, sess_a, max_players=3)
        token_b = _join_room(server, sess_b, room_id)
        token_c = _join_room(server, sess_c, room_id)

        _ready_up(server, room_id, token_a)
        _ready_up(server, room_id, token_b)
        _ready_up(server, room_id, token_c)
        _start_game(server, room_id, token_a)

        # 每人用不同招式
        moves_cycle = [
            ("QI", "PO", "SHAN_DIAN"),
            ("PO", "QI", "GI"),
            ("QI", "QI", "QI"),
        ]

        round_count = 0
        for cycle in moves_cycle:
            room = _get_room_state(server, room_id)
            room_data = room.get("room", room)
            if room_data.get("status") == "finished":
                break

            _submit_move(server, room_id, token_a, cycle[0])
            _submit_move(server, room_id, token_b, cycle[1])
            _submit_move(server, room_id, token_c, cycle[2])

            _handle_decisions(server, room_id, token_a)
            _handle_decisions(server, room_id, token_b)
            _handle_decisions(server, room_id, token_c)
            round_count += 1

        assert round_count > 0

    def test_replay_page_loads_without_errors(self, server):
        """回放页能正确加载 2.0 对局数据。"""
        sess_a, _, _ = _guest_login(server)
        sess_b, _, _ = _guest_login(server)

        room_id, token_a = _create_room(server, sess_a, max_players=2)
        token_b = _join_room(server, sess_b, room_id)
        _ready_up(server, room_id, token_a)
        _ready_up(server, room_id, token_b)
        _start_game(server, room_id, token_a)

        # 玩到结束
        for _ in range(30):
            room = _get_room_state(server, room_id)
            room_data = room.get("room", room)
            if room_data.get("status") == "finished":
                break
            _submit_move(server, room_id, token_a, "QI")
            _submit_move(server, room_id, token_b, "PO")
            _handle_decisions(server, room_id, token_a)
            _handle_decisions(server, room_id, token_b)

        room = _get_room_state(server, room_id)
        battle_id = room.get("room", {}).get("battle_id")
        assert battle_id, "应对战结束有 battle_id"

        # 验证回放 API 数据结构
        resp = sess_a.get(f"{server}/api/battles/{battle_id}")
        battle = resp.json()["battle"]

        rounds = battle.get("rounds", [])
        assert len(rounds) > 0

        for i, rd in enumerate(rounds):
            assert "moves" in rd, f"第{i+1}回合缺 moves"
            assert "pre_snapshots" in rd, f"第{i+1}回合缺 pre_snapshots"
            assert "post_snapshots" in rd, f"第{i+1}回合缺 post_snapshots"
            assert "speed_layer_events" in rd, f"第{i+1}回合缺 speed_layer_events"

        # 最终结果
        final = battle.get("final_result", {})
        rankings = final.get("rankings", [])
        assert len(rankings) == 2
        assert any(r.get("is_winner") for r in rankings)

    def test_spectator_does_not_affect_game(self, server):
        """观战者加入不影响对局进行。"""
        sess_a, _, _ = _guest_login(server)
        sess_b, _, _ = _guest_login(server)
        sess_spect, _, _ = _guest_login(server)

        room_id, token_a = _create_room(server, sess_a, max_players=2)
        token_b = _join_room(server, sess_b, room_id)
        # 观战者加入
        resp = sess_spect.post(f"{server}/api/v2/rooms/{room_id}/join",
                               json={"as_spectator": True})
        data = resp.json()
        assert data.get("ok"), f"观战加入失败: {data}"

        _ready_up(server, room_id, token_a)
        _ready_up(server, room_id, token_b)
        _start_game(server, room_id, token_a)

        # 玩一回合
        _submit_move(server, room_id, token_a, "QI")
        _submit_move(server, room_id, token_b, "QI")

        # 房间应对战正常进行
        room = _get_room_state(server, room_id)
        assert room.get("ok")
