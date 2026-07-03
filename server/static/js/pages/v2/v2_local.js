/**
 * ClapClap 2.0 本地模拟对战 —— 主控制器
 *
 * 事件绑定、API 调用、结算流程驱动。对齐 v1 local_page.js 风格。
 */

/* ═══════════════════════════════════════════════════════════════
   初始化
   ═══════════════════════════════════════════════════════════════ */

function initV2LocalPage() {
    v2LoadSettings();

    // 应用紧凑模式
    if (v2Settings.compactMode) {
        document.body.classList.add("v2-compact-mode");
    }

    // 自动决策复选框
    var autoCb = document.getElementById("auto-resolve-checkbox");
    if (autoCb) {
        autoCb.checked = v2Settings.autoResolve;
        autoCb.addEventListener("change", function() {
            v2Settings.autoResolve = this.checked;
            v2SaveSettings();
        });
    }

    // 紧凑模式复选框
    var compactCb = document.getElementById("compact-mode-checkbox");
    if (compactCb) {
        compactCb.checked = v2Settings.compactMode;
        compactCb.addEventListener("change", function() {
            v2Settings.compactMode = this.checked;
            document.body.classList.toggle("v2-compact-mode", this.checked);
            v2SaveSettings();
        });
    }

    // ── 准备阶段 ──
    document.getElementById("setup-inc-btn").addEventListener("click", function() {
        if (v2PlayerCount < 6) { v2PlayerCount++; v2PlayerNames.length = v2PlayerCount; renderSetupPhase(); }
    });
    document.getElementById("setup-dec-btn").addEventListener("click", function() {
        if (v2PlayerCount > 2) { v2PlayerCount--; v2PlayerNames.length = v2PlayerCount; renderSetupPhase(); }
    });
    document.getElementById("setup-start-btn").addEventListener("click", startGame);

    // ── 对局阶段 ──
    document.getElementById("step-btn").addEventListener("click", submitMoves);
    document.getElementById("clear-selection-btn").addEventListener("click", clearAllSelections);
    document.getElementById("reset-btn").addEventListener("click", confirmReset);

    // ── 内联决策按钮 ──
    document.getElementById("decision-submit-btn").addEventListener("click", submitDecision);
    document.getElementById("decision-auto-btn").addEventListener("click", autoResolveDecisions);

    // ── 内联回合总结 ──
    document.getElementById("round-summary-continue-btn").addEventListener("click", continueToNextRound);

    // ── 内联对局结束 ──
    document.getElementById("end-reset-btn").addEventListener("click", function() {
        hideEndCard();
        resetToSetup();
    });

    // ── 帮助弹窗 ──
    document.getElementById("help-open-btn").addEventListener("click", function() {
        document.getElementById("help-modal-mask").classList.add("show");
    });
    document.getElementById("help-close-btn").addEventListener("click", function() {
        document.getElementById("help-modal-mask").classList.remove("show");
    });
    document.getElementById("help-modal-mask").addEventListener("click", function(e) {
        if (e.target.id === "help-modal-mask") document.getElementById("help-modal-mask").classList.remove("show");
    });

    // ── 键盘 ──
    document.addEventListener("keydown", handleKeyboard);

    // ── 初始化 ──
    v2PlayerCount = 2;
    v2PlayerNames = ["玩家1", "玩家2"];
    v2PlayerTypes = ["human", "human"];
    v2AiDifficulty = "normal";
    renderSetupPhase();
    document.getElementById("setup-phase").style.display = "";
    document.getElementById("battle-phase").style.display = "none";
}

/* ═══════════════════════════════════════════════════════════════
   准备 → 对局
   ═══════════════════════════════════════════════════════════════ */

