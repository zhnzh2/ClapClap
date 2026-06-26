"""
E2E 测试共用夹具。

启动 Flask 开发服务器 + 创建测试用户。
需要: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SERVER_URL = "http://127.0.0.1:5000"


def _is_playwright_available():
    try:
        import playwright
        return True
    except ImportError:
        return False


def _find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    """启动 Flask 开发服务器（session 级别，所有测试共享）。"""
    if not _is_playwright_available():
        pytest.skip("Playwright 未安装。运行: pip install playwright && playwright install chromium")

    import socket
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env.setdefault("FLASK_DEBUG", "0")

    server_dir = Path(__file__).resolve().parent.parent.parent / "server"
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", str(port), "--no-debugger"],
        cwd=str(server_dir),
        env={**env, "FLASK_APP": "app.py"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待服务就绪
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            sock.close()
            break
        except OSError:
            time.sleep(0.3)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        pytest.fail(f"服务器未能在 15 秒内启动（端口 {port}）")

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def browser_contexts(server):
    """创建两个独立的浏览器上下文（模拟两个玩家）。"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx1 = browser.new_context()
        ctx2 = browser.new_context()
        yield server, ctx1, ctx2
        browser.close()


@pytest.fixture
def api_session(server):
    """创建一个已认证的 requests 会话。"""
    import requests
    sess = requests.Session()
    # 访客登录
    resp = sess.post(f"{server}/api/auth/guest", json={})
    data = resp.json()
    assert data.get("ok"), f"访客登录失败: {data}"
    token = data["session_token"]
    sess.headers["X-Session-Token"] = token
    return sess, data["user"], token
