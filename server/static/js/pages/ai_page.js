/**
 * ClapClap 1.0 AI 对战页面。
 *
 * 真人固定 P1，AI 固定 P2。
 * 复用 core/api.js、core/session.js、core/logout_button.js、core/modal.js。
 */

// =========================================================================
// 全局状态
// =========================================================================

var aiLatestState = null;
var aiSelectedMove = null;
var aiDifficulty = "normal";
var aiThinking = false;
var aiEndModalShownForWinner = null;
var aiLastMoveLabel = null;
var aiLastMoveName = null;

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

// 快捷键映射（仅 P1 使用）
var aiFixedKeyMap = {
    CHI: "1", SHUANG_CHI: "2", SHAN: "3", GAO: "4",
    QI: "Q", SHIELD: "W", SHI_ZI: "E", BA_GUA: "R",
    GI: "A", PO: "S", LENG_FENG: "D", RU_LAI: "F", HEI_DONG: "G",
    FIRE: "Z", SHAN_DIAN: "X", LIE_YAN: "C", SHINING: "V"
};

// =========================================================================
// 渲染函数
// =========================================================================

function aiWinnerText(winner) {
    if (winner === null) return "未结束";
    if (winner === 0) return "双败 / 平局";
    if (winner === 1) return "你获胜了！";
    if (winner === 2) return "AI 获胜";
    return "未知";
}

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
        aiResourceItem("闪次数", player.flash_used)
    );
}

function aiMoveCategoryTitle(category) {
    if (category === "resource") return "资源";
    if (category === "attack_qi") return "气系攻击";
    if (category === "attack_shield") return "盾系攻击";
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
        } else if (
            ["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"].indexOf(item.name) !== -1
        ) {
            groups.attack_qi.push(item);
        } else if (
            ["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"].indexOf(item.name) !== -1
        ) {
            groups.attack_shield.push(item);
        } else if (
            ["SHI_ZI", "BA_GUA"].indexOf(item.name) !== -1
        ) {
            groups.defense.push(item);
        } else {
            groups.trick.push(item);
        }
    }
    return groups;
}

function aiRenderMoveButtons(containerId, legalMoves, catalog, selectedMove, onSelect) {
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

            var legal = legalMoves.indexOf(item.name) !== -1;
            if (!legal) {
                btn.classList.add("disabled");
            }
            if (selectedMove === item.name) {
                btn.classList.add("selected");
            }

            var hotkey = aiFixedKeyMap[item.name] || "";

            btn.innerHTML =
                (hotkey ? '<div class="move-hotkey">' + hotkey + '</div>' : "") +
                '<div class="move-label">' + item.label + '</div>' +
                '<div class="move-name">' + item.name + '</div>';

            btn.addEventListener("click", (function(moveName) {
                return function() {
                    if (!legal) return;
                    onSelect(moveName);
                };
            })(item.name));

            wrap.appendChild(btn);
            grid.appendChild(wrap);
        }

        container.appendChild(grid);
    }
}

function aiRenderLatestRound(log) {
    if (!log) {
        return "<div class='muted'>当前还没有回合记录。</div>";
    }

    var resultLine = "";
    if (log.winner_after_round === 0) {
        resultLine = "<div><strong>本局结果：</strong><span class='danger-text'>双败 / 平局</span></div>";
    } else if (log.winner_after_round === 1) {
        resultLine = "<div><strong>本局结果：</strong><span class='good-text'>你获胜了！</span></div>";
    } else if (log.winner_after_round === 2) {
        resultLine = "<div><strong>本局结果：</strong><span class='good-text'>AI 获胜</span></div>";
    }

    return (
        '<div class="round-box">' +
        '<div><strong>第 ' + log.round_num + ' 回合</strong></div>' +
        '<div>你的动作：' + log.p1_move_label + ' (' + log.p1_move + ')</div>' +
        '<div>AI 动作：' + log.p2_move_label + ' (' + log.p2_move + ')</div>' +
        '<div>你受到伤害：<span class="' + (log.p1_damage_taken > 0 ? "danger-text" : "good-text") + '">' + log.p1_damage_taken + '</span></div>' +
        '<div>AI 受到伤害：<span class="' + (log.p2_damage_taken > 0 ? "danger-text" : "good-text") + '">' + log.p2_damage_taken + '</span></div>' +
        '<div>你的说明：' + (log.p1_note || "无") + '</div>' +
        '<div>AI 说明：' + (log.p2_note || "无") + '</div>' +
        '<div><strong>总结：</strong>' + log.summary + '</div>' +
        resultLine +
        '</div>'
    );
}

