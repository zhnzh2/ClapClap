/**
 * 2.0 对局回放页面 JS
 * 支持多人对战、速度层时间线、资源变化、名次等 v2 特性。
 */
(function () {
    "use strict";

    var battleId = window.V2_RECORD_BATTLE_ID;
    var battle = null;
    var currentUser = null;
    var selectedRoundIdx = -1;
    var chatExpanded = false;
    var jsonExpanded = false;

    var $loading, $error, $errorText, $page;

    // 玩家颜色方案（对应 p0~p5）
    var PLAYER_COLORS = [
        { bg: "#eff6ff", border: "#bfdbfe", text: "#1e40af", name: "蓝" },
        { bg: "#fff7ed", border: "#fed7aa", text: "#c2410c", name: "橙" },
        { bg: "#f0fdf4", border: "#bbf7d0", text: "#166534", name: "绿" },
        { bg: "#faf5ff", border: "#e9d5ff", text: "#7c3aed", name: "紫" },
        { bg: "#fdf2f8", border: "#fbcfe8", text: "#be185d", name: "粉" },
        { bg: "#ecfeff", border: "#a5f3fc", text: "#155e75", name: "青" }
    ];

    document.addEventListener("DOMContentLoaded", function () {
        $loading = document.getElementById("record-loading");
        $error = document.getElementById("record-error");
        $errorText = document.getElementById("record-error-text");
        $page = document.getElementById("record-page");

        if (!battleId) {
            showError("无效的对局 ID。");
            return;
        }

        if (!initAccountButton()) return;
        initAdminButton();
        initBackButton();
        loadBattle();
    });

    // ── 账号按钮 ──────────────────────────────────────────────────

    function initAccountButton() {
        var user = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
        if (!user) {
            window.location.href = "/v2/login?expired=1";
            return false;
        }
        currentUser = user;

        var btn = document.getElementById("header-account-btn");
        if (btn) {
            btn.textContent = user.username;
            btn.addEventListener("click", function () {
                window.location.href = "/v2/user/" + user.uid;
            });
        }
        return true;
    }

    function initAdminButton() {
        var adminBtn = document.getElementById("header-admin-btn");
        if (!adminBtn) return;
        if (currentUser && (currentUser.role === "admin" || currentUser.role === "站主")) {
            adminBtn.style.display = "";
            adminBtn.addEventListener("click", function () {
                if (window.AdminUsersModal) AdminUsersModal.open();
            });
        }
    }

    function initBackButton() {
        var btn = document.getElementById("record-back-btn");
        if (btn) {
            btn.addEventListener("click", function () {
                if (document.referrer && document.referrer.indexOf(location.origin) === 0) {
                    history.back();
                } else {
                    window.location.href = "/v2";
                }
            });
        }
    }

    // ── 加载对局数据 ──────────────────────────────────────────────

    function loadBattle() {
        showLoading(true);
        window.ApiUtils.apiGet("/v2/api/battles/" + battleId)
            .then(function (res) {
                showLoading(false);
                if (!res.ok) {
                    showError(res.error || "加载对局失败");
                    return;
                }
                battle = res.data.battle;
                if (!battle) {
                    showError("对局数据为空。");
                    return;
                }
                var rv = String(battle.rule_version || "1.0");
                if (!rv.startsWith("2.")) {
                    // 重定向到 1.0 回放页面
                    window.location.replace("/v1/record/" + encodeURIComponent(battleId));
                    return;
                }
                showPage();
                renderHeader();
                renderRoundList();
                renderChat();
                renderRawJson();
            })
            .catch(function () {
                showLoading(false);
                showError("网络错误，无法加载对局数据。");
            });
    }

    function showLoading(show) {
        if ($loading) $loading.style.display = show ? "flex" : "none";
    }

    function showError(msg) {
        if ($error) $error.style.display = msg ? "flex" : "none";
        if (msg && $errorText) $errorText.textContent = msg;
        if ($page) $page.style.display = msg ? "none" : "";
    }

    function showPage() {
        if ($page) $page.style.display = "";
    }

    // ── 顶部信息栏 ────────────────────────────────────────────────

    function renderHeader() {
        // 副标题：模式 + 人数
        var subEl = document.getElementById("v2-record-subtitle");
        if (subEl) {
            var parts = [];
            parts.push(battle.mode_label || "对局");
            var seats = battle.seats || [];
            var pCount = seats.length || Object.keys(battle.participants || {}).length;
            parts.push(pCount + "人对战");
            if (battle.room && battle.room.room_id) {
                parts.push("房间 " + escHtml(battle.room.room_id));
            }
            subEl.textContent = parts.join(" · ");
        }

        // 元信息：时间 + 结果 + 房间详情
        var metaEl = document.getElementById("record-meta");
        if (!metaEl) return;

        var timeStr = "";
        try {
            var d = new Date(battle.start_time);
            if (!isNaN(d.getTime())) timeStr = d.toLocaleString("zh-CN");
        } catch (e) {}
        if (!timeStr) timeStr = battle.start_time || "";

        // 结果标签
        var resultClass = "";
        var resultLabel = "";
        var finalResult = battle.final_result;
        if (finalResult && finalResult.winner) {
            var winnerName = playerName(finalResult.winner);
            resultClass = "record-result-win";
            resultLabel = "胜者: " + winnerName;
        } else if (battle.winner) {
            resultClass = "record-result-win";
            resultLabel = "胜者: " + playerName(String(battle.winner));
        } else if (battle.end_time) {
            resultClass = "record-result-draw";
            resultLabel = "已结束";
        } else {
            resultClass = "record-result-ongoing";
            resultLabel = "进行中";
        }

        var html = '<span class="record-time">' + escHtml(timeStr) + '</span>'
            + '<span class="record-result-badge ' + resultClass + '">' + escHtml(resultLabel) + '</span>'
            + '<button class="battle-copy-btn" id="copy-battle-id-btn" title="复制对局 ID">📋 复制 ID</button>';

        metaEl.innerHTML = html;

        // 绑定复制按钮
        var copyBtn = document.getElementById("copy-battle-id-btn");
        if (copyBtn) {
            copyBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(battleId).then(function () {
                        copyBtn.textContent = "✓ 已复制";
                        setTimeout(function () { copyBtn.textContent = "📋 复制 ID"; }, 2000);
                    });
                }
            });
        }

        // AI 元数据
        if (battle.opponent_type === "ai" || battle.mode === "ai") {
            var aiBar = document.createElement("div");
            aiBar.className = "ai-meta-bar";
            var aiParts = ["🤖 AI 对局"];
            var diff = battle.ai_difficulty;
            if (diff) aiParts.push("难度：" + (diff === "easy" ? "简单" : (diff === "hard" ? "困难" : "普通")));
            var pt = battle.ai_policy_type;
            if (pt) aiParts.push("策略：" + pt);
            var mv = battle.ai_model_version;
            if (mv) aiParts.push("模型：" + String(mv));
            var fr = battle.ai_fallback_reason;
            if (fr) aiParts.push("降级原因：" + String(fr));
            if (battle.ai_seat) aiParts.push("AI 座位：" + String(battle.ai_seat));
            aiBar.textContent = aiParts.join(" · ");
            metaEl.parentNode.insertBefore(aiBar, metaEl.nextSibling);
        }

        // 参与者 + 房间信息卡片（header 下方）
        renderParticipantBar();
    }

    function renderParticipantBar() {
        // 在 header 下面插入参与者条
        var oldBar = document.getElementById("v2-participant-bar");
        if (oldBar) oldBar.remove();

        var header = document.querySelector(".v2-record-header");
        if (!header) return;

        var bar = document.createElement("div");
        bar.id = "v2-participant-bar";
        bar.className = "v2-participant-bar";

        var seats = battle.seats || [];
        var participants = battle.participants || {};

        // 参与者头像行
        var chipsHtml = "";
        var playerIds = seats.length > 0
            ? seats.map(function (s) { return s.player_id; })
            : Object.keys(participants);

        playerIds.forEach(function (pid, idx) {
            var info = participants[pid] || {};
            var name = info.username || pid;
            var color = PLAYER_COLORS[idx % PLAYER_COLORS.length];
            var hostMark = (info.is_host) ? ' <span class="v2-host-mark">房主</span>' : "";
            var rankStr = "";
            if (battle.final_result && battle.final_result.rankings) {
                var ranking = battle.final_result.rankings.find(function (r) { return r.player_id === pid; });
                if (ranking && ranking.is_winner) {
                    rankStr = ' <span class="v2-champion-mark">🏆</span>';
                }
            }
            chipsHtml += '<span class="v2-player-chip" style="background:' + color.bg
                + ';border-color:' + color.border + ';color:' + color.text + '">'
                + escHtml(name) + hostMark + rankStr
                + '</span>';
        });

        // 房间信息
        var roomHtml = "";
        if (battle.room && battle.room.room_id) {
            roomHtml = '<span class="v2-room-info">'
                + '房间: <strong>' + escHtml(battle.room.room_id) + '</strong>'
                + ' · ' + (battle.room.max_players || "?") + '人房';
            if (battle.host && battle.host.username) {
                roomHtml += ' · 房主: ' + escHtml(battle.host.username);
            }
            roomHtml += '</span>';
        }

        bar.innerHTML = '<div class="v2-participant-chips">' + chipsHtml + '</div>' + roomHtml;
        header.insertAdjacentElement("afterend", bar);
    }

    // ── 左侧回合列表 ──────────────────────────────────────────────

    function renderRoundList() {
        var listEl = document.getElementById("record-round-list");
        if (!listEl) return;

        var rounds = battle.rounds || [];
        if (rounds.length === 0) {
            listEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:13px;">无回合记录</div>';
            return;
        }

        var html = "";
        for (var i = 0; i < rounds.length; i++) {
            var r = rounds[i];
            var roundNum = r.round_num || (i + 1);

            // 动作简述
            var moves = r.moves || {};
            var moveParts = [];
            var playerIds = Object.keys(moves);
            for (var j = 0; j < Math.min(playerIds.length, 4); j++) {
                var pid = playerIds[j];
                moveParts.push(escHtml(shortPlayerName(pid)) + ":" + escHtml(moves[pid]));
            }
            if (playerIds.length > 4) moveParts.push("+" + (playerIds.length - 4));
            var movesText = moveParts.join(" ") || "无动作";

            // 回合标签
            var tagHtml = "";
            var deaths = r.deaths || [];
            var deathPids = deaths.map(function (d) { return d.player_id; });
            if (deathPids.length > 0) {
                tagHtml = '<span class="record-round-tag tag-loss">' + deathPids.length + '人出局</span>';
            }
            if (r.winner && !r.game_ended) {
                tagHtml += '<span class="record-round-tag tag-win">' + escHtml(shortPlayerName(r.winner)) + '胜</span>';
            }
            if (r.game_ended) {
                tagHtml += '<span class="record-round-tag tag-draw">终局</span>';
            }

            html += '<div class="record-round-item" data-round-idx="' + i + '">'
                + '<span class="record-round-num">' + roundNum + '</span>'
                + '<div class="record-round-brief">'
                + '<span class="record-round-moves">' + movesText + '</span>'
                + tagHtml
                + '</div>'
                + '</div>';
        }

        listEl.innerHTML = html;

        // 绑定点击事件
        var items = listEl.querySelectorAll(".record-round-item");
        items.forEach(function (item) {
            item.addEventListener("click", function () {
                var idx = parseInt(this.getAttribute("data-round-idx"));
                selectRound(idx);
            });
        });

        // 默认选中最后一回合
        selectRound(rounds.length - 1);
    }

    function selectRound(idx) {
        var rounds = battle.rounds || [];
        if (idx < 0 || idx >= rounds.length) return;

        selectedRoundIdx = idx;

        // 更新列表高亮
        var items = document.querySelectorAll(".record-round-item");
        items.forEach(function (item) {
            var i = parseInt(item.getAttribute("data-round-idx"));
            if (i === idx) {
                item.classList.add("record-round-item-active");
            } else {
                item.classList.remove("record-round-item-active");
            }
        });

        // 渲染详情
        renderRoundDetail(rounds[idx]);
    }

    // ── 右侧回合详情 ──────────────────────────────────────────────

    function renderRoundDetail(roundData) {
        var detailEl = document.getElementById("record-detail");
        if (!detailEl) return;

        var roundNum = roundData.round_num || "?";
        var isFull = roundData.record_schema === "v2_round_full";

        var html = '<h2 class="record-round-header">第 ' + roundNum + ' 回合</h2>';

        if (!isFull) {
            html += '<div class="record-old-data-hint">⚠ 此对局记录于增强记录功能之前，部分信息为自动推断。</div>';
        }

        html += renderMovesOverview(roundData);
        html += renderSpeedTimeline(roundData);
        html += renderResourceChanges(roundData);
        html += renderRoundResult(roundData);
        html += renderThreeChain(roundData);

        detailEl.innerHTML = html;

        // 绑定速度层折叠事件
        initSpeedLayerToggles(detailEl);
    }

    // ── a) 玩家出招总览 ───────────────────────────────────────────

    function renderMovesOverview(r) {
        var moves = r.moves || {};
        var resourceCheck = r.resource_check_ok || {};
        var illegalPlayers = r.illegal_players || [];
        var flashedPlayers = r.flashed_players || [];

        var playerIds = Object.keys(moves);
        if (playerIds.length === 0) {
            // 尝试从 participants 获取
            playerIds = Object.keys(battle.participants || {});
        }

        var rows = playerIds.map(function (pid, idx) {
            var moveName = moves[pid] || "?";
            var ok = resourceCheck[pid];
            var validLabel = ok === false ? "✗ 无效" : "✓ 有效";
            var validCls = ok === false ? "invalid" : "";

            var notes = [];
            if (illegalPlayers.indexOf(pid) >= 0) notes.push("爆气/爆盾");
            if (flashedPlayers.indexOf(pid) >= 0) notes.push("闪电触发");
            var noteStr = notes.length > 0 ? ' <span class="v2-move-note">' + notes.join(" · ") + '</span>' : "";

            return '<tr>'
                + '<td><span class="v2-player-dot" style="background:' + playerColor(idx).text + '"></span>'
                + escHtml(playerName(pid)) + '</td>'
                + '<td><strong>' + escHtml(moveName) + '</strong>' + noteStr + '</td>'
                + '<td class="' + validCls + '">' + validLabel + '</td>'
                + '</tr>';
        }).join("");

        return '<div class="v2-section">'
            + '<div class="v2-section-title">玩家出招</div>'
            + '<table class="v2-moves-table">'
            + '<thead><tr><th>玩家</th><th>动作</th><th>有效性</th></tr></thead>'
            + '<tbody>' + rows + '</tbody>'
            + '</table>'
            + '</div>';
    }

    // ── b) 速度层时间线 ───────────────────────────────────────────

    function renderSpeedTimeline(r) {
        var speedLayers = r.speed_layers;
        if (!speedLayers || speedLayers.length === 0) {
            // 尝试从原始字段构造
            speedLayers = buildSpeedLayers(r);
        }
        if (!speedLayers || speedLayers.length === 0) {
            return '<div class="v2-section"><div class="v2-section-title">速度层时间线</div>'
                + '<div class="v2-empty-hint">无速度层数据</div></div>';
        }

        var html = '<div class="v2-section"><div class="v2-section-title">速度层时间线</div>';

        speedLayers.forEach(function (sl) {
            var hasConflict = sl.had_conflict;
            var conflictBadge = hasConflict ? ' <span class="v2-conflict-badge">冲突</span>' : '';
            var eventCount = (sl.events || []).length;
            var decisionCount = (sl.decisions || []).length;

            html += '<div class="v2-speed-layer">'
                + '<div class="v2-speed-layer-header" data-layer-toggle="' + sl.layer + '">'
                + '<span class="v2-speed-layer-arrow">▶</span>'
                + '<span class="v2-speed-layer-num">第 ' + sl.layer + ' 层</span>'
                + conflictBadge
                + '<span class="v2-speed-layer-summary">'
                + (eventCount > 0 ? eventCount + ' 事件' : '')
                + (decisionCount > 0 ? (eventCount > 0 ? ' · ' : '') + decisionCount + ' 决策' : '')
                + '</span>'
                + '</div>'
                + '<div class="v2-speed-layer-body" style="display:none;">';

            // 声明
            var decls = sl.declarations || {};
            var declPids = Object.keys(decls);
            if (declPids.length > 0) {
                html += '<div class="v2-layer-subtitle">声明</div>';
                declPids.forEach(function (pid) {
                    var d = decls[pid] || {};
                    var targets = (d.targets || []).map(function (t) { return playerName(t); }).join("、");
                    html += '<div class="v2-layer-item">'
                        + '<span class="v2-layer-player">' + escHtml(playerName(pid)) + '</span>'
                        + ' → <strong>' + escHtml(d.move || "?") + '</strong>'
                        + ' 目标: ' + escHtml(targets || "无")
                        + (d.is_split ? ' (分裂)' : '')
                        + '</div>';
                });
            }

            // 冲突
            var conflicts = sl.conflicts || [];
            if (conflicts.length > 0) {
                html += '<div class="v2-layer-subtitle conflict">冲突</div>';
                conflicts.forEach(function (c) {
                    html += '<div class="v2-layer-item conflict-item">'
                        + '类型: <strong>' + escHtml(c.conflict_type || "?") + '</strong>'
                        + (c.detail ? ' · ' + escHtml(c.detail) : '')
                        + '</div>';
                });
            }

            // 决策
            var decisions = sl.decisions || [];
            if (decisions.length > 0) {
                html += '<div class="v2-layer-subtitle decision">决策</div>';
                decisions.forEach(function (d) {
                    var typeLabel = {
                        "conflict_resolve": "冲突解决",
                        "target_select": "选择目标",
                        "three_chain_select": "三连选择"
                    }[d.decision_type] || d.decision_type || "?";
                    var chosen = (d.chosen || []).map(function (id) {
                        var opt = (d.options || []).find(function (o) { return o.id === id; });
                        return opt ? opt.label : id;
                    }).join("、");
                    html += '<div class="v2-layer-item decision-item">'
                        + escHtml(playerName(d.player_id)) + ' '
                        + '<span class="v2-decision-type">' + escHtml(typeLabel) + '</span>'
                        + ' → ' + escHtml(chosen || "?")
                        + (d.reason ? ' <span class="v2-decision-reason">(' + escHtml(d.reason) + ')</span>' : '')
                        + '</div>';
                });
            }

            // 事件
            var events = sl.events || [];
            if (events.length > 0) {
                html += '<div class="v2-layer-subtitle event">事件</div>';
                events.forEach(function (ev) {
                    var eventLabel = ev.detail || (ev.event_type + " " + (ev.source_player_id || "") + " → " + (ev.target_player_id || ""));
                    html += '<div class="v2-layer-item event-item">'
                        + '<span class="v2-event-type">' + escHtml(ev.event_type || "?") + '</span>'
                        + ' · ' + escHtml(eventLabel)
                        + '</div>';
                });
            }

            html += '</div></div>';
        });

        html += '</div>';
        return html;
    }

    function buildSpeedLayers(r) {
        // 从原始字段构造 speed_layers（兼容旧数据）
        var declarationsByLayer = r.target_declarations_by_layer || {};
        var conflictsByLayer = r.conflicts_by_layer || {};
        var decisionLog = r.decision_log || [];
        var events = r.speed_layer_events || [];

        var layerNumbers = {};
        [declarationsByLayer, conflictsByLayer].forEach(function (src) {
            Object.keys(src).forEach(function (k) {
                layerNumbers[parseInt(k)] = true;
            });
        });
        events.forEach(function (e) {
            layerNumbers[parseInt(e.speed_layer) || 0] = true;
        });
        decisionLog.forEach(function (d) {
            layerNumbers[parseInt(d.speed_layer) || 0] = true;
        });

        var layers = [];
        Object.keys(layerNumbers).sort(function (a, b) { return parseInt(a) - parseInt(b); }).forEach(function (layerNum) {
            var layerKey = String(layerNum);
            var layerInt = parseInt(layerNum);
            var layerEvents = events.filter(function (e) { return parseInt(e.speed_layer || 0) === layerInt; });
            var layerDecisions = decisionLog.filter(function (d) { return parseInt(d.speed_layer || 0) === layerInt; });
            layers.push({
                layer: layerInt,
                declarations: declarationsByLayer[layerKey] || {},
                conflicts: conflictsByLayer[layerKey] || [],
                decisions: layerDecisions,
                events: layerEvents,
                had_conflict: (conflictsByLayer[layerKey] || []).length > 0
            });
        });

        return layers.length > 0 ? layers : null;
    }

    function initSpeedLayerToggles(detailEl) {
        var headers = detailEl.querySelectorAll("[data-layer-toggle]");
        headers.forEach(function (hdr) {
            hdr.addEventListener("click", function () {
                var body = hdr.nextElementSibling;
                var arrow = hdr.querySelector(".v2-speed-layer-arrow");
                if (body) {
                    var isOpen = body.style.display !== "none";
                    body.style.display = isOpen ? "none" : "block";
                    if (arrow) arrow.textContent = isOpen ? "▶" : "▼";
                }
            });
        });
    }

    // ── c) 资源变化 ───────────────────────────────────────────────

    function renderResourceChanges(r) {
        var changes = r.changes;
        if (!changes || Object.keys(changes).length === 0) {
            // 从 pre_snapshots / post_snapshots 计算
            changes = buildChanges(r);
        }

        var playerIds = Object.keys(changes);
        if (playerIds.length === 0) {
            return '<div class="v2-section"><div class="v2-section-title">资源变化</div>'
                + '<div class="v2-empty-hint">无资源快照数据</div></div>';
        }

        var RESOURCE_FIELDS = [
            { key: "hp", label: "HP" },
            { key: "qi", label: "气" },
            { key: "shield", label: "盾" },
            { key: "spark", label: "火种" },
            { key: "battery", label: "电池" },
            { key: "pickaxe", label: "镐" }
        ];

        // 表头
        var headerRow = '<th>玩家</th>';
        RESOURCE_FIELDS.forEach(function (f) {
            headerRow += '<th>' + f.label + '</th>';
        });

        // 数据行
        var rows = "";
        playerIds.forEach(function (pid, idx) {
            var ch = changes[pid] || {};
            var color = playerColor(idx);
            rows += '<tr>'
                + '<td><span class="v2-player-dot" style="background:' + color.text + '"></span>'
                + escHtml(playerName(pid)) + '</td>';
            RESOURCE_FIELDS.forEach(function (f) {
                var c = ch[f.key];
                if (c) {
                    var deltaClass = c.delta > 0 ? "v2-delta-pos" : (c.delta < 0 ? "v2-delta-neg" : "v2-delta-zero");
                    rows += '<td class="v2-resource-cell">'
                        + '<span class="v2-resource-before">' + (c.before != null ? c.before : "?") + '</span>'
                        + ' → <span class="v2-resource-after">' + (c.after != null ? c.after : "?") + '</span>'
                        + ' <span class="' + deltaClass + '">' + formatDelta(c.delta) + '</span>'
                        + '</td>';
                } else {
                    rows += '<td class="v2-resource-cell v2-resource-none">—</td>';
                }
            });
            rows += '</tr>';
        });

        return '<div class="v2-section">'
            + '<div class="v2-section-title">资源变化</div>'
            + '<div class="v2-resource-table-wrap">'
            + '<table class="v2-resource-table">'
            + '<thead><tr>' + headerRow + '</tr></thead>'
            + '<tbody>' + rows + '</tbody>'
            + '</table>'
            + '</div>'
            + '</div>';
    }

    function buildChanges(r) {
        var pre = r.pre_snapshots || {};
        var post = r.post_snapshots || {};
        var playerIds = Object.keys(pre).concat(Object.keys(post)).filter(function (v, i, a) { return a.indexOf(v) === i; });
        var changes = {};
        playerIds.forEach(function (pid) {
            var before = pre[pid] || {};
            var after = post[pid] || {};
            var delta = {};
            var keys = Object.keys(before).concat(Object.keys(after)).filter(function (v, i, a) { return a.indexOf(v) === i; });
            var hasChange = false;
            keys.forEach(function (key) {
                var oldVal = before[key];
                var newVal = after[key];
                if (oldVal !== newVal) {
                    hasChange = true;
                    if (typeof oldVal === "number" && typeof newVal === "number") {
                        delta[key] = { before: oldVal, after: newVal, delta: newVal - oldVal };
                    } else {
                        delta[key] = { before: oldVal, after: newVal };
                    }
                }
            });
            if (hasChange) changes[pid] = delta;
        });
        return changes;
    }

    // ── d) 回合结果 ───────────────────────────────────────────────

    function renderRoundResult(r) {
        var result = r.result || {};
        var deaths = result.deaths || r.deaths || [];
        var rankUpdates = result.rank_updates || r.rank_updates || {};
        var winner = result.winner !== undefined ? result.winner : r.winner;
        var gameEnded = result.game_ended !== undefined ? result.game_ended : r.game_ended;

        var hasContent = deaths.length > 0 || Object.keys(rankUpdates).length > 0 || winner || gameEnded;
        if (!hasContent) return "";

        var html = '<div class="v2-section"><div class="v2-section-title">回合结果</div>';

        // 死亡
        if (deaths.length > 0) {
            html += '<div class="v2-result-block">';
            deaths.forEach(function (d) {
                html += '<div class="v2-death-item">💀 '
                    + escHtml(playerName(d.player_id)) + ' 出局'
                    + (d.cause ? ' (' + escHtml(d.cause) + ')' : '')
                    + (d.speed_layer ? ' @第' + d.speed_layer + '层' : '')
                    + '</div>';
            });
            html += '</div>';
        }

        // 名次更新
        var rankPids = Object.keys(rankUpdates);
        if (rankPids.length > 0) {
            html += '<div class="v2-result-block">';
            html += '<div class="v2-result-label">名次更新</div>';
            // 按名次排序
            var sorted = rankPids.slice().sort(function (a, b) { return (rankUpdates[a] || 999) - (rankUpdates[b] || 999); });
            sorted.forEach(function (pid) {
                var rank = rankUpdates[pid];
                var medal = rank === 1 ? "🥇" : (rank === 2 ? "🥈" : (rank === 3 ? "🥉" : ""));
                html += '<div class="v2-rank-item">'
                    + medal + ' <strong>' + escHtml(playerName(pid)) + '</strong>'
                    + ' → 第 ' + rank + ' 名'
                    + '</div>';
            });
            html += '</div>';
        }

        // 回合胜者
        if (winner && !gameEnded) {
            html += '<div class="v2-result-block">'
                + '<span class="v2-round-winner">🏆 回合胜者: ' + escHtml(playerName(String(winner))) + '</span>'
                + '</div>';
        }

        // 对局结束
        if (gameEnded) {
            html += '<div class="v2-result-block v2-game-ended">'
                + '🎉 <strong>对局结束</strong>'
                + (winner ? ' · 最终胜者: ' + escHtml(playerName(String(winner))) : '')
                + '</div>';
        }

        html += '</div>';
        return html;
    }

    // ── e) 三连 / 二三连 ──────────────────────────────────────────

    function renderThreeChain(r) {
        var groups = r.three_chain_groups || [];
        var twoThree = r.two_three_chains;

        if (groups.length === 0 && !twoThree) return "";

        var html = '<div class="v2-section"><div class="v2-section-title">三连/连锁</div>';

        if (groups.length > 0) {
            groups.forEach(function (g, i) {
                html += '<div class="v2-layer-item">'
                    + '三连组 ' + (i + 1) + ': '
                    + escHtml(JSON.stringify(g))
                    + '</div>';
            });
        }

        if (twoThree) {
            html += '<div class="v2-layer-item">'
                + '二三连已触发'
                + '</div>';
        }

        html += '</div>';
        return html;
    }

    // ── 聊天 ──────────────────────────────────────────────────────

    function renderChat() {
        var chatMessages = battle.chat || [];
        // 也收集回合内聊天
        (battle.rounds || []).forEach(function (r) {
            var rc = r.chat || [];
            chatMessages = chatMessages.concat(rc);
        });

        if (chatMessages.length === 0) return;

        var chatContainer = document.createElement("div");
        chatContainer.id = "v2-chat-section";
        chatContainer.className = "v2-chat-section";

        var headerHtml = '<div class="v2-chat-header" id="v2-chat-toggle">'
            + '<span class="v2-chat-arrow">▶</span>'
            + ' 聊天记录 (' + chatMessages.length + ' 条)'
            + '</div>';

        var bodyHtml = chatMessages.map(function (msg) {
            var timeStr = "";
            try {
                var d = new Date(msg.timestamp);
                if (!isNaN(d.getTime())) timeStr = d.toLocaleTimeString("zh-CN");
            } catch (e) {}
            return '<div class="v2-chat-item">'
                + '<span class="v2-chat-time">' + escHtml(timeStr || msg.timestamp || "") + '</span>'
                + ' <span class="v2-chat-sender">' + escHtml(msg.sender || "?") + '</span>: '
                + escHtml(msg.message || "")
                + '</div>';
        }).join("");

        chatContainer.innerHTML = headerHtml
            + '<div class="v2-chat-body" style="display:none;">' + bodyHtml + '</div>';

        // 插入到 page 底部
        var page = document.getElementById("record-page");
        if (page) page.appendChild(chatContainer);

        document.getElementById("v2-chat-toggle").addEventListener("click", function () {
            var body = chatContainer.querySelector(".v2-chat-body");
            var arrow = chatContainer.querySelector(".v2-chat-arrow");
            chatExpanded = !chatExpanded;
            body.style.display = chatExpanded ? "block" : "none";
            arrow.textContent = chatExpanded ? "▼" : "▶";
        });
    }

    // ── 原始 JSON ─────────────────────────────────────────────────

    function renderRawJson() {
        var container = document.createElement("div");
        container.id = "v2-json-section";
        container.className = "v2-json-section";

        container.innerHTML = '<div class="v2-json-header" id="v2-json-toggle">'
            + '<span class="v2-json-arrow">▶</span>'
            + ' 完整 JSON 数据（调试用）'
            + '</div>'
            + '<div class="v2-json-body" style="display:none;">'
            + '<pre class="v2-json-pre">' + escHtml(JSON.stringify(battle, null, 2)) + '</pre>'
            + '</div>';

        var page = document.getElementById("record-page");
        if (page) page.appendChild(container);

        document.getElementById("v2-json-toggle").addEventListener("click", function () {
            var body = container.querySelector(".v2-json-body");
            var arrow = container.querySelector(".v2-json-arrow");
            jsonExpanded = !jsonExpanded;
            body.style.display = jsonExpanded ? "block" : "none";
            arrow.textContent = jsonExpanded ? "▼" : "▶";
        });
    }

    // ── 工具函数 ──────────────────────────────────────────────────

    function playerName(pid) {
        if (!pid && pid !== 0) return "?";
        var key = String(pid);
        var participants = battle.participants || {};
        var info = participants[key];
        if (info) {
            if (info.status === "deleted") return "已注销用户";
            if (info.username) return info.username;
        }
        // try seat data
        var seats = battle.seats || [];
        for (var i = 0; i < seats.length; i++) {
            if (seats[i].player_id === key && seats[i].username) return seats[i].username;
        }
        return key;
    }

    function shortPlayerName(pid) {
        var full = playerName(pid);
        return full.length > 4 ? full.substring(0, 3) + "…" : full;
    }

    function playerColor(idx) {
        return PLAYER_COLORS[idx % PLAYER_COLORS.length];
    }

    function formatDelta(delta) {
        if (delta == null) return "";
        if (delta > 0) return "+" + delta;
        return String(delta);
    }

    function escHtml(str) {
        if (str == null) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

})();
