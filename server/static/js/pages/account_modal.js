/**
 * 账号管理弹窗。
 * 在任意页面调用 window.AccountModal.open() 打开。
 */
(function () {

    function open() {
        var user = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
        if (!user) {
            window.location.href = "/login";
            return;
        }

        // 获取最新用户信息
        ApiUtils.apiGet("/api/auth/me").then(function (result) {
            if (result.ok && result.data.user) {
                user = result.data.user;
            }
            _renderModal(user);
        }).catch(function () {
            _renderModal(user);
        });
    }

    function _renderModal(user) {
        var existing = document.getElementById("account-modal-mask");
        if (existing) { existing.remove(); }

        var mask = document.createElement("div");
        mask.id = "account-modal-mask";
        mask.className = "modal-mask show";
        mask.style.zIndex = "1000";

        var card = document.createElement("div");
        card.className = "modal-card large";
        card.innerHTML =
            '<div class="modal-title">账号管理</div>' +
            '<div class="account-field-row">' +
            '  <label>UID</label>' +
            '  <input type="text" value="' + _esc(user.uid) + '" disabled style="background:#f3f4f6;color:#6b7280;" />' +
            '</div>' +
            '<div class="account-field-row">' +
            '  <label>用户名</label>' +
            '  <input type="text" id="am-username" value="' + _esc(user.username) + '" placeholder="输入新用户名" />' +
            '</div>' +
            '<div class="account-field-row">' +
            '  <label>新密码</label>' +
            '  <input type="password" id="am-password" placeholder="输入新密码" />' +
            '</div>' +
            '<div class="account-field-row">' +
            '  <label>确认新密码</label>' +
            '  <input type="password" id="am-confirm-password" placeholder="再次输入新密码" />' +
            '</div>' +
            '<div class="account-field-row">' +
            '  <label>介绍信</label>' +
            '  <textarea id="am-intro" placeholder="简单介绍一下自己吧">' + _esc(user.intro || "") + '</textarea>' +
            '</div>' +
            '<div class="account-save-msg" id="am-save-msg"></div>' +
            '<div class="modal-actions">' +
            '  <button class="primary" id="am-save-btn">保存修改</button>' +
            '  <button class="secondary" id="am-logout-btn">退出登录</button>' +
            '  <button class="danger" id="am-delete-btn">注销账号</button>' +
            '</div>';

        mask.appendChild(card);
        document.body.appendChild(mask);

        // 点击弹窗外区域关闭
        mask.addEventListener("click", function (e) {
            if (e.target === mask) { mask.remove(); }
        });

        // 保存
        document.getElementById("am-save-btn").addEventListener("click", async function () {
            var newUsername = (document.getElementById("am-username").value || "").trim();
            var newPassword = document.getElementById("am-password").value || "";
            var confirmPw = document.getElementById("am-confirm-password").value || "";
            var newIntro = (document.getElementById("am-intro").value || "").trim();

            var payload = {};

            if (newUsername && newUsername !== user.username) {
                payload.username = newUsername;
            }
            if (newPassword) {
                if (newPassword !== confirmPw) {
                    _setSaveMsg("两次输入的新密码不一致。", "error");
                    return;
                }
                payload.password = newPassword;
                payload.confirm_password = confirmPw;
            }
            if (newIntro !== (user.intro || "")) {
                payload.intro = newIntro;
            }

            if (Object.keys(payload).length === 0) {
                _setSaveMsg("没有需要保存的修改。", "info");
                return;
            }

            _setSaveMsg("正在保存……", "info");
            var result = await ApiUtils.apiPost("/api/auth/update", payload);

            if (!result.ok) {
                _setSaveMsg(result.error || "保存失败。", "error");
                return;
            }

            // 更新本地缓存的用户信息
            if (result.data.user) {
                var token = SessionUtils.getSessionToken();
                SessionUtils.saveSession(token, result.data.user);
            }

            _setSaveMsg("保存成功！", "success");

            // 如果用户名更新了，刷新弹窗
            if (result.data.user) {
                user = result.data.user;
                setTimeout(function () {
                    mask.remove();
                    _renderModal(user);
                }, 800);
            }
        });

        // 退出登录
        document.getElementById("am-logout-btn").addEventListener("click", async function () {
            await ApiUtils.apiPost("/api/auth/logout", {});
            _clearAllUserData();
            window.location.href = "/login";
        });

        // 注销账号 - 使用警告确认弹窗
        document.getElementById("am-delete-btn").addEventListener("click", function () {
            if (typeof ModalUtils !== "undefined" && ModalUtils.showConfirmModal) {
                ModalUtils.showConfirmModal({
                    title: "注销账号",
                    body: "此操作不可撤销。你的所有数据将被永久删除，包括用户信息、房间记录和匹配状态。确认注销吗？",
                    confirmText: "确认注销",
                    cancelText: "取消",
                    confirmClassName: "danger",
                    onConfirm: _doDelete
                    // 取消时确认弹窗自动关闭，账号弹窗保持不动
                });
            } else {
                if (confirm("确认注销账号？此操作不可撤销。")) {
                    _doDelete();
                }
            }
        });
    }

    async function _doDelete() {
        var result = await ApiUtils.apiPost("/api/auth/delete", {});
        if (!result.ok) {
            if (typeof ModalUtils !== "undefined") {
                ModalUtils.showInfoModal({
                    title: "注销失败",
                    body: result.error || "注销账号失败，请稍后重试。",
                    buttonText: "关闭"
                });
            } else {
                alert(result.error || "注销账号失败。");
            }
            return;
        }
        // 成功：关闭账号弹窗、清理缓存、跳转登录页
        var existing = document.getElementById("account-modal-mask");
        if (existing) { existing.remove(); }
        _clearAllUserData();
        window.location.href = "/login";
    }

    // 清理该用户在本地的所有缓存数据
    function _clearAllUserData() {
        SessionUtils.clearSession();
        // 清理所有 clapclap 相关的 localStorage 键
        var keysToRemove = [
            "clapclap_match_identity",
            "clapclap_match_state",
            "clapclap_server_boot_id",
            "clapclap_ui_settings_v2"
        ];
        try {
            keysToRemove.forEach(function (k) { localStorage.removeItem(k); });
            // 清理所有房间身份（以 clapclap_room_ 开头的键）
            var keys = Object.keys(localStorage);
            for (var i = 0; i < keys.length; i++) {
                if (keys[i].indexOf("clapclap_room_") === 0) {
                    localStorage.removeItem(keys[i]);
                }
            }
        } catch (e) {}
    }

    function _setSaveMsg(text, type) {
        var el = document.getElementById("am-save-msg");
        if (el) {
            el.textContent = text || "";
            el.className = "account-save-msg " + (type || "info");
        }
    }

    // 修复：正确处理 0、false、空字符串
    function _esc(text) {
        if (text === undefined || text === null) { return ""; }
        return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    window.AccountModal = {
        open: open
    };
})();
