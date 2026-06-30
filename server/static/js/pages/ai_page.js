/**
 * ClapClap 1.0 AI 对战页面。
 *
 * 真人可选择 P1 或 P2，AI 固定控制另一侧。
 * 页面分为进入页和对战页；对战页默认只显示核心信息。
 */

// =========================================================================
// 全局状态
// =========================================================================

var aiLatestState = null;
var aiSelectedMove = null;
var aiDifficulty = "normal";
var aiHumanSeat = "p1";
var aiThinking = false;
var aiEndModalShownForWinner = null;
var aiLastMoveLabel = null;
var aiLastMoveName = null;
var aiPolicyType = null;
var aiInferenceMs = null;
var aiBattleStarted = false;

var aiUiSettings = {
    showMoveCodes: false,
    showHotkeys: false,
    showPolicy: false,
    showInference: false,
    showRoundDetails: false,
    showHistory: false
};

// =========================================================================
// 动作说明（与 local 页面一致）
// =========================================================================

var aiMoveDescriptions = {
    QI: "资源动作。获得 1 气。",
    SHIELD: "资源动作。获得 1 盾。",
    GI: "气系攻击。消耗 1 气，攻击力 1。可抢对方本回合出的镐。",
    PO: "气系攻击。消耗 2 气，攻击力 2。会被你吃 / 双吃针对。",
    LENG_FENG: "气系攻击。消耗 3 气，攻击力 3。",
    RU_LAI: "气系攻击。消耗 5 气，攻击力 4，伤害 2。",
    HEI_DONG: "气系攻击。消耗 8 气，攻击力 5，伤害 3。当前版本不拆分。",
    FIRE: "盾系攻击。消耗 2 盾，攻击力 1.5，并获得 1 火种。",
    SHAN_DIAN: "盾系攻击。消耗 3 盾，攻击力 2，并获得 1 电池。会被你吃 / 双吃针对。",
    LIE_YAN: "盾系攻击。优先消耗 2 火种，否则消耗 4 盾。攻击力 3。",
    SHINING: "盾系攻击。优先消耗 2 电池，否则消耗 6 盾。攻击力 4，伤害 2。会被双吃针对。",
    SHI_ZI: "防御动作。消耗 2 气，防御力 3。",
    BA_GUA: "防御动作。消耗 3 气，防御力 4。",
    CHI: "锦囊动作。消耗 1 气。可针对破、闪电。",
    SHUANG_CHI: "锦囊动作。消耗 2 气。可针对破、闪电、Shining。当前版本不拆分。",
    SHAN: "锦囊动作。每局最多 2 次。使用后完全退出本回合结算。",
    GAO: "锦囊动作。消耗 2 气，获得 1 镐。镐可抵挡伤害，2 个及以上会爆镐。"
};

var aiFixedKeyMap = {
    CHI: "1", SHUANG_CHI: "2", SHAN: "3", GAO: "4",
    QI: "Q", SHIELD: "W", SHI_ZI: "E", BA_GUA: "R",
    GI: "A", PO: "S", LENG_FENG: "D", RU_LAI: "F", HEI_DONG: "G",
    FIRE: "Z", SHAN_DIAN: "X", LIE_YAN: "C", SHINING: "V"
};

// =========================================================================
// 基础工具
// =========================================================================

function aiOtherSeat(seat) {
    return seat === "p1" ? "p2" : "p1";
}

function aiSeatPlayerNumber(seat) {
    return seat === "p2" ? 2 : 1;
}

function aiSeatLabel(seat) {
    return seat === "p2" ? "P2" : "P1";
}

function aiHumanPlayerNumber() {
    return aiSeatPlayerNumber(aiHumanSeat);
}

function aiAiSeat() {
    if (aiLatestState && aiLatestState.ai_seat) return aiLatestState.ai_seat;
    return aiOtherSeat(aiHumanSeat);
}

function aiWait(ms) {
    return new Promise(function(resolve) {
        setTimeout(resolve, ms);
    });
}

