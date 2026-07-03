/**
 * ClapClap 2.0 本地模拟对战 —— UI 渲染层
 * 对齐 v1 local_page_ui.js 风格，扩展多人布局 + 结算进度 + 内联决策区
 */

/* ═══════════════════════════════════════════════════════════════
   准备阶段
   ═══════════════════════════════════════════════════════════════ */

function renderSetupPhase() {
    var countEl = document.getElementById("setup-count");
    countEl.textContent = v2PlayerCount;

    var grid = document.getElementById("setup-players-grid");

    // 根据人数设置列数
    var cols;
    if (v2PlayerCount <= 2) cols = 2;
    else if (v2PlayerCount === 3) cols = 3;
    else if (v2PlayerCount === 4) cols = 2;
    else cols = 3;  // 5~6

    grid.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";

    // 初始化 playerTypes 数组
    while (v2PlayerTypes.length < v2PlayerCount) v2PlayerTypes.push("human");
    v2PlayerTypes.length = v2PlayerCount;

    var html = "";
    for (var i = 0; i < v2PlayerCount; i++) {
        var name = v2PlayerNames[i] || ("玩家" + (i + 1));
        var color = V2_PLAYER_COLORS[i];
        var isAi = v2PlayerTypes[i] === "ai";
        html += '<div class="setup-player-card">';
        html += '<div class="setup-player-avatar" style="background:' + color + ';">' + (i + 1) + '</div>';
        html += '<div class="setup-player-number">玩家 ' + (i + 1) + '</div>';
        html += '<input type="text" id="setup-name-' + i + '" value="' + escHtml(name) + '" maxlength="10" placeholder="输入名称" />';
        // 类型切换
        html += '<div class="setup-player-type">';
        html += '<button class="setup-type-btn' + (isAi ? '' : ' active') + '" id="setup-type-human-' + i + '" data-idx="' + i + '" data-type="human">👤 人类</button>';
        html += '<button class="setup-type-btn' + (isAi ? ' active' : '') + '" id="setup-type-ai-' + i + '" data-idx="' + i + '" data-type="ai">🤖 AI</button>';
        html += '</div>';
        // AI 难度选择（仅 AI 玩家显示）
        html += '<div class="setup-ai-difficulty" id="setup-ai-diff-' + i + '" style="display:' + (isAi ? '' : 'none') + ';">';
        html += '<select id="setup-ai-diff-select-' + i + '">';
        html += '<option value="normal"' + (v2AiDifficulty === "normal" ? " selected" : "") + '>普通 AI</option>';
        html += '<option value="random"' + (v2AiDifficulty === "random" ? " selected" : "") + '>随机 AI</option>';
        html += '</select>';
        html += '</div>';
        html += '</div>';
    }
    grid.innerHTML = html;

    for (var i2 = 0; i2 < v2PlayerCount; i2++) {
        var input = document.getElementById("setup-name-" + i2);
        if (input) {
            (function(idx) {
                input.addEventListener("input", function() {
                    v2PlayerNames[idx] = this.value.trim() || ("玩家" + (idx + 1));
                });
            })(i2);
        }

        // 类型切换按钮
        var humanBtn = document.getElementById("setup-type-human-" + i2);
        var aiBtn = document.getElementById("setup-type-ai-" + i2);
        if (humanBtn && aiBtn) {
            (function(idx, hBtn, aBtn) {
                hBtn.addEventListener("click", function() {
                    v2PlayerTypes[idx] = "human";
                    hBtn.classList.add("active");
                    aBtn.classList.remove("active");
                    var diffEl = document.getElementById("setup-ai-diff-" + idx);
                    if (diffEl) diffEl.style.display = "none";
                });
                aBtn.addEventListener("click", function() {
                    v2PlayerTypes[idx] = "ai";
                    aBtn.classList.add("active");
                    hBtn.classList.remove("active");
                    var diffEl = document.getElementById("setup-ai-diff-" + idx);
                    if (diffEl) diffEl.style.display = "";
                });
            })(i2, humanBtn, aiBtn);
        }

        // AI 难度选择
        var diffSelect = document.getElementById("setup-ai-diff-select-" + i2);
        if (diffSelect) {
            (function(idx) {
                diffSelect.addEventListener("change", function() {
                    v2AiDifficulty = this.value;
                });
            })(i2);
        }
    }
}

/* ═══════════════════════════════════════════════════════════════
   对局主入口
   ═══════════════════════════════════════════════════════════════ */

