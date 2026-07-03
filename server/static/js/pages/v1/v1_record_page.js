/**
 * 对局回放页面 JS
 * 左侧回合列表 + 右侧选中回合详情
 */
(function () {
    "use strict";

    var battleId = window.RECORD_BATTLE_ID;
    var battle = null;
    var currentUser = null;
    var selectedRoundIdx = -1;  // 当前选中回合的索引（-1 表示未选中）

    var $loading, $error, $errorText, $page;

    document.addEventListener("DOMContentLoaded", function () {
        $loading = document.getElementById("record-loading");
        $error = document.getElementById("record-error");
        $errorText = document.getElementById("record-error-text");
        $page = document.getElementById("record-page");

        if (!battleId) {
            showError("无效的对局 ID。");
            return;
        }

        initAccountButton();
        initAdminButton();
        initBackButton();
        loadBattle();
    });

    // ── 账号按钮 ──────────────────────────────────────────────────

    function initAccountButton() {
        var user = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
        if (!user) {
            window.location.href = "/v1/login?expired=1";
            return;
        }
        currentUser = user;

        var btn = document.getElementById("header-account-btn");
        if (btn) {
            btn.textContent = user.username;
            btn.addEventListener("click", function () {
                window.location.href = "/v1/user/" + user.uid;
            });
        }
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
                    window.location.href = "/v1";
                }
            });
        }
    }

    // ── 加载对局数据 ──────────────────────────────────────────────

    function loadBattle() {
        showLoading(true);

        window.ApiUtils.apiGet("/v1/api/battles/" + battleId)
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
                // 2.0 对局重定向到 v2 回放页面
                if (battle.rule_version && String(battle.rule_version).startsWith("2.")) {
                    window.location.replace("/v2/record/" + encodeURIComponent(battleId));
                    return;
                }
                showPage();
                renderHeader();
                renderRoundList();
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
        var p1Info = (battle.participants && battle.participants.p1) ? battle.participants.p1 : {};
        var p2Info = (battle.participants && battle.participants.p2) ? battle.participants.p2 : {};
        var p1Name = (p1Info.status === "deleted") ? "已注销用户" : (p1Info.username || "P1");
        var p2Name = (p2Info.status === "deleted") ? "已注销用户" : (p2Info.username || "P2");

        var playersEl = document.getElementById("record-players");
        if (playersEl) {
            playersEl.textContent = p1Name + " vs " + p2Name;
        }

        var metaEl = document.getElementById("record-meta");
        if (!metaEl) return;

        // 时间
        var timeStr = "";
        try {
            var d = new Date(battle.start_time);
            if (!isNaN(d.getTime())) timeStr = d.toLocaleString("zh-CN");
        } catch (e) {}
        if (!timeStr) timeStr = battle.start_time || "";

        // 结果
        var winner = battle.winner;
        var resultClass = "";
        var resultLabel = "";
        if (winner === 1) {
            resultClass = "record-result-win";
            resultLabel = p1Name + " 胜";
        } else if (winner === 2) {
            resultClass = "record-result-loss";
            resultLabel = p2Name + " 胜";
        } else if (winner === 0) {
            resultClass = "record-result-draw";
            resultLabel = "平局";
        } else if (battle.end_time) {
            resultClass = "record-result-draw";
            resultLabel = "未知";
        } else {
            resultClass = "record-result-ongoing";
            resultLabel = "进行中";
        }

        metaEl.innerHTML = '<span class="record-time">' + escHtml(timeStr) + '</span>'
            + '<span class="record-result-badge ' + resultClass + '">' + escHtml(resultLabel) + '</span>'
            + '<button class="battle-copy-btn" id="copy-battle-id-btn" title="复制对局 ID">📋 复制 ID</button>';

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
            metaEl.appendChild(aiBar);
        }
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
            var moveLabel1 = r.p1_move_label || r.p1_move || "?";
            var moveLabel2 = r.p2_move_label || r.p2_move || "?";

            // 回合结果标签
            var tagHtml = "";
            var w = r.winner_after_round;
            if (w === 1) tagHtml = '<span class="record-round-tag tag-win">P1胜</span>';
            else if (w === 2) tagHtml = '<span class="record-round-tag tag-loss">P2胜</span>';
            else if (w === 0) tagHtml = '<span class="record-round-tag tag-draw">双败</span>';

            html += '<div class="record-round-item" data-round-idx="' + i + '">'
                + '<span class="record-round-num">' + roundNum + '</span>'
                + '<div class="record-round-brief">'
                + '<span class="record-round-moves">' + escHtml(moveLabel1) + ' / ' + escHtml(moveLabel2) + '</span>'
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

        var p1Name = (battle.participants && battle.participants.p1) ? battle.participants.p1.username : "P1";
        var p2Name = (battle.participants && battle.participants.p2) ? battle.participants.p2.username : "P2";
        var roundNum = roundData.round_num || "?";

        // 检查是否为旧数据（只有基本字段）
        var isOldData = !roundData.hasOwnProperty("p1_valid") && !roundData.hasOwnProperty("p1_after");

        var html = '<h2 class="record-round-header">第 ' + roundNum + ' 回合</h2>';

        if (isOldData) {
            // 旧数据：只显示基本动作
            html += '<div class="record-old-data-hint">⚠ 此对局是在增强记录功能之前进行的，仅显示双方的动作名。资源详情不可用。</div>';
            html += renderSimpleCards(roundData, p1Name, p2Name);
        } else {
            // 完整数据
            html += renderPlayerCards(roundData, p1Name, p2Name);
            html += renderResources(roundData, p1Name, p2Name);
            html += renderSummary(roundData);
            html += renderNotes(roundData, p1Name, p2Name);
        }

        detailEl.innerHTML = html;
    }

    function renderSimpleCards(r, p1Name, p2Name) {
        var moveLabel1 = r.p1_move_label || r.p1_move || "?";
        var moveLabel2 = r.p2_move_label || r.p2_move || "?";
        return '<div class="record-players-cards">'
            + playerCard(p1Name, "p1-header", [
                { label: "动作", value: moveLabel1 }
            ])
            + playerCard(p2Name, "p2-header", [
                { label: "动作", value: moveLabel2 }
            ])
            + '</div>';
    }

    function renderPlayerCards(r, p1Name, p2Name) {
        var moveLabel1 = r.p1_move_label || r.p1_move || "?";
        var moveLabel2 = r.p2_move_label || r.p2_move || "?";

        var p1Rows = [
            { label: "动作", value: moveLabel1 },
            { label: "有效性", value: r.p1_valid ? "✓ 有效" : "✗ 无效", cls: r.p1_valid ? "" : "invalid" }
        ];

        if (r.p1_damage_taken > 0) {
            p1Rows.push({ label: "受到伤害", value: String(r.p1_damage_taken), cls: "damage" });
        }
        if (r.p1_pickaxe_blocked > 0) {
            p1Rows.push({ label: "镐格挡", value: String(r.p1_pickaxe_blocked), cls: "blocked" });
        }

        var p2Rows = [
            { label: "动作", value: moveLabel2 },
            { label: "有效性", value: r.p2_valid ? "✓ 有效" : "✗ 无效", cls: r.p2_valid ? "" : "invalid" }
        ];

        if (r.p2_damage_taken > 0) {
            p2Rows.push({ label: "受到伤害", value: String(r.p2_damage_taken), cls: "damage" });
        }
        if (r.p2_pickaxe_blocked > 0) {
            p2Rows.push({ label: "镐格挡", value: String(r.p2_pickaxe_blocked), cls: "blocked" });
        }

        return '<div class="record-players-cards">'
            + playerCard(p1Name, "p1-header", p1Rows)
            + playerCard(p2Name, "p2-header", p2Rows)
            + '</div>';
    }

    function playerCard(name, headerClass, rows) {
        var rowsHtml = rows.map(function (row) {
            return '<div class="record-player-row">'
                + '<span class="record-player-label">' + escHtml(row.label) + '</span>'
                + '<span class="record-player-value' + (row.cls ? " " + row.cls : "") + '">' + escHtml(row.value) + '</span>'
                + '</div>';
        }).join("");
        return '<div class="record-player-card">'
            + '<div class="record-player-card-header ' + headerClass + '">' + escHtml(name) + '</div>'
            + '<div class="record-player-card-body">' + rowsHtml + '</div>'
            + '</div>';
    }

    // ── 资源快照 ──────────────────────────────────────────────────

    function renderResources(r, p1Name, p2Name) {
        var p1After = r.p1_after || {};
        var p2After = r.p2_after || {};

        var fields = [
            { key: "hp", label: "HP" },
            { key: "qi", label: "气" },
            { key: "shield", label: "盾" },
            { key: "spark", label: "火种" },
            { key: "battery", label: "电池" },
            { key: "pickaxe", label: "镐" }
        ];

        var p1Rows = fields.map(function (f) {
            var val = p1After.hasOwnProperty(f.key) ? p1After[f.key] : "?";
            return resourceRow(f.label, val);
        }).join("");

        var p2Rows = fields.map(function (f) {
            var val = p2After.hasOwnProperty(f.key) ? p2After[f.key] : "?";
            return resourceRow(f.label, val);
        }).join("");

        return '<div class="record-resources">'
            + '<div class="record-resources-title">回合后资源快照</div>'
            + '<div class="record-resources-grid">'
            + '<div class="record-resource-col">'
            + '<div class="record-resource-col-header p1-res">' + escHtml(p1Name) + '</div>'
            + p1Rows
            + '</div>'
            + '<div class="record-resource-col">'
            + '<div class="record-resource-col-header p2-res">' + escHtml(p2Name) + '</div>'
            + p2Rows
            + '</div>'
            + '</div>'
            + '</div>';
    }

    function resourceRow(name, val) {
        var cls = (val === 0 || val === "0") ? " zero" : "";
        return '<div class="record-resource-row">'
            + '<span class="record-resource-name">' + escHtml(name) + '</span>'
            + '<span class="record-resource-val' + cls + '">' + escHtml(String(val)) + '</span>'
            + '</div>';
    }

    // ── 摘要 ──────────────────────────────────────────────────────

    function renderSummary(r) {
        if (!r.summary) return "";
        return '<div class="record-summary-section">'
            + '<div class="record-summary-label">回合摘要</div>'
            + '<div class="record-summary-text">' + escHtml(r.summary) + '</div>'
            + '</div>';
    }

    // ── 备注 ──────────────────────────────────────────────────────

    function renderNotes(r, p1Name, p2Name) {
        var note1 = r.p1_note || "";
        var note2 = r.p2_note || "";
        if (!note1 && !note2) return "";

        return '<div class="record-notes">'
            + (note1 ? '<div class="record-note-card"><div class="record-note-label">' + escHtml(p1Name) + ' 备注</div><div class="record-note-text">' + escHtml(note1) + '</div></div>' : "")
            + (note2 ? '<div class="record-note-card"><div class="record-note-label">' + escHtml(p2Name) + ' 备注</div><div class="record-note-text">' + escHtml(note2) + '</div></div>' : "")
            + '</div>';
    }

    // ── 工具函数 ──────────────────────────────────────────────────

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