function aiWinnerText(winner) {
    if (winner === null || winner === undefined) return "未结束";
    if (winner === 0) return "平局";
    if (winner === aiHumanPlayerNumber()) return "你获胜";
    return "AI 获胜";
}

function aiDifficultyLabel(diff) {
    if (diff === "easy") return "简单";
    if (diff === "hard") return "困难";
    return "普通";
}

function aiPolicyTypeLabel(policyType) {
    if (policyType === "model") return "训练模型";
    if (policyType === "heuristic_fallback") return "模型降级";
    if (policyType === "heuristic") return "启发式";
    if (policyType === "random") return "随机";
    return "待选择";
}

function aiSetText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
}

function aiSetHtml(id, html) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = html;
}

// =========================================================================
// 进入页 / 设置
// =========================================================================

function aiShowEntryPage() {
    aiBattleStarted = false;
    document.getElementById("ai-entry-page").classList.remove("ai-hidden");
    document.getElementById("ai-battle-page").classList.remove("show");
    aiSetText("ai-entry-message", "默认：P1 先手，普通难度。");
    aiHideDeployPanel();
}

function aiShowBattlePage() {
    aiBattleStarted = true;
    document.getElementById("ai-entry-page").classList.add("ai-hidden");
    document.getElementById("ai-battle-page").classList.add("show");
    aiApplyUiSettings();
}

function aiUpdateChoiceControls() {
    var diffBtns = document.querySelectorAll(".ai-diff-btn");
    for (var i = 0; i < diffBtns.length; i++) {
        var diff = diffBtns[i].getAttribute("data-diff");
        diffBtns[i].disabled = aiBattleStarted && aiLatestState && aiLatestState.winner === null;
        diffBtns[i].classList.toggle("active", diff === aiDifficulty);
    }

    var seatBtns = document.querySelectorAll(".ai-seat-btn");
    for (var j = 0; j < seatBtns.length; j++) {
        var seat = seatBtns[j].getAttribute("data-seat");
        seatBtns[j].disabled = aiBattleStarted && aiLatestState && aiLatestState.winner === null;
        seatBtns[j].classList.toggle("active", seat === aiHumanSeat);
    }
}

function aiSetDifficulty(diff) {
    if (diff !== "easy" && diff !== "normal" && diff !== "hard") return;
    if (aiBattleStarted && aiLatestState && aiLatestState.winner === null) {
        aiSetText("ai-message", "本局难度已锁定，退出本局后可以切换。");
        aiUpdateChoiceControls();
        return;
    }
    aiDifficulty = diff;
    aiUpdateChoiceControls();
    aiSetText("ai-entry-message", "已选择：" + aiSeatLabel(aiHumanSeat) + "，" + aiDifficultyLabel(aiDifficulty) + "难度。");
}

function aiSetHumanSeat(seat) {
    if (seat !== "p1" && seat !== "p2") return;
    if (aiBattleStarted && aiLatestState && aiLatestState.winner === null) {
        aiSetText("ai-message", "本局座位已锁定，退出本局后可以换边。");
        aiUpdateChoiceControls();
        return;
    }
    aiHumanSeat = seat;
    aiSelectedMove = null;
    aiUpdateChoiceControls();
    aiSetText("ai-entry-message", "已选择：" + aiSeatLabel(aiHumanSeat) + "，" + aiDifficultyLabel(aiDifficulty) + "难度。");
    if (aiLatestState && aiBattleStarted) aiRenderState(aiLatestState);
}

function aiApplyUiSettings() {
    var battlePage = document.getElementById("ai-battle-page");
    if (!battlePage) return;
    battlePage.classList.toggle("show-codes", aiUiSettings.showMoveCodes);
    battlePage.classList.toggle("show-hotkeys", aiUiSettings.showHotkeys);

    var latest = document.getElementById("ai-latest-round");
    if (latest) latest.classList.toggle("compact", !aiUiSettings.showRoundDetails);

    var historyWrap = document.getElementById("ai-history-wrap");
    if (historyWrap) historyWrap.classList.toggle("hidden", !aiUiSettings.showHistory);

    if (aiLatestState) aiRenderState(aiLatestState);
}