function renderV2State(state) {
    v2LatestState = state;
    var players = state.players || [];
    var catalog = state.move_catalog || [];
    var legalMoves = state.legal_moves || {};
    var logs = state.history || [];

    // 状态栏
    var winnerText = state.winner === null ? "进行中" :
        (state.winner === "" ? "平局" : (getPlayerName(state.winner, players) + " 获胜"));
    var aliveCount = state.alive_count || 0;
    document.getElementById("status-bar").innerHTML =
        '<span class="status-badge">回合 ' + state.round_num + '</span>' +
        '<span class="winner-badge">' + winnerText + '</span>' +
        '<span class="turn-badge">存活 ' + aliveCount + ' 人</span>';

    document.getElementById("reset-btn").style.display = "";

    // 玩家卡片
    renderPlayerCards(players);

    // 动作选择区
    if (!state.is_game_over && state.phase !== "finished") {
        document.getElementById("move-selection-card").style.display = "";
        renderMoveSelectors(players, legalMoves, catalog);
    } else {
        document.getElementById("move-selection-card").style.display = "none";
    }

    // 最近回合
    var lastLog = logs.length > 0 ? logs[logs.length - 1] : null;
    document.getElementById("latest-round").innerHTML = renderLatestRound(lastLog, players);

    // 历史
    renderHistory(logs, players);
}

/* ═══════════════════════════════════════════════════════════════
   玩家资源卡片 —— 与 v1 风格一致，根据人数调整列数
   ═══════════════════════════════════════════════════════════════ */

function renderPlayerCards(players) {
    var container = document.getElementById("player-cards");
    var aliveCount = players.filter(function(p) { return p.status === "alive"; }).length || players.length;

    // 根据存活人数动态调整列数
    var cols;
    if (aliveCount <= 2) cols = 2;
    else if (aliveCount === 3) cols = 3;
    else if (aliveCount === 4) cols = 2;   // 2x2
    else cols = 3;                          // 5~6: 3x2

    container.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";

    var html = "";
    for (var i = 0; i < players.length; i++) {
        var p = players[i];
        var color = V2_PLAYER_COLORS[i] || "#888";
        var isDead = p.status === "dead";
        var isFocused = p.player_id === v2FocusedPlayer;
        var cls = "player-panel" + (isDead ? " dead" : "") + (isFocused ? " focused" : "");

        var isAi = v2AiPlayerIds.indexOf(p.player_id) >= 0;
        html += '<div class="' + cls + '" data-player-id="' + p.player_id + '" title="' + (isAi ? 'AI 玩家' : '点击切换焦点') + '">';
        html += '<div class="player-name">';
        html += '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + color + ';"></span> ';
        html += escHtml(p.username);
        if (isAi) html += ' <span class="ai-badge">🤖 AI</span>';
        if (isDead) html += ' <span class="danger-text">(已淘汰)</span>';
        html += '</div>';

        if (isDead) {
            html += '<div class="player-status">死亡于 R' + (p.death_round || "?") +
                ' · ' + (V2_DEATH_LABELS[p.death_cause] || p.death_cause || "?");
            if (p.final_rank != null) html += ' · 第' + p.final_rank + '名';
            html += '</div>';
        } else {
            var st = "";
            if (p.move_revealed && p.pending_move) st = '亮招: ' + (V2_MOVE_LABELS[p.pending_move] || p.pending_move);
            else if (p.move_submitted) st = '已提交';
            else st = '等待出招';
            if (p.is_flashed) st += " [闪]";
            if (p.resolution_status === "resolved") st += " ✓已操作";
            html += '<div class="player-status">' + st + '</div>';
        }

        html += '<div class="resource-grid">';
        html += resourceItem("生命", p.hp, "hp");
        html += resourceItem("气", p.qi, "qi");
        html += resourceItem("盾", p.shield, "shield");
        html += resourceItem("火种", p.spark, "spark");
        html += resourceItem("电池", p.battery, "battery");
        html += resourceItem("镐", p.pickaxe, "pickaxe");
        html += resourceItem("闪次数", (p.flash_used != null ? (2 - p.flash_used) : 2), "flash");
        html += '</div>';
        html += '</div>';
    }
    container.innerHTML = html;

    var cards = container.querySelectorAll(".player-panel");
    for (var j = 0; j < cards.length; j++) {
        (function(pid) {
            cards[j].addEventListener("click", function() {
                v2FocusedPlayer = pid;
                if (v2LatestState) renderV2State(v2LatestState);
            });
        })(players[j].player_id);
    }
}

