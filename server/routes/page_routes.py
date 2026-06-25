from flask import Blueprint, render_template, current_app

from app.room_manager import get_room

page_bp = Blueprint("page", __name__)

@page_bp.get("/login")
def login_page():
    return render_template("login.html")


@page_bp.get("/")
def home():
    return render_template(
        "home.html",
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )

@page_bp.get("/local")
def local_mode():
    return render_template("local.html")


@page_bp.get("/rooms")
def rooms_mode():
    return render_template("rooms.html", error_message=None)


@page_bp.get("/match")
def match_mode():
    return render_template(
        "match.html",
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )


@page_bp.get("/rules/1.0")
def rules_1_0():
    return render_template("rule.html", version="1.0")


@page_bp.get("/ai")
def ai_mode():
    return render_template("ai.html")


@page_bp.get("/room/<room_id>")
def room_detail(room_id: str):
    room = get_room(room_id)
    if room is None:
        return render_template(
            "rooms.html",
            error_message="房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。"
        )
    return render_template(
        "room_detail.html",
        room_id=room_id,
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )

@page_bp.get("/favicon.ico")
def favicon():
    return "", 204


@page_bp.get("/user/<int:uid>")
def user_page(uid: int):
    """用户主页。"""
    return render_template("user.html", uid=uid)


@page_bp.get("/record/<battle_id>")
def record_page(battle_id: str):
    """对局回放页面。"""
    return render_template("record.html", battle_id=battle_id)