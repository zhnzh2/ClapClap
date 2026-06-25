/**
 * ClapClap 2.0 房间 UI 渲染函数。
 *
 * 从 v2_room_page.js 调用，负责所有 DOM 更新。
 */
(function () {
    "use strict";

    // ═══════════════════════════════════════════════════════
    // 动作分类与显示名
    // ═══════════════════════════════════════════════════════

    var MOVE_GROUPS = {
        resource_defense: {
            label: "资源与防御",
            moves: ["QI", "SHIELD", "SHI_ZI", "BA_GUA"],
        },
        attack_qi: {
            label: "气系攻击",
            moves: ["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"],
        },
        attack_shield: {
            label: "盾系攻击",
            moves: ["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"],
        },
        trick: {
            label: "锦囊",
            moves: ["CHI", "SHUANG_CHI", "SHAN", "GAO"],
        },
    };

    var MOVE_LABELS = {
        QI: "气", SHIELD: "盾",
        GI: "gi", PO: "破", LENG_FENG: "冷锋", RU_LAI: "如来", HEI_DONG: "黑洞",
        FIRE: "Fire", SHAN_DIAN: "闪电", LIE_YAN: "烈焰", SHINING: "Shining",
        SHI_ZI: "十字", BA_GUA: "八卦",
        CHI: "你吃", SHUANG_CHI: "双吃", SHAN: "闪", GAO: "镐",
    };

    var SPEED_LAYER_NAMES = {
        1: "闪", 2: "三连", 3: "你吃/双吃", 4: "gi→黑洞",
        5: "黑洞", 6: "如来/Shining", 7: "冷锋/烈焰",
        8: "gi攻击/抢镐", 9: "破/闪电", 10: "Fire",
        11: "gi无目标", 12: "气/盾/加镐",
    };

    var PHASE_LABELS = {
        waiting_moves: "等待出招",
        resource_check: "资源检查",
        reveal: "亮招",
        flash: "闪结算",
        three_chain: "三连判定",
        speed_layer: "速度层结算",
        death_check: "死亡判定",
        round_summary: "回合总结",
        finished: "对局结束",
    };

    // ═══════════════════════════════════════════════════════
    // 主渲染入口
    // ═══════════════════════════════════════════════════════

    window.renderRoom = function (room) {
        if (!room) return;

        document.getElementById("top-subtitle").textContent = "房间号：" + room.room_id;

        switch (room.status) {
        case "lobby":
            document.getElementById("lobby-phase").style.display = "";
            document.getElementById("battle-phase").style.display = "none";
            window.renderLobby(room);
            break;
        case "playing":
            document.getElementById("lobby-phase").style.display = "none";
            document.getElementById("battle-phase").style.display = "";
            document.getElementById("game-over-card").style.display = "none";
            window.renderPlaying(room);
            break;
        case "finished":
            document.getElementById("lobby-phase").style.display = "none";
            document.getElementById("battle-phase").style.display = "";
            window.renderPlaying(room);
            window.renderGameOver(room);
            break;
        }

        window.renderChatMessages(room.chat_messages || []);
        if (room.game && room.game.history) {
            window.renderHistory(room.game.history);
        }
    };

    // ═══════════════════════════════════════════════════════
    // 大厅渲染
    // ═══════════════════════════════════════════════════════

    window.renderLobby = function (room) {
        var mySeatIndex = room.my_seat_index;
        var isHost = (mySeatIndex === room.host_seat_index);
        var isPlayer = (room.my_role === "player");

        // 房间信息
        document.getElementById("lobby-room-id").textContent = room.room_id;
        document.getElementById("lobby-rule-version").textContent = room.rule_version;
        document.getElementById("lobby-player-count").textContent = room.player_count + " / " + room.max_players;
        document.getElementById("lobby-start-condition").textContent = _startConditionText(room.start_condition);
        document.getElementById("lobby-spectate-count").textContent = room.spectator_count || 0;

        // 座位列表
        var seatsHtml = "";
        for (var i = 1; i <= room.max_players; i++) {
            var seat = _findSeat(room.seats, i);
            if (seat) {
                var classes = ["lobby-seat-card"];
                if (seat.seat_index === room.host_seat_index) classes.push("is-host");
                if (i === mySeatIndex) classes.push("is-self");

                var badges = [];
                if (seat.seat_index === room.host_seat_index) badges.push('<span class="badge host">房主</span>');
                if (seat.ready) badges.push('<span class="badge ready">已准备</span>');
                else badges.push('<span class="badge not-ready">未准备</span>');
                if (i === mySeatIndex) badges.push('<span class="badge self">我</span>');
                if (seat.online) badges.push('<span class="badge online">在线</span>');
                else badges.push('<span class="badge offline">离线</span>');

                seatsHtml += '<div class="' + classes.join(" ") + '">' +
                    '<div class="seat-index">席位 ' + i + '</div>' +
                    '<div class="seat-name">' + _esc(seat.username) + '</div>' +
                    '<div class="seat-badges">' + badges.join("") + '</div>' +
                    '</div>';
            } else {
                seatsHtml += '<div class="lobby-seat-card empty-slot">' +
                    '<div class="seat-index">席位 ' + i + '</div>' +
                    '<div class="seat-name">空位</div>' +
                    '</div>';
            }
        }
        document.getElementById("lobby-seats").innerHTML = seatsHtml;

        // 观战者
        var specCount = room.spectator_count || 0;
        var specArea = document.getElementById("lobby-spectators-area");
        if (specCount > 0) {
            specArea.style.display = "";
            var specs = room.seats ? room.seats.filter(function (s) { return !s; }) : [];
            document.getElementById("lobby-spectators").textContent = specCount + " 人观战中";
        } else {
            specArea.style.display = "none";
        }

        // 按钮
        var readyBtn = document.getElementById("lobby-ready-btn");
        var startBtn = document.getElementById("lobby-start-btn");

        if (isPlayer) {
            readyBtn.style.display = "";
            var mySeat = _findSeat(room.seats, mySeatIndex);
            readyBtn.textContent = (mySeat && mySeat.ready) ? "取消准备" : "准备";
        } else {
            readyBtn.style.display = "none";
        }

        if (isHost) {
            startBtn.style.display = "";
            startBtn.disabled = room.player_count < room.min_players;
        } else {
            startBtn.style.display = "none";
        }

        // 消息
        setMessage("（邀请制）将房间号发给朋友即可加入。加入后房主可开始对局。", "muted");
    };

    // ═══════════════════════════════════════════════════════
    // 对局渲染
    // ═══════════════════════════════════════════════════════

    window.renderPlaying = function (room) {
        var game = room.game;
        var myPlayerId = room.my_player_id;

        if (!game) return;

        // 状态栏
        document.getElementById("battle-round").textContent = game.round_num;
        var phaseLabel = PHASE_LABELS[game.phase] || game.phase;
        if (game.sub_phase) {
            phaseLabel += " · " + game.sub_phase;
        }
        document.getElementById("battle-phase-label").textContent = phaseLabel;
        document.getElementById("battle-alive-count").textContent = game.alive_count;

        // 速度层进度条
        window.renderSpeedLayerBar(game);

        // 玩家卡片
        window.renderPlayerCards(game, room.seats, myPlayerId);

        // 动作选择
        if (myPlayerId && game.phase === "waiting_moves") {
            document.getElementById("move-selection-card").style.display = "";
            window.renderMoveSelection(game, myPlayerId);
        } else if (myPlayerId && game.phase !== "waiting_moves") {
            // 结算中：显示动作区但禁用
            document.getElementById("move-selection-card").style.display = "";
            document.getElementById("move-groups").innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px;">结算中，请等待...</div>';
            document.getElementById("move-status-line").textContent = "";
        } else {
            // 观战者无动作选择
            document.getElementById("move-selection-card").style.display = "none";
        }

        // 结算事件
        if (game.phase === "speed_layer" || game.phase === "round_summary") {
            document.getElementById("settlement-card").style.display = "";
            window.renderSettlementEvents(game);
        } else {
            document.getElementById("settlement-card").style.display = "none";
        }
    };

    // ═══════════════════════════════════════════════════════
    // 玩家卡片
    // ═══════════════════════════════════════════════════════

    window.renderPlayerCards = function (game, seats, myPlayerId) {
        var players = game.players || [];
        var html = "";

        for (var i = 0; i < players.length; i++) {
            var p = players[i];
            var seat = _findSeatByPlayerId(seats, p.player_id);
            var username = (seat && seat.username) || p.username || p.player_id;
            var isSelf = (p.player_id === myPlayerId);
            var isDead = (p.status === "dead");

            var cardClasses = ["player-card"];
            if (isSelf) cardClasses.push("is-self");
            if (isDead) cardClasses.push("is-dead");
            if (p.resolution_status === "resolved") cardClasses.push("is-resolved");

            var badges = [];
            if (seat && seat.is_host) badges.push('<span class="badge host">房主</span>');
            if (isSelf) badges.push('<span class="badge self">我</span>');
            if (isDead) {
                badges.push('<span class="badge offline">死亡</span>');
                if (p.final_rank) badges.push('<span class="badge host">第' + p.final_rank + '名</span>');
            } else if (p.resolution_status === "resolved") {
                badges.push('<span class="badge ready">已操作</span>');
            } else {
                badges.push('<span class="badge not-ready">未操作</span>');
            }
            if (p.move_submitted) badges.push('<span class="badge online">已出招</span>');

            // HP 颜色
            var hpClass = "card-hp";
            if (p.hp <= 1) hpClass += " hp-low";
            else hpClass += " hp-ok";

            // 动作显示
            var moveHtml = "";
            if (p.move_revealed || isSelf) {
                if (p.pending_move) {
                    moveHtml = '<div class="card-move move-visible">' +
                        (MOVE_LABELS[p.pending_move] || p.pending_move) + '</div>';
                }
            } else if (p.move_submitted) {
                moveHtml = '<div class="card-move">已提交</div>';
            }

            // 目标显示（仅自己可见）
            var targetHtml = "";
            if (isSelf && p.target_intent && p.target_intent.length > 0) {
                var targets = p.target_intent.map(function (tid) {
                    var tp = _findPlayer(players, tid);
                    return tp ? (tp.username || tp.player_id) : tid;
                });
                targetHtml = '<div class="card-target">→ ' + targets.join(", ") + '</div>';
            }

            html += '<div class="' + cardClasses.join(" ") + '">' +
                '<div class="card-name-row">' +
                '<span class="card-name">' + _esc(username) + '</span>' +
                '<span class="card-badges">' + badges.join("") + '</span>' +
                '</div>' +
                '<div class="' + hpClass + '">' + p.hp + '</div>' +
                '<div class="card-resources">' +
                _resItem("气", p.qi) +
                _resItem("盾", p.shield) +
                _resItem("火种", p.spark) +
                _resItem("电池", p.battery) +
                _resItem("镐", p.pickaxe) +
                _resItem("闪", (2 - (p.flash_used || 0)) + "/2") +
                '</div>' +
                moveHtml + targetHtml +
                '</div>';
        }

        document.getElementById("player-cards").innerHTML = html;
    };

    // ═══════════════════════════════════════════════════════
    // 速度层进度条
    // ═══════════════════════════════════════════════════════

    window.renderSpeedLayerBar = function (game) {
        var bar = document.getElementById("speed-layer-bar");
        if (!bar) return;

        var currentLayer = game.current_speed_layer || 0;

        // 在等待出招阶段，不显示
        if (game.phase === "waiting_moves" || game.phase === "resource_check" || game.phase === "reveal") {
            bar.style.display = "none";
            return;
        }

        bar.style.display = "";

        // 确定哪些层已完成
        var completedUpTo = 0;
        if (game.phase === "flash") completedUpTo = 1;
        else if (game.phase === "three_chain") completedUpTo = 1;
        else if (game.phase === "speed_layer") {
            // current_speed_layer 表示正在处理的层
            completedUpTo = Math.max(0, currentLayer - 1);
        } else if (game.phase === "death_check" || game.phase === "round_summary") {
            completedUpTo = 12;
        }

        var dotsHtml = "";
        for (var i = 1; i <= 12; i++) {
            var cls = "speed-layer-dot";
            if (i <= completedUpTo) cls += " done";
            else if (i === currentLayer && game.phase === "speed_layer") cls += " current";
            dotsHtml += '<div class="' + cls + '" title="层' + i + ': ' + (SPEED_LAYER_NAMES[i] || "") + '"></div>';
        }
        bar.innerHTML = dotsHtml;
    };

    // ═══════════════════════════════════════════════════════
    // 动作选择
    // ═══════════════════════════════════════════════════════

    window.renderMoveSelection = function (game, myPlayerId) {
        var player = _findPlayer(game.players, myPlayerId);
        if (!player || player.status === "dead") {
            document.getElementById("move-groups").innerHTML =
                '<div style="text-align:center;color:var(--muted);padding:20px;">你已死亡，无法操作。</div>';
            document.getElementById("move-status-line").textContent = "";
            return;
        }

        if (player.move_submitted) {
            document.getElementById("move-status-line").textContent = "✓ 已提交：" +
                (MOVE_LABELS[player.pending_move] || player.pending_move);
        } else {
            document.getElementById("move-status-line").textContent = "请选择一个动作";
        }

        var legalMoves = (game.legal_moves && game.legal_moves[myPlayerId]) || [];
        var legalSet = {};
        legalMoves.forEach(function (m) { legalSet[m] = true; });

        var selectedMove = window.__v2_selected_move || null;
        var groupsHtml = "";

        for (var groupKey in MOVE_GROUPS) {
            var group = MOVE_GROUPS[groupKey];
            groupsHtml += '<div class="move-group">' +
                '<div class="move-group-label">' + group.label + '</div>' +
                '<div class="move-grid">';

            for (var j = 0; j < group.moves.length; j++) {
                var m = group.moves[j];
                var label = MOVE_LABELS[m] || m;
                var isLegal = legalSet[m];
                var isSelected = (selectedMove === m);

                var classes = ["move-btn"];
                if (isSelected) classes.push("selected");
                if (!isLegal) classes.push("disabled");

                groupsHtml += '<button class="' + classes.join(" ") + '" ' +
                    'data-move="' + m + '" ' +
                    (isLegal ? '' : 'disabled') + ' ' +
                    'onclick="window.__v2_selectMove(\'' + m + '\')">' +
                    label + '</button>';
            }

            groupsHtml += '</div></div>';
        }

        document.getElementById("move-groups").innerHTML = groupsHtml;
        document.getElementById("submit-move-btn").disabled = !selectedMove;
    };

    // ═══════════════════════════════════════════════════════
    // 结算事件
    // ═══════════════════════════════════════════════════════

    window.renderSettlementEvents = function (game) {
        var container = document.getElementById("settlement-events");
        var history = game.history;
        if (!history || history.length === 0) {
            container.innerHTML = '<div class="settlement-event ev-info">暂无事件。</div>';
            return;
        }

        var log = history[history.length - 1];
        var events = log.speed_layer_events || [];
        if (events.length === 0) {
            container.innerHTML = '<div class="settlement-event ev-info">本回合无结算事件。</div>';
            return;
        }

        var html = "";
        var lastLayer = -1;
        for (var i = 0; i < events.length; i++) {
            var ev = events[i];
            var layer = ev.speed_layer || 0;
            if (layer !== lastLayer) {
                html += '<div style="margin-top:6px;font-weight:bold;font-size:12px;color:var(--muted);">' +
                    '层 ' + layer + ' · ' + (SPEED_LAYER_NAMES[layer] || "") + '</div>';
                lastLayer = layer;
            }
            var evClass = _eventClass(ev.event_type);
            html += '<div class="settlement-event ' + evClass + '">' +
                '<span class="settlement-layer-label">层' + layer + '</span>' +
                _esc(ev.detail || "") + '</div>';
        }

        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    };

    // ═══════════════════════════════════════════════════════
    // 对局结束
    // ═══════════════════════════════════════════════════════

    window.renderGameOver = function (room) {
        var card = document.getElementById("game-over-card");
        var body = document.getElementById("game-over-body");
        card.style.display = "";

        var game = room.game;
        if (!game) return;

        // 排名
        var players = game.players || [];
        players.sort(function (a, b) { return (a.final_rank || 99) - (b.final_rank || 99); });

        var html = '<ul class="rank-list">';
        for (var i = 0; i < players.length; i++) {
            var p = players[i];
            var rank = p.final_rank || "?";
            var cls = "rank-item";
            if (rank === 1) cls += " rank-1";
            html += '<li class="' + cls + '">' +
                '<span class="rank-name">' + _esc(p.username || p.player_id) + '</span>' +
                '<span class="rank-badge">第' + rank + '名</span>' +
                '</li>';
        }
        html += '</ul>';

        if (game.winner) {
            var wp = _findPlayer(players, game.winner);
            html += '<div class="summary-winner">🏆 ' + (wp ? _esc(wp.username || wp.player_id) : game.winner) + ' 获胜！</div>';
        }

        body.innerHTML = html;

        // 重赛投票
        var votes = room.rematch_votes || {};
        var voteCount = Object.keys(votes).length;
        var playerCount = room.player_count;
        document.getElementById("rematch-vote-btn").style.display = (room.my_role === "player") ? "" : "none";
        document.getElementById("rematch-status").textContent = "重赛投票：" + voteCount + " / " + playerCount;
    };

    // ═══════════════════════════════════════════════════════
    // 聊天渲染
    // ═══════════════════════════════════════════════════════

    window.renderChatMessages = function (messages) {
        var container = document.getElementById("chat-messages");
        if (!container) return;
        var html = "";
        for (var i = 0; i < messages.length; i++) {
            var msg = messages[i];
            var time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "";
            html += '<div class="chat-item">' +
                '<span class="chat-sender">' + _esc(msg.sender || "") + '</span>' +
                '<span class="chat-text">' + _esc(msg.message || "") + '</span>' +
                '<span class="chat-time">' + time + '</span>' +
                '</div>';
        }
        container.innerHTML = html;
        if (html) container.scrollTop = container.scrollHeight;
    };

    window.appendChatItem = function (msg) {
        var container = document.getElementById("chat-messages");
        if (!container) return;
        var time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "";
        var div = document.createElement("div");
        div.className = "chat-item";
        div.innerHTML = '<span class="chat-sender">' + _esc(msg.sender || "") + '</span>' +
            '<span class="chat-text">' + _esc(msg.message || "") + '</span>' +
            '<span class="chat-time">' + time + '</span>';
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    };

    // ═══════════════════════════════════════════════════════
    // 历史渲染
    // ═══════════════════════════════════════════════════════

    window.renderHistory = function (history) {
        var container = document.getElementById("history");
        if (!container) return;
        if (!history || history.length === 0) {
            container.innerHTML = '<div style="color:var(--muted);font-size:13px;">暂无回合记录。</div>';
            return;
        }

        var html = "";
        for (var i = history.length - 1; i >= 0; i--) {
            var r = history[i];
            html += '<div class="history-entry">' +
                '<div class="history-round">第 ' + r.round_num + ' 回合</div>' +
                '<div class="history-moves">';

            var moves = r.moves || {};
            for (var pid in moves) {
                html += pid + ': ' + (MOVE_LABELS[moves[pid]] || moves[pid]) + ' ';
            }

            html += '</div>';
            if (r.deaths && r.deaths.length > 0) {
                html += '<div style="color:#dc2626;font-size:12px;">死亡: ';
                for (var j = 0; j < r.deaths.length; j++) {
                    html += r.deaths[j].player_id + ' ';
                }
                html += '</div>';
            }
            html += '</div>';
        }
        container.innerHTML = html;
    };

    // ═══════════════════════════════════════════════════════
    // 内部辅助函数
    // ═══════════════════════════════════════════════════════

    function _findSeat(seats, seatIndex) {
        if (!seats) return null;
        for (var i = 0; i < seats.length; i++) {
            if (seats[i].seat_index === seatIndex) return seats[i];
        }
        return null;
    }

    function _findSeatByPlayerId(seats, playerId) {
        if (!seats) return null;
        for (var i = 0; i < seats.length; i++) {
            if (seats[i].player_id === playerId) return seats[i];
        }
        return null;
    }

    function _findPlayer(players, playerId) {
        if (!players) return null;
        for (var i = 0; i < players.length; i++) {
            if (players[i].player_id === playerId) return players[i];
        }
        return null;
    }

    function _resItem(label, value) {
        var valClass = "res-value";
        if (value > 0) valClass += " res-highlight";
        return '<div class="resource-item">' +
            '<div class="res-label">' + label + '</div>' +
            '<div class="' + valClass + '">' + value + '</div>' +
            '</div>';
    }

    function _startConditionText(cond) {
        switch (cond) {
        case "host": return "房主手动开始";
        case "all_ready": return "全员准备";
        case "full": return "满员自动";
        default: return cond;
        }
    }

    function _eventClass(eventType) {
        if (!eventType) return "ev-info";
        if (eventType.indexOf("attack") === 0 || eventType.indexOf("gi_") === 0) return "ev-attack";
        if (eventType.indexOf("block") >= 0 || eventType.indexOf("miss") >= 0) return "ev-block";
        if (eventType.indexOf("trick") >= 0 || eventType.indexOf("chi") >= 0) return "ev-trick";
        if (eventType.indexOf("resource") >= 0 || eventType.indexOf("pickaxe") >= 0) return "ev-resource";
        if (eventType.indexOf("death") >= 0) return "ev-death";
        return "ev-info";
    }

    function _esc(s) {
        if (!s) return "";
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
})();
