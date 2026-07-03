from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from app.storage import DATA_DIR, DB_PATH

status_bp = Blueprint("status", __name__)

# 敏感环境变量关键词：诊断接口不暴露包含这些关键词的值
_SENSITIVE_ENV_KEYWORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "PRIVATE")


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


@status_bp.get("/api/health/diagnostics")
def api_diagnostics():
    """状态诊断接口 — 检查数据存储可读写性，不暴露敏感信息。"""
    checks: dict[str, dict] = {}

    # 1. 检查 users.csv 可读
    users_csv = DATA_DIR / "users" / "users.csv"
    if users_csv.is_file():
        try:
            content = users_csv.read_text(encoding="utf-8")
            line_count = len([l for l in content.splitlines() if l.strip()])
            checks["users_csv"] = {
                "status": "ok",
                "path": str(users_csv),
                "lines": line_count,
            }
        except Exception as exc:
            checks["users_csv"] = {"status": "error", "detail": str(exc)}
    else:
        checks["users_csv"] = {"status": "ok", "detail": "文件不存在（可能尚无注册用户）"}

    # 2. 检查 clapclap.db 可连接
    if DB_PATH.is_file():
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("SELECT 1")
            conn.close()
            checks["database"] = {"status": "ok", "path": str(DB_PATH)}
        except Exception as exc:
            checks["database"] = {"status": "error", "detail": str(exc)}
    else:
        checks["database"] = {"status": "ok", "detail": "数据库文件不存在（可能首次启动）"}

    # 3. 检查 data/battles/ 可写
    battles_dir = DATA_DIR / "battles"
    try:
        battles_dir.mkdir(parents=True, exist_ok=True)
        test_file = battles_dir / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        checks["battles_dir"] = {"status": "ok", "path": str(battles_dir), "writable": True}
    except Exception as exc:
        checks["battles_dir"] = {"status": "error", "path": str(battles_dir), "writable": False, "detail": str(exc)}

    # 4. 环境变量摘要（只报告是否设置，不暴露值）
    env_vars: dict[str, bool] = {}
    relevant_vars = [
        "DATA_DIR", "SECRET_KEY", "BACKUP_GITHUB_TOKEN", "BACKUP_GITHUB_REPO",
        "EXPORT_TOKEN", "CLAPCLAP_AI_INFERENCE_TIMEOUT_MS",
        "OPENROUTER_API_KEY",
    ]
    for var in relevant_vars:
        env_vars[var] = bool(os.environ.get(var, "").strip())

    # 5. SERVER_BOOT_ID
    boot_id = current_app.config.get("SERVER_BOOT_ID", "unknown")

    # 汇总
    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return jsonify({
        "ok": all_ok,
        "server_boot_id": boot_id,
        "data_dir": str(DATA_DIR),
        "checks": checks,
        "env_vars_set": env_vars,
    })


@status_bp.get("/api/health/release-checklist")
def api_release_checklist():
    """发布前检查清单 — 验证关键配置是否存在。"""
    issues: list[str] = []
    warnings: list[str] = []

    # DATA_DIR
    if not os.environ.get("DATA_DIR"):
        issues.append("DATA_DIR 环境变量未设置。线上必须指向 Railway Volume 路径。")

    # SECRET_KEY
    if not os.environ.get("SECRET_KEY"):
        issues.append("SECRET_KEY 环境变量未设置。Flask session 将使用默认密钥，不安全。")

    # 数据目录是否存在
    if not DATA_DIR.exists():
        issues.append(f"DATA_DIR ({DATA_DIR}) 不存在。")

    # 备份配置检查
    if not os.environ.get("BACKUP_GITHUB_TOKEN"):
        warnings.append("BACKUP_GITHUB_TOKEN 未设置，备份功能将禁用。")
    if not os.environ.get("BACKUP_GITHUB_REPO"):
        warnings.append("BACKUP_GITHUB_REPO 未设置，备份功能将禁用。")

    # 导出配置检查
    if not os.environ.get("EXPORT_TOKEN"):
        warnings.append("EXPORT_TOKEN 未设置，导出接口将不可用。")

    # AI API Key
    if not os.environ.get("OPENROUTER_API_KEY"):
        warnings.append("OPENROUTER_API_KEY 未设置，AI 对战将不可用。")

    # 检查是否有硬编码的敏感值（简单启发式）
    # 不做深度扫描，只提示检查
    warnings.append("请确保代码中不包含硬编码的 API Key、token 或密码。")

    passed = len(issues) == 0
    return jsonify({
        "ok": passed,
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "server_boot_id": current_app.config.get("SERVER_BOOT_ID", "unknown"),
        "data_dir": str(DATA_DIR),
    })