function resourceItem(label, value, key) {
    return '<div class="resource-item' + (key ? " theme-" + key : "") + '">' +
        '<div class="resource-label">' + label + '</div>' +
        '<div class="resource-value">' + value + '</div>' +
        '</div>';
}

/* ═══════════════════════════════════════════════════════════════
   动作选择区 —— 与 v1 风格一致，根据人数调整列数
   ═══════════════════════════════════════════════════════════════ */

function v2GetMoveGroups(catalog) {
    var groups = { resource: [], attack_qi: [], attack_shield: [], defense: [], trick: [], special: [] };
    for (var i = 0; i < catalog.length; i++) {
        var item = catalog[i];
        if (item.name === "QI" || item.name === "SHIELD" || item.name === "GAO") groups.resource.push(item);
        else if (["GI","PO","LENG_FENG","RU_LAI","HEI_DONG"].indexOf(item.name) !== -1) groups.attack_qi.push(item);
        else if (["FIRE","SHAN_DIAN","LIE_YAN","SHINING"].indexOf(item.name) !== -1) groups.attack_shield.push(item);
        else if (["SHI_ZI","BA_GUA"].indexOf(item.name) !== -1) groups.defense.push(item);
        else if (["CHI","SHUANG_CHI"].indexOf(item.name) !== -1) groups.trick.push(item);
        else groups.special.push(item);
    }
    return groups;
}

function v2CategoryTitle(cat) {
    var map = { resource: "资源", attack_qi: "气系攻击", attack_shield: "盾系攻击", defense: "防御", trick: "锦囊", special: "特殊" };
    return map[cat] || cat;
}