function aiRenderHistory(logs) {
    var historyEl = document.getElementById("ai-history");
    historyEl.innerHTML = "";

    if (logs.length === 0) {
        historyEl.innerHTML = "<div class='muted'>当前还没有历史记录。</div>";
        return;
    }

    for (var i = logs.length - 1; i >= 0; i--) {
        var log = logs[i];
        var item = document.createElement("div");
        item.className = "history-item";
        item.innerHTML =
            '<div><strong>第 ' + log.round_num + ' 回合</strong></div>' +
            '<div>你：' + log.p1_move_label + ' (' + log.p1_move + ') | AI：' + log.p2_move_label + ' (' + log.p2_move + ')</div>' +
            '<div>你受伤：' + log.p1_damage_taken + ' | AI 受伤：' + log.p2_damage_taken + '</div>' +
            '<div>你的说明：' + (log.p1_note || "无") + '</div>' +
            '<div>AI 说明：' + (log.p2_note || "无") + '</div>' +
            '<div><strong>总结：</strong>' + log.summary + '</div>';
        historyEl.appendChild(item);
    }
    historyEl.scrollTop = 0;
}

// =========================================================================
// 状态渲染总入口
// =========================================================================

function aiRenderState(state) {
    aiLatestState = state;
    window._aiBattleId = state.battle_id || window._aiBattleId || null;

    var catalog = state.move_catalog || [];
    var logs = state.history || [];

    // 基本信息
    document.getElementById("ai-basic-info").innerHTML =
        '<span class="status-badge">回合：' + state.round_num + '</span>' +
        '<span class="winner-badge">胜负：' + aiWinnerText(state.winner) + '</span>' +
        '<span class="status-badge">难度：' + aiDifficultyLabel(aiDifficulty) + '</span>';

    // 双方资源
    document.getElementById("ai-p1-state").innerHTML = aiRenderPlayerState(state.p1);
    document.getElementById("ai-p2-state").innerHTML = aiRenderPlayerState(state.p2);

    // P1 动作按钮
    var legal = state.legal_moves ? (state.legal_moves.p1 || []) : [];
    aiRenderMoveButtons("ai-p1-move-groups", legal, catalog, aiSelectedMove, function(moveName) {
        aiSelectedMove = moveName;
        aiRenderState(aiLatestState);
        document.getElementById("ai-message").textContent =
            "已选择 " + moveName + "，点击「出招」提交。";
    });

    // AI 侧信息
    var aiMoveBox = document.getElementById("ai-move-box");
    if (aiThinking) {
        aiMoveBox.innerHTML = "<div class='muted'>AI 正在思考中...</div>";
    } else if (aiLastMoveName && aiLastMoveLabel) {
        aiMoveBox.innerHTML =
            '<div><strong>AI 本回合出了：</strong></div>' +
            '<div class="good-text">' + aiLastMoveLabel + ' (' + aiLastMoveName + ')</div>';
    } else if (state.winner === null && logs.length > 0) {
        var lastLog = logs[logs.length - 1];
        aiMoveBox.innerHTML =
            '<div><strong>AI 上一回合出了：</strong></div>' +
            '<div class="good-text">' + lastLog.p2_move_label + ' (' + lastLog.p2_move + ')</div>';
    } else if (state.winner !== null) {
        aiMoveBox.innerHTML = "<div class='muted'>游戏已结束。</div>";
    } else {
        aiMoveBox.innerHTML = "<div class='muted'>等待你出招...</div>";
    }

    // 最近一回合
    document.getElementById("ai-latest-round").innerHTML =
        aiRenderLatestRound(logs.length > 0 ? logs[logs.length - 1] : null);

    // 历史
    aiRenderHistory(logs);

    // 提交按钮状态
    var stepBtn = document.getElementById("ai-step-btn");
    if (state.winner !== null) {
        stepBtn.disabled = true;
        stepBtn.textContent = "游戏已结束";
    } else if (aiThinking) {
        stepBtn.disabled = true;
        stepBtn.textContent = "AI 思考中...";
    } else {
        stepBtn.disabled = false;
        stepBtn.textContent = "出招";
    }

    aiMaybeShowEndModal(state);
}

