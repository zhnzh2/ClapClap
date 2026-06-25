/**
 * ClapClap 2.0 房间对战页 —— 主控制器
 *
 * Socket.IO 连接、API 调用、事件绑定、状态同步。
 */

/* ═══════════════════════════════════════════════════════════════
   全局状态
   ═══════════════════════════════════════════════════════════════ */

var v2RoomId = window.CLAPCLAP_V2_ROOM_ID;
var v2MyPlayerToken = null;
var v2MySeatIndex = null;
var v2MyPlayerId = null;
var v2MyRole = null;      // "player" | "spectator"
var v2Socket = null;
var v2PollTimer = null;
var v2HeartbeatTimer = null;
var v2LatestRoom = null;

/* ═══════════════════════════════════════════════════════════════
   初始化
   ═══════════════════════════════════════════════════════════════ */

function initV2RoomPage() {
    // 登录检查
    if (typeof SessionUtils === "undefined" || !SessionUtils.isLoggedIn()) {
        window.location.href = "/login";
        return;
    }

    // 服务重启检测
    if (typeof BootUtils !== "undefined" && window.SERVER_BOOT_ID) {
        BootUtils.handleServerBootChange(window.SERVER_BOOT_ID, { clearStorage: true });
    }

    // 加载身份
    var identity = window.V2RoomIdentity ? window.V2RoomIdentity.load(v2RoomId) : null;
    if (identity) {
        v2MyPlayerToken = identity.player_token;
        v2MySeatIndex = identity.seat_index;
    }

    // 账号按钮
    _setupAccountButton();

    // 事件绑定
    _bindLobbyEvents();
    _bindBattleEvents();
    _bindDecisionEvents();
    _bindChatEvents();
    _bindOverlayEvents();

    // 连接 Socket
    _connectSocket();

    // 获取初始状态
    fetchRoomState();
}

/* ═══════════════════════════════════════════════════════════════
   Socket.IO
   ═══════════════════════════════════════════════════════════════ */

function _connectSocket() {
    if (!window.__socket_io_available) {
        setMessage("Socket.IO 不可用，使用 HTTP 轮询。", "waiting");
        startPolling();
        return;
    }

    try {
        v2Socket = (typeof io === "function") ? io() : null;
    } catch (e) {
        v2Socket = null;
    }

    if (!v2Socket) {
        setMessage("Socket.IO 连接失败，使用 HTTP 轮询。", "waiting");
        startPolling();
        return;
    }

    v2Socket.on("connect", function () {
        setMessage("已连接。", "info");
        if (v2PollTimer) stopPolling();

        v2Socket.emit("join_room_v2", {
            room_id: v2RoomId,
            player_token: v2MyPlayerToken,
        });

        startHeartbeat();
    });

    v2Socket.on("disconnect", function () {
        setMessage("连接断开，尝试重连...", "waiting");
        stopHeartbeat();
        startPolling();
    });

    // ── 服务器事件 ──
    v2Socket.on("room_v2_state", function (data) {
        if (data.ok && data.room) {
            v2LatestRoom = data.room;
            if (data.room.my_seat_index != null) v2MySeatIndex = data.room.my_seat_index;
            if (data.room.my_player_id) v2MyPlayerId = data.room.my_player_id;
            if (data.room.my_role) v2MyRole = data.room.my_role;
            window.renderRoom(data.room);
            _updateIdentityFromRoom(data.room);
            setMessage("", "muted");
        }
    });

    v2Socket.on("settlement_progress_v2", function (data) {
        if (data.action === "request_decision") {
            setMessage("等待决策中...", "waiting");
        } else if (data.action === "round_complete") {
            setMessage("本回合结算完成。", "success");
        } else if (data.action === "game_over") {
            setMessage("对局结束！", "success");
        }
    });

    v2Socket.on("decision_request_v2", function (data) {
        if (data.ok && data.decision_request) {
            window.showDecisionModal(data.decision_request);
            setMessage("需要你的决策！", "waiting");
        }
    });

    v2Socket.on("decision_requests_summary_v2", function (data) {
        if (data.ok) {
            window.showDecisionSummary(data);
        }
    });

    v2Socket.on("round_summary_v2", function (data) {
        if (data.ok && data.summary) {
            window.showRoundSummary(data.summary);
        }
    });

    v2Socket.on("chat_v2_broadcast", function (data) {
        if (data.ok && data.message) {
            window.appendChatItem(data.message);
        }
    });

    v2Socket.on("chat_v2_error", function (data) {
        setMessage(data.error || "聊天消息发送失败。", "error");
    });

    v2Socket.on("player_left_v2", function (data) {
        setMessage("玩家已离开房间。", "info");
    });

    v2Socket.on("host_changed_v2", function (data) {
        setMessage("房主已变更为 " + (data.new_host_username || "另一玩家") + "。", "info");
    });

    v2Socket.on("game_started_v2", function () {
        setMessage("对局已开始！", "success");
    });

    v2Socket.on("room_v2_error", function (data) {
        setMessage(data.error || "房间错误。", "error");
    });

    v2Socket.on("decision_v2_error", function (data) {
        setMessage(data.error || "决策提交失败。", "error");
    });
}