async function startGame() {
    v2PlayerNames = [];
    for (var i = 0; i < v2PlayerCount; i++) {
        var input = document.getElementById("setup-name-" + i);
        v2PlayerNames.push(input ? (input.value.trim() || ("玩家" + (i + 1))) : ("玩家" + (i + 1)));
    }

    var result = await ApiUtils.apiPost("/v2/api/local/reset", {
        player_count: v2PlayerCount,
        names: v2PlayerNames,
        player_types: v2PlayerTypes,
        ai_difficulty: v2AiDifficulty,
    });

    if (!result.ok) { setMessage("创建对局失败：" + (result.error || "")); return; }

    v2FocusedPlayer = "p1";
    v2SelectedMoves = {};
    v2SettlementResult = null;
    v2EndShown = false;
    v2RoundSummaryShown = false;
    v2IsSetupPhase = false;

    // 解析 AI 信息
    var playerTypes = result.data.state._player_types || {};
    v2HumanPlayerIds = [];
    v2AiPlayerIds = [];
    for (var i = 0; i < v2PlayerCount; i++) {
        var pid = "p" + (i + 1);
        if (playerTypes[pid] === "ai") {
            v2AiPlayerIds.push(pid);
        } else {
            v2HumanPlayerIds.push(pid);
        }
    }
    v2AiDifficulty = result.data.state._ai_difficulty || "normal";

    document.getElementById("setup-phase").style.display = "none";
    document.getElementById("battle-phase").style.display = "";
    hideSettlementProgress();
    hideDecisionArea();
    hideRoundSummaryCard();
    hideEndCard();

    renderV2State(result.data.state);
    var aiCount = v2AiPlayerIds.length;
    var msg = result.data.message || "对局已创建，请为每位玩家选择动作。";
    if (aiCount > 0) {
        msg += "（" + aiCount + " 名 AI 自动出招）";
    }
    setMessage(msg);
}

function confirmReset() {
    if (v2LatestState && !v2LatestState.is_game_over && v2LatestState.round_num > 0) {
        ModalUtils.showConfirmModal({
            title: "确认重新开始",
            body: "当前对局尚未结束，确定要放弃并重新开始吗？",
            onConfirm: resetToSetup,
            confirmText: "重新开始",
            cancelText: "取消",
        });
    } else {
        resetToSetup();
    }
}

async function resetToSetup() {
    v2SelectedMoves = {};
    v2SettlementResult = null;
    v2EndShown = false;
    v2RoundSummaryShown = false;
    v2FocusedPlayer = "p1";
    v2IsSetupPhase = true;

    document.getElementById("setup-phase").style.display = "";
    document.getElementById("battle-phase").style.display = "none";
    document.getElementById("reset-btn").style.display = "none";
    hideSettlementProgress();
    hideDecisionArea();
    hideRoundSummaryCard();
    hideEndCard();

    renderSetupPhase();
    setMessage("已返回准备阶段。");
}

/* ═══════════════════════════════════════════════════════════════
   提交动作
   ═══════════════════════════════════════════════════════════════ */

async function submitMoves() {
    if (!v2LatestState || v2LatestState.is_game_over) return;

    var alivePlayers = (v2LatestState.players || []).filter(function(p) { return p.status === "alive"; });
    var moves = {};
    // 只收集人类玩家的动作，AI 由后端自动补齐
    for (var i = 0; i < alivePlayers.length; i++) {
        var pid = alivePlayers[i].player_id;
        var isAi = v2AiPlayerIds.indexOf(pid) >= 0;
        if (isAi) continue; // AI 由后端自动生成
        if (!v2SelectedMoves[pid]) { setMessage("请为 " + alivePlayers[i].username + " 选择动作。"); return; }
        moves[pid] = v2SelectedMoves[pid];
    }

    // 如果全部是 AI，使用 auto_resolve
    var useAutoResolve = v2Settings.autoResolve || v2HumanPlayerIds.length === 0
        || (alivePlayers.every(function(p) { return v2AiPlayerIds.indexOf(p.player_id) >= 0; }));

    setMessage("正在提交动作并结算...");
    var result = await ApiUtils.apiPost("/v2/api/local/step", {
        moves: moves,
        auto_resolve: useAutoResolve,
    });

    if (!result.ok) { setMessage("提交失败：" + (result.error || "")); return; }

    v2LatestState = result.data.state;
    v2SelectedMoves = {};
    var settlement = result.data.settlement || {};
    handleSettlementResult(settlement);
    renderV2State(v2LatestState);
}

/* ═══════════════════════════════════════════════════════════════
   结算结果处理
   ═══════════════════════════════════════════════════════════════ */

function handleSettlementResult(settlement) {
    var action = settlement.action || "";

    if (action === "request_decision") {
        renderSettlementProgress(settlement);
        setMessage("等待决策 — 请在「结算进度」卡片中选择目标。");
        // 滚动到结算卡片
        var card = document.getElementById("settlement-card");
        if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
    }

    if (action === "round_complete") {
        renderSettlementProgress(settlement);
        fetchRoundSummary();
        setMessage("回合结算完成，查看下方总结。");
        return;
    }

    if (action === "game_over") {
        renderSettlementProgress(settlement);
        fetchRoundSummary();
        setMessage("对局已结束！");
        return;
    }

    // 其他状态（waiting 等）
    renderSettlementProgress(settlement);
    setMessage("结算中...");
}

