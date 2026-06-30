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
    var battleFilters = {
        mode: "all",
        result: "all",
        difficulty: "all",
        opponent: "",
        dateFrom: "",
        dateTo: "",
        groupBy: "time",
        q: ""
    };
    var selectedBattleIds = {};

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
            window.location.href = "/v1/login?expired=1";
            return;
        }
        currentUser = user;

        // 设置按钮文字为用户名
        if ($accountBtn) {
            $accountBtn.textContent = user.username;
            $accountBtn.addEventListener("click", function () {
                window.location.href = "/v1/user/" + user.uid;
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
                    window.location.href = "/v1";
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

        window.ApiUtils.apiGet("/v1/api/user/" + uid)
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

        window.ApiUtils.apiPost("/v1/api/auth/update", { intro: newIntro })
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

        window.ApiUtils.apiPost("/v1/api/auth/update", {
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
            + '<div class="battle-stats" id="battle-stats" style="display:none;"></div>'
            + '<div class="battle-tools">'
            + '<div class="battle-filter-grid">'
            + '<label class="battle-filter-field">类型'
            + '<select id="battle-filter-mode">'
            + '<option value="all">全部</option>'
            + '<option value="ai">AI 人机</option>'
            + '<option value="v1">1.0 真人</option>'
            + '<option value="v2">2.0 多人</option>'
            + '<option value="local">本地对战</option>'
            + '<option value="room">房间对战</option>'
            + '</select></label>'
            + '<label class="battle-filter-field">结果'
            + '<select id="battle-filter-result">'
            + '<option value="all">全部</option>'
            + '<option value="win">胜</option>'
            + '<option value="loss">负</option>'
            + '<option value="draw">平</option>'
            + '<option value="ongoing">进行中</option>'
            + '<option value="completed">已结束</option>'
            + '</select></label>'
            + '<label class="battle-filter-field">AI 难度'
            + '<select id="battle-filter-difficulty">'
            + '<option value="all">全部</option>'
            + '<option value="easy">简单</option>'
            + '<option value="normal">普通</option>'
            + '<option value="hard">困难</option>'
            + '</select></label>'
            + '<label class="battle-filter-field">开始日期'
            + '<input id="battle-filter-date-from" type="date" />'
            + '</label>'
            + '<label class="battle-filter-field">结束日期'
            + '<input id="battle-filter-date-to" type="date" />'
            + '</label>'
            + '<label class="battle-filter-field">对手'
            + '<input id="battle-filter-opponent" type="search" maxlength="32" placeholder="对手用户名" />'
            + '</label>'
            + '<label class="battle-filter-field">分类'
            + '<select id="battle-filter-group-by">'
            + '<option value="time">按月份</option>'
            + '<option value="opponent">按对手</option>'
            + '<option value="none">不分类</option>'
            + '</select></label>'
            + '<label class="battle-filter-field keyword">关键词'
            + '<input id="battle-filter-q" type="search" maxlength="40" placeholder="对局 ID / 玩家名 / 策略" />'
            + '</label>'
            + '</div>'
            + '<div class="battle-tool-actions">'
            + '<button class="battle-tool-btn primary" id="battle-apply-filters">应用筛选</button>'
            + '<button class="battle-tool-btn" id="battle-reset-filters">重置</button>'
            + '<button class="battle-tool-btn download" id="battle-download-zip">打包下载</button>'
            + '<button class="battle-tool-btn" id="battle-select-page">全选本页</button>'
            + '<button class="battle-tool-btn download" id="battle-download-selected" disabled>下载选中</button>'
            + '</div>'
            + '<div class="battle-filter-summary" id="battle-filter-summary">可按类型、胜负、时间、对手和 AI 难度筛选历史记录。</div>'
            + '</div>'
            + '<div class="battle-list" id="battle-list">'
            + '<div class="battle-list-loading">加载中...</div>'
            + '</div>'
            + '</div>';

        bindBattleFilterControls();
        loadBattles(false);
    }

    function battleQueryString(offset) {
        var params = new URLSearchParams();
        params.set("limit", String(battlesPageSize));
        params.set("offset", String(offset));
        params.set("mode", battleFilters.mode || "all");
        params.set("result", battleFilters.result || "all");
        params.set("difficulty", battleFilters.difficulty || "all");
        if (battleFilters.opponent) params.set("opponent", battleFilters.opponent);
        if (battleFilters.dateFrom) params.set("date_from", battleFilters.dateFrom);
        if (battleFilters.dateTo) params.set("date_to", battleFilters.dateTo);
        if (battleFilters.q) {
            params.set("q", battleFilters.q);
        }
        return params.toString();
    }

    function readBattleFiltersFromDom() {
        battleFilters = {
            mode: (document.getElementById("battle-filter-mode") || {}).value || "all",
            result: (document.getElementById("battle-filter-result") || {}).value || "all",
            difficulty: (document.getElementById("battle-filter-difficulty") || {}).value || "all",
            opponent: ((document.getElementById("battle-filter-opponent") || {}).value || "").trim(),
            dateFrom: (document.getElementById("battle-filter-date-from") || {}).value || "",
            dateTo: (document.getElementById("battle-filter-date-to") || {}).value || "",
            groupBy: (document.getElementById("battle-filter-group-by") || {}).value || "time",
            q: ((document.getElementById("battle-filter-q") || {}).value || "").trim()
        };
    }

    function setBattleFilterDomValues() {
        var mode = document.getElementById("battle-filter-mode");
        var result = document.getElementById("battle-filter-result");
        var difficulty = document.getElementById("battle-filter-difficulty");
        var opponent = document.getElementById("battle-filter-opponent");
        var dateFrom = document.getElementById("battle-filter-date-from");
        var dateTo = document.getElementById("battle-filter-date-to");
        var groupBy = document.getElementById("battle-filter-group-by");
        var q = document.getElementById("battle-filter-q");
        if (mode) mode.value = battleFilters.mode;
        if (result) result.value = battleFilters.result;
        if (difficulty) difficulty.value = battleFilters.difficulty;
        if (opponent) opponent.value = battleFilters.opponent || "";
        if (dateFrom) dateFrom.value = battleFilters.dateFrom || "";
        if (dateTo) dateTo.value = battleFilters.dateTo || "";
        if (groupBy) groupBy.value = battleFilters.groupBy || "time";
        if (q) q.value = battleFilters.q || "";
    }

    function bindBattleFilterControls() {
        setBattleFilterDomValues();

        var applyBtn = document.getElementById("battle-apply-filters");
        var resetBtn = document.getElementById("battle-reset-filters");
        var downloadBtn = document.getElementById("battle-download-zip");
        var selectPageBtn = document.getElementById("battle-select-page");
        var downloadSelectedBtn = document.getElementById("battle-download-selected");
        var qInput = document.getElementById("battle-filter-q");

        if (applyBtn) {
            applyBtn.addEventListener("click", function () {
                readBattleFiltersFromDom();
                selectedBattleIds = {};
                battlesOffset = 0;
                loadBattles(false);
            });
        }
        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                battleFilters = { mode: "all", result: "all", difficulty: "all", opponent: "", dateFrom: "", dateTo: "", groupBy: "time", q: "" };
                selectedBattleIds = {};
                setBattleFilterDomValues();
                battlesOffset = 0;
                loadBattles(false);
            });
        }
        if (downloadBtn) {
            downloadBtn.addEventListener("click", downloadFilteredBattles);
        }
        if (selectPageBtn) {
            selectPageBtn.addEventListener("click", selectLoadedBattles);
        }
        if (downloadSelectedBtn) {
            downloadSelectedBtn.addEventListener("click", downloadSelectedBattles);
        }
        if (qInput) {
            qInput.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    readBattleFiltersFromDom();
                    selectedBattleIds = {};
                    battlesOffset = 0;
                    loadBattles(false);
                }
            });
        }
    }

    function loadBattles(append) {
        var listEl = document.getElementById("battle-list");
        if (!listEl) return;

        window.ApiUtils.apiGet(
            "/v1/api/user/" + uid + "/battles?" + battleQueryString(battlesOffset)
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
                if (!append) {
                    renderBattleStats(res.data.stats || null);
                    renderBattleFilterSummary(res.data.total || 0, res.data.filtered_stats || null);
                }
                var lastGroup = append ? getLastRenderedBattleGroup(listEl) : null;
                battles.forEach(function (b) {
                    var group = battleGroupLabel(b);
                    if (battleFilters.groupBy !== "none" && group !== lastGroup) {
                        listEl.appendChild(createBattleGroupHeader(group));
                        lastGroup = group;
                    }
                    listEl.appendChild(createBattleItem(b));
                });
                updateSelectedBattleControls();
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

    function renderBattleFilterSummary(total, filteredStats) {
        var el = document.getElementById("battle-filter-summary");
        if (!el) return;

        var aiCount = filteredStats && filteredStats.ai ? (filteredStats.ai.total || 0) : 0;
        var v1Count = filteredStats && filteredStats.v1 ? (filteredStats.v1.total || 0) : 0;
        var v2Count = filteredStats && filteredStats.v2 ? (filteredStats.v2.total || 0) : 0;
        var active = [];
        if (battleFilters.mode !== "all") active.push("类型：" + battleFilters.mode);
        if (battleFilters.result !== "all") active.push("结果：" + battleFilters.result);
        if (battleFilters.difficulty !== "all") active.push("AI 难度：" + difficultyText(battleFilters.difficulty));
        if (battleFilters.dateFrom) active.push("开始：" + battleFilters.dateFrom);
        if (battleFilters.dateTo) active.push("结束：" + battleFilters.dateTo);
        if (battleFilters.opponent) active.push("对手：" + battleFilters.opponent);
        if (battleFilters.q) active.push("关键词：" + battleFilters.q);

        el.textContent = "筛选结果 " + total + " 场"
            + "（1.0 真人 " + v1Count + "，AI " + aiCount + "，2.0 " + v2Count + "）"
            + (active.length ? " · " + active.join(" · ") : " · 当前未启用筛选");
    }

    function downloadFilteredBattles() {
        readBattleFiltersFromDom();
        downloadBattlesZip([], "battle-download-zip");
    }

    function downloadSelectedBattles() {
        readBattleFiltersFromDom();
        downloadBattlesZip(Object.keys(selectedBattleIds), "battle-download-selected");
    }

    function downloadBattlesZip(selectedIds, buttonId) {
        var onlySelected = selectedIds && selectedIds.length > 0;

        var btn = document.getElementById(buttonId);
        if (btn) {
            btn.disabled = true;
            btn.textContent = onlySelected ? "下载中..." : "打包中...";
        }

        var params = new URLSearchParams();
        params.set("mode", battleFilters.mode || "all");
        params.set("result", battleFilters.result || "all");
        params.set("difficulty", battleFilters.difficulty || "all");
        if (battleFilters.opponent) params.set("opponent", battleFilters.opponent);
        if (battleFilters.dateFrom) params.set("date_from", battleFilters.dateFrom);
        if (battleFilters.dateTo) params.set("date_to", battleFilters.dateTo);
        if (battleFilters.q) params.set("q", battleFilters.q);
        if (onlySelected) params.set("ids", selectedIds.join(","));

        var headers = {};
        if (window.SessionUtils) {
            var token = window.SessionUtils.getSessionToken();
            if (token) headers["X-Session-Token"] = token;
        }

        fetch("/v1/api/user/" + uid + "/battles/download?" + params.toString(), {
            method: "GET",
            headers: headers
        })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (data) {
                        throw new Error((data && data.error) || "下载失败。");
                    }).catch(function (error) {
                        throw error;
                    });
                }
                return response.blob();
            })
            .then(function (blob) {
                var url = URL.createObjectURL(blob);
                var a = document.createElement("a");
                a.href = url;
                a.download = onlySelected
                    ? "clapclap_selected_battles_uid" + uid + ".zip"
                    : "clapclap_battles_uid" + uid + ".zip";
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
                var summary = document.getElementById("battle-filter-summary");
                if (summary) summary.textContent += onlySelected ? " · 已开始下载选中对局" : " · 已开始下载 ZIP";
            })
            .catch(function (error) {
                var summary = document.getElementById("battle-filter-summary");
                if (summary) summary.textContent = error.message || "下载失败。";
            })
            .finally(function () {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = onlySelected ? "下载选中" : "打包下载";
                    updateSelectedBattleControls();
                }
            });
    }

    function selectLoadedBattles() {
        document.querySelectorAll(".battle-select-checkbox").forEach(function (input) {
            var bid = input.getAttribute("data-battle-id");
            if (bid) {
                selectedBattleIds[bid] = true;
                input.checked = true;
            }
        });
        updateSelectedBattleControls();
    }

    function updateSelectedBattleControls() {
        var count = Object.keys(selectedBattleIds).length;
        var btn = document.getElementById("battle-download-selected");
        var summary = document.getElementById("battle-filter-summary");
        if (btn) {
            btn.disabled = count === 0;
            btn.textContent = count ? ("下载选中 " + count) : "下载选中";
        }
        if (summary && count) {
            summary.setAttribute("data-selected-text", "已选 " + count + " 场");
        }
    }

    function createBattleGroupHeader(label) {
        var div = document.createElement("div");
        div.className = "battle-group-header";
        div.setAttribute("data-group-label", label);
        div.textContent = label;
        return div;
    }

    function getLastRenderedBattleGroup(listEl) {
        var headers = listEl.querySelectorAll(".battle-group-header");
        if (!headers.length) return null;
        return headers[headers.length - 1].getAttribute("data-group-label");
    }

    function battleGroupLabel(b) {
        if (battleFilters.groupBy === "opponent") {
            var opponents = b.opponents || [];
            if (opponents.length) return "对手：" + opponents.join("、");
            return "对手：未知";
        }
        if (battleFilters.groupBy === "time") {
            return b.date_bucket || "未知时间";
        }
        return "";
    }

    function renderBattleStats(stats) {
        var el = document.getElementById("battle-stats");
        if (!el || !stats) return;

        var v1 = stats.v1 || {};
        var ai = stats.ai || {};
        var v2 = stats.v2 || {};
        var v2Avg = v2.average_rank == null ? "—" : v2.average_rank;
        var v2Rates = v2.total
            ? Math.round((v2.championships || 0) * 100 / v2.total) + "%"
            : "—";

        var byCount = v2.by_player_count || {};
        var countKeys = Object.keys(byCount).sort(function (a, b) { return parseInt(a) - parseInt(b); });
        var countHtml = countKeys.length
            ? countKeys.map(function (key) {
                var item = byCount[key];
                var avg = item.average_rank == null ? "—" : item.average_rank;
                return '<span class="battle-stat-pill">' + item.player_count + '人局 '
                    + item.total + '场 · 冠军 ' + item.championships + ' · 平均 ' + avg + '</span>';
            }).join("")
            : '<span class="battle-stat-pill muted">暂无 2.0 分人数统计</span>';

        el.innerHTML = '<div class="battle-stat-card">'
            + '<div class="battle-stat-title">1.0 双人战绩</div>'
            + '<div class="battle-stat-main">' + (v1.total || 0) + ' 场</div>'
            + '<div class="battle-stat-sub">胜 ' + (v1.wins || 0)
            + ' · 负 ' + (v1.losses || 0)
            + ' · 平 ' + (v1.draws || 0)
            + (v1.ongoing ? ' · 进行中 ' + v1.ongoing : '')
            + '</div>'
            + '</div>'
            + '<div class="battle-stat-card">'
            + '<div class="battle-stat-title">AI 人机对战</div>'
            + '<div class="battle-stat-main">' + (ai.total || 0) + ' 场</div>'
            + '<div class="battle-stat-sub">胜 ' + (ai.wins || 0)
            + ' · 负 ' + (ai.losses || 0)
            + ' · 平 ' + (ai.draws || 0)
            + (ai.ongoing ? ' · 进行中 ' + ai.ongoing : '')
            + '</div>'
            + '</div>'
            + '<div class="battle-stat-card accent">'
            + '<div class="battle-stat-title">2.0 多人战绩</div>'
            + '<div class="battle-stat-main">' + (v2.total || 0) + ' 场 · 冠军 ' + (v2.championships || 0) + '</div>'
            + '<div class="battle-stat-sub">冠军率 ' + v2Rates + ' · 平均名次 ' + v2Avg + '</div>'
            + '<div class="battle-stat-pills">' + countHtml + '</div>'
            + '</div>';
        el.style.display = "";
    }

    function createBattleItem(b) {
        var isV2 = b.rule_version && String(b.rule_version).startsWith("2.");
        if (isV2) {
            return createV2BattleItem(b);
        }

        var result = b.result || "unknown";
        var p1Name = b.p1_name || "P1";
        var p2Name = b.p2_name || "P2";
        var isAiBattle = b.mode === "ai" || b.opponent_type === "ai";

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
        var modeText = isAiBattle
            ? ' · AI ' + (b.ai_difficulty ? difficultyText(b.ai_difficulty) : '')
            : '';

        var div = document.createElement("div");
        div.className = "battle-item";
        div.innerHTML = '<label class="battle-select-wrap" title="选择此对局"><input class="battle-select-checkbox" type="checkbox" data-battle-id="' + escHtml(b.battle_id) + '" /></label>'
            + '<div class="battle-result-badge battle-result-' + result + '">' + escHtml(resultLabel) + '</div>'
            + '<div class="battle-info">'
            + '<div class="battle-info-row">'
            + '<span class="battle-opponent">' + escHtml(p1Name) + ' vs ' + escHtml(p2Name) + '</span>'
            + '<span class="battle-rounds">' + roundsText + '</span>'
            + '</div>'
            + '<div class="battle-info-row">'
            + '<span class="battle-time">' + escHtml(timeStr) + '</span>'
            + (modeText ? '<span class="battle-time">' + escHtml(modeText) + '</span>' : '')
            + '</div>'
            + '</div>'
            + '<span class="battle-result-text result-' + result + '">' + escHtml(resultLabel) + '</span>';

        bindBattleSelection(div, b.battle_id);

        // 点击跳转到回放页面
        div.addEventListener("click", function () {
            window.location.href = "/v1/record/" + encodeURIComponent(b.battle_id);
        });

        return div;
    }

    function createV2BattleItem(b) {
        var playerCount = b.player_count || 0;
        var modeLabel = b.mode_label || "对局";
        var myRank = b.my_rank;
        var isWinner = b.is_winner;
        var participantNames = b.participant_names || [];
        var namesPreview = participantNames.slice(0, 4).join("、");
        if (participantNames.length > 4) namesPreview += " 等" + participantNames.length + "人";

        // 名次标签
        var rankBadge = "";
        var rankClass = "";
        if (myRank === 1 && isWinner) {
            rankBadge = "🏆 冠军";
            rankClass = "win";
        } else if (myRank != null) {
            rankBadge = "第" + myRank + "名";
            rankClass = myRank <= 2 ? "win" : (myRank >= playerCount ? "loss" : "draw");
        } else if (!b.end_time) {
            rankBadge = "进行中";
            rankClass = "ongoing";
        } else {
            rankBadge = "?";
            rankClass = "unknown";
        }

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
        var modeBadge = modeLabel === "房间对战"
            ? '<span class="v2-mode-badge room">' + escHtml(modeLabel) + '</span>'
            : '<span class="v2-mode-badge local">' + escHtml(modeLabel) + '</span>';

        var div = document.createElement("div");
        div.className = "battle-item battle-item-v2";
        div.innerHTML = '<label class="battle-select-wrap" title="选择此对局"><input class="battle-select-checkbox" type="checkbox" data-battle-id="' + escHtml(b.battle_id) + '" /></label>'
            + '<div class="battle-result-badge battle-result-' + rankClass + '">' + escHtml(rankBadge) + '</div>'
            + '<div class="battle-info">'
            + '<div class="battle-info-row">'
            + modeBadge
            + '<span class="battle-opponent">多人对局 · ' + playerCount + '人</span>'
            + '<span class="battle-rounds">' + roundsText + '</span>'
            + '</div>'
            + '<div class="battle-info-row">'
            + '<span class="battle-time">' + escHtml(timeStr) + '</span>'
            + '<span class="battle-participants-v2">' + escHtml(namesPreview) + '</span>'
            + '</div>'
            + '</div>'
            + '<span class="battle-result-text result-' + rankClass + '">' + escHtml(rankBadge) + '</span>';

        bindBattleSelection(div, b.battle_id);

        div.addEventListener("click", function () {
            window.location.href = "/v2/record/" + encodeURIComponent(b.battle_id);
        });

        return div;
    }

    function bindBattleSelection(div, battleId) {
        var checkbox = div.querySelector(".battle-select-checkbox");
        if (!checkbox) return;
        checkbox.checked = !!selectedBattleIds[battleId];
        checkbox.addEventListener("click", function (event) {
            event.stopPropagation();
        });
        checkbox.addEventListener("change", function (event) {
            event.stopPropagation();
            if (checkbox.checked) {
                selectedBattleIds[battleId] = true;
            } else {
                delete selectedBattleIds[battleId];
            }
            updateSelectedBattleControls();
        });
        var label = div.querySelector(".battle-select-wrap");
        if (label) {
            label.addEventListener("click", function (event) {
                event.stopPropagation();
            });
        }
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

    function difficultyText(diff) {
        if (diff === "easy") return "简单";
        if (diff === "hard") return "困难";
        return "普通";
    }

})();
