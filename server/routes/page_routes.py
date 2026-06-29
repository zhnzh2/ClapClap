from flask import Blueprint, redirect, render_template, current_app

from app.v1.room_manager import get_room

page_bp = Blueprint("page", __name__)

@page_bp.get("/")
def home():
    return redirect("/v1", code=302)


@page_bp.get("/v1")
def v1_home():
    return render_template(
        "v1/home.html",
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )

@page_bp.get("/v1/local")
def local_mode():
    return render_template("v1/local.html")


@page_bp.get("/v1/rooms")
def rooms_mode():
    return render_template("v1/rooms.html", error_message=None)


@page_bp.get("/v1/match")
def match_mode():
    return render_template(
        "v1/match.html",
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )


@page_bp.get("/v1/rules")
def rules_1_0():
    return render_template("rule.html", version="1.0")


@page_bp.get("/v1/ai")
def ai_mode():
    return render_template("v1/ai.html")


@page_bp.get("/v1/room/<room_id>")
def room_detail(room_id: str):
    room = get_room(room_id)
    if room is None:
        return render_template(
            "v1/rooms.html",
            error_message="房间不存在，可能是房主已退出、房间已失效，或服务刚刚重启。"
        )
    return render_template(
        "v1/room_detail.html",
        room_id=room_id,
        server_boot_id=current_app.config.get("SERVER_BOOT_ID", "")
    )


@page_bp.get("/favicon.ico")
def favicon():
    return "", 204


@page_bp.get("/v1/user/<int:uid>")
def user_page(uid: int):
    """用户主页。"""
    return render_template("v1/user.html", uid=uid)


@page_bp.get("/v1/record/<battle_id>")
def record_page(battle_id: str):
    """对局回放页面。"""
    return render_template("v1/record.html", battle_id=battle_id)
