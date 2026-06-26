/**
 * 退出登录按钮共享处理逻辑。
 * 页面中只需放入 id="header-logout-btn" 的按钮即可自动绑定。
 */
(function () {
    function _clearAllUserData() {
        if (window.SessionUtils) {
            window.SessionUtils.clearSession();
        }
        var keysToRemove = [
            "clapclap_match_identity",
            "clapclap_match_state",
            "clapclap_server_boot_id",
            "clapclap_ui_settings_v2"
        ];
        try {
            keysToRemove.forEach(function (k) { localStorage.removeItem(k); });
            var keys = Object.keys(localStorage);
            for (var i = 0; i < keys.length; i++) {
                if (keys[i].indexOf("clapclap_room_") === 0) {
                    localStorage.removeItem(keys[i]);
                }
            }
        } catch (e) {}
    }

    function init() {
        var btn = document.getElementById("header-logout-btn");
        if (!btn) return;

        btn.addEventListener("click", async function () {
            btn.disabled = true;
            btn.textContent = "退出中...";
            try {
                if (window.ApiUtils) {
                    await window.ApiUtils.apiPost("/api/auth/logout", {});
                }
            } catch (e) {
                // 即使 API 调用失败也继续清理
            }
            _clearAllUserData();
            window.location.href = "/login";
        });
    }

    // DOM 加载完成后自动初始化
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
