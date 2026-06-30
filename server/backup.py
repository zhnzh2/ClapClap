"""
定时将 SQLite 数据库、用户目录和对战记录备份到 GitHub 私有仓库。

环境变量：
  BACKUP_GITHUB_TOKEN     - GitHub Personal Access Token（需要 repo 权限）
  BACKUP_GITHUB_REPO      - 仓库地址，例如 github.com/user/backup.git
  BACKUP_INTERVAL_MINUTES - 备份间隔（分钟），默认 30
  BACKUP_RETENTION_HOURS  - 备份分支保留时间（小时），默认 24

启动方式：在 server/app.py 中调用 start_backup_thread()。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.storage import DATA_DIR, DB_PATH

GITHUB_TOKEN = os.environ.get("BACKUP_GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("BACKUP_GITHUB_REPO", "").strip()
INTERVAL_MINUTES = int(os.environ.get("BACKUP_INTERVAL_MINUTES", "30"))
RETENTION_HOURS = int(os.environ.get("BACKUP_RETENTION_HOURS", "24"))

REPO_DIR = DATA_DIR / "_backup_repo"
BACKUP_FILE = REPO_DIR / "clapclap.db"
BATTLES_BACKUP_DIR = REPO_DIR / "battles"
USERS_BACKUP_DIR = REPO_DIR / "users"

_thread_started = False


def _git(*args: str, cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    """运行 git 命令，统一异常处理。"""
    return subprocess.run(
        ["git", *args],
        cwd=cwd or REPO_DIR,
        capture_output=True,
        text=True,
    )


def _ensure_repo() -> bool:
    """确保备份仓库存在且可推送。首次启动时 clone，之后仅 pull。"""
    if REPO_DIR.exists() and (REPO_DIR / ".git").is_dir():
        # 已存在，尝试 pull
        result = _git("pull", "--ff-only", "origin", "main")
        if result.returncode == 0:
            return True
        # pull 失败则重置为远程最新
        print(f"[backup] pull 失败，重置为远程 origin/main: {result.stderr.strip()}")
        _git("fetch", "origin")
        _git("reset", "--hard", "origin/main")
        return True

    # 首次 clone：确保目标目录干净（git clone 要求目标不存在或为空目录）
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR, ignore_errors=True)
    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    result = subprocess.run(
        ["git", "clone", "--depth", "1", remote_url, str(REPO_DIR)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[backup] clone 失败: {result.stderr.strip()}")
        return False

    # 配置 git 用户
    _git("config", "user.name", "ClapClap Backup Bot")
    _git("config", "user.email", "backup@clapclap.club")

    return True


def _run_backup() -> None:
    """执行一次备份：复制数据 → 提交 → 推送。"""
    if not DB_PATH.exists():
        print("[backup] 数据库文件不存在，跳过")
        return

    # 复制数据库文件和文件系统数据到仓库目录
    shutil.copy2(DB_PATH, BACKUP_FILE)
    for source, target in (
        (DATA_DIR / "battles", BATTLES_BACKUP_DIR),
        (DATA_DIR / "users", USERS_BACKUP_DIR),
    ):
        if target.exists():
            shutil.rmtree(target)
        if source.exists():
            ignore = shutil.ignore_patterns("_backup_repo", "__pycache__", "*.tmp")
            shutil.copytree(source, target, ignore=ignore)

    # 暂存
    result = _git("add", "clapclap.db", "battles", "users")
    if result.returncode != 0:
        print(f"[backup] git add 失败: {result.stderr.strip()}")
        return

    # 检查是否有变更
    diff_result = _git("diff", "--staged", "--quiet")
    if diff_result.returncode == 0:
        # 没有变更
        return

    # 提交
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    result = _git("commit", "-m", f"Backup {timestamp}")
    if result.returncode != 0:
        print(f"[backup] git commit 失败: {result.stderr.strip()}")
        return

    # 推送
    result = _git("push", "origin", "main")
    if result.returncode != 0:
        print(f"[backup] git push 失败: {result.stderr.strip()}")
        return

    print(f"[backup] 备份成功推送: {timestamp}")
    _cleanup_old_commits()


def _cleanup_old_commits() -> None:
    """简单的提交清理：如果提交数超过阈值则发出提示。

    不自动 force push 删除历史，避免破坏远程仓库。
    用户可以在 GitHub 仓库页面手动管理历史。
    """
    # 检查提交数量
    result = _git("rev-list", "--count", "HEAD")
    if result.returncode != 0:
        return
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return

    # 如果提交超过 1000 条，打印提示
    if count > 1000:
        print(
            f"[backup] 提示：备份仓库已有 {count} 条提交。"
            f"可考虑在 GitHub 仓库页面手动清理，或创建新的备份仓库。"
        )


def _backup_loop() -> None:
    """后台备份循环。"""
    print(f"[backup] 备份线程已启动，间隔 {INTERVAL_MINUTES} 分钟")
    print(f"[backup] 目标仓库: github.com/{GITHUB_REPO}")

    # 首次启动稍等一下，等 Flask 完全就绪
    time.sleep(10)

    # 初始化仓库
    if not _ensure_repo():
        print("[backup] 仓库初始化失败，备份线程退出")
        return

    while True:
        try:
            _run_backup()
        except Exception as e:
            print(f"[backup] 备份出错: {e}")

        time.sleep(INTERVAL_MINUTES * 60)


def start_backup_thread() -> bool:
    """启动后台备份线程。返回是否成功启动。"""
    global _thread_started

    if _thread_started:
        return True

    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("[backup] BACKUP_GITHUB_TOKEN 或 BACKUP_GITHUB_REPO 未设置，备份功能禁用")
        return False

    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[backup] 当前环境没有 git，备份功能禁用")
        return False

    _thread_started = True
    thread = threading.Thread(target=_backup_loop, daemon=True, name="backup-thread")
    thread.start()
    return True
