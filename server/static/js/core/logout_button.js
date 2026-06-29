/**
 * 退出登录按钮共享处理逻辑。
 * 页面中只需放入 id="header-logout-btn" 的按钮即可自动绑定。
 */
(function () {
    function _clearAllUserData() {
        if (window.SessionUtils) {
            window.SessionUtils.clearSession();
        }
        if (window.StorageUtils && typeof window.StorageUtils.clearAllClapClapStorage === "function") {
            window.StorageUtils.clearAllClapClapStorage();
            return;
        }
        var keysToRemove = [
            "clapclap_match_identity",
            "clapclap_match_state",
            "clapclap_server_boot_id",
            "clapclap_v2_match_state",
            "clapclap_ui_settings_v2",
            "clapclap_v2_ui_settings",
            "clapclap_v2_room_ui_settings"
        ];
        try {
            keysToRemove.forEach(function (k) { localStorage.removeItem(k); });
            var keys = Object.keys(localStorage);
            for (var i = 0; i < keys.length; i++) {
                if (keys[i].indexOf("clapclap_room_") === 0) {
                    localStorage.removeItem(keys[i]);
                }
                if (keys[i].indexOf("clapclap_v2_room_") === 0) {
                    localStorage.removeItem(keys[i]);
                }
                if (keys[i].indexOf("clapclap_v2_room_ui_settings") === 0) {
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
                    var versionPrefix = window.location.pathname.indexOf("/v2") === 0 ? "/v2" : "/v1";
                    await window.ApiUtils.apiPost(versionPrefix + "/api/auth/logout", {});
                }
            } catch (e) {
                // 即使 API 调用失败也继续清理
            }
            _clearAllUserData();
            var versionPrefix = window.location.pathname.indexOf("/v2") === 0 ? "/v2" : "/v1";
            window.location.href = versionPrefix + "/login";
        });
    }

    // DOM 加载完成后自动初始化
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
