from __future__ import annotations

from flask import Blueprint, jsonify

status_bp = Blueprint("status", __name__)

@status_bp.get("/api/modes/status")
def api_modes_status():
    return jsonify(
        {
            "ok": True,
            "modes": {
                "local": {
                    "status": "available",
                    "label": "当前可用",
                    "description": "本地双人操作模式，适合体验规则、测试玩法、检查回合结算。",
                },
                "rooms": {
                    "status": "available",
                    "label": "当前可用",
                    "description": "创建或加入房间，与指定玩家进行联机对战。",
                },
                "match": {
                    "status": "available",
                    "label": "当前可用",
                    "description": "进入匹配队列，与在线玩家自动配对。",
                },
                "ai": {
                    "status": "planned",
                    "label": "后续接入",
                    "description": "AI 模式入口已预留，后续接入自动对战。",
                },
            },
        }
    )
