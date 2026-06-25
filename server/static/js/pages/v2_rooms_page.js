/**
 * ClapClap 2.0 房间列表页逻辑。
 */
(function () {
    "use strict";

    var createMax = 4;
    var createMin = 2;

    // ═══════════════════════════════════════════════════
    // 面板切换
    // ═══════════════════════════════════════════════════

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

    // ═══════════════════════════════════════════════════
    // 人数步进器
    // ═══════════════════════════════════════════════════

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

    // ═══════════════════════════════════════════════════
    // 创建房间
    // ═══════════════════════════════════════════════════

    document.getElementById("create-room-btn").addEventListener("click", async function () {
        var payload = {
            max_players: createMax,
            min_players: createMin,
            start_condition: document.getElementById("create-start-condition").value,
            allow_spectate: document.getElementById("create-allow-spectate").checked,
            public: document.getElementById("create-public").checked,
        };
        try {
            var result = await ApiUtils.apiPost("/api/v2/rooms", payload);
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

    // ═══════════════════════════════════════════════════
    // 加入房间（房间号）
    // ═══════════════════════════════════════════════════

    document.getElementById("join-room-btn").addEventListener("click", async function () {
        var roomId = document.getElementById("join-room-id").value.trim().toUpperCase();
        if (!roomId) { _msg("join-message", "请输入房间号。", "error"); return; }
        await _doJoin(roomId, "join-message");
    });

    document.getElementById("join-room-id").addEventListener("keydown", function (e) {
        if (e.key === "Enter") document.getElementById("join-room-btn").click();
    });

    // ═══════════════════════════════════════════════════
    // 公开房间列表
    // ═══════════════════════════════════════════════════

    async function loadPublicRooms() {
        var tbody = document.getElementById("public-rooms-body");
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">加载中...</td></tr>';
        try {
            var result = await ApiUtils.apiGet("/api/v2/rooms");
            if (!result.ok) {
                tbody.innerHTML = '<tr><td colspan="5" class="table-empty">加载失败</td></tr>';
                return;
            }
            var rooms = result.data.rooms || [];
            if (rooms.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="table-empty">暂无公开房间</td></tr>';
                return;
            }
            var html = "";
            for (var i = 0; i < rooms.length; i++) {
                var r = rooms[i];
                var statusLabel = {lobby: "等待中", playing: "游戏中", finished: "已结束"}[r.status] || r.status;
                var btnHtml = "";
                if (r.status === "lobby" && r.player_count < r.max_players) {
                    btnHtml = '<button class="btn-small join" onclick="window.__v2_joinPublicRoom(\'' + r.room_id + '\')">加入</button>';
                } else if (r.status === "playing") {
                    btnHtml = '<span class="btn-small playing">对战中</span>';
                } else {
                    btnHtml = '<span class="btn-small full">已满</span>';
                }
                html += '<tr>' +
                    '<td><span class="room-code">' + _esc(r.room_id) + '</span></td>' +
                    '<td>' + _esc(r.host_name) + '</td>' +
                    '<td><span class="people-count">' + r.player_count + '/' + r.max_players + '</span></td>' +
                    '<td><span class="status-badge ' + r.status + '">' + statusLabel + '</span></td>' +
                    '<td>' + btnHtml + '</td>' +
                    '</tr>';
            }
            tbody.innerHTML = html;
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="5" class="table-empty">加载失败</td></tr>';
        }
    }

    window.__v2_joinPublicRoom = async function (roomId) {
        document.getElementById("join-room-id").value = roomId;
        await _doJoin(roomId, "join-panel-message");
    };

    // ═══════════════════════════════════════════════════
    // 辅助
    // ═══════════════════════════════════════════════════

    async function _doJoin(roomId, msgId) {
        try {
            var result = await ApiUtils.apiPost("/api/v2/rooms/" + roomId + "/join", {});
            if (!result.ok) {
                _msg(msgId, result.error || "加入失败。", "error");
                return;
            }
            var data = result.data;
            window.V2RoomIdentity.save(roomId, data.player_token, data.seat_index);
            window.location.href = "/v2/room/" + roomId;
        } catch (e) {
            _msg(msgId, "加入失败：" + e, "error");
        }
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