function aiSyncSettingInputs() {
    var inputs = document.querySelectorAll(".ai-setting-toggle");
    for (var i = 0; i < inputs.length; i++) {
        var key = inputs[i].getAttribute("data-setting");
        inputs[i].checked = !!aiUiSettings[key];
    }
}

function aiOpenSettingsModal() {
    aiSyncSettingInputs();
    document.getElementById("ai-settings-modal-mask").classList.add("show");
}

function aiCloseSettingsModal() {
    document.getElementById("ai-settings-modal-mask").classList.remove("show");
}

// =========================================================================
// 部署进度
// =========================================================================

function aiHideDeployPanel() {
    var panel = document.getElementById("ai-deploy-panel");
    var progress = document.getElementById("ai-deploy-progress");
    if (panel) panel.style.display = "none";
    if (progress) progress.style.width = "0";
}

function aiSetDeployProgress(text, percent) {
    var panel = document.getElementById("ai-deploy-panel");
    var progress = document.getElementById("ai-deploy-progress");
    if (panel) panel.style.display = "block";
    aiSetText("ai-deploy-text", text);
    if (progress) progress.style.width = percent + "%";
}

async function aiRunDeployProgress() {
    var steps = [
        { text: "检查模型目录...", percent: 18 },
        { text: "读取部署清单...", percent: 38 },
        { text: "验证动作空间...", percent: 58 },
        { text: "准备推理运行时...", percent: 78 }
    ];

    var deployResult = null;
    for (var i = 0; i < steps.length; i++) {
        aiSetDeployProgress(steps[i].text, steps[i].percent);
        var started = Date.now();
        if (i === 1) {
            deployResult = await ApiUtils.apiPost("/v1/api/ai/deploy", {
                difficulty: aiDifficulty
            });
        }
        var elapsed = Date.now() - started;
        if (elapsed < 120) await aiWait(120 - elapsed);
    }

    if (!deployResult || !deployResult.ok) {
        aiSetDeployProgress("部署检查失败。", 100);
        throw new Error((deployResult && deployResult.error) || "部署检查失败。");
    }

    aiPolicyType = deployResult.data.policy_type || aiPolicyType;
    var status = deployResult.data.model_status || {};
    aiSetDeployProgress(status.available ? "模型已就绪。" : "模型不可用，已准备降级策略。", 100);
    await aiWait(120);
}

async function aiStartBattle() {
    var startBtn = document.getElementById("ai-start-btn");
    startBtn.disabled = true;
    aiSetText("ai-entry-message", "正在准备对战...");

    try {
        if (aiDifficulty === "hard") {
            await aiRunDeployProgress();
        } else {
            aiHideDeployPanel();
            await aiWait(120);
        }

        var result = await ApiUtils.apiPost("/v1/api/ai/reset");
        if (!result.ok) {
            aiSetText("ai-entry-message", "重置失败：" + result.error);
            return;
        }

        aiSelectedMove = null;
        aiThinking = false;
        aiEndModalShownForWinner = null;
        aiLastMoveLabel = null;
        aiLastMoveName = null;
        aiInferenceMs = null;
        window._aiBattleId = null;
        aiCloseEndModal();
        aiShowBattlePage();
        aiRenderState(result.data.state);
        aiSetText("ai-message", "对战已开始。选择动作后出招。");
    } catch (error) {
        aiSetText("ai-entry-message", error.message || "进入对战失败。");
    } finally {
        startBtn.disabled = false;
    }
}

// =========================================================================
// 渲染函数
// =========================================================================

function aiResourceItem(label, value) {
    return (
        '<div class="resource-item">' +
        '<div class="resource-label">' + label + '</div>' +
        '<div class="resource-value">' + value + '</div>' +
        '</div>'
    );
}

function aiRenderPlayerState(player) {
    return (
        aiResourceItem("生命", player.hp) +
        aiResourceItem("气", player.qi) +
        aiResourceItem("盾", player.shield) +
        aiResourceItem("火种", player.spark) +
        aiResourceItem("电池", player.battery) +
        aiResourceItem("镐", player.pickaxe) +
        aiResourceItem("闪", player.flash_used)
    );
}

