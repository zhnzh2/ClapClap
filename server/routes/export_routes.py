from __future__ import annotations

import os

from flask import Blueprint, abort, send_file

from app.storage import DB_PATH

export_bp = Blueprint("export", __name__)

EXPORT_TOKEN = os.environ.get("EXPORT_TOKEN", "").strip()


def _check_token() -> bool:
    """验证导出 token。未配置 token 时始终拒绝。"""
    if not EXPORT_TOKEN:
        return False
    from flask import request

    token = request.args.get("token", "")
    return token == EXPORT_TOKEN


@export_bp.get("/api/export-db")
def api_export_db():
    """下载当前 SQLite 数据库文件。
    需要在请求中附带 ?token=<EXPORT_TOKEN>。
    """
    if not _check_token():
        abort(404)

    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name="clapclap.db",
        mimetype="application/octet-stream",
    )