function renderMoveSelectors(players, legalMoves, catalog) {
    var container = document.getElementById("move-selectors");
    var aliveOnly = players.filter(function(p) { return p.status === "alive"; });

    // 根据存活人数动态调整列数
    var n = aliveOnly.length;
    var cols;
    if (n <= 2) cols = n;
    else if (n === 3) cols = 3;
    else if (n === 4) cols = 2;    // 2x2
    else cols = 3;                 // 5~6: 3x2

    container.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";

    if (n === 0) {
        container.innerHTML = '<div class="muted">所有玩家已淘汰。</div>';
        return;
    }

    // 确保焦点玩家是人类玩家
    var humanAlive = aliveOnly.filter(function(p) { return v2AiPlayerIds.indexOf(p.player_id) < 0; });
    if (humanAlive.length === 0) humanAlive = aliveOnly; // 全是 AI 时回退
    if (!v2FocusedPlayer || !aliveOnly.some(function(p) { return p.player_id === v2FocusedPlayer; })) {
        v2FocusedPlayer = humanAlive[0].player_id;
    }
    // 如果焦点是 AI 且有人类存活，切换到第一个人类
    if (v2AiPlayerIds.indexOf(v2FocusedPlayer) >= 0 && humanAlive.length > 0 && humanAlive !== aliveOnly) {
        v2FocusedPlayer = humanAlive[0].player_id;
    }

    var focusedName = getPlayerName(v2FocusedPlayer, players);
    var hasAi = v2AiPlayerIds.length > 0;
    document.getElementById("focused-player-label").textContent = "键盘焦点：" + focusedName + "（Tab 切换）" + (hasAi ? "  |  🤖 AI 自动出招" : "");

    var allGroups = v2GetMoveGroups(catalog);

    var html = "";
    for (var i = 0; i < aliveOnly.length; i++) {
        var p = aliveOnly[i];
        var pid = p.player_id;
        var color = V2_PLAYER_COLORS[i] || "#888";
        var isFocused = pid === v2FocusedPlayer;
        var isAi = v2AiPlayerIds.indexOf(pid) >= 0;
        var movesForPlayer = isAi ? [] : (legalMoves[pid] || []);
        var selectedMove = v2SelectedMoves[pid] || null;

        html += '<div class="move-side' + (isFocused ? " focused" : "") + (isAi ? " ai-player" : "") + '" style="border-left:3px solid ' + color + ';">';
        html += '<h3>' + escHtml(p.username);
        if (isAi) {
            html += '<span class="ai-badge">🤖 AI</span>';
        }
        html += '<span class="active-turn-tip">' + (isAi ? '自动' : (selectedMove ? '已选' : '未选')) + '</span></h3>';

        if (isAi) {
            // AI 占位：显示难度和自动提示
            html += '<div class="selector-selected ai-placeholder">';
            html += '<span class="muted">🤖 AI 自动选择中...</span>';
            html += '<div class="ai-difficulty-tag">难度：' + (v2AiDifficulty === "random" ? "随机" : "普通") + '</div>';
            html += '</div>';
        } else {
            html += '<div class="selector-selected">';
            html += selectedMove ? ('<b>' + (V2_MOVE_LABELS[selectedMove] || selectedMove) + '</b><span class="muted"> · 再按同键或 Enter 提交</span>') : '<span class="muted">—</span>';
            html += '</div>';

            // 按类别输出
            var catKeys = ["resource", "defense", "trick", "attack_qi", "attack_shield", "special"];
            for (var c = 0; c < catKeys.length; c++) {
                var cat = catKeys[c];
                var items = allGroups[cat] || [];
                var catMoves = items.filter(function(m) { return movesForPlayer.indexOf(m.name) !== -1; });
                if (catMoves.length === 0) continue;

                html += '<div class="move-group-title">' + v2CategoryTitle(cat) + '</div>';
                html += '<div class="move-grid">';
                for (var m = 0; m < catMoves.length; m++) {
                    var mv = catMoves[m];
                    var isSelected = selectedMove === mv.name;
                    var hotkey = v2KeyForMove(mv.name);
                    html += '<div class="move-btn-wrap">';
                    html += '<button class="move-btn' + (isSelected ? " selected" : "") + '"';
                    html += ' data-player="' + pid + '" data-move="' + mv.name + '"';
                    if (isSelected) html += ' style="border-color:' + color + ';background:' + color + '15;color:' + color + ';"';
                    html += '>';
                    if (hotkey) html += '<span class="move-hotkey">' + hotkey + '</span>';
                    html += '<div class="move-label">' + (V2_MOVE_LABELS[mv.name] || mv.label) + '</div>';
                    html += '<div class="move-name">' + mv.label + '</div>';
                    html += '</button>';
                    html += '</div>';
                }
                html += '</div>';
            }
        }
        html += '</div>';
    }
    container.innerHTML = html;

    // 绑定点击
    var buttons = container.querySelectorAll(".move-btn");
    for (var b = 0; b < buttons.length; b++) {
        buttons[b].addEventListener("click", function() {
            var pid = this.getAttribute("data-player");
            var mv = this.getAttribute("data-move");
            var wasSelected = v2SelectedMoves[pid] === mv;
            v2SelectedMoves[pid] = mv;
            if (v2LatestState) renderV2State(v2LatestState);
            if (wasSelected && typeof v2AllAlivePlayersSelected === "function" && v2AllAlivePlayersSelected()) {
                submitMoves();
            }
        });
    }

    updateStepButton(aliveOnly);
    updateSelectionInfo(aliveOnly, cols);
}

function updateStepButton(alivePlayers) {
    var btn = document.getElementById("step-btn");
    var allSelected = true;
    for (var i = 0; i < alivePlayers.length; i++) {
        if (!v2SelectedMoves[alivePlayers[i].player_id]) { allSelected = false; break; }
    }
    btn.disabled = !allSelected || (v2LatestState && v2LatestState.is_game_over);
    btn.textContent = allSelected ? "提交本回合" : "等待全部选择完成";
}

function updateSelectionInfo(alivePlayers, cols) {
    var row = document.getElementById("selection-info-row");
    if (!row) return;
    row.style.gridTemplateColumns = "repeat(" + (cols || 2) + ", 1fr)";
    var html = "";
    for (var i = 0; i < alivePlayers.length; i++) {
        var p = alivePlayers[i];
        var mv = v2SelectedMoves[p.player_id];
        html += '<div class="selection-box">';
        html += escHtml(p.username) + '：';
        html += mv ? ('<b>' + (V2_MOVE_LABELS[mv] || mv) + '</b>') : '<span class="muted">未选择</span>';
        html += '</div>';
    }
    row.innerHTML = html;
}

/* ═══════════════════════════════════════════════════════════════
   结算进度
   ═══════════════════════════════════════════════════════════════ */

