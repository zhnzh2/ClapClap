from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from models import GameState
from state_api import get_game_state_payload, parse_move_name
from game import GameEngine


app = Flask(__name__)

CURRENT_STATE = GameState()

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    return "", 204

@app.get("/state")
def get_state():
    return jsonify(get_game_state_payload(CURRENT_STATE, include_history=True))


@app.post("/reset")
def reset_game():
    global CURRENT_STATE
    CURRENT_STATE = GameState()
    return jsonify(
        {
            "ok": True,
            "message": "游戏已重置。",
            "state": get_game_state_payload(CURRENT_STATE, include_history=True),
        }
    )


@app.post("/step")
def step_game():
    global CURRENT_STATE

    data = request.get_json(silent=True)
    if data is None:
        return jsonify(
            {
                "ok": False,
                "error": "请求体必须是 JSON。"
            }
        ), 400

    p1_move_name = data.get("p1_move")
    p2_move_name = data.get("p2_move")

    if not isinstance(p1_move_name, str) or not isinstance(p2_move_name, str):
        return jsonify(
            {
                "ok": False,
                "error": "必须提供字符串类型的 p1_move 和 p2_move。"
            }
        ), 400

    try:
        p1_move = parse_move_name(p1_move_name)
        p2_move = parse_move_name(p2_move_name)
    except ValueError as exc:
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
            }
        ), 400

    GameEngine.resolve_round(CURRENT_STATE, p1_move, p2_move)

    return jsonify(
        {
            "ok": True,
            "message": "本回合已结算。",
            "state": get_game_state_payload(CURRENT_STATE, include_history=True),
        }
    )


@app.get("/health")
def health_check():
    return jsonify(
        {
            "ok": True,
            "message": "ClapClap server is running."
        }
    )


if __name__ == "__main__":
    app.run(debug=True)