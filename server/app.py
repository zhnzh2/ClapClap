from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.matchmaking import load_match_state
from app.v2.matchmaking import load_match_state_v2
from app.room_manager import load_rooms_from_storage
from app.v2.room_manager import load_rooms_v2_from_storage
from app.storage import init_storage
from app.users import ensure_admin_account

from server.extensions import socketio
from server.routes import page_bp, local_bp, room_bp, match_bp, status_bp, export_bp, auth_bp, v2_page_bp, v2_local_bp
from server.routes.room_v2_routes import room_v2_bp
from server.routes.match_v2_routes import match_v2_bp

app = Flask(__name__)
app.config["SERVER_BOOT_ID"] = uuid4().hex

socketio.init_app(app)

init_storage()
ensure_admin_account()
load_rooms_from_storage()
load_rooms_v2_from_storage()
load_match_state()
load_match_state_v2()

app.register_blueprint(page_bp)
app.register_blueprint(local_bp)
app.register_blueprint(room_bp)
app.register_blueprint(match_bp)
app.register_blueprint(status_bp)
app.register_blueprint(export_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(room_v2_bp)
app.register_blueprint(v2_page_bp)
app.register_blueprint(v2_local_bp)
app.register_blueprint(match_v2_bp)

import server.socket_events  # noqa: F401
import server.socket_events_v2  # noqa: F401
import server.backup

server.backup.start_backup_thread()

if __name__ == "__main__":
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