function aiMaybeShowEndModal(state) {
    if (state.winner === null) {
        aiEndModalShownForWinner = null;
        return;
    }
    if (aiEndModalShownForWinner === state.winner) return;

    aiEndModalShownForWinner = state.winner;
    document.getElementById("ai-end-result-text").textContent = aiWinnerText(state.winner);

    var detail = "最终回合数：" + state.round_num + " | 难度：" + aiDifficulty;
    // 如果有 battle_id，显示查看入口
    var battleId = state.battle_id || window._aiBattleId;
    if (battleId) {
        detail +=
            ' | <a href="/v1/record/' + battleId + '" target="_blank">查看对局记录</a>';
    }
    document.getElementById("ai-end-result-detail").innerHTML = detail;
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
        document.getElementById("ai-message").textContent =
            "获取状态失败：" + result.error;
        return;
    }
    aiRenderState(result.data);
    document.getElementById("ai-message").textContent = "状态已刷新。";
}

async function aiResetGame() {
    var result = await ApiUtils.apiPost("/v1/api/ai/reset");
    if (!result.ok) {
        document.getElementById("ai-message").textContent =
            "重置失败：" + result.error;
        return;
    }

    aiSelectedMove = null;
    aiThinking = false;
    aiEndModalShownForWinner = null;
    aiLastMoveLabel = null;
    aiLastMoveName = null;
    window._aiBattleId = null;
    aiCloseEndModal();

    aiRenderState(result.data.state);
    document.getElementById("ai-message").textContent =
        result.data.message || "AI 对战已重置。";
    document.getElementById("ai-move-box").innerHTML =
        "<div class='muted'>等待你出招...</div>";
}

async function aiStepGame() {
    if (!aiSelectedMove) {
        document.getElementById("ai-message").textContent =
            "请先选择你的动作。";
        return;
    }

    if (aiThinking) return;

    aiThinking = true;
    aiRenderState(aiLatestState); // 更新按钮为"思考中"
    document.getElementById("ai-message").textContent = "AI 正在思考...";

    var result = await ApiUtils.apiPost("/v1/api/ai/step", {
        human_move: aiSelectedMove,
        difficulty: aiDifficulty,
        human_seat: "p1"
    });

    aiThinking = false;

    if (!result.ok) {
        document.getElementById("ai-message").textContent =
            result.error || "提交失败。";
        aiRenderState(aiLatestState);
        return;
    }

    // 更新 AI 侧信息
    var aiMove = result.data.ai_move;
    var aiMoveLabel = result.data.ai_move_label;
    aiLastMoveName = aiMove;
    aiLastMoveLabel = aiMoveLabel;
    window._aiBattleId = result.data.battle_id || (result.data.state && result.data.state.battle_id) || window._aiBattleId;
    document.getElementById("ai-move-box").innerHTML =
        '<div><strong>AI 本回合出了：</strong></div>' +
        '<div class="good-text">' + aiMoveLabel + ' (' + aiMove + ')</div>';

    // 清除选择，渲染新状态
    aiSelectedMove = null;
    aiRenderState(result.data.state);

    document.getElementById("ai-message").textContent =
        result.data.message || "本回合已结算。";
}

