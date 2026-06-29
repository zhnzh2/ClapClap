/**
 * ClapClap 2.0 房间列表页逻辑。
 * Step8: 观战入口 + 筛选 + 密码房间 + 邀请
 */
(function () {
    "use strict";

    if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
        window.location.href = "/v2/login?expired=1";
        return;
    }

    var createMax = 4;
    var createMin = 2;

    // ═══════════════════════════════════════════════════════
    // 面板切换
    // ═══════════════════════════════════════════════════════

    var createEntry = document.getElementById("create-entry-card");
    var joinEntry = document.getElementById("join-entry-card");
    var createPanel = document.getElementById("create-panel");
    var joinPanel = document.getElementById("join-panel");

    createEntry.addEventListener("click", function () {
        var isOpen = createPanel.style.display !== "none";
        createPanel.style.display = isOpen ? "none" : "";
        joinPanel.style.display = "none";
        createEntry.classList.toggle("active", !isOpen);
        joinEntry.classList.remove("active");
    });

    joinEntry.addEventListener("click", function () {
        var isOpen = joinPanel.style.display !== "none";
        joinPanel.style.display = isOpen ? "none" : "";
        createPanel.style.display = "none";
        joinEntry.classList.toggle("active", !isOpen);
        createEntry.classList.remove("active");
        if (!isOpen) loadPublicRooms();
    });

    document.getElementById("create-cancel-btn").addEventListener("click", function () {
        createPanel.style.display = "none";
        createEntry.classList.remove("active");
    });

    // ═══════════════════════════════════════════════════════
    // 人数步进器
    // ═══════════════════════════════════════════════════════

    function syncSteppers() {
        document.getElementById("create-max").textContent = createMax;
        document.getElementById("create-min").textContent = createMin;
    }

    document.getElementById("create-max-inc").addEventListener("click", function () {
        if (createMax < 6) { createMax++; syncSteppers(); }
    });
    document.getElementById("create-max-dec").addEventListener("click", function () {
        if (createMax > 2 && createMax > createMin) { createMax--; syncSteppers(); }
    });
    document.getElementById("create-min-inc").addEventListener("click", function () {
        if (createMin < createMax) { createMin++; syncSteppers(); }
    });
    document.getElementById("create-min-dec").addEventListener("click", function () {
        if (createMin > 2) { createMin--; syncSteppers(); }
    });

    // ═══════════════════════════════════════════════════════
    // 创建房间
    // ═══════════════════════════════════════════════════════

    document.getElementById("create-room-btn").addEventListener("click", async function () {
        var payload = {
            max_players: createMax,
            min_players: createMin,
            start_condition: document.getElementById("create-start-condition").value,
            allow_spectate: document.getElementById("create-allow-spectate").checked,
            public: document.getElementById("create-public").checked,
        };
        // 密码字段
        var pw = document.getElementById("create-password").value.trim();
        if (pw) payload.password = pw;

        try {
            var result = await ApiUtils.apiPost("/v2/api/rooms", payload);
            if (!result.ok) {
                _msg("create-message", result.error || "创建失败。", "error");
                return;
            }
            var data = result.data;
            if (!data.player_token) {
                _msg("create-message", "服务端未返回 player_token。", "error");
                return;
            }
            window.V2RoomIdentity.save(data.room.room_id, data.player_token, data.seat_index);
            window.location.href = "/v2/room/" + data.room.room_id;
        } catch (e) {
            _msg("create-message", "创建失败：" + e, "error");
        }
    });

    // ═══════════════════════════════════════════════════════
    // 加入房间（房间号）
    // ═══════════════════════════════════════════════════════

    document.getElementById("join-room-btn").addEventListener("click", async function () {
        var roomId = document.getElementById("join-room-id").value.trim().toUpperCase();
        if (!roomId) { _msg("join-message", "请输入房间号。", "error"); return; }
        await _doJoin(roomId, false, "join-message");
    });

    document.getElementById("join-room-id").addEventListener("keydown", function (e) {
        if (e.key === "Enter") document.getElementById("join-room-btn").click();
    });

    // ═══════════════════════════════════════════════════════
    // 筛选事件绑定
    // ═══════════════════════════════════════════════════════

    document.getElementById("filter-status").addEventListener("change", loadPublicRooms);
    document.getElementById("filter-min-slots").addEventListener("change", loadPublicRooms);

    // ═══════════════════════════════════════════════════════
    // 密码弹窗
    // ═══════════════════════════════════════════════════════

    var _pwRoomId = null;
    var _pwAsSpectator = false;
    var _pwMsgId = "join-message";

    document.getElementById("password-submit-btn").addEventListener("click", async function () {
        var pw = document.getElementById("password-input").value;
        if (!_pwRoomId) return;
        _hidePasswordModal();
        await _doJoin(_pwRoomId, _pwAsSpectator, _pwMsgId, pw);
    });

    document.getElementById("password-cancel-btn").addEventListener("click", function () {
        _hidePasswordModal();
        _pwRoomId = null;
    });

    document.getElementById("password-modal-mask").addEventListener("click", function (e) {
        if (e.target.id === "password-modal-mask") {
            _hidePasswordModal();
            _pwRoomId = null;
        }
    });

    document.getElementById("password-input").addEventListener("keydown", function (e) {
        if (e.key === "Enter") document.getElementById("password-submit-btn").click();
    });

    // ═══════════════════════════════════════════════════════
    // 公开房间列表
    // ═══════════════════════════════════════════════════════

    async function loadPublicRooms() {
        var tbody = document.getElementById("public-rooms-body");
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">加载中...</td></tr>';

        // 构建筛选参数
        var params = [];
        var statusVal = document.getElementById("filter-status").value;
        if (statusVal) params.push("status=" + encodeURIComponent(statusVal));
        var minSlots = document.getElementById("filter-min-slots").value;
        if (minSlots) params.push("min_slots=" + encodeURIComponent(minSlots));
        var url = "/v2/api/rooms";
        if (params.length > 0) url += "?" + params.join("&");

        try {
            var result = await ApiUtils.apiGet(url);
            if (!result.ok) {
                tbody.innerHTML = '<tr><td colspan="6" class="table-empty">加载失败</td></tr>';
                return;
            }
            var rooms = result.data.rooms || [];
            if (rooms.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="table-empty">暂无匹配的公开房间</td></tr>';
                return;
            }
            var html = "";
            for (var i = 0; i < rooms.length; i++) {
                var r = rooms[i];
                var statusLabel = {lobby: "等待中", playing: "游戏中", finished: "已结束"}[r.status] || r.status;
                var freeSlots = r.max_players - r.player_count;
                var spectateBadge = r.allow_spectate ? "" : " · 不可观战";
                var lockIcon = r.has_password ? " 🔒" : "";

                // 操作按钮
                var btnHtml = "";
                if (r.status === "lobby" && freeSlots > 0) {
                    btnHtml = '<button class="btn-small join" onclick="window.__v2_joinPublicRoom(\'' + r.room_id + '\')">参战</button>';
                    if (r.allow_spectate) {
                        btnHtml += ' <button class="btn-small spectate" onclick="window.__v2_spectatePublicRoom(\'' + r.room_id + '\')">观战</button>';
                    }
                } else if (r.status === "playing") {
                    if (r.allow_spectate) {
                        btnHtml = '<button class="btn-small spectate" onclick="window.__v2_spectatePublicRoom(\'' + r.room_id + '\')">观战</button>';
                    } else {
                        btnHtml = '<span class="btn-small nospectate">对战中</span>';
                    }
                } else if (r.status === "lobby" && freeSlots === 0) {
                    if (r.allow_spectate) {
                        btnHtml = '<button class="btn-small spectate" onclick="window.__v2_spectatePublicRoom(\'' + r.room_id + '\')">观战</button>';
                    } else {
                        btnHtml = '<span class="btn-small full">已满</span>';
                    }
                } else {
                    btnHtml = '<span class="btn-small full">已结束</span>';
                }

                html += '<tr>' +
                    '<td><span class="room-code">' + _esc(r.room_id) + lockIcon + '</span></td>' +
                    '<td>' + _esc(r.host_name) + '</td>' +
                    '<td><span class="people-count">' + r.player_count + '/' + r.max_players + '</span></td>' +
                    '<td><span class="spec-count">' + (r.spectator_count || 0) + '</span></td>' +
                    '<td><span class="status-badge ' + r.status + '">' + statusLabel + spectateBadge + '</span></td>' +
                    '<td>' + btnHtml + '</td>' +
                    '</tr>';
            }
            tbody.innerHTML = html;
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="6" class="table-empty">加载失败</td></tr>';
        }
    }

    window.__v2_joinPublicRoom = async function (roomId) {
        document.getElementById("join-room-id").value = roomId;
        await _doJoin(roomId, false, "join-panel-message");
    };

    window.__v2_spectatePublicRoom = async function (roomId) {
        await _doJoin(roomId, true, "join-panel-message");
    };

    // ═══════════════════════════════════════════════════════
    // 辅助
    // ═══════════════════════════════════════════════════════

    async function _doJoin(roomId, asSpectator, msgId, password) {
        var payload = {};
        if (asSpectator) payload.as_spectator = true;
        if (password) payload.password = password;

        try {
            var result = await ApiUtils.apiPost("/v2/api/rooms/" + roomId + "/join", payload);
            if (!result.ok) {
                var err = result.error || "加入失败。";
                var code = result.error_code || "";
                if (code === "PASSWORD_REQUIRED") {
                    // 弹出密码输入框
                    _pwRoomId = roomId;
                    _pwAsSpectator = asSpectator;
                    _pwMsgId = msgId;
                    _showPasswordModal();
                    document.getElementById("password-input").value = "";
                    document.getElementById("password-input").focus();
                    return;
                }
                _msg(msgId, err, "error");
                return;
            }
            var data = result.data;
            if (asSpectator) {
                // 观战者：保存 spectator_token
                if (data.spectator_token) {
                    window.V2RoomIdentity.saveSpectator(roomId, data.spectator_token);
                }
            } else if (data.player_token) {
                window.V2RoomIdentity.save(roomId, data.player_token, data.seat_index);
            }
            window.location.href = "/v2/room/" + roomId;
        } catch (e) {
            _msg(msgId, "加入失败：" + e, "error");
        }
    }

    function _showPasswordModal() {
        var mask = document.getElementById("password-modal-mask");
        if (mask) mask.classList.add("show");
    }

    function _hidePasswordModal() {
        var mask = document.getElementById("password-modal-mask");
        if (mask) mask.classList.remove("show");
    }

    function _msg(id, text, type) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.className = "message " + (type || "info");
    }

    function _esc(s) {
        if (!s) return "";
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
})();
