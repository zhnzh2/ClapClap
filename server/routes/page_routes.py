from flask import Blueprint, render_template

from app.room_manager import get_room

page_bp = Blueprint("page", __name__)


@page_bp.get("/")
def home():
    return render_template("home.html")


@page_bp.get("/local")
def local_mode():
    return render_template("local.html")


@page_bp.get("/rooms")
def rooms_mode():
    return render_template("rooms.html", error_message=None)


@page_bp.get("/match")
def match_mode():
    return render_template("match.html")


@page_bp.get("/ai")
def ai_mode():
    return render_template("ai.html")


@page_bp.get("/room/<room_id>")
def room_detail(room_id: str):
    room = get_room(room_id)
    if room is None:
        return render_template(
            "rooms.html",
            error_message="房间不存在。"
        )
    return render_template("room_detail.html", room_id=room_id)


@page_bp.get("/favicon.ico")
def favicon():
    return "", 204