from __future__ import annotations

import atexit
import signal
from uuid import uuid4

from flask import Flask

from app.matchmaking import load_match_state
from app.room_manager import load_rooms_from_storage
from app.storage import init_storage, DB_PATH

from server.extensions import socketio
from server.routes import page_bp, local_bp, room_bp, match_bp

app = Flask(__name__)
app.config["SERVER_BOOT_ID"] = uuid4().hex

socketio.init_app(app)

init_storage()
load_rooms_from_storage()
load_match_state()

app.register_blueprint(page_bp)
app.register_blueprint(local_bp)
app.register_blueprint(room_bp)
app.register_blueprint(match_bp)

import server.socket_events  # noqa: F401


def cleanup_db_file() -> None:
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"[cleanup] 已删除数据库文件: {DB_PATH}")
    except Exception as exc:
        print(f"[cleanup] 删除数据库文件失败: {exc}")


def handle_exit_signal(signum, frame) -> None:
    cleanup_db_file()
    raise KeyboardInterrupt


atexit.register(cleanup_db_file)
signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)


if __name__ == "__main__":
    socketio.run(app, debug=True)