function aiMoveCategoryTitle(category) {
    if (category === "resource") return "资源";
    if (category === "attack_qi") return "气攻";
    if (category === "attack_shield") return "盾攻";
    if (category === "defense") return "防御";
    if (category === "trick") return "锦囊";
    return "其他";
}

function aiGetMoveGroups(catalog) {
    var groups = {
        resource: [],
        attack_qi: [],
        attack_shield: [],
        defense: [],
        trick: []
    };
    for (var i = 0; i < catalog.length; i++) {
        var item = catalog[i];
        if (item.name === "QI" || item.name === "SHIELD") {
            groups.resource.push(item);
        } else if (["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"].indexOf(item.name) !== -1) {
            groups.attack_qi.push(item);
        } else if (["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"].indexOf(item.name) !== -1) {
            groups.attack_shield.push(item);
        } else if (["SHI_ZI", "BA_GUA"].indexOf(item.name) !== -1) {
            groups.defense.push(item);
        } else {
            groups.trick.push(item);
        }
    }
    return groups;
}

function aiRenderMoveButtons(containerId, legalMoves, catalog, selectedMove, selectedSeat, onSelect) {
    var container = document.getElementById(containerId);
    container.innerHTML = "";

    var groups = aiGetMoveGroups(catalog);
    var groupKeys = Object.keys(groups);

    for (var gi = 0; gi < groupKeys.length; gi++) {
        var groupKey = groupKeys[gi];
        var items = groups[groupKey];
        if (items.length === 0) continue;

        var title = document.createElement("div");
        title.className = "move-group-title";
        title.textContent = aiMoveCategoryTitle(groupKey);
        container.appendChild(title);

        var grid = document.createElement("div");
        grid.className = "move-grid";

        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var wrap = document.createElement("div");
            wrap.className = "move-btn-wrap";

            var btn = document.createElement("button");
            btn.className = "move-btn";
            btn.type = "button";
            btn.title = aiMoveDescriptions[item.name] || "";

            var legal = legalMoves.indexOf(item.name) !== -1;
            if (!legal) btn.classList.add("disabled");
            if (selectedMove === item.name) {
                btn.classList.add("selected");
                btn.classList.add(selectedSeat === "p2" ? "p2-selected" : "p1-selected");
            }

            var hotkey = aiFixedKeyMap[item.name] || "";
            btn.innerHTML =
                (hotkey ? '<div class="move-hotkey">' + hotkey + '</div>' : "") +
                '<div class="move-label">' + item.label + '</div>' +
                '<div class="move-name">' + item.name + '</div>';

            btn.addEventListener("click", (function(moveName, isLegal) {
                return function() {
                    if (!isLegal || aiThinking) return;
                    onSelect(moveName);
                };
            })(item.name, legal));

            wrap.appendChild(btn);
            grid.appendChild(wrap);
        }

        container.appendChild(grid);
    }
}

function aiRoundValue(log, seat, key) {
    return log[seat + "_" + key];
}

function aiRenderLatestRound(log) {
    if (!log) {
        return "<div class='muted'>还没有回合记录。</div>";
    }

    var humanSeat = log.human_seat || aiHumanSeat;
    var aiSeat = log.ai_seat || aiOtherSeat(humanSeat);
    var humanMove = aiRoundValue(log, humanSeat, "move_label");
    var aiMove = aiRoundValue(log, aiSeat, "move_label");
    var humanDamage = aiRoundValue(log, humanSeat, "damage_taken") || 0;
    var aiDamage = aiRoundValue(log, aiSeat, "damage_taken") || 0;
    var humanNote = aiRoundValue(log, humanSeat, "note") || "无";
    var aiNote = aiRoundValue(log, aiSeat, "note") || "无";

    var resultLine = "";
    if (log.winner_after_round !== null && log.winner_after_round !== undefined) {
        resultLine = '<div><strong>结果：</strong>' + aiWinnerText(log.winner_after_round) + '</div>';
    }

    return (
        '<div><strong>第 ' + log.round_num + ' 回合</strong>：你 ' + humanMove + ' / AI ' + aiMove + '</div>' +
        '<div>伤害：你 <span class="' + (humanDamage > 0 ? "danger-text" : "good-text") + '">' + humanDamage + '</span>' +
        ' · AI <span class="' + (aiDamage > 0 ? "danger-text" : "good-text") + '">' + aiDamage + '</span></div>' +
        '<div class="round-detail-extra">你的说明：' + humanNote + '</div>' +
        '<div class="round-detail-extra">AI 说明：' + aiNote + '</div>' +
        '<div class="round-detail-extra">' + (log.summary || "") + '</div>' +
        resultLine
    );
}

