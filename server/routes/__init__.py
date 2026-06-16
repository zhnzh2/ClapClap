from server.routes.page_routes import page_bp
from server.routes.local_routes import local_bp
from server.routes.room_routes import room_bp
from server.routes.match_routes import match_bp
from server.routes.status_routes import status_bp
from server.routes.export_routes import export_bp

__all__ = [
    "page_bp",
    "local_bp",
    "room_bp",
    "match_bp",
    "status_bp",
    "export_bp",
]