function renderSettlementProgress(result) {
    v2SettlementResult = result;
    var card = document.getElementById("settlement-card");
    card.style.display = "";
    document.getElementById("decision-area").style.display = "none";

    var layer = result.current_speed_layer || 0;
    var layerName = V2_SPEED_LAYER_NAMES[layer] || "";
    var progressData = result.progress_data || {};
    var phaseName = progressData.phase_name || result.phase || "";
    document.getElementById("settlement-phase-label").textContent = "— " + escHtml(phaseName);

    // 速度层进度条
    var barHtml = '<div class="phase-indicator">速度层 ' + layer + '/12' + (layerName ? ' — ' + layerName : '') + '</div>';
    barHtml += renderSpeedLayerBar(layer);
    document.getElementById("settlement-phase-bar").innerHTML = barHtml;

    // 事件流（含自动决策原因）—— Step8: 默认折叠
    var events = getEventsFromLatestRound(v2LatestState);
    var decisionLog = getDecisionLogFromLatestRound(v2LatestState);
    var feedHtml = "";

    // 先显示结算事件
    if (events.length > 0) {
        for (var i = 0; i < events.length; i++) {
            var ev = events[i];
            feedHtml += '<div class="event-item">';
            feedHtml += '<span class="ev-layer">[L' + ev.speed_layer + ']</span> ';
            feedHtml += escHtml(ev.detail || "");
            feedHtml += '</div>';
        }
    }

    // 再显示自动决策原因日志
    if (decisionLog.length > 0) {
        feedHtml += '<div class="auto-decision-log">';
        feedHtml += '<div style="padding:6px 10px;font-weight:bold;font-size:12px;color:#e67e22;border-bottom:1px solid #f0f0f0;">自动决策原因</div>';
        for (var d = 0; d < decisionLog.length; d++) {
            var dl = decisionLog[d];
            feedHtml += '<div class="ad-item">';
            feedHtml += '[L' + (dl.speed_layer || "?") + '] <b>' + escHtml(getPlayerName(dl.player_id)) + '</b>: ' + escHtml(dl.reason || "");
            feedHtml += '</div>';
        }
        feedHtml += '</div>';
    }

    // Step8: 默认折叠详细日志
    var collapsed = v2Settings.collapseSettlementLog !== false; // 默认 true
    var feedEl = document.getElementById("settlement-event-feed");
    feedEl.innerHTML = feedHtml;
    var collapseToggle = document.getElementById("settlement-collapse-toggle");
    if (collapseToggle) {
        if (collapsed) {
            feedEl.classList.add("collapsed");
            collapseToggle.textContent = "▶ 展开详细日志 (" + events.length + " 条事件)";
        } else {
            feedEl.classList.remove("collapsed");
            collapseToggle.textContent = "▼ 收起详细日志";
        }
        collapseToggle.style.display = (events.length > 0 || decisionLog.length > 0) ? "" : "none";
        collapseToggle.onclick = function () {
            var isCollapsed = feedEl.classList.contains("collapsed");
            if (isCollapsed) {
                feedEl.classList.remove("collapsed");
                collapseToggle.textContent = "▼ 收起详细日志";
                v2Settings.collapseSettlementLog = false;
            } else {
                feedEl.classList.add("collapsed");
                collapseToggle.textContent = "▶ 展开详细日志 (" + events.length + " 条事件)";
                v2Settings.collapseSettlementLog = true;
            }
            v2SaveSettings();
        };
    }

    // 决策请求
    var decisionReqs = result.decision_requests || [];
    if (result.action === "request_decision" && decisionReqs.length > 0) {
        renderDecisionArea(decisionReqs, layer, layerName);
    }
}

function renderSpeedLayerBar(currentLayer) {
    var html = '<div class="speed-layer-bar">';
    for (var l = 1; l <= 12; l++) {
        var cls = "speed-layer-dot";
        if (l < currentLayer) cls += " done";
        else if (l === currentLayer) cls += " current";
        html += '<div class="' + cls + '">' + l +
            '<span class="speed-layer-tooltip">L' + l + ': ' + (V2_SPEED_LAYER_NAMES[l] || "") + '</span></div>';
    }
    html += '</div>';
    return html;
}

function hideSettlementProgress() {
    document.getElementById("settlement-card").style.display = "none";
    document.getElementById("decision-area").style.display = "none";
    v2SettlementResult = null;
}

/* ═══════════════════════════════════════════════════════════════
   内联决策区
   ═══════════════════════════════════════════════════════════════ */