async function fetchRoundSummary() {
    if (!v2LatestState || !v2LatestState.history || v2LatestState.history.length === 0) return;
    try {
        var result = await ApiUtils.apiGet("/v2/api/local/state");
        if (result.ok && result.data.state) {
            var state = result.data.state;
            v2LatestState = state;
            if (state.history && state.history.length > 0) {
                var lastLog = state.history[state.history.length - 1];
                var summary = buildSummaryFromLog(lastLog, state);
                hideSettlementProgress();
                renderRoundSummaryCard(summary);
                renderV2State(state);
                if (state.is_game_over) {
                    renderEndCard(state);
                }
            }
        }
    } catch (e) { console.error("获取回合总结失败:", e); }
}

function buildSummaryFromLog(log, state) {
    var summary = {
        round_num: log.round_num || 0,
        moves: log.moves || {},
        resource_check: { ok: log.resource_check_ok || {}, illegal: log.illegal_players || [] },
        flashed_players: log.flashed_players || [],
        three_chain: { groups: log.three_chain_groups || [], two_groups: log.two_three_chains || false },
        deaths: log.deaths || [],
        pre_snapshots: log.pre_snapshots || {},
        post_snapshots: log.post_snapshots || {},
        winner: log.winner,
        game_ended: log.game_ended || (state && state.is_game_over) || false,
        alive_count: state ? state.alive_count : 0,
        resource_changes: {},
    };
    var preKeys = Object.keys(summary.pre_snapshots);
    for (var i = 0; i < preKeys.length; i++) {
        var pid = preKeys[i];
        var pre = summary.pre_snapshots[pid] || {};
        var post = summary.post_snapshots[pid] || {};
        var chg = {};
        var keys = Object.keys(pre).concat(Object.keys(post));
        for (var k = 0; k < keys.length; k++) {
            var key = keys[k];
            var preVal = pre[key] || 0;
            var postVal = post[key] || 0;
            if (preVal !== postVal) chg[key] = postVal - preVal;
        }
        if (Object.keys(chg).length > 0) summary.resource_changes[pid] = chg;
    }
    return summary;
}

/* ═══════════════════════════════════════════════════════════════
   决策提交
   ═══════════════════════════════════════════════════════════════ */

async function submitDecision() {
    var decisions = collectDecisionData();
    if (Object.keys(decisions).length === 0) { setMessage("请至少为每位玩家选择一个选项（可放空）。"); return; }

    hideDecisionArea();
    setMessage("正在提交决策...");

    var result = await ApiUtils.apiPost("/v2/api/local/decision", {
        decisions: decisions,
        auto_resolve: v2Settings.autoResolve,
    });

    if (!result.ok) { setMessage("决策提交失败：" + (result.error || "")); return; }

    v2LatestState = result.data.state;
    var settlement = result.data.settlement || {};
    handleSettlementResult(settlement);
    renderV2State(v2LatestState);
}

async function autoResolveDecisions() {
    hideDecisionArea();
    setMessage("正在自动决策...");

    var result = await ApiUtils.apiPost("/v2/api/local/decision", {
        decisions: {},
        auto_resolve: true,
    });

    if (!result.ok) { setMessage("自动决策失败：" + (result.error || "")); return; }

    v2LatestState = result.data.state;
    var settlement = result.data.settlement || {};
    handleSettlementResult(settlement);
    renderV2State(v2LatestState);
}

/* ═══════════════════════════════════════════════════════════════
   继续下一回合
   ═══════════════════════════════════════════════════════════════ */