function aiRenderHistory(logs) {
    var historyEl = document.getElementById("ai-history");
    historyEl.innerHTML = "";

    if (!aiUiSettings.showHistory) return;
    if (logs.length === 0) {
        historyEl.innerHTML = "<div class='muted'>暂无历史。</div>";
        return;
    }

    for (var i = logs.length - 1; i >= 0; i--) {
        var log = logs[i];
        var humanSeat = log.human_seat || aiHumanSeat;
        var aiSeat = log.ai_seat || aiOtherSeat(humanSeat);
        var item = document.createElement("div");
        item.className = "history-item";
        item.innerHTML =
            '<div><strong>第 ' + log.round_num + ' 回合</strong></div>' +
            '<div>你：' + aiRoundValue(log, humanSeat, "move_label") +
            ' | AI：' + aiRoundValue(log, aiSeat, "move_label") + '</div>' +
            '<div>伤害：你 ' + (aiRoundValue(log, humanSeat, "damage_taken") || 0) +
            ' | AI ' + (aiRoundValue(log, aiSeat, "damage_taken") || 0) + '</div>';
        historyEl.appendChild(item);
    }
    historyEl.scrollTop = 0;
}

function aiRenderState(state) {
    aiLatestState = state;
    window._aiBattleId = state.battle_id || window._aiBattleId || null;
    if (state.ai_difficulty) aiDifficulty = state.ai_difficulty;
    if (state.human_seat) aiHumanSeat = state.human_seat;
    if (state.ai_policy_type) aiPolicyType = state.ai_policy_type;

    var catalog = state.move_catalog || [];
    var logs = state.history || [];
    var aiSeat = state.ai_seat || aiAiSeat();

    var statusHtml =
        '<span class="status-badge">回合 ' + state.round_num + '</span>' +
        '<span class="winner-badge">' + aiWinnerText(state.winner) + '</span>' +
        '<span class="status-badge">你 ' + aiSeatLabel(aiHumanSeat) + '</span>' +
        '<span class="status-badge">AI ' + aiSeatLabel(aiSeat) + '</span>' +
        '<span class="status-badge">' + aiDifficultyLabel(aiDifficulty) + '</span>';
    if (aiUiSettings.showPolicy) {
        statusHtml += '<span class="status-badge ai-policy-extra">策略 ' + aiPolicyTypeLabel(aiPolicyType) + '</span>';
    }
    if (aiUiSettings.showInference && aiInferenceMs !== null) {
        statusHtml += '<span class="status-badge ai-policy-extra">推理 ' + aiInferenceMs + ' ms</span>';
    }
    aiSetHtml("ai-basic-info", statusHtml);

    var humanPlayer = state[aiHumanSeat] || state.p1;
    var aiPlayer = state[aiSeat] || state.p2;
    aiSetText("ai-human-state-title", "你的资源 (" + aiSeatLabel(aiHumanSeat) + ")");
    aiSetText("ai-opponent-state-title", "AI 资源 (" + aiSeatLabel(aiSeat) + ")");
    aiSetHtml("ai-p1-state", aiRenderPlayerState(humanPlayer));
    aiSetHtml("ai-p2-state", aiRenderPlayerState(aiPlayer));

    var legal = state.legal_moves ? (state.legal_moves[aiHumanSeat] || []) : [];
    aiRenderMoveButtons("ai-p1-move-groups", legal, catalog, aiSelectedMove, aiHumanSeat, function(moveName) {
        aiSelectedMove = moveName;
        aiRenderState(aiLatestState);
        aiSetText("ai-message", "已选择 " + moveName + "，点击出招。");
    });

    var aiMoveBox = document.getElementById("ai-move-box");
    if (aiThinking) {
        aiMoveBox.innerHTML = "<div class='muted'>AI 正在思考...</div>";
    } else if (aiLastMoveName && aiLastMoveLabel) {
        aiMoveBox.innerHTML = '<div><strong>AI 本回合：</strong><span class="good-text">' + aiLastMoveLabel + '</span></div>' +
            (aiUiSettings.showMoveCodes ? '<div class="muted">' + aiLastMoveName + '</div>' : "");
    } else if (state.winner === null && logs.length > 0) {
        var lastLog = logs[logs.length - 1];
        var lastAiSeat = lastLog.ai_seat || aiSeat;
        aiMoveBox.innerHTML = '<div><strong>AI 上回合：</strong><span class="good-text">' +
            aiRoundValue(lastLog, lastAiSeat, "move_label") + '</span></div>' +
            (aiUiSettings.showMoveCodes ? '<div class="muted">' + aiRoundValue(lastLog, lastAiSeat, "move") + '</div>' : "");
    } else if (state.winner !== null) {
        aiMoveBox.innerHTML = "<div class='muted'>游戏已结束。</div>";
    } else {
        aiMoveBox.innerHTML = "<div class='muted'>等待你出招...</div>";
    }

    aiSetHtml("ai-latest-round", aiRenderLatestRound(logs.length > 0 ? logs[logs.length - 1] : null));
    aiRenderHistory(logs);

    var stepBtn = document.getElementById("ai-step-btn");
    if (state.winner !== null) {
        stepBtn.disabled = true;
        stepBtn.textContent = "已结束";
    } else if (aiThinking) {
        stepBtn.disabled = true;
        stepBtn.textContent = "思考中";
    } else {
        stepBtn.disabled = false;
        stepBtn.textContent = "出招";
    }

    aiUpdateChoiceControls();
    aiApplyUiSettingsClassesOnly();
    aiMaybeShowEndModal(state);
}