function renderDecisionArea(decisionRequests, layer, layerName) {
    var area = document.getElementById("decision-area");
    area.style.display = "";

    layer = layer || ((v2SettlementResult && v2SettlementResult.current_speed_layer) || 0);
    layerName = layerName || V2_SPEED_LAYER_NAMES[layer] || "";

    var heading = area.querySelector(".decision-heading");
    if (heading) {
        heading.textContent = "速度层 " + layer + " — " + (layerName || "选择目标");
    }

    var content = document.getElementById("decision-content");
    var html = "";
    for (var r = 0; r < decisionRequests.length; r++) {
        html += renderSingleDecision(decisionRequests[r]);
    }
    content.innerHTML = html;
    bindDecisionOptionClicks();
    autoSelectFirstValidOptions();
}

function autoSelectFirstValidOptions() {
    var segments = document.querySelectorAll("#decision-content .decision-options");
    for (var i = 0; i < segments.length; i++) {
        var opts = segments[i].querySelectorAll(".decision-option");
        var selected = false;
        for (var j = 0; j < opts.length; j++) {
            if (opts[j].getAttribute("data-valid") !== "false" && !selected) {
                opts[j].classList.add("selected");
                selected = true;
            }
        }
    }
}

function renderSingleDecision(req) {
    var html = "";
    var playerId = req.player_id || "";
    var playerName = getPlayerName(playerId, (v2LatestState && v2LatestState.players) || []);
    var prompt = req.prompt || "";
    var options = req.options || [];
    var splitCount = req.split_count || 1;

    // 决策提示
    html += '<div class="decision-prompt"><b>' + escHtml(playerName) + '</b>：' + escHtml(prompt);
    if (splitCount > 1) html += '（需选 ' + splitCount + ' 段，请为每段分别选择目标）';
    html += '</div>';

    if (splitCount > 1) {
        // 多段选择（如黑洞3段、Shining2段、双吃2段）
        for (var seg = 0; seg < splitCount; seg++) {
            html += '<div class="decision-segment"><div class="seg-title">第 ' + (seg + 1) + ' 段</div>';
            html += '<div class="decision-options" data-player="' + playerId + '" data-segment="' + seg + '">';
            html += decisionOptionList(options);
            html += '</div></div>';
        }
        // 添加放空全部按钮
        html += '<div style="margin-top:4px;font-size:11px;color:#888;">提示：每段独立选择。可选同一目标多次，或选择「放空」跳过某段。</div>';
    } else {
        html += '<div class="decision-options" data-player="' + playerId + '" data-segment="0">';
        html += decisionOptionList(options);
        html += '</div>';
    }
    return html;
}

function decisionOptionList(options) {
    var h = "";
    for (var o = 0; o < options.length; o++) {
        var opt = options[o];
        var optId = opt.option_id !== undefined ? opt.option_id : opt;
        var optLabel = opt.label || optId;
        if (optId === "") optLabel = "放空";
        var isValid = opt.is_valid !== false;
        h += '<div class="decision-option' + (!isValid ? " invalid" : "") + '"';
        h += ' data-option-id="' + escHtml(String(optId)) + '" data-valid="' + isValid + '">';
        h += '<span class="option-label">' + escHtml(optLabel) + '</span>';
        if (!isValid && opt.reason) h += ' <span class="option-reason">' + escHtml(opt.reason) + '</span>';
        h += '</div>';
    }
    return h;
}

function bindDecisionOptionClicks() {
    var options = document.querySelectorAll("#decision-content .decision-option");
    for (var i = 0; i < options.length; i++) {
        options[i].addEventListener("click", function() {
            if (this.getAttribute("data-valid") === "false") return;
            var parent = this.parentElement;
            // 同一 segment 内只能单选
            var siblings = parent.querySelectorAll(".decision-option");
            for (var s = 0; s < siblings.length; s++) siblings[s].classList.remove("selected");
            this.classList.add("selected");
        });
    }
}

/**
 * 收集决策数据。
 * 对于拆分技能（多段），返回 {player_id: [target1, target2, ...]}。
 * 对于单段技能，返回 {player_id: target_id}。
 */
function collectDecisionData() {
    var decisions = {};
    var segments = document.querySelectorAll("#decision-content .decision-options");
    for (var i = 0; i < segments.length; i++) {
        var seg = segments[i];
        var playerId = seg.getAttribute("data-player");
        var segIdx = parseInt(seg.getAttribute("data-segment") || "0");
        var selected = seg.querySelector(".decision-option.selected");
        var optId = selected ? selected.getAttribute("data-option-id") : "";

        if (!decisions[playerId]) {
            decisions[playerId] = [];
            // 预填充空值以保证索引位置正确
            for (var s = 0; s < segIdx; s++) {
                decisions[playerId].push("");
            }
        }

        // 确保数组长度足够
        while (decisions[playerId].length <= segIdx) {
            decisions[playerId].push("");
        }
        decisions[playerId][segIdx] = optId;
    }

    // 如果只有一个选项且是单段，简化为字符串
    var keys = Object.keys(decisions);
    for (var k = 0; k < keys.length; k++) {
        var arr = decisions[keys[k]];
        // 过滤掉全空的段
        var nonEmpty = arr.filter(function(x) { return x !== ""; });
        if (arr.length === 1) {
            decisions[keys[k]] = arr[0];
        }
    }
    return decisions;
}

