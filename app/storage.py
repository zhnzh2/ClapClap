from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "clapclap.db"

def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS room_store (
                room_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )

        conn.commit()

def save_room(room_id: str, payload: str | dict, updated_at: str | None = None) -> None:
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO room_store (room_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (room_id, payload, updated_at),
        )
        conn.commit()

def load_all_rooms() -> dict[str, dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT room_id, payload FROM room_store"
        ).fetchall()

    result: dict[str, dict] = {}

    for row in rows:
        room_id = row["room_id"]
        payload_raw = row["payload"]

        try:
            result[room_id] = json.loads(payload_raw)
        except Exception:
            continue

    return result

def load_room(room_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT payload FROM room_store WHERE room_id = ?",
            (room_id,),
        ).fetchone()

    if row is None:
        return None

    try:
        return json.loads(row["payload"])
    except Exception:
        return None

def delete_room(room_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM room_store WHERE room_id = ?",
            (room_id,),
        )
        conn.commit()

def load_kv(key: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM kv_store WHERE key = ?",
            (key,),
        ).fetchone()

    if row is None:
        return None

    try:
        return json.loads(row["value"])
    except Exception:
        return None

def save_kv(key: str, value) -> None:

    payload = json.dumps(value, ensure_ascii=False)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO kv_store (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, payload),
        )
        conn.commit()

def delete_kv(key: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM kv_store WHERE key = ?",
            (key,),
        )
        conn.commit()