/* ═══════════════════════════════════════════════════════════════
   HTTP 轮询
   ═══════════════════════════════════════════════════════════════ */

function startPolling() {
    if (v2PollTimer) return;
    v2PollTimer = setInterval(fetchRoomState, 5000);
}

function stopPolling() {
    if (v2PollTimer) { clearInterval(v2PollTimer); v2PollTimer = null; }
}

function startHeartbeat() {
    stopHeartbeat();
    v2HeartbeatTimer = setInterval(function () {
        if (v2Socket && v2Socket.connected) {
            v2Socket.emit("room_v2_heartbeat", {
                room_id: v2RoomId,
                player_token: v2MyPlayerToken,
            });
        }
    }, 5000);
}

function stopHeartbeat() {
    if (v2HeartbeatTimer) { clearInterval(v2HeartbeatTimer); v2HeartbeatTimer = null; }
}

/* ═══════════════════════════════════════════════════════════════
   REST API 调用
   ═══════════════════════════════════════════════════════════════ */

async function fetchRoomState() {
    try {
        var url = "/api/v2/rooms/" + v2RoomId;
        if (v2MyPlayerToken) url += "?player_token=" + encodeURIComponent(v2MyPlayerToken);
        var result = await ApiUtils.apiGet(url);
        if (result.ok && result.data && result.data.room) {
            v2LatestRoom = result.data.room;
            if (result.data.room.my_seat_index != null) v2MySeatIndex = result.data.room.my_seat_index;
            if (result.data.room.my_player_id) v2MyPlayerId = result.data.room.my_player_id;
            if (result.data.room.my_role) v2MyRole = result.data.room.my_role;
            window.renderRoom(result.data.room);
            _updateIdentityFromRoom(result.data.room);
            setMessage("", "muted");
        } else if (result.data && result.data.error_code === "ROOM_NOT_FOUND") {
            setMessage("房间不存在或已失效。", "error");
            stopPolling();
            setTimeout(function () { window.location.href = "/v2/rooms"; }, 3000);
        }
    } catch (e) {
        setMessage("获取房间状态失败。", "error");
    }
}

async function toggleReady() {
    if (!v2MyPlayerToken) return;
    try {
        var result = await ApiUtils.apiPost("/api/v2/rooms/" + v2RoomId + "/ready", {
            player_token: v2MyPlayerToken,
        });
        if (!result.ok) {
            setMessage(result.error || "操作失败。", "error");
        }
    } catch (e) {
        setMessage("操作失败：" + e, "error");
    }
}

async function startGame() {
    if (!v2MyPlayerToken) return;
    try {
        var result = await ApiUtils.apiPost("/api/v2/rooms/" + v2RoomId + "/start", {
            player_token: v2MyPlayerToken,
        });
        if (!result.ok) {
            setMessage(result.error || "开始失败。", "error");
        }
    } catch (e) {
        setMessage("开始失败：" + e, "error");
    }
}

async function submitMove() {
    var moveName = window.__v2_selected_move;
    if (!moveName || !v2MyPlayerToken) return;

    try {
        var result = await ApiUtils.apiPost("/api/v2/rooms/" + v2RoomId + "/step", {
            player_token: v2MyPlayerToken,
            move_name: moveName,
        });

        if (result.ok) {
            window.__v2_selected_move = null;
            setMessage("动作已提交！" + (result.data.message || ""), "success");
            // 如果后端直接完成了结算，刷新状态
            if (result.data.resolved) {
                fetchRoomState();
            }
        } else {
            setMessage(result.error || "提交失败。", "error");
        }
    } catch (e) {
        setMessage("提交失败：" + e, "error");
    }
}

