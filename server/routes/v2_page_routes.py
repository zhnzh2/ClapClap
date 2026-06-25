"""ClapClap 2.0 页面路由。"""

from flask import Blueprint, render_template, current_app

from app.v2.room_manager import get_room_v2

v2_page_bp = Blueprint("v2_page", __name__)


@v2_page_bp.get("/v2")
def v2_home():
    """2.0 入口页（大厅）。"""
    return render_template("v2/home.html")


@v2_page_bp.get("/v2/local")
def v2_local():
    """2.0 本地模拟对战。"""
    return render_template("v2/local.html")


@v2_page_bp.get("/v2/rooms")
def v2_rooms():
    """2.0 多人房间列表/创建/加入页。"""
    return render_template("v2/rooms.html")


@v2_page_bp.get("/v2/room/<room_id>")
def v2_room_detail(room_id: str):
    """2.0 多人房间对战页。"""
    room = get_room_v2(room_id)
    if room is None:
        return render_template(
            "v2/rooms.html",
            error_message="房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。"
        )
    return render_template(
        "v2/room.html",
        room_id=room_id,
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )
