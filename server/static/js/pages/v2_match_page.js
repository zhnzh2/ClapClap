/**
 * ClapClap 2.0 自动匹配页面逻辑。
 * Step8: 加入队列、排队、取消、成功跳转、刷新恢复。
 */
(function () {
    "use strict";

    var MATCH_STORAGE_KEY = "clapclap_v2_match_state";

    var preferredPlayers = 4;
    var myToken = null;
    var myState = "idle";       // idle | queued | matched
    var matchedRoomId = null;
    var matchedRoomPlayerToken = null;
    var matchedSeatIndex = null;
    var pollingTimer = null;
    var waitStartTime = null;

    // ═══════════════════════════════════════════════════════
    // 初始化
    // ═══════════════════════════════════════════════════════

    function init() {
        if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
            window.location.href = "/login";
            return;
        }

        // 恢复之前的匹配状态
        var saved = _loadMatchState();
        if (saved) {
            myToken = saved.token;
            preferredPlayers = saved.preferred_players || 4;
            matchedRoomId = saved.room_id || null;
            matchedRoomPlayerToken = saved.room_player_token || null;
            matchedSeatIndex = saved.seat_index || null;
            waitStartTime = saved.wait_start ? new Date(saved.wait_start) : null;
            document.getElementById("pref-count").textContent = preferredPlayers;
        } else {
            myToken = _generateToken();
        }

        // 步进器
        document.getElementById("pref-dec-btn").addEventListener("click", function () {
            if (preferredPlayers > 2) { preferredPlayers--; document.getElementById("pref-count").textContent = preferredPlayers; }
        });
        document.getElementById("pref-inc-btn").addEventListener("click", function () {
            if (preferredPlayers < 6) { preferredPlayers++; document.getElementById("pref-count").textContent = preferredPlayers; }
        });

        // 按钮
        document.getElementById("join-queue-btn").addEventListener("click", joinQueue);
        document.getElementById("cancel-queue-btn").addEventListener("click", cancelQueue);
        document.getElementById("enter-room-btn").addEventListener("click", enterRoom);

        // 先检查当前状态
        checkMyState();
        fetchQueueStatus();

        // 轮询
        pollingTimer = setInterval(function () {
            if (myState === "queued") checkMyState();
            fetchQueueStatus();
        }, 5000);
    }

    // ═══════════════════════════════════════════════════════
    // 状态管理
    // ═══════════════════════════════════════════════════════

    function _loadMatchState() {
        try {
            var raw = localStorage.getItem(MATCH_STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) { return null; }
    }

    function _saveMatchState(state) {
        try {
            var data = {
                token: myToken,
                preferred_players: preferredPlayers,
                state: state,
                wait_start: waitStartTime ? waitStartTime.toISOString() : null,
                room_id: matchedRoomId,
                room_player_token: matchedRoomPlayerToken,
                seat_index: matchedSeatIndex,
            };
            localStorage.setItem(MATCH_STORAGE_KEY, JSON.stringify(data));
        } catch (e) { /* ignore */ }
    }

    function _clearMatchState() {
        try { localStorage.removeItem(MATCH_STORAGE_KEY); } catch (e) { /* ignore */ }
    }

    function _generateToken() {
        return "v2m_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
    }

    // ═══════════════════════════════════════════════════════
    // API 调用
    // ═══════════════════════════════════════════════════════

    async function joinQueue() {
        try {
            var result = await ApiUtils.apiPost("/api/v2/match/join", {
                player_token: myToken,
                preferred_players: preferredPlayers,
            });
            if (!result.ok) {
                _msg("setup-message", result.error || "加入失败。", "error");
                return;
            }
            var data = result.data;
            if (data.matched) {
                _onMatched(data.room_id, data.room_player_token, data.seat_index);
            } else {
                _onQueued(data.queue_size || 1);
            }
        } catch (e) {
            _msg("setup-message", "加入失败：" + e, "error");
        }
    }

    async function cancelQueue() {
        try {
            var result = await ApiUtils.apiPost("/api/v2/match/cancel", {
                player_token: myToken,
            });
            if (result.ok) {
                _onIdle(result.data.message || "已取消匹配。");
            }
        } catch (e) {
            _msg("queue-message", "取消失败：" + e, "error");
        }
    }

    async function checkMyState() {
        try {
            var result = await ApiUtils.apiGet("/api/v2/match/me?player_token=" + encodeURIComponent(myToken));
            if (!result.ok) return;
            var state = result.data.state;
            if (state.status === "matched") {
                _onMatched(state.room_id, state.room_player_token, state.seat_index);
            } else if (state.status === "queued") {
                _onQueued(0);
            } else if (myState === "queued") {
                _onIdle("匹配状态已变更。");
            }
        } catch (e) { /* ignore polling errors */ }
    }

    async function fetchQueueStatus() {
        try {
            var result = await ApiUtils.apiGet("/api/v2/match/status");
            if (!result.ok) return;
            var status = result.data.status;
            document.getElementById("queue-status-text").textContent =
                "当前队列 " + (status.queue_size || 0) + " 人等待中";

            var playersHtml = "";
            var players = status.players || [];
            for (var i = 0; i < players.length; i++) {
                var p = players[i];
                var mins = Math.floor((p.waiting_seconds || 0) / 60);
                var secs = (p.waiting_seconds || 0) % 60;
                playersHtml += '<div class="queue-player-item">' +
                    '<span class="qp-name">' + _esc(p.player_name) + '</span>' +
                    '<span class="qp-pref">期望 ' + p.preferred_players + ' 人</span>' +
                    '<span class="qp-time">等待 ' + mins + '分' + secs + '秒</span>' +
                    '</div>';
            }
            document.getElementById("queue-players").innerHTML = playersHtml || '<div class="queue-empty">暂无排队玩家</div>';
        } catch (e) { /* ignore */ }
    }

    async function enterRoom() {
        if (!matchedRoomId) return;
        if (!matchedRoomPlayerToken) {
            try {
                var result = await ApiUtils.apiGet("/api/v2/match/me?player_token=" + encodeURIComponent(myToken));
                if (result.ok && result.data.state.room_player_token) {
                    matchedRoomPlayerToken = result.data.state.room_player_token;
                    matchedSeatIndex = result.data.state.seat_index;
                }
            } catch (e) { /* ignore */ }
        }

        if (!matchedRoomPlayerToken) {
            _msg("matched-message", "还没有拿到房间身份，请稍等一秒再试。", "waiting");
            return;
        }

        window.V2RoomIdentity.save(matchedRoomId, matchedRoomPlayerToken, matchedSeatIndex);
        _clearMatchState();
        window.location.href = "/v2/room/" + matchedRoomId;
    }

    // ═══════════════════════════════════════════════════════
    // 状态切换
    // ═══════════════════════════════════════════════════════

    function _onIdle(message) {
        myState = "idle";
        matchedRoomId = null;
        matchedRoomPlayerToken = null;
        matchedSeatIndex = null;
        waitStartTime = null;
        _clearMatchState();
        myToken = _generateToken();
        document.getElementById("setup-card").style.display = "";
        document.getElementById("queue-card").style.display = "none";
        document.getElementById("matched-card").style.display = "none";
        if (message) _msg("setup-message", message, "info");
    }

    function _onQueued(queueSize) {
        myState = "queued";
        matchedRoomId = null;
        matchedRoomPlayerToken = null;
        matchedSeatIndex = null;
        if (!waitStartTime) waitStartTime = new Date();
        _saveMatchState("queued");
        document.getElementById("setup-card").style.display = "none";
        document.getElementById("queue-card").style.display = "";
        document.getElementById("matched-card").style.display = "none";
        document.getElementById("queue-text").textContent = "正在匹配 " + preferredPlayers + " 人对局...";
        document.getElementById("queue-detail").textContent = "当前队列 " + (queueSize || "?") + " 人";
        _updateWaitTime();
    }

    function _onMatched(roomId, roomPlayerToken, seatIndex) {
        myState = "matched";
        matchedRoomId = roomId;
        if (roomPlayerToken) matchedRoomPlayerToken = roomPlayerToken;
        if (seatIndex != null) matchedSeatIndex = seatIndex;
        _saveMatchState("matched");
        document.getElementById("setup-card").style.display = "none";
        document.getElementById("queue-card").style.display = "none";
        document.getElementById("matched-card").style.display = "";
        document.getElementById("matched-text").textContent = "已为你创建房间，快进入吧！";
        document.getElementById("matched-room").textContent = "房间号：" + roomId;
    }

    function _updateWaitTime() {
        if (!waitStartTime) return;
        var elapsed = Math.floor((Date.now() - waitStartTime.getTime()) / 1000);
        var mins = Math.floor(elapsed / 60);
        var secs = elapsed % 60;
        document.getElementById("queue-time").textContent = "已等待 " + mins + " 分 " + secs + " 秒";
        if (myState === "queued") {
            setTimeout(_updateWaitTime, 1000);
        }
    }

    // ═══════════════════════════════════════════════════════
    // 辅助
    // ═══════════════════════════════════════════════════════

    function _msg(id, text, type) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.className = "message " + (type || "info");
        el.style.display = text ? "block" : "none";
    }

    function _esc(s) {
        if (!s) return "";
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // ═══════════════════════════════════════════════════════
    // 启动
    // ═══════════════════════════════════════════════════════

    init();
})();