function continueToNextRound() {
    hideRoundSummaryCard();
    hideEndCard();
    v2SelectedMoves = {};
    v2SettlementResult = null;
    if (v2LatestState) renderV2State(v2LatestState);
    setMessage("新回合开始，请选择动作。");
    // 滚动到动作选择区
    var moveCard = document.getElementById("move-selection-card");
    if (moveCard) moveCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ═══════════════════════════════════════════════════════════════
   键盘操作
   ═══════════════════════════════════════════════════════════════ */

function handleKeyboard(event) {
    if (event.target && ["INPUT", "TEXTAREA", "SELECT"].indexOf(event.target.tagName) !== -1) return;
    // 弹窗打开时不触发动作快捷键
    if (document.querySelector(".modal-mask.show")) return;

    var key = event.key;

    // Tab：切换焦点玩家
    if (key === "Tab") {
        event.preventDefault();
        if (!v2IsSetupPhase && v2LatestState) { cycleFocusPlayer(); renderV2State(v2LatestState); }
        return;
    }

    // Escape：关闭帮助弹窗
    if (key === "Escape") {
        var helpMask = document.getElementById("help-modal-mask");
        if (helpMask && helpMask.classList.contains("show")) {
            helpMask.classList.remove("show");
            return;
        }
        return;
    }

    // Backspace：撤销焦点玩家选择 / 关闭弹窗
    if (key === "Backspace") {
        event.preventDefault();
        if (!v2IsSetupPhase && v2FocusedPlayer) {
            v2SelectedMoves[v2FocusedPlayer] = null;
            if (v2LatestState) renderV2State(v2LatestState);
            setMessage("已撤销 " + getPlayerName(v2FocusedPlayer, (v2LatestState && v2LatestState.players) || []) + " 的选择。");
        }
        return;
    }

    // Enter：提交 / 确认决策 / 继续
    if (key === "Enter") {
        // 决策区可见 → 提交决策
        var decisionArea = document.getElementById("decision-area");
        if (decisionArea && decisionArea.style.display !== "none") {
            submitDecision();
            return;
        }
        // 回合总结可见 → 继续
        var summaryCard = document.getElementById("round-summary-card");
        if (summaryCard && summaryCard.style.display !== "none") {
            continueToNextRound();
            return;
        }
        // 对局结束可见 → 重新开始
        var endCard = document.getElementById("end-card");
        if (endCard && endCard.style.display !== "none") {
            hideEndCard();
            resetToSetup();
            return;
        }
        // 对局阶段 → 提交动作
        if (!v2IsSetupPhase) { submitMoves(); return; }
        return;
    }

    // 动作快捷键
    if (v2IsSetupPhase || !v2FocusedPlayer) return;
    var moveName = V2_KEY_TO_MOVE[key.toLowerCase()];
    if (moveName && v2LatestState) {
        var legalMoves = v2LatestState.legal_moves || {};
        var playerLegal = legalMoves[v2FocusedPlayer] || [];
        if (playerLegal.indexOf(moveName) !== -1) {
            event.preventDefault();
            if (v2SelectedMoves[v2FocusedPlayer] === moveName) {
                if (v2AllAlivePlayersSelected()) {
                    submitMoves();
                    return;
                }
                cycleFocusPlayer();
                renderV2State(v2LatestState);
                setMessage("已选择 " + (V2_MOVE_LABELS[moveName] || moveName) + "，继续为下一位玩家选择。");
                return;
            }
            v2SelectedMoves[v2FocusedPlayer] = moveName;
            renderV2State(v2LatestState);
            setMessage("已为 " + getPlayerName(v2FocusedPlayer, v2LatestState.players || []) + " 选择 " + (V2_MOVE_LABELS[moveName] || moveName) + "。再次按该键或按 Enter 提交。");
        }
    }
}

function v2AllAlivePlayersSelected() {
    if (!v2LatestState) return false;
    var alivePlayers = (v2LatestState.players || []).filter(function(p) { return p.status === "alive"; });
    if (alivePlayers.length === 0) return false;
    for (var i = 0; i < alivePlayers.length; i++) {
        if (!v2SelectedMoves[alivePlayers[i].player_id]) return false;
    }
    return true;
}

function cycleFocusPlayer() {
    if (!v2LatestState) return;
    var alivePlayers = (v2LatestState.players || []).filter(function(p) { return p.status === "alive"; });
    if (alivePlayers.length === 0) return;
    var currentIdx = -1;
    for (var i = 0; i < alivePlayers.length; i++) {
        if (alivePlayers[i].player_id === v2FocusedPlayer) { currentIdx = i; break; }
    }
    v2FocusedPlayer = alivePlayers[(currentIdx + 1) % alivePlayers.length].player_id;
}

/* ═══════════════════════════════════════════════════════════════
   辅助
   ═══════════════════════════════════════════════════════════════ */

function clearAllSelections() {
    v2SelectedMoves = {};
    if (v2LatestState) renderV2State(v2LatestState);
    setMessage("已清空所有选择。");
}

function setMessage(msg) {
    document.getElementById("message").textContent = msg;
}

/* ═══════════════════════════════════════════════════════════════
   启动
   ═══════════════════════════════════════════════════════════════ */

if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
    window.location.href = "/v2/login?expired=1";
} else {
    initV2LocalPage();
}
