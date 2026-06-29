from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4

from server.app import app
from scripts.validate_data import validate_data_dir


def _make_test_data_root() -> Path:
    root = Path.cwd() / "test_artifacts" / "release-readiness-data" / uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_mode_status_keeps_v1_available_and_exposes_v2_modes():
    client = app.test_client()
    response = client.get("/api/modes/status")
    data = response.get_json()

    assert response.status_code == 200
    assert data["ok"] is True

    modes = data["modes"]
    assert modes["local"]["status"] == "available"
    assert modes["rooms"]["status"] == "available"
    assert modes["match"]["status"] == "available"

    assert modes["v2_local"]["status"] == "available"
    assert modes["v2_rooms"]["status"] == "available"
    assert modes["v2_match"]["status"] == "available"
    assert modes["v2_records"]["status"] == "available"


def test_v1_and_v2_page_routes_are_parallel_not_shadowed():
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/" in rules
    assert "/v1/local" in rules
    assert "/v1/rooms" in rules
    assert "/v1/match" in rules
    assert "/v1/record/<battle_id>" in rules

    assert "/v2" in rules
    assert "/v2/local" in rules
    assert "/v2/rooms" in rules
    assert "/v2/match" in rules
    assert "/v2/record/<battle_id>" in rules


def test_root_redirects_to_v1_and_auth_redirects_stay_versioned():
    client = app.test_client()

    root_response = client.get("/", follow_redirects=False)
    assert root_response.status_code == 302
    assert root_response.headers["Location"] == "/v1"

    legacy_login = client.get("/login", follow_redirects=False)
    assert legacy_login.status_code == 302
    assert legacy_login.headers["Location"] == "/v1/login"

    v2_api_response = client.get("/v2/api/auth/me")
    assert v2_api_response.status_code == 401
    assert v2_api_response.get_json()["redirect"] == "/v2/login"


def test_release_data_validator_accepts_legacy_v1_and_full_v2_records():
    root = _make_test_data_root()
    try:
        data_dir = root / "data"
        battles_dir = data_dir / "battles"
        users_dir = data_dir / "users" / "User_1"
        battles_dir.mkdir(parents=True)
        users_dir.mkdir(parents=True)

        v1_id = "20260626010101001"
        v2_id = "20260626010101002"
        (battles_dir / f"{v1_id}.json").write_text(
            json.dumps({
                "battle_id": v1_id,
                "participants": {
                    "p1": {"username": "Alice", "uid": 1, "status": "active"},
                    "p2": {"username": "Bob", "uid": 2, "status": "active"},
                },
                "rounds": [],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (battles_dir / f"{v2_id}.json").write_text(
            json.dumps({
                "battle_id": v2_id,
                "schema_version": "2.0.0",
                "rule_version": "2.0",
                "mode": "room",
                "participants": {
                    "p1": {"username": "Alice", "uid": 1, "seat_index": 1, "status": "active"},
                    "p2": {"username": "Bob", "uid": 2, "seat_index": 2, "status": "active"},
                    "p3": {"username": "Cora", "uid": 3, "seat_index": 3, "status": "active"},
                },
                "rounds": [{
                    "record_schema": "v2_round_full",
                    "moves": {"p1": "气", "p2": "气", "p3": "气"},
                    "pre_snapshots": {"p1": {"qi": 0}, "p2": {"qi": 0}, "p3": {"qi": 0}},
                    "post_snapshots": {"p1": {"qi": 1}, "p2": {"qi": 1}, "p3": {"qi": 1}},
                    "speed_layers": [],
                }],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        (users_dir / "battles").write_text(f"{v1_id}\n{v2_id}\n", encoding="utf-8")

        db_path = data_dir / "clapclap.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE room_store (room_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT)")
            conn.execute("CREATE TABLE kv_store (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)")
            conn.execute(
                "INSERT INTO room_store (room_id, payload, updated_at) VALUES (?, ?, datetime('now'))",
                (
                    "ABC123",
                    json.dumps({
                        "room_id": "ABC123",
                        "rule_version": "2.0",
                        "seats": [{"seat_index": 1, "username": "Alice"}],
                        "host_seat_index": 1,
                        "min_players": 2,
                        "max_players": 6,
                    }, ensure_ascii=False),
                ),
            )

        report = validate_data_dir(data_dir)

        assert report.ok is True
        assert report.checked_battles == 2
        assert report.checked_rooms == 1
        assert report.checked_user_indexes == 1
        assert report.errors == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_release_data_validator_flags_unknown_rule_version():
    root = _make_test_data_root()
    try:
        data_dir = root / "data"
        battles_dir = data_dir / "battles"
        battles_dir.mkdir(parents=True)
        battle_id = "20260626020202002"
        (battles_dir / f"{battle_id}.json").write_text(
            json.dumps({
                "battle_id": battle_id,
                "rule_version": "9.9",
                "participants": {
                    "p1": {"username": "Alice", "uid": 1},
                    "p2": {"username": "Bob", "uid": 2},
                },
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        report = validate_data_dir(data_dir)

        assert report.ok is False
        assert any("未知 rule_version" in message for message in report.errors)
    finally:
        shutil.rmtree(root, ignore_errors=True)