function aiApplyUiSettingsClassesOnly() {
    var battlePage = document.getElementById("ai-battle-page");
    if (!battlePage) return;
    battlePage.classList.toggle("show-codes", aiUiSettings.showMoveCodes);
    battlePage.classList.toggle("show-hotkeys", aiUiSettings.showHotkeys);
    var latest = document.getElementById("ai-latest-round");
    if (latest) latest.classList.toggle("compact", !aiUiSettings.showRoundDetails);
    var historyWrap = document.getElementById("ai-history-wrap");
    if (historyWrap) historyWrap.classList.toggle("hidden", !aiUiSettings.showHistory);
}

function aiMaybeShowEndModal(state) {
    if (state.winner === null) {
        aiEndModalShownForWinner = null;
        return;
    }
    if (aiEndModalShownForWinner === state.winner) return;

    aiEndModalShownForWinner = state.winner;
    aiSetText("ai-end-result-text", aiWinnerText(state.winner));

    var detail = "最终回合数：" + state.round_num + " | 难度：" + aiDifficultyLabel(aiDifficulty);
    var battleId = state.battle_id || window._aiBattleId;
    if (battleId) {
        detail += ' | <a href="/v1/record/' + battleId + '" target="_blank">查看对局记录</a>';
    }
    aiSetHtml("ai-end-result-detail", detail);
    document.getElementById("ai-end-modal-mask").classList.add("show");
}

function aiCloseEndModal() {
    document.getElementById("ai-end-modal-mask").classList.remove("show");
}

// =========================================================================
// API 交互
// =========================================================================

async function aiFetchState() {
    var result = await ApiUtils.apiGet("/v1/api/ai/state");
    if (!result.ok) {
        aiSetText("ai-message", "获取状态失败：" + result.error);
        return;
    }
    aiRenderState(result.data);
    aiSetText("ai-message", "状态已刷新。");
}

