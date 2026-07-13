"""全项目 pytest 隔离夹具。

每个测试使用独立数据目录，并清理所有进程内运行状态，避免测试顺序、
登录限流、房间、匹配和 Socket 身份相互污染。
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from uuid import uuid4

import pytest


# 在 pytest 导入测试模块（以及 server.app）前先隔离启动期数据目录。
_PYTEST_RUNTIME_ROOT = Path(__file__).resolve().parent / ".pytest_runtime"
_PYTEST_BOOT_DATA_DIR = _PYTEST_RUNTIME_ROOT / f"boot_{uuid4().hex}"
_PYTEST_BOOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(_PYTEST_BOOT_DATA_DIR)


def _remove_tree_with_retries(path: Path) -> None:
    """兼容 Windows / OneDrive 对刚关闭 SQLite 文件的短暂占用。"""
    for attempt in range(8):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.05 * (attempt + 1))


def _clear_runtime_state() -> None:
    from app.v1 import matchmaking as matchmaking_v1
    from app.v1.models import GameState
    from app.v1.room_manager import ROOMS, ROOMS_LOCK, ROOM_RUNTIME_LOCKS
    from app.v2 import matchmaking as matchmaking_v2
    from app.v2.models import GameStateV2
    from app.v2.room_manager import ROOMS_V2, ROOMS_V2_LOCK
    import server.runtime as runtime
    import server.socket_events_v2 as socket_events_v2
    from server.routes import auth_routes

    auth_routes._LOGIN_ATTEMPTS.clear()
    runtime.clear_ai_sessions()
    runtime.clear_local_sessions()

    with runtime.CURRENT_STATE_LOCK:
        runtime.CURRENT_STATE = GameState()
        runtime.CURRENT_BATTLE_ID = None
    with runtime.CURRENT_STATE_V2_LOCK:
        runtime.CURRENT_STATE_V2 = GameStateV2()
        runtime.CURRENT_BATTLE_ID_V2 = None
        runtime.CURRENT_ENGINE_V2 = None
        runtime.CURRENT_V2_PLAYER_TYPES.clear()
        runtime.CURRENT_V2_AI_DIFFICULTY = "normal"

    with ROOMS_LOCK:
        ROOMS.clear()
        ROOM_RUNTIME_LOCKS.clear()
    with matchmaking_v1.MATCH_LOCK:
        matchmaking_v1.MATCH_WAITING = None
        matchmaking_v1.PLAYER_MATCH_STATE.clear()

    with ROOMS_V2_LOCK:
        ROOMS_V2.clear()
    with matchmaking_v2.MATCH_LOCK_V2:
        matchmaking_v2.MATCH_QUEUE_V2.clear()
        matchmaking_v2.PLAYER_MATCH_STATE_V2.clear()

    socket_events_v2._SOCKET_V2_IDENTITIES.clear()
    socket_events_v2._CHAT_V2_RECENT.clear()


@pytest.fixture(autouse=True)
def isolate_test_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request,
):
    """为每个测试切换独立 DATA_DIR，并重置所有共享运行状态。"""
    data_dir = tmp_path / "data"
    users_dir = data_dir / "users"
    battles_dir = data_dir / "battles"
    db_path = data_dir / "clapclap.db"

    monkeypatch.setenv("DATA_DIR", str(data_dir))

    import app.storage as storage
    from app import battle_recorder, users
    import server.backup as backup
    import server.routes.export_routes as export_routes
    import server.routes.status_routes as status_routes

    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", db_path)
    monkeypatch.setattr(users, "DATA_DIR", data_dir)
    monkeypatch.setattr(users, "USERS_DIR", users_dir)
    monkeypatch.setattr(users, "CSV_PATH", users_dir / "users.csv")
    monkeypatch.setattr(battle_recorder, "DATA_DIR", data_dir)
    monkeypatch.setattr(battle_recorder, "BATTLES_DIR", battles_dir)
    monkeypatch.setattr(battle_recorder, "RUB_DIR", battles_dir / "rub")
    monkeypatch.setattr(backup, "DATA_DIR", data_dir)
    monkeypatch.setattr(backup, "DB_PATH", db_path)
    monkeypatch.setattr(backup, "REPO_DIR", data_dir / "_backup_repo")
    monkeypatch.setattr(export_routes, "DB_PATH", db_path)
    monkeypatch.setattr(status_routes, "DATA_DIR", data_dir)
    monkeypatch.setattr(status_routes, "DB_PATH", db_path)

    # 少量旧测试通过 ``from app.storage import DATA_DIR`` 保存了模块局部引用。
    if hasattr(request.module, "DATA_DIR"):
        monkeypatch.setattr(request.module, "DATA_DIR", data_dir)

    users._session_to_uid.clear()
    users._uid_to_session.clear()
    users._session_index_source = None
    storage.init_storage()
    users._ensure_dirs()
    _clear_runtime_state()

    try:
        yield
    finally:
        _clear_runtime_state()
        users._session_to_uid.clear()
        users._uid_to_session.clear()
        users._session_index_source = None


def pytest_sessionfinish(session, exitstatus):
    """清理启动期数据和测试运行根目录。"""
    _remove_tree_with_retries(_PYTEST_RUNTIME_ROOT)
