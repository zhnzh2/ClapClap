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
                    "status": "available",
                    "label": "当前可用",
                    "description": "1.0 人机对战模式，后端自动生成 AI 动作并记录对局。",
                },
                "v2_local": {
                    "status": "available",
                    "label": "2.0 已可用",
                    "description": "2.0 本地多人裁判模式，适合验证速度层结算和完整回合记录。",
                },
                "v2_rooms": {
                    "status": "available",
                    "label": "2.0 已可用",
                    "description": "2.0 多人房间模式，支持参战、观战、决策暂停恢复和聊天。",
                },
                "v2_match": {
                    "status": "available",
                    "label": "2.0 已可用",
                    "description": "2.0 多人匹配队列，按目标人数凑齐后自动创建多人房间。",
                },
                "v2_records": {
                    "status": "available",
                    "label": "2.0 已可用",
                    "description": "2.0 对局记录与回放，展示速度层、冲突、资源变化和最终名次。",
                },
            },
        }
    )
