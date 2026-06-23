from __future__ import annotations

from datetime import datetime, timezone
import unittest
from uuid import uuid4

from app import battle_recorder, users
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

    def test_password_change_requires_correct_current_password(self):
        user, token = self._register_and_login("password-user")
        headers = {"X-Session-Token": token}

        missing = self.client.post(
            "/api/auth/update",
            json={"password": "new-password", "confirm_password": "new-password"},
            headers=headers,
        )
        self.assertEqual(missing.status_code, 400)

        wrong = self.client.post(
            "/api/auth/update",
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
            "/api/auth/update",
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
            "/api/auth/update",
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
            f"/api/user/{user['uid']}/battles?limit=2&offset=1",
            headers={"X-Session-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["battles"]), 2)
        self.assertEqual(payload["total"], 5)
        self.assertTrue(payload["has_more"])
        self.assertEqual(payload["next_offset"], 3)


if __name__ == "__main__":
    unittest.main()