// =========================================================================
// 难度选择
// =========================================================================

function aiSetDifficulty(diff) {
    aiDifficulty = diff;
    // 更新按钮状态
    var btns = document.querySelectorAll(".ai-diff-btn");
    for (var i = 0; i < btns.length; i++) {
        if (btns[i].getAttribute("data-diff") === diff) {
            btns[i].classList.add("active");
        } else {
            btns[i].classList.remove("active");
        }
    }
}

function aiDifficultyLabel(diff) {
    if (diff === "easy") return "简单";
    if (diff === "hard") return "困难";
    return "普通";
}

// =========================================================================
// 键盘操作
// =========================================================================

function aiHandleKeyboard(keyText) {
    if (!aiLatestState || aiLatestState.winner !== null) return;
    if (aiThinking) return;

    // 检查弹窗
    var endModal = document.getElementById("ai-end-modal-mask");
    if (endModal && endModal.classList.contains("show")) return;

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

    var legal = aiLatestState.legal_moves ? (aiLatestState.legal_moves.p1 || []) : [];
    if (legal.indexOf(matchedMove) !== -1) {
        aiSelectedMove = matchedMove;
        aiRenderState(aiLatestState);
        document.getElementById("ai-message").textContent =
            "已选择 " + matchedMove + "，点击「出招」或按 Enter 提交。";
    }
}

// =========================================================================
// 初始化
// =========================================================================

function aiInitPage() {
    // 键盘事件
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
                aiResetGame();
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
                document.getElementById("ai-message").textContent = "已取消选择。";
            }
            return;
        }

        if (key === "Escape") {
            aiCloseEndModal();
        }
    });

    // 难度按钮
    var diffBtns = document.querySelectorAll(".ai-diff-btn");
    for (var i = 0; i < diffBtns.length; i++) {
        diffBtns[i].addEventListener("click", function() {
            aiSetDifficulty(this.getAttribute("data-diff"));
        });
    }

    // 操作按钮
    document.getElementById("ai-step-btn").addEventListener("click", aiStepGame);
    document.getElementById("ai-reset-btn").addEventListener("click", function() {
        if (aiLatestState && aiLatestState.winner === null && aiLatestState.round_num > 0) {
            // 有进行中的对局，确认后重置
            if (typeof ModalUtils !== "undefined" && ModalUtils.confirm) {
                ModalUtils.confirm(
                    "确认重置",
                    "当前对局尚未结束，确定要重新开始吗？",
                    function() { aiResetGame(); }
                );
            } else {
                aiResetGame();
            }
        } else {
            aiResetGame();
        }
    });
    document.getElementById("ai-refresh-btn").addEventListener("click", aiFetchState);
    document.getElementById("ai-clear-btn").addEventListener("click", function() {
        aiSelectedMove = null;
        if (aiLatestState) aiRenderState(aiLatestState);
        document.getElementById("ai-message").textContent = "已清空选择。";
    });

    // 结束弹窗
    document.getElementById("ai-end-close-btn").addEventListener("click", aiCloseEndModal);
    document.getElementById("ai-end-reset-btn").addEventListener("click", async function() {
        aiCloseEndModal();
        await aiResetGame();
    });
    document.getElementById("ai-end-modal-mask").addEventListener("click", function(event) {
        if (event.target.id === "ai-end-modal-mask") aiCloseEndModal();
    });

    // 初始加载
    aiSetDifficulty("normal");
    aiFetchState();
}

// 入口
if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
    window.location.href = "/v1/login?expired=1";
} else {
    aiInitPage();
}
