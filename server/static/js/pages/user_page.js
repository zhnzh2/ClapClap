/**
 * 用户主页 JS
 * 负责加载用户信息、切换面板、编辑简介/密码、展示历史对局
 */
(function () {
    "use strict";

    // ── 初始状态 ──────────────────────────────────────────────────

    var uid = window.USER_PAGE_UID;
    var currentUser = null;     // 当前登录用户
    var profile = null;         // 页面展示的用户
    var isOwner = false;        // 当前用户是否就是页面主人
    var activePanel = "info";   // info | settings | battles
    var battlesOffset = 0;
    var battlesPageSize = 50;

    // DOM 缓存
    var $loading = null;
    var $page = null;
    var $error = null;
    var $errorText = null;
    var $content = null;
    var $accountBtn = null;
    var $adminBtn = null;

    // ── 入口 ──────────────────────────────────────────────────────

    document.addEventListener("DOMContentLoaded", function () {
        $loading = document.getElementById("user-page-loading");
        $page = document.getElementById("user-page");
        $error = document.getElementById("user-page-error");
        $errorText = document.getElementById("user-error-text");
        $content = document.getElementById("user-content");
        $accountBtn = document.getElementById("header-account-btn");
        $adminBtn = document.getElementById("header-admin-btn");

        if (uid === undefined || uid === null || uid === "" || isNaN(uid)) {
            showError("无效的用户 ID。");
            return;
        }

        initAccountButton();
        initBackButton();
        initSidebarNav();
        initAdminButton();
        loadPage();
    });

    // ── 账号按钮 ──────────────────────────────────────────────────

    function initAccountButton() {
        var user = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
        if (!user) {
            window.location.href = "/login";
            return;
        }
        currentUser = user;

        // 设置按钮文字为用户名
        if ($accountBtn) {
            $accountBtn.textContent = user.username;
            $accountBtn.addEventListener("click", function () {
                window.location.href = "/user/" + user.uid;
            });
        }
    }

    // ── 管理员按钮 ────────────────────────────────────────────────

    function initAdminButton() {
        if (!$adminBtn) return;
        if (currentUser && (currentUser.role === "admin" || currentUser.role === "站主")) {
            $adminBtn.style.display = "";
            $adminBtn.addEventListener("click", function () {
                if (window.AdminUsersModal) {
                    AdminUsersModal.open();
                }
            });
        }
    }

    // ── 返回按钮 ──────────────────────────────────────────────────

    function initBackButton() {
        var btn = document.getElementById("user-back-btn");
        if (btn) {
            btn.addEventListener("click", function () {
                if (document.referrer && document.referrer.indexOf(location.origin) === 0) {
                    history.back();
                } else {
                    window.location.href = "/";
                }
            });
        }
    }

    // ── 侧边栏导航切换 ────────────────────────────────────────────

    function initSidebarNav() {
        var navItems = document.querySelectorAll(".user-nav-item");
        navItems.forEach(function (item) {
            item.addEventListener("click", function () {
                var panel = this.getAttribute("data-panel");
                switchPanel(panel);
            });
        });
    }

    function switchPanel(panel) {
        activePanel = panel;

        // 更新导航高亮
        document.querySelectorAll(".user-nav-item").forEach(function (item) {
            var p = item.getAttribute("data-panel");
            if (p === panel) {
                item.classList.add("user-nav-item-active");
            } else {
                item.classList.remove("user-nav-item-active");
            }
        });

        // 渲染面板
        renderPanel(panel);
    }

    // ── 页面加载 ──────────────────────────────────────────────────

    function loadPage() {
        showLoading(true);
        showError(null);

        window.ApiUtils.apiGet("/api/user/" + uid)
            .then(function (res) {
                showLoading(false);
                if (!res.ok) {
                    showError(res.error || "加载用户信息失败。");
                    return;
                }
                profile = res.data.user;
                isOwner = currentUser && currentUser.uid === profile.uid;
                showPage();
                renderSidebar();
                renderPanel("info");
            })
            .catch(function () {
                showLoading(false);
                showError("网络错误，无法加载用户信息。");
            });
    }

    // ── 显示切换 ──────────────────────────────────────────────────

    function showLoading(show) {
        if ($loading) $loading.style.display = show ? "flex" : "none";
    }

    function showError(msg) {
        if ($error) {
            $error.style.display = msg ? "flex" : "none";
            if (msg && $errorText) $errorText.textContent = msg;
        }
        if ($page) $page.style.display = msg ? "none" : "";
    }

    function showPage() {
        if ($page) $page.style.display = "";
    }

    // ── 渲染侧边栏 ────────────────────────────────────────────────

    function renderSidebar() {
        if (!profile) return;

        // 头像圆圈
        var avatar = document.getElementById("user-avatar-circle");
        if (avatar) {
            avatar.textContent = (profile.username || "?")[0].toUpperCase();
        }

        // 用户名
        var nameEl = document.getElementById("user-sidebar-name");
        if (nameEl) {
            nameEl.textContent = profile.username || "未知用户";
        }

        // 角色标签
        var roleEl = document.getElementById("user-sidebar-role");
        if (roleEl) {
            var role = profile.role || "用户";
            var roleText = role === "admin" ? "管理员" : (role === "站主" ? "站主" : "用户");
            roleEl.textContent = roleText;
            roleEl.className = "user-sidebar-role";
            if (role === "admin" || role === "站主") {
                roleEl.classList.add(role === "站主" ? "role-owner" : "role-admin");
            }
        }
    }

    // ── 渲染面板 ──────────────────────────────────────────────────

    function renderPanel(panel) {
        if (!$content) return;

        switch (panel) {
            case "info":
                renderInfoPanel();
                break;
            case "settings":
                renderSettingsPanel();
                break;
            case "battles":
                renderBattlesPanel();
                break;
        }
    }

    // ==================================================================
    //  基本信息面板
    // ==================================================================

    function renderInfoPanel() {
        if (!profile) return;

        var createdStr = profile.created_at || "未知";
        // 格式化时间
        try {
            var d = new Date(createdStr);
            if (!isNaN(d.getTime())) {
                createdStr = d.toLocaleString("zh-CN");
            }
        } catch (e) {}

        var roleText = profile.role === "admin" ? "管理员" : (profile.role === "站主" ? "站主" : "用户");

        var html = '<div class="user-panel">';
        html += '<h2 class="user-panel-title">基本信息</h2>';

        // 信息网格
        html += '<div class="info-grid">';
        html += infoItem("UID", String(profile.uid));
        html += infoItem("用户名", escHtml(profile.username || ""));
        html += infoItem("角色", roleText);
        html += infoItem("注册时间", createdStr);
        html += '</div>';

        // 个人简介
        html += '<div class="info-section" id="intro-section">';
        html += '<div class="info-section-header">';
        html += '<span class="info-section-title">个人简介</span>';
        if (isOwner) {
            html += '<button class="info-edit-btn" id="intro-edit-btn" onclick="UserPage._editIntro()">编辑</button>';
        }
        html += '</div>';
        html += '<div class="info-section-body" id="intro-body">';
        html += '<div class="info-section-text">' + escHtml(profile.intro || "暂无简介") + '</div>';
        html += '</div>';
        html += '</div>';

        // 修改密码（仅本人可见）
        if (isOwner) {
            html += '<div class="info-section" id="password-section">';
            html += '<div class="info-section-header">';
            html += '<span class="info-section-title">修改密码</span>';
            html += '<button class="info-edit-btn" id="password-edit-btn" onclick="UserPage._editPassword()">修改</button>';
            html += '</div>';
            html += '<div class="info-section-body" id="password-body">';
            html += '<div class="info-section-text" style="color:var(--muted);">点击"修改"更改密码。</div>';
            html += '</div>';
            html += '</div>';
        }

        html += '</div>';
        $content.innerHTML = html;
    }

    function infoItem(label, value) {
        return '<div class="info-item">'
            + '<span class="info-item-label">' + escHtml(label) + '</span>'
            + '<span class="info-item-value">' + escHtml(value) + '</span>'
            + '</div>';
    }

    // ── 编辑简介 ──────────────────────────────────────────────────

    window.UserPage = window.UserPage || {};

    UserPage._editIntro = function () {
        var body = document.getElementById("intro-body");
        if (!body) return;

        var currentIntro = profile.intro || "";

        body.innerHTML = '<div class="info-edit-form">'
            + '<textarea id="intro-textarea" maxlength="500" placeholder="写一段自我介绍...">' + escHtml(currentIntro) + '</textarea>'
            + '<div class="info-edit-actions">'
            + '<button class="info-save-btn" onclick="UserPage._saveIntro()">保存</button>'
            + '<button class="info-cancel-btn" onclick="UserPage._cancelEditIntro()">取消</button>'
            + '</div>'
            + '<div id="intro-message"></div>'
            + '</div>';

        var ta = document.getElementById("intro-textarea");
        if (ta) ta.focus();
    };

    UserPage._cancelEditIntro = function () {
        var body = document.getElementById("intro-body");
        if (!body) return;
        body.innerHTML = '<div class="info-section-text">' + escHtml(profile.intro || "暂无简介") + '</div>';
    };

    UserPage._saveIntro = function () {
        var ta = document.getElementById("intro-textarea");
        var msgEl = document.getElementById("intro-message");
        if (!ta) return;

        var newIntro = ta.value.trim();
        if (newIntro === (profile.intro || "")) {
            UserPage._cancelEditIntro();
            return;
        }

        window.ApiUtils.apiPost("/api/auth/update", { intro: newIntro })
            .then(function (res) {
                if (!res.ok) {
                    if (msgEl) {
                        msgEl.innerHTML = '<div class="info-message info-message-error">' + escHtml(res.error || "保存失败") + '</div>';
                    }
                    return;
                }
                // 更新本地缓存
                profile.intro = newIntro;
                if (currentUser && currentUser.uid === profile.uid) {
                    currentUser.intro = newIntro;
                    window.SessionUtils.saveSession(
                        window.SessionUtils.getSessionToken(),
                        currentUser
                    );
                }
                // 恢复显示
                var body = document.getElementById("intro-body");
                if (body) {
                    body.innerHTML = '<div class="info-section-text">' + escHtml(newIntro || "暂无简介") + '</div>';
                }
                if (msgEl) {
                    msgEl.innerHTML = '<div class="info-message info-message-success">简介已更新。</div>';
                    setTimeout(function () {
                        if (msgEl) msgEl.innerHTML = "";
                    }, 2000);
                }
            })
            .catch(function () {
                if (msgEl) {
                    msgEl.innerHTML = '<div class="info-message info-message-error">网络错误。</div>';
                }
            });
    };

    // ── 修改密码 ──────────────────────────────────────────────────

    UserPage._editPassword = function () {
        var body = document.getElementById("password-body");
        if (!body) return;

        body.innerHTML = '<div class="info-edit-form">'
            + '<input type="password" id="password-old" placeholder="当前密码" />'
            + '<input type="password" id="password-new" placeholder="新密码" />'
            + '<input type="password" id="password-confirm" placeholder="确认新密码" />'
            + '<div class="info-edit-actions">'
            + '<button class="info-save-btn" onclick="UserPage._savePassword()">保存</button>'
            + '<button class="info-cancel-btn" onclick="UserPage._cancelEditPassword()">取消</button>'
            + '</div>'
            + '<div id="password-message"></div>'
            + '</div>';
    };

    UserPage._cancelEditPassword = function () {
        var body = document.getElementById("password-body");
        if (!body) return;
        body.innerHTML = '<div class="info-section-text" style="color:var(--muted);">点击"修改"更改密码。</div>';
    };

    UserPage._savePassword = function () {
        var oldPwd = document.getElementById("password-old");
        var newPwd = document.getElementById("password-new");
        var confirmPwd = document.getElementById("password-confirm");
        var msgEl = document.getElementById("password-message");

        if (!oldPwd || !newPwd || !confirmPwd) return;

        var oldVal = oldPwd.value;
        var newVal = newPwd.value;
        var confirmVal = confirmPwd.value;

        if (!oldVal || !newVal || !confirmVal) {
            if (msgEl) msgEl.innerHTML = '<div class="info-message info-message-error">请填写所有密码字段。</div>';
            return;
        }

        if (newVal !== confirmVal) {
            if (msgEl) msgEl.innerHTML = '<div class="info-message info-message-error">两次输入的新密码不一致。</div>';
            return;
        }

        window.ApiUtils.apiPost("/api/auth/update", {
            current_password: oldVal,
            password: newVal,
            confirm_password: confirmVal
        })
            .then(function (res) {
                if (!res.ok) {
                    if (msgEl) msgEl.innerHTML = '<div class="info-message info-message-error">' + escHtml(res.error || "修改失败") + '</div>';
                    return;
                }
                UserPage._cancelEditPassword();
                // 在 cancel 后重新设置消息
                var body = document.getElementById("password-body");
                if (body) {
                    body.innerHTML = '<div class="info-section-text" style="color:var(--muted);">密码已成功修改。</div>'
                        + '<div class="info-message info-message-success" style="margin-top:8px;">密码已更新。</div>';
                }
            })
            .catch(function () {
                if (msgEl) msgEl.innerHTML = '<div class="info-message info-message-error">网络错误。</div>';
            });
    };

    // ==================================================================
    //  设置面板
    // ==================================================================

    function renderSettingsPanel() {
        if (!$content) return;

        var html = '<div class="user-panel">';
        html += '<h2 class="user-panel-title">设置</h2>';

        html += '<div class="settings-group">';
        html += '<div class="settings-placeholder">暂无设置项，后续将添加界面偏好等选项。</div>';
        html += '</div>';

        html += '</div>';
        $content.innerHTML = html;
    }

    // ==================================================================
    //  历史对局面板
    // ==================================================================

    function renderBattlesPanel() {
        if (!$content) return;

        battlesOffset = 0;

        $content.innerHTML = '<div class="user-panel">'
            + '<h2 class="user-panel-title">历史对局</h2>'
            + '<div class="battle-list" id="battle-list">'
            + '<div class="battle-list-loading">加载中...</div>'
            + '</div>'
            + '</div>';

        loadBattles(false);
    }

    function loadBattles(append) {
        var listEl = document.getElementById("battle-list");
        if (!listEl) return;

        window.ApiUtils.apiGet(
            "/api/user/" + uid + "/battles?limit=" + battlesPageSize + "&offset=" + battlesOffset
        )
            .then(function (res) {
                if (!res.ok) {
                    listEl.innerHTML = '<div class="battle-list-error">' + escHtml(res.error || "加载失败") + '</div>';
                    return;
                }

                var battles = res.data.battles || [];
                if (!append && battles.length === 0) {
                    listEl.innerHTML = '<div class="battle-list-empty">暂无对局记录。</div>';
                    return;
                }

                if (!append) listEl.innerHTML = "";
                battles.forEach(function (b) {
                    listEl.appendChild(createBattleItem(b));
                });
                battlesOffset = res.data.next_offset || (battlesOffset + battles.length);

                var oldButton = document.getElementById("battle-load-more");
                if (oldButton) oldButton.remove();
                if (res.data.has_more) {
                    var moreButton = document.createElement("button");
                    moreButton.id = "battle-load-more";
                    moreButton.className = "battle-load-more";
                    moreButton.textContent = "加载更多";
                    moreButton.addEventListener("click", function () {
                        moreButton.disabled = true;
                        moreButton.textContent = "加载中...";
                        loadBattles(true);
                    });
                    listEl.appendChild(moreButton);
                }
            })
            .catch(function () {
                if (listEl) {
                    listEl.innerHTML = '<div class="battle-list-error">网络错误。</div>';
                }
            });
    }

    function createBattleItem(b) {
        var result = b.result || "unknown";
        var p1Name = b.p1_name || "P1";
        var p2Name = b.p2_name || "P2";

        // 结果标签映射
        var resultLabels = {
            win: "胜",
            loss: "负",
            draw: "平",
            unknown: "?",
            ongoing: "进行中"
        };
        var resultLabel = resultLabels[result] || "?";

        // 格式化时间
        var timeStr = "";
        try {
            var d = new Date(b.start_time);
            if (!isNaN(d.getTime())) {
                timeStr = d.toLocaleString("zh-CN");
            }
        } catch (e) {
            timeStr = b.start_time || "";
        }

        var roundsText = (b.round_count || 0) + " 回合";

        var div = document.createElement("div");
        div.className = "battle-item";
        div.innerHTML = '<div class="battle-result-badge battle-result-' + result + '">' + escHtml(resultLabel) + '</div>'
            + '<div class="battle-info">'
            + '<div class="battle-info-row">'
            + '<span class="battle-opponent">' + escHtml(p1Name) + ' vs ' + escHtml(p2Name) + '</span>'
            + '<span class="battle-rounds">' + roundsText + '</span>'
            + '</div>'
            + '<div class="battle-info-row">'
            + '<span class="battle-time">' + escHtml(timeStr) + '</span>'
            + '</div>'
            + '</div>'
            + '<span class="battle-result-text result-' + result + '">' + escHtml(resultLabel) + '</span>';

        // 点击跳转到回放页面
        div.addEventListener("click", function () {
            window.location.href = "/record/" + encodeURIComponent(b.battle_id);
        });

        return div;
    }

    // ==================================================================
    //  工具函数
    // ==================================================================

    function escHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

})();
