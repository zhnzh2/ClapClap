from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.matchmaking import load_match_state
from app.room_manager import load_rooms_from_storage
from app.storage import init_storage
from app.users import ensure_admin_account

from server.extensions import socketio
from server.routes import page_bp, local_bp, room_bp, match_bp, status_bp, export_bp, auth_bp

app = Flask(__name__)
app.config["SERVER_BOOT_ID"] = uuid4().hex

socketio.init_app(app)

init_storage()
ensure_admin_account()
load_rooms_from_storage()
load_match_state()

app.register_blueprint(page_bp)
app.register_blueprint(local_bp)
app.register_blueprint(room_bp)
app.register_blueprint(match_bp)
app.register_blueprint(status_bp)
app.register_blueprint(export_bp)
app.register_blueprint(auth_bp)

import server.socket_events  # noqa: F401
import server.backup         # noqa: F401; 在 Flask 就绪后启动备份线程
server.backup.start_backup_thread()

if __name__ == "__main__":
    socketio.run(app, debug=True)