async function leaveRoom() {
    if (!v2MyPlayerToken) { _goToRooms(); return; }
    try {
        await ApiUtils.apiPost("/api/v2/rooms/" + v2RoomId + "/leave", {
            player_token: v2MyPlayerToken,
        });
    } catch (e) {
        // 忽略
    }
    _goToRooms();
}

async function voteRematch(vote) {
    if (!v2MyPlayerToken) return;
    try {
        var result = await ApiUtils.apiPost("/api/v2/rooms/" + v2RoomId + "/rematch", {
            player_token: v2MyPlayerToken,
            vote: vote,
        });
        if (!result.ok) {
            setMessage(result.error || "投票失败。", "error");
        }
    } catch (e) {
        setMessage("投票失败：" + e, "error");
    }
}

// 决策提交
async function _submitDecision(selected) {
    if (!v2MyPlayerToken || selected.length === 0) return;

    var decisions = {};
    decisions[v2MyPlayerId] = selected;

    // 优先通过 Socket
    if (v2Socket && v2Socket.connected) {
        v2Socket.emit("submit_decision_v2", {
            room_id: v2RoomId,
            player_token: v2MyPlayerToken,
            decisions: decisions,
        });
        return;
    }

    // HTTP fallback
    try {
        var result = await ApiUtils.apiPost("/api/v2/rooms/" + v2RoomId + "/decision", {
            player_token: v2MyPlayerToken,
            decisions: decisions,
        });
        if (result.ok) {
            if (result.data.resolved) fetchRoomState();
        } else {
            setMessage(result.error || "决策提交失败。", "error");
        }
    } catch (e) {
        setMessage("决策提交失败：" + e, "error");
    }
}

/* ═══════════════════════════════════════════════════════════════
   大厅事件绑定
   ═══════════════════════════════════════════════════════════════ */

function _bindLobbyEvents() {
    var readyBtn = document.getElementById("lobby-ready-btn");
    if (readyBtn) readyBtn.addEventListener("click", toggleReady);

    var startBtn = document.getElementById("lobby-start-btn");
    if (startBtn) startBtn.addEventListener("click", startGame);

    var copyBtn = document.getElementById("copy-room-id-btn");
    if (copyBtn) copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(v2RoomId).then(function () {
            setMessage("房间号已复制：" + v2RoomId, "success");
        }).catch(function () {
            setMessage("复制失败，请手动复制：" + v2RoomId, "error");
        });
    });
}

/* ═══════════════════════════════════════════════════════════════
   对局事件绑定
   ═══════════════════════════════════════════════════════════════ */

function _bindBattleEvents() {
    document.getElementById("submit-move-btn").addEventListener("click", submitMove);
    document.getElementById("cancel-move-btn").addEventListener("click", function () {
        window.__v2_selected_move = null;
        if (v2LatestRoom && v2LatestRoom.game) {
            window.renderMoveSelection(v2LatestRoom.game, v2MyPlayerId);
        }
    });

    document.getElementById("rematch-vote-btn").addEventListener("click", function () {
        voteRematch(true);
    });

    // 全局键盘
    document.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !document.getElementById("decision-modal-mask").classList.contains("show")) {
            var submitBtn = document.getElementById("submit-move-btn");
            if (submitBtn && !submitBtn.disabled) submitBtn.click();
        }
        if (e.key === "Backspace" && !e.target.closest("input")) {
            document.getElementById("cancel-move-btn").click();
        }
        // 1-8 快捷键选动作
        var keyMap = { "1": "CHI", "2": "SHUANG_CHI", "3": "SHAN", "4": "GAO",
                       "q": "QI", "w": "SHIELD", "e": "SHI_ZI", "r": "BA_GUA",
                       "a": "GI", "s": "PO", "d": "LENG_FENG", "f": "RU_LAI", "g": "HEI_DONG",
                       "z": "FIRE", "x": "SHAN_DIAN", "c": "LIE_YAN", "v": "SHINING" };
        var moveName = keyMap[e.key.toLowerCase()];
        if (moveName) {
            window.__v2_selectMove(moveName);
        }
    });
}

/* ═══════════════════════════════════════════════════════════════
   决策事件绑定
   ═══════════════════════════════════════════════════════════════ */