function hideDecisionArea() {
    document.getElementById("decision-area").style.display = "none";
    document.getElementById("decision-content").innerHTML = "";
}

/* ═══════════════════════════════════════════════════════════════
   回合总结与对局结束
   ═══════════════════════════════════════════════════════════════ */

function renderRoundSummaryCard(summary) {
    if (!summary) return;
    v2RoundSummaryShown = true;
    var card = document.getElementById("round-summary-card");
    card.style.display = "";
    document.getElementById("round-summary-title").textContent = "回合 " + (summary.round_num || "?") + " 结算完成";

    var content = document.getElementById("round-summary-content");
    var html = "";

    // 本回合动作
    var moves = summary.moves || {};
    var moveKeys = Object.keys(moves);
    if (moveKeys.length > 0) {
        html += '<div class="summary-section"><h3>本回合动作</h3><div class="summary-moves">';
        for (var i = 0; i < moveKeys.length; i++) {
            var pid = moveKeys[i];
            html += '<span class="summary-move-tag">' + escHtml(getPlayerName(pid)) + ': <b>' + (V2_MOVE_LABELS[moves[pid]] || moves[pid]) + '</b></span>';
        }
        html += '</div></div>';
    }

    // 闪
    var flashed = summary.flashed_players || [];
    if (flashed.length > 0) {
        html += '<div class="summary-section"><h3>使用闪</h3>' + flashed.map(function(pid) { return escHtml(getPlayerName(pid)); }).join(" · ") + '</div>';
    }

    // 三连
    var tc = summary.three_chain || {};
    if (tc.groups && tc.groups.length > 0) {
        html += '<div class="summary-section"><h3>三连</h3>';
        for (var g = 0; g < tc.groups.length; g++) {
            html += '<div style="color:#e67e22;font-weight:bold;">' + escHtml((tc.groups[g].players || []).map(function(pid) { return getPlayerName(pid); }).join(" → ")) + '</div>';
        }
        if (tc.two_groups) html += '<div class="danger-text">两组独立三连！本回合结束。</div>';
        html += '</div>';
    }

    // 死亡
    var deaths = summary.deaths || [];
    if (deaths.length > 0) {
        html += '<div class="summary-section"><h3>死亡</h3>';
        for (var d = 0; d < deaths.length; d++) {
            html += '<div class="summary-death">' + escHtml(getPlayerName(deaths[d].player_id)) + ' — ' + (V2_DEATH_LABELS[deaths[d].cause] || deaths[d].cause || "?") + '</div>';
        }
        html += '</div>';
    }

    // 资源变化
    var changes = summary.resource_changes || {};
    var chgKeys = Object.keys(changes);
    if (chgKeys.length > 0) {
        html += '<div class="summary-section"><h3>资源变化</h3>';
        for (var c = 0; c < chgKeys.length; c++) {
            var cpid = chgKeys[c];
            var chg = changes[cpid];
            var ck = Object.keys(chg);
            var parts = [];
            for (var k = 0; k < ck.length; k++) {
                var key = ck[k], val = chg[key];
                parts.push(key + ': <span class="' + (val > 0 ? "good-text" : (val < 0 ? "danger-text" : "")) + '">' + (val > 0 ? "+" : "") + val + '</span>');
            }
            html += '<div class="summary-change">' + escHtml(getPlayerName(cpid)) + '：' + parts.join(" · ") + '</div>';
        }
        html += '</div>';
    }

    // 对局状态
    if (summary.game_ended) {
        html += '<div class="summary-section"><h3>对局结束</h3>';
        html += '<div class="end-inline-content"><div class="big-result">' + escHtml(summary.winner === "" ? "平局！" : (getPlayerName(summary.winner) + " 获胜！")) + '</div></div>';
        html += '</div>';
    } else {
        html += '<div class="summary-section">存活 ' + (summary.alive_count || 0) + ' 人，准备下一回合。</div>';
    }

    content.innerHTML = html;
    var contBtn = document.getElementById("round-summary-continue-btn");
    contBtn.textContent = summary.game_ended ? "查看最终排名" : "继续下一回合";
}