async function aiResetCurrentGame(returnToEntry) {
    var result = await ApiUtils.apiPost("/v1/api/ai/reset");
    if (!result.ok) {
        aiSetText("ai-message", "重置失败：" + result.error);
        return;
    }

    aiSelectedMove = null;
    aiThinking = false;
    aiEndModalShownForWinner = null;
    aiLastMoveLabel = null;
    aiLastMoveName = null;
    aiInferenceMs = null;
    window._aiBattleId = null;
    aiCloseEndModal();
    aiRenderState(result.data.state);

    if (returnToEntry) {
        aiShowEntryPage();
    } else {
        aiSetText("ai-message", result.data.message || "AI 对战已重置。");
        aiSetHtml("ai-move-box", "<div class='muted'>等待你出招...</div>");
    }
}

async function aiStepGame() {
    if (!aiSelectedMove) {
        aiSetText("ai-message", "请先选择你的动作。");
        return;
    }
    if (aiThinking) return;

    aiThinking = true;
    aiRenderState(aiLatestState);
    aiSetText("ai-message", "AI 正在思考...");

    var result = await ApiUtils.apiPost("/v1/api/ai/step", {
        human_move: aiSelectedMove,
        difficulty: aiDifficulty,
        human_seat: aiHumanSeat
    });

    aiThinking = false;

    if (!result.ok) {
        aiSetText("ai-message", result.error || "提交失败。");
        aiRenderState(aiLatestState);
        return;
    }

    aiLastMoveName = result.data.ai_move;
    aiLastMoveLabel = result.data.ai_move_label;
    aiPolicyType = result.data.ai_policy_type || (result.data.state && result.data.state.ai_policy_type) || aiPolicyType;
    aiInferenceMs = result.data.ai_inference_ms == null ? null : result.data.ai_inference_ms;
    window._aiBattleId = result.data.battle_id || (result.data.state && result.data.state.battle_id) || window._aiBattleId;

    aiSelectedMove = null;
    aiRenderState(result.data.state);
    aiSetText("ai-message", result.data.message || "本回合已结算。");
}

// =========================================================================
// 键盘操作
// =========================================================================

function aiHandleKeyboard(keyText) {
    if (!aiBattleStarted || !aiLatestState || aiLatestState.winner !== null || aiThinking) return;

    var endModal = document.getElementById("ai-end-modal-mask");
    var settingsModal = document.getElementById("ai-settings-modal-mask");
    if ((endModal && endModal.classList.contains("show")) ||
        (settingsModal && settingsModal.classList.contains("show"))) {
        return;
    }

    var upperKey = keyText.toUpperCase();
    var matchedMove = null;
    var moveNames = Object.keys(aiFixedKeyMap);
    for (var i = 0; i < moveNames.length; i++) {
        if (aiFixedKeyMap[moveNames[i]] === upperKey) {
            matchedMove = moveNames[i];
            break;
        }
    }
    if (!matchedMove) return;

    var legal = aiLatestState.legal_moves ? (aiLatestState.legal_moves[aiHumanSeat] || []) : [];
    if (legal.indexOf(matchedMove) !== -1) {
        aiSelectedMove = matchedMove;
        aiRenderState(aiLatestState);
        aiSetText("ai-message", "已选择 " + matchedMove + "，按 Enter 出招。");
    }
}

// =========================================================================
// 初始化
// =========================================================================

