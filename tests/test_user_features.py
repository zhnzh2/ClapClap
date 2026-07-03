from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
import unittest
from uuid import uuid4

from app import battle_recorder, users
from app.v2 import matchmaking as matchmaking_v2
from app.v2.room_manager import ROOMS_V2, create_room_v2, get_room_v2
from server.app import app


class TestUserFeatures(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.user_ids: list[int] = []
        self.battle_ids: set[str] = set()

    def tearDown(self):
        for battle_id in self.battle_ids:
            battle_recorder.delete_battle(battle_id)
        for uid in self.user_ids:
            users.delete_user(uid)

    def _register_and_login(self, username: str, password: str = "old-password"):
        unique_name = f"{username}-{uuid4().hex[:8]}"
        registered = users.register(unique_name, password, verified="1")
        self.assertTrue(registered["ok"], registered)
        self.user_ids.append(registered["user"]["uid"])
        logged_in = users.login(unique_name, password)
        self.assertTrue(logged_in["ok"], logged_in)
        return registered["user"], logged_in["session_token"]

    def _register_with_role(self, username: str, role: str = "user", verified: str = "1"):
        unique_name = f"{username}-{uuid4().hex[:8]}"
        registered = users.register(unique_name, "old-password", verified=verified, role=role)
        self.assertTrue(registered["ok"], registered)
        self.user_ids.append(registered["user"]["uid"])
        logged_in = users.login(unique_name, "old-password")
        self.assertTrue(logged_in["ok"], logged_in)
        return registered["user"], logged_in["session_token"]

    def test_password_change_requires_correct_current_password(self):
        user, token = self._register_and_login("password-user")
        headers = {"X-Session-Token": token}

        missing = self.client.post(
            "/v1/api/auth/update",
            json={"password": "new-password", "confirm_password": "new-password"},
            headers=headers,
        )
        self.assertEqual(missing.status_code, 400)

        wrong = self.client.post(
            "/v1/api/auth/update",
            json={
                "current_password": "wrong-password",
                "password": "new-password",
                "confirm_password": "new-password",
            },
            headers=headers,
        )
        self.assertEqual(wrong.status_code, 403)
        self.assertTrue(users.verify_password(user["uid"], "old-password"))

        changed = self.client.post(
            "/v1/api/auth/update",
            json={
                "current_password": "old-password",
                "password": "new-password",
                "confirm_password": "new-password",
            },
            headers=headers,
        )
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(users.verify_password(user["uid"], "new-password"))

    def test_invalid_password_does_not_partially_update_username(self):
        user, token = self._register_and_login("atomic-update")
        response = self.client.post(
            "/v1/api/auth/update",
            json={
                "username": "should-not-stick",
                "current_password": "old-password",
                "password": "x",
                "confirm_password": "x",
            },
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(users.get_user_by_uid(user["uid"])["username"], user["username"])

    def test_battle_name_collision_preserves_both_records(self):
        first, _ = self._register_and_login("higher-uid")
        second, _ = self._register_and_login("lower-priority")
        moment = datetime.now(timezone.utc)

        first_id = battle_recorder.create_battle({
            "p1": {"username": second["username"], "uid": second["uid"]},
        }, moment)
        second_id = battle_recorder.create_battle({
            "p1": {"username": first["username"], "uid": first["uid"]},
            "p2": {"username": second["username"], "uid": second["uid"]},
        }, moment)
        renamed_id = str(int(first_id) + 1)
        self.battle_ids.update({first_id, renamed_id})

        self.assertEqual(second_id, first_id)
        self.assertIsNotNone(battle_recorder.read_battle(first_id))
        self.assertIsNotNone(battle_recorder.read_battle(renamed_id))

    def test_delete_user_cleans_v2_rooms_and_match_state(self):
        user, _ = self._register_and_login("delete-v2-user")
        room, _, _ = create_room_v2(user["username"], public=True)
        player_token = "cleanup-v2-token-" + uuid4().hex[:8]

        with matchmaking_v2.MATCH_LOCK_V2:
            matchmaking_v2.MATCH_QUEUE_V2.append(matchmaking_v2.WaitingPlayerV2(
                player_name=user["username"],
                player_token=player_token,
                preferred_players=4,
            ))
            matchmaking_v2.PLAYER_MATCH_STATE_V2[player_token] = {
                "status": "queued",
                "player_name": user["username"],
                "preferred_players": 4,
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }

        self.assertIn(room.room_id, ROOMS_V2)
        users.delete_user(user["uid"])

        self.assertIsNone(get_room_v2(room.room_id))
        self.assertNotIn(player_token, matchmaking_v2.PLAYER_MATCH_STATE_V2)
        self.assertFalse(any(
            waiting.player_name == user["username"]
            for waiting in matchmaking_v2.MATCH_QUEUE_V2
        ))

    def test_admin_can_bulk_verify_and_delete_users(self):
        admin, admin_token = self._register_with_role("bulk-admin", role="admin")
        first = users.register(f"bulk-user-a-{uuid4().hex[:8]}", "old-password", verified="0")
        second = users.register(f"bulk-user-b-{uuid4().hex[:8]}", "old-password", verified="0")
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)
        first_uid = first["user"]["uid"]
        second_uid = second["user"]["uid"]
        self.user_ids.extend([first_uid, second_uid])

        verify = self.client.post(
            "/v1/api/admin/users/bulk",
            json={"action": "verify", "uids": [first_uid, second_uid, 0]},
            headers={"X-Session-Token": admin_token},
        )
        self.assertEqual(verify.status_code, 200)
        payload = verify.get_json()
        self.assertEqual(payload["success_count"], 2)
        self.assertEqual(users.get_user_by_uid(first_uid)["verified"], "1")
        self.assertEqual(users.get_user_by_uid(second_uid)["verified"], "1")

        delete = self.client.post(
            "/v1/api/admin/users/bulk",
            json={"action": "delete", "uids": [first_uid, second_uid, 0]},
            headers={"X-Session-Token": admin_token},
        )
        self.assertEqual(delete.status_code, 200)
        payload = delete.get_json()
        self.assertEqual(payload["success_count"], 2)
        self.assertFalse(users.user_exists(first_uid))
        self.assertFalse(users.user_exists(second_uid))
        self.user_ids = [uid for uid in self.user_ids if uid not in {first_uid, second_uid}]

    def test_battle_list_is_paginated(self):
        user, token = self._register_and_login("history-user")
        opponent, _ = self._register_and_login("history-opponent")
        for millisecond in range(5):
            moment = datetime(2026, 6, 19, 12, 0, 0, millisecond * 1000, tzinfo=timezone.utc)
            battle_recorder.create_battle({
                "p1": {"username": user["username"], "uid": user["uid"]},
                "p2": {"username": opponent["username"], "uid": opponent["uid"]},
            }, moment)
            self.battle_ids.add(battle_recorder._timestamp_name(moment))

        response = self.client.get(
            f"/v1/api/user/{user['uid']}/battles?limit=2&offset=1",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["battles"]), 2)
        self.assertEqual(payload["total"], 5)
        self.assertTrue(payload["has_more"])
        self.assertEqual(payload["next_offset"], 3)

    def test_battle_list_filters_by_date_and_opponent(self):
        user, token = self._register_and_login("history-filter-user")
        alpha, _ = self._register_and_login("alpha-opponent")
        beta, _ = self._register_and_login("beta-opponent")

        first_time = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        second_time = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
        first_id = battle_recorder.create_battle({
            "p1": {"username": user["username"], "uid": user["uid"]},
            "p2": {"username": alpha["username"], "uid": alpha["uid"]},
        }, first_time)
        second_id = battle_recorder.create_battle({
            "p1": {"username": user["username"], "uid": user["uid"]},
            "p2": {"username": beta["username"], "uid": beta["uid"]},
        }, second_time)
        self.battle_ids.update({first_id, second_id})

        response = self.client.get(
            f"/v1/api/user/{user['uid']}/battles?date_from=2026-06-01&opponent=beta",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["battles"][0]["battle_id"], second_id)
        self.assertEqual(payload["battles"][0]["date_bucket"], "2026-06")
        self.assertIn(beta["username"], payload["battles"][0]["opponents"])

    def test_v2_battle_record_keeps_full_header_and_round_timeline(self):
        battle_id = battle_recorder.create_battle(
            {
                "p1": {
                    "username": "Alice",
                    "uid": -1,
                    "seat_index": 1,
                    "player_id": "p1",
                    "is_host": True,
                },
                "p2": {
                    "username": "Bob",
                    "uid": -1,
                    "seat_index": 2,
                    "player_id": "p2",
                    "is_host": False,
                },
            },
            rule_version="2.0",
            mode="room",
            seats=[
                {"seat_index": 1, "player_id": "p1", "username": "Alice", "uid": -1, "is_host": True},
                {"seat_index": 2, "player_id": "p2", "username": "Bob", "uid": -1, "is_host": False},
            ],
            host={"seat_index": 1, "player_id": "p1", "username": "Alice", "uid": -1},
            room={"room_id": "ABC123", "max_players": 2, "min_players": 2},
        )
        self.battle_ids.add(battle_id)

        battle_recorder.record_round(battle_id, {
            "round_num": 1,
            "moves": {"p1": "破", "p2": "闪电"},
            "resource_check_ok": {"p1": True, "p2": True},
            "target_declarations_by_layer": {
                "9": {
                    "p1": {"move": "破", "targets": ["p2"], "is_split": False, "split_count": 1},
                    "p2": {"move": "闪电", "targets": ["p1"], "is_split": False, "split_count": 1},
                }
            },
            "conflicts_by_layer": {
                "9": [{
                    "conflict_type": "mutual",
                    "speed_layer": 9,
                    "involved_players": ["p1", "p2"],
                    "details": {"after_negotiation": {"p1": "p2", "p2": "p1"}},
                    "resolved": True,
                }]
            },
            "decision_log": [{
                "speed_layer": 9,
                "player_id": "p1",
                "decision_type": "conflict_resolve",
                "options": [{"id": "p2", "label": "Bob"}],
                "chosen": ["p2"],
                "reason": "玩家确认",
            }],
            "speed_layer_events": [{
                "event_type": "damage",
                "speed_layer": 9,
                "source_player_id": "p1",
                "target_player_id": "p2",
                "detail": "p1 攻击 p2",
                "data": {"damage": 1},
            }],
            "deaths": [{"player_id": "p2", "cause": "normal", "round": 1, "speed_layer": 9}],
            "pre_snapshots": {"p1": {"hp": 1, "qi": 1}, "p2": {"hp": 1, "qi": 0}},
            "post_snapshots": {"p1": {"hp": 1, "qi": 1}, "p2": {"hp": 0, "qi": 0}},
            "rank_updates": {"p1": 1, "p2": 2},
            "winner": "p1",
            "game_ended": True,
        })
        battle_recorder.end_battle(battle_id, "p1")

        data = battle_recorder.read_battle(battle_id)
        self.assertEqual(data["schema_version"], "2.0.0")
        self.assertEqual(data["mode"], "room")
        self.assertEqual(data["mode_label"], "房间对战")
        self.assertEqual(data["room"]["room_id"], "ABC123")
        self.assertEqual(data["host"]["player_id"], "p1")
        self.assertEqual([s["seat_index"] for s in data["seats"]], [1, 2])

        round_data = data["rounds"][0]
        self.assertEqual(round_data["record_schema"], "v2_round_full")
        self.assertEqual(round_data["moves"], {"p1": "破", "p2": "闪电"})
        self.assertEqual(round_data["speed_layers"][0]["layer"], 9)
        self.assertTrue(round_data["speed_layers"][0]["had_conflict"])
        self.assertEqual(round_data["speed_layers"][0]["decisions"][0]["chosen"], ["p2"])
        self.assertEqual(round_data["changes"]["p2"]["hp"]["delta"], -1)
        self.assertEqual(round_data["result"]["rank_updates"], {"p1": 1, "p2": 2})
        self.assertEqual(data["final_result"]["winner"], "p1")
        self.assertEqual(data["final_result"]["rankings"][0]["player_id"], "p1")

    def test_v2_battle_list_includes_summary_and_separate_stats(self):
        alice, token = self._register_and_login("v2-summary-alice")
        bob, _ = self._register_and_login("v2-summary-bob")
        cora, _ = self._register_and_login("v2-summary-cora")

        battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": alice["username"], "uid": alice["uid"], "seat_index": 1, "player_id": "p1"},
                "p2": {"username": bob["username"], "uid": bob["uid"], "seat_index": 2, "player_id": "p2"},
                "p3": {"username": cora["username"], "uid": cora["uid"], "seat_index": 3, "player_id": "p3"},
            },
            rule_version="2.0",
            mode="room",
            seats=[
                {"seat_index": 1, "player_id": "p1", "username": alice["username"], "uid": alice["uid"]},
                {"seat_index": 2, "player_id": "p2", "username": bob["username"], "uid": bob["uid"]},
                {"seat_index": 3, "player_id": "p3", "username": cora["username"], "uid": cora["uid"]},
            ],
            host={"seat_index": 1, "player_id": "p1", "username": alice["username"], "uid": alice["uid"]},
            room={"room_id": "V2STAT", "max_players": 3, "min_players": 3},
        )
        self.battle_ids.add(battle_id)
        battle_recorder.record_round(battle_id, {
            "round_num": 1,
            "moves": {"p1": "气", "p2": "盾", "p3": "破"},
            "pre_snapshots": {},
            "post_snapshots": {},
            "rank_updates": {"p1": 1, "p2": 2, "p3": 3},
            "winner": "p1",
            "game_ended": True,
        })
        battle_recorder.end_battle(battle_id, "p1")

        response = self.client.get(
            f"/v1/api/user/{alice['uid']}/battles",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["stats"]["v1"]["total"], 0)
        self.assertEqual(payload["stats"]["v2"]["total"], 1)
        self.assertEqual(payload["stats"]["v2"]["championships"], 1)
        self.assertEqual(payload["stats"]["v2"]["average_rank"], 1.0)
        self.assertEqual(payload["stats"]["v2"]["by_player_count"]["3"]["total"], 1)

        item = payload["battles"][0]
        self.assertEqual(item["rule_version"], "2.0")
        self.assertEqual(item["player_count"], 3)
        self.assertEqual(item["my_rank"], 1)
        self.assertTrue(item["is_winner"])
        self.assertIn(alice["username"], item["participant_names"])

    def test_ai_battles_are_listed_but_counted_separately(self):
        player, token = self._register_and_login("ai-stats-player")

        battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        self.battle_ids.add(battle_id)
        battle_recorder.set_battle_metadata(battle_id, {
            "opponent_type": "ai",
            "ai_policy_type": "heuristic",
            "ai_difficulty": "normal",
            "ai_model_version": None,
            "ai_seat": "p2",
        })
        battle_recorder.record_round(battle_id, {
            "round_num": 1,
            "p1_move": "GI",
            "p1_move_label": "gi",
            "p2_move": "QI",
            "p2_move_label": "气",
            "winner_after_round": 1,
        })
        battle_recorder.end_battle(battle_id, 1)

        response = self.client.get(
            f"/v1/api/user/{player['uid']}/battles",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["stats"]["v1"]["total"], 0)
        self.assertEqual(payload["stats"]["ai"]["total"], 1)
        self.assertEqual(payload["stats"]["ai"]["wins"], 1)

        item = payload["battles"][0]
        self.assertEqual(item["mode"], "ai")
        self.assertEqual(item["opponent_type"], "ai")
        self.assertEqual(item["ai_difficulty"], "normal")

    def test_user_battles_can_filter_ai_records(self):
        player, token = self._register_and_login("ai-filter-player")

        ai_battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        self.battle_ids.add(ai_battle_id)
        battle_recorder.set_battle_metadata(ai_battle_id, {
            "opponent_type": "ai",
            "ai_policy_type": "heuristic_fallback",
            "ai_difficulty": "hard",
            "ai_seat": "p2",
            "human_seat": "p1",
        })
        battle_recorder.record_round(ai_battle_id, {
            "round_num": 1,
            "human_seat": "p1",
            "ai_seat": "p2",
            "human_move": "QI",
            "ai_move": "GI",
            "p1_move": "QI",
            "p2_move": "GI",
            "winner_after_round": None,
        })

        opponent, _ = self._register_and_login("ai-filter-opponent")
        human_battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": opponent["username"], "uid": opponent["uid"]},
            },
            rule_version="1.0",
            mode="local",
        )
        self.battle_ids.add(human_battle_id)

        response = self.client.get(
            f"/v1/api/user/{player['uid']}/battles?mode=ai&difficulty=hard",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["filtered_stats"]["ai"]["total"], 1)
        self.assertEqual(payload["battles"][0]["battle_id"], ai_battle_id)
        self.assertEqual(payload["battles"][0]["ai_policy_type"], "heuristic_fallback")

    def test_user_battle_zone_summary_respects_filters(self):
        player, token = self._register_and_login("zone-filter-player")
        opponent, _ = self._register_and_login("zone-filter-opponent")

        ai_battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        human_battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": opponent["username"], "uid": opponent["uid"]},
            },
            rule_version="1.0",
            mode="local",
        )
        self.battle_ids.update({ai_battle_id, human_battle_id})
        battle_recorder.set_battle_metadata(ai_battle_id, {
            "opponent_type": "ai",
            "ai_policy_type": "heuristic",
            "ai_difficulty": "normal",
        })

        response = self.client.get(
            f"/v1/api/user/{player['uid']}/battles?mode=ai",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["zone_summary"]["v1_ai"]["total"], 1)
        self.assertEqual(payload["zone_summary"]["v1_human"]["total"], 0)
        self.assertEqual(payload["zone_summary"]["v2_human"]["total"], 0)

    def test_user_battle_days_filter_accepts_naive_start_time(self):
        player, token = self._register_and_login("naive-date-player")

        battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        self.battle_ids.add(battle_id)
        battle_recorder.set_battle_metadata(battle_id, {
            "opponent_type": "ai",
            "ai_difficulty": "normal",
            "start_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        })

        response = self.client.get(
            f"/v1/api/user/{player['uid']}/battles?days=7",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)

    def test_user_can_download_filtered_ai_battles_with_training_samples(self):
        player, token = self._register_and_login("ai-export-player")

        battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        self.battle_ids.add(battle_id)
        battle_recorder.set_battle_metadata(battle_id, {
            "opponent_type": "ai",
            "ai_policy_type": "heuristic",
            "ai_difficulty": "normal",
            "ai_seat": "p2",
            "human_seat": "p1",
        })
        battle_recorder.record_round(battle_id, {
            "round_num": 1,
            "human_seat": "p1",
            "ai_seat": "p2",
            "human_move": "QI",
            "ai_move": "SHIELD",
            "p1_move": "QI",
            "p2_move": "SHIELD",
            "winner_after_round": None,
        })

        response = self.client.get(
            f"/v1/api/user/{player['uid']}/battles/download?mode=ai",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.data), "r") as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn(f"battles/{battle_id}.json", names)
            self.assertIn("training/ai_battle_samples.jsonl", names)

            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["battle_count"], 1)
            self.assertEqual(manifest["training_sample_count"], 1)

            lines = archive.read("training/ai_battle_samples.jsonl").decode("utf-8").strip().splitlines()
            sample = json.loads(lines[0])
            self.assertEqual(sample["battle_id"], battle_id)
            self.assertEqual(sample["human_move"], "QI")
            self.assertEqual(sample["ai_move"], "SHIELD")

    def test_user_can_download_selected_battle_ids_only(self):
        player, token = self._register_and_login("selected-export-player")

        first_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        second_id = battle_recorder.create_battle(
            {
                "p1": {"username": player["username"], "uid": player["uid"]},
                "p2": {"username": "ClapClap AI", "uid": -2},
            },
            rule_version="1.0",
            mode="ai",
        )
        self.battle_ids.update({first_id, second_id})
        for battle_id in (first_id, second_id):
            battle_recorder.set_battle_metadata(battle_id, {
                "opponent_type": "ai",
                "ai_policy_type": "heuristic",
                "ai_difficulty": "normal",
                "ai_seat": "p2",
                "human_seat": "p1",
            })

        response = self.client.get(
            f"/v1/api/user/{player['uid']}/battles/download?mode=ai&ids={first_id}",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)

        with zipfile.ZipFile(io.BytesIO(response.data), "r") as archive:
            names = set(archive.namelist())
            self.assertIn(f"battles/{first_id}.json", names)
            self.assertNotIn(f"battles/{second_id}.json", names)
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["battle_count"], 1)

    def test_user_cannot_download_other_users_battles(self):
        owner, _ = self._register_and_login("download-owner")
        viewer, viewer_token = self._register_and_login("download-viewer")
        self.assertNotEqual(owner["uid"], viewer["uid"])

        response = self.client.get(
            f"/v1/api/user/{owner['uid']}/battles/download",
            headers={"X-Session-Token": viewer_token},
        )
        self.assertEqual(response.status_code, 403)

    def test_multiplayer_battle_moves_to_rub_only_after_all_participants_deleted(self):
        alice, _ = self._register_and_login("rub-v2-alice")
        bob, _ = self._register_and_login("rub-v2-bob")
        cora, _ = self._register_and_login("rub-v2-cora")

        battle_id = battle_recorder.create_battle(
            {
                "p1": {"username": alice["username"], "uid": alice["uid"]},
                "p2": {"username": bob["username"], "uid": bob["uid"]},
                "p3": {"username": cora["username"], "uid": cora["uid"]},
            },
            rule_version="2.0",
            mode="room",
        )
        self.battle_ids.add(battle_id)

        battle_recorder.mark_user_deleted_in_battles(alice["username"], alice["uid"])
        battle_recorder.mark_user_deleted_in_battles(bob["username"], bob["uid"])
        data = battle_recorder.read_battle(battle_id)
        self.assertIsNotNone(data)
        self.assertEqual(data["participants"]["p1"]["status"], "deleted")
        self.assertEqual(data["participants"]["p2"]["status"], "deleted")
        self.assertEqual(data["participants"]["p3"]["status"], "active")

        battle_recorder.mark_user_deleted_in_battles(cora["username"], cora["uid"])
        moved = battle_recorder.read_battle(battle_id)
        self.assertIsNotNone(moved)
        self.assertTrue(all(
            info["status"] == "deleted"
            for info in moved["participants"].values()
        ))


if __name__ == "__main__":
    unittest.main()
