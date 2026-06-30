import os

from flask_socketio import SocketIO

_origins_raw = os.environ.get(
    "SOCKETIO_CORS_ORIGINS",
    "http://127.0.0.1:5000,http://localhost:5000,https://clapclap.club",
)
_cors_origins = [origin.strip() for origin in _origins_raw.split(",") if origin.strip()]

socketio = SocketIO(cors_allowed_origins=_cors_origins, async_mode="threading")
