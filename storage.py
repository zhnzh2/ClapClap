from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock


DB_PATH = Path("clapclap.db")
DB_LOCK = RLock()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_storage() -> None:
    with DB_LOCK:
        conn = get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    room_id TEXT PRIMARY KEY,
                    room_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def save_room(room_id: str, room_data: dict) -> None:
    with DB_LOCK:
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO rooms (room_id, room_json)
                VALUES (?, ?)
                ON CONFLICT(room_id) DO UPDATE SET room_json = excluded.room_json
                """,
                (room_id, json.dumps(room_data, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()


def load_room(room_id: str) -> dict | None:
    with DB_LOCK:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT room_json FROM rooms WHERE room_id = ?",
                (room_id,),
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["room_json"])
        finally:
            conn.close()


def load_all_rooms() -> dict[str, dict]:
    with DB_LOCK:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT room_id, room_json FROM rooms").fetchall()
            result: dict[str, dict] = {}
            for row in rows:
                result[row["room_id"]] = json.loads(row["room_json"])
            return result
        finally:
            conn.close()


def save_kv(key: str, value: dict) -> None:
    with DB_LOCK:
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO kv_store (key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                """,
                (key, json.dumps(value, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()


def load_kv(key: str) -> dict | None:
    with DB_LOCK:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT value_json FROM kv_store WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["value_json"])
        finally:
            conn.close()