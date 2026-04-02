from __future__ import annotations

from flask import Flask

from app.matchmaking import load_match_state
from app.room_manager import load_rooms_from_storage
from app.storage import init_storage

from server.extensions import socketio
from server.routes import page_bp, local_bp, room_bp, match_bp

app = Flask(__name__)

socketio.init_app(app)

init_storage()
load_rooms_from_storage()
load_match_state()

app.register_blueprint(page_bp)
app.register_blueprint(local_bp)
app.register_blueprint(room_bp)
app.register_blueprint(match_bp)

import server.socket_events  # noqa: F401

if __name__ == "__main__":
    socketio.run(app, debug=True)