function _bindDecisionEvents() {
    document.getElementById("decision-submit-btn").addEventListener("click", function () {
        _submitDecision(selectedOptions);
        window.hideDecisionModal();
    });

    document.getElementById("decision-auto-btn").addEventListener("click", function () {
        window.__v2_autoSubmitDecision();
    });

    document.getElementById("decision-modal-mask").addEventListener("click", function (e) {
        if (e.target.id === "decision-modal-mask") window.hideDecisionModal();
    });

    document.getElementById("round-summary-continue-btn").addEventListener("click", function () {
        window.hideRoundSummary();
    });

    document.getElementById("round-summary-mask").addEventListener("click", function (e) {
        if (e.target.id === "round-summary-mask") window.hideRoundSummary();
    });

    // 决策提交回调
    window.__v2_submitDecisionCallback = _submitDecision;
}

/* ═══════════════════════════════════════════════════════════════
   聊天事件绑定
   ═══════════════════════════════════════════════════════════════ */

function _bindChatEvents() {
    var chatInput = document.getElementById("chat-input");
    var chatSend = document.getElementById("chat-send-btn");

    function sendChat() {
        var msg = chatInput.value.trim();
        if (!msg) return;
        if (msg.length > 50) {
            setMessage("消息不能超过 50 个字符。", "error");
            return;
        }
        if (v2Socket && v2Socket.connected) {
            v2Socket.emit("chat_message_v2", {
                room_id: v2RoomId,
                player_token: v2MyPlayerToken,
                message: msg,
            });
        }
        chatInput.value = "";
    }

    if (chatSend) chatSend.addEventListener("click", sendChat);
    if (chatInput) chatInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") sendChat();
    });

    // 快速聊天
    var quickBtns = document.querySelectorAll(".quick-chat-btn");
    quickBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var msg = btn.getAttribute("data-msg");
            if (v2Socket && v2Socket.connected) {
                v2Socket.emit("chat_message_v2", {
                    room_id: v2RoomId,
                    player_token: v2MyPlayerToken,
                    message: msg,
                });
            }
        });
    });
}

/* ═══════════════════════════════════════════════════════════════
   弹窗/按钮事件
   ═══════════════════════════════════════════════════════════════ */

function _bindOverlayEvents() {
    document.getElementById("leave-room-btn").addEventListener("click", function () {
        if (typeof ModalUtils !== "undefined") {
            ModalUtils.showConfirmModal({
                title: "退出房间",
                body: "确定要退出房间吗？如果对局正在进行中，退出将视为投降。",
                confirmText: "退出",
                cancelText: "取消",
                onConfirm: leaveRoom,
            });
        } else {
            leaveRoom();
        }
    });

    // 账号按钮
    var adminBtn = document.getElementById("header-admin-btn");
    if (adminBtn) {
        var user = SessionUtils.getSessionUser ? SessionUtils.getSessionUser() : null;
        if (user && user.uid === 0) {
            adminBtn.style.display = "";
            adminBtn.addEventListener("click", function () {
                if (typeof AdminUsersModal !== "undefined") AdminUsersModal.open();
            });
        }
    }

}

/* ═══════════════════════════════════════════════════════════════
   辅助函数
   ═══════════════════════════════════════════════════════════════ */

function _updateIdentityFromRoom(room) {
    if (room && room.my_seat_index != null && v2MyPlayerToken) {
        window.V2RoomIdentity.save(v2RoomId, v2MyPlayerToken, room.my_seat_index);
    }
}

function _setupAccountButton() {
    var btn = document.getElementById("header-account-btn");
    if (!btn) return;
    if (typeof SessionUtils === "undefined") return;
    var user = SessionUtils.getSessionUser();
    if (user) {
        btn.textContent = user.username;
        btn.addEventListener("click", function () {
            window.location.href = "/user/" + user.uid;
        });
    }
}

function _goToRooms() {
    if (window.V2RoomIdentity) window.V2RoomIdentity.remove(v2RoomId);
    window.location.href = "/v2/rooms";
}

function setMessage(text, type) {
    var el = document.getElementById("message");
    if (!el) return;
    el.textContent = text;
    el.className = "message-box " + (type || "muted");
}

// ── 动作选择 ──
window.__v2_selected_move = null;

window.__v2_selectMove = function (moveName) {
    window.__v2_selected_move = moveName;
    if (v2LatestRoom && v2LatestRoom.game) {
        window.renderMoveSelection(v2LatestRoom.game, v2MyPlayerId);
    }
};