function hideRoundSummaryCard() {
    document.getElementById("round-summary-card").style.display = "none";
    v2RoundSummaryShown = false;
}

function renderEndCard(state) {
    if (v2EndShown) return;
    v2EndShown = true;
    var players = state.players || [];
    var winnerId = state.winner;
    var resultText = winnerId === "" ? "平局！" : (getPlayerName(winnerId, players) + " 获胜！");

    var ranked = players.filter(function(p) { return p.final_rank != null; }).sort(function(a, b) { return (a.final_rank || 99) - (b.final_rank || 99); });
    var detailText = ranked.map(function(p) { return "第" + p.final_rank + "名: " + p.username; }).join(" · ");

    document.getElementById("end-result-text").textContent = resultText;
    document.getElementById("end-result-detail").textContent = detailText;
    document.getElementById("end-card").style.display = "";
}

function hideEndCard() {
    document.getElementById("end-card").style.display = "none";
    v2EndShown = false;
}

/* ═══════════════════════════════════════════════════════════════
   最近回合 + 历史记录 —— 与 v1 一致
   ═══════════════════════════════════════════════════════════════ */

function renderLatestRound(log, players) {
    if (!log) return '<span class="muted">当前还没有回合记录。</span>';
    var moves = log.moves || {};
    var deaths = log.deaths || [];
    var parts = [];
    var mk = Object.keys(moves);
    for (var i = 0; i < mk.length; i++) {
        parts.push(getPlayerName(mk[i], players) + '：<b>' + (V2_MOVE_LABELS[moves[mk[i]]] || moves[mk[i]]) + '</b>');
    }
    var html = '<div>动作：' + parts.join(" · ") + '</div>';
    if (deaths.length > 0) {
        html += '<div>死亡：' + deaths.map(function(d) {
            return getPlayerName(d.player_id, players) + '<span class="danger-text">(' + (V2_DEATH_LABELS[d.cause] || d.cause) + ')</span>';
        }).join(" · ") + '</div>';
    }
    return html;
}

function renderHistory(logs, players) {
    var container = document.getElementById("history");
    if (!logs || logs.length === 0) { container.innerHTML = ""; return; }
    var html = "";
    for (var i = logs.length - 1; i >= 0; i--) {
        var log = logs[i];
        var moves = log.moves || {};
        var deaths = log.deaths || [];
        var parts = [];
        var mk2 = Object.keys(moves);
        for (var j = 0; j < mk2.length; j++) {
            parts.push(getPlayerName(mk2[j], players) + '：' + (V2_MOVE_LABELS[moves[mk2[j]]] || moves[mk2[j]]));
        }
        html += '<div class="history-item">';
        html += '<div class="hr-header">R' + (log.round_num || "?") + ' — ' + parts.join(" · ") + '</div>';
        if (deaths.length > 0) {
            html += '<div class="hr-detail">死亡: ' + deaths.map(function(d) {
                return getPlayerName(d.player_id, players) + "(" + (V2_DEATH_LABELS[d.cause] || d.cause) + ")";
            }).join(" · ") + '</div>';
        }
        html += '</div>';
    }
    container.innerHTML = html;
}

/* ═══════════════════════════════════════════════════════════════
   辅助函数
   ═══════════════════════════════════════════════════════════════ */

function getPlayerName(playerId, players) {
    if (!playerId) return "?";
    if (!players) return playerId;
    for (var i = 0; i < players.length; i++) {
        if (players[i].player_id === playerId) return players[i].username || playerId;
    }
    return playerId;
}

function escHtml(str) {
    if (str == null) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function v2KeyForMove(moveName) {
    for (var k in V2_KEY_TO_MOVE) {
        if (V2_KEY_TO_MOVE[k] === moveName) return k.toUpperCase();
    }
    return "";
}

function getEventsFromLatestRound(state) {
    if (!state || !state.history) return [];
    var logs = state.history;
    if (logs.length === 0) return [];
    return logs[logs.length - 1].speed_layer_events || [];
}

function getDecisionLogFromLatestRound(state) {
    if (!state || !state.history) return [];
    var logs = state.history;
    if (logs.length === 0) return [];
    return logs[logs.length - 1].decision_log || [];
}