function aiInitPage() {
    document.addEventListener("keydown", function(event) {
        if (event.target && ["INPUT", "TEXTAREA", "SELECT"].indexOf(event.target.tagName) !== -1) {
            return;
        }

        var key = event.key;
        if (/^[1-4]$/.test(key) || /^[qwerasdfgzxcv]$/i.test(key)) {
            aiHandleKeyboard(key);
            return;
        }

        if (key === "Enter") {
            if (document.getElementById("ai-end-modal-mask").classList.contains("show")) {
                aiCloseEndModal();
                aiResetCurrentGame(false);
                return;
            }
            if (aiSelectedMove && aiLatestState && aiLatestState.winner === null && !aiThinking) {
                aiStepGame();
            }
            return;
        }

        if (key === "Backspace") {
            event.preventDefault();
            if (document.getElementById("ai-end-modal-mask").classList.contains("show")) {
                aiCloseEndModal();
                return;
            }
            if (aiSelectedMove) {
                aiSelectedMove = null;
                aiRenderState(aiLatestState);
                aiSetText("ai-message", "已取消选择。");
            }
            return;
        }

        if (key === "Escape") {
            aiCloseEndModal();
            aiCloseSettingsModal();
        }
    });

    var diffBtns = document.querySelectorAll(".ai-diff-btn");
    for (var i = 0; i < diffBtns.length; i++) {
        diffBtns[i].addEventListener("click", function() {
            aiSetDifficulty(this.getAttribute("data-diff"));
        });
    }

    var seatBtns = document.querySelectorAll(".ai-seat-btn");
    for (var si = 0; si < seatBtns.length; si++) {
        seatBtns[si].addEventListener("click", function() {
            aiSetHumanSeat(this.getAttribute("data-seat"));
        });
    }

    document.getElementById("ai-start-btn").addEventListener("click", aiStartBattle);
    document.getElementById("ai-settings-btn").addEventListener("click", aiOpenSettingsModal);
    document.getElementById("ai-help-btn").addEventListener("click", function() {
        if (typeof ModalUtils !== "undefined" && ModalUtils.showInfoModal) {
            ModalUtils.showInfoModal({
                title: "AI 对战帮助",
                body: "进入页选择座位和难度。困难模式会先检查模型部署状态；模型不可用时自动降级。对战页默认只显示核心信息，更多内容可在设置中打开。",
                buttonText: "知道了"
            });
        }
    });
    document.getElementById("ai-step-btn").addEventListener("click", aiStepGame);
    document.getElementById("ai-reset-btn").addEventListener("click", function() {
        if (aiLatestState && aiLatestState.winner === null && aiLatestState.round_num > 0) {
            if (typeof ModalUtils !== "undefined" && ModalUtils.showConfirmModal) {
                ModalUtils.showConfirmModal({
                    title: "退出本局",
                    body: "当前对局尚未结束，确定要退出并返回进入页吗？",
                    confirmText: "退出本局",
                    cancelText: "取消",
                    onConfirm: function() { aiResetCurrentGame(true); }
                });
            } else {
                aiResetCurrentGame(true);
            }
        } else {
            aiResetCurrentGame(true);
        }
    });
    document.getElementById("ai-refresh-btn").addEventListener("click", aiFetchState);
    document.getElementById("ai-clear-btn").addEventListener("click", function() {
        aiSelectedMove = null;
        if (aiLatestState) aiRenderState(aiLatestState);
        aiSetText("ai-message", "已清空选择。");
    });

    document.getElementById("ai-end-close-btn").addEventListener("click", aiCloseEndModal);
    document.getElementById("ai-end-reset-btn").addEventListener("click", async function() {
        aiCloseEndModal();
        await aiResetCurrentGame(false);
    });
    document.getElementById("ai-end-modal-mask").addEventListener("click", function(event) {
        if (event.target.id === "ai-end-modal-mask") aiCloseEndModal();
    });

    document.getElementById("ai-settings-close-btn").addEventListener("click", aiCloseSettingsModal);
    document.getElementById("ai-settings-modal-mask").addEventListener("click", function(event) {
        if (event.target.id === "ai-settings-modal-mask") aiCloseSettingsModal();
    });
    var toggles = document.querySelectorAll(".ai-setting-toggle");
    for (var ti = 0; ti < toggles.length; ti++) {
        toggles[ti].addEventListener("change", function() {
            var key = this.getAttribute("data-setting");
            aiUiSettings[key] = !!this.checked;
            aiApplyUiSettings();
        });
    }

    aiSetDifficulty("normal");
    aiSetHumanSeat("p1");
    aiSyncSettingInputs();
    aiShowEntryPage();
}

if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
    window.location.href = "/v1/login?expired=1";
} else {
    aiInitPage();
}
