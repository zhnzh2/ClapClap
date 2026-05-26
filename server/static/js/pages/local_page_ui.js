function winnerText(winner) {
    if (winner === null) return "未结束";
    if (winner === 0) return "双败 / 平局";
    if (winner === 1) return "P1 获胜";
    if (winner === 2) return "P2 获胜";
    return "未知";
}

function resourceThemeClass(key) {
    if (!settings.coloredResources) return "";
    if (key === "hp") return "theme-hp";
    if (key === "qi") return "theme-qi";
    if (key === "shield") return "theme-shield";
    if (key === "spark") return "theme-spark";
    if (key === "battery") return "theme-battery";
    if (key === "pickaxe") return "theme-pickaxe";
    if (key === "flash_used") return "theme-flash";
    return "";
}

function resourceItem(label, value, key) {
    return `
        <div class="resource-item ${resourceThemeClass(key)}">
            <div class="resource-label">${label}</div>
            <div class="resource-value">${value}</div>
        </div>
    `;
}

function renderPlayerState(player) {
    return `
        ${resourceItem("生命", player.hp, "hp")}
        ${resourceItem("气", player.qi, "qi")}
        ${resourceItem("盾", player.shield, "shield")}
        ${resourceItem("火种", player.spark, "spark")}
        ${resourceItem("电池", player.battery, "battery")}
        ${resourceItem("镐", player.pickaxe, "pickaxe")}
        ${resourceItem("闪次数", player.flash_used, "flash_used")}
    `;
}

function moveCategoryTitle(category) {
    if (category === "resource") return "资源";
    if (category === "attack_qi") return "气系攻击";
    if (category === "attack_shield") return "盾系攻击";
    if (category === "defense") return "防御";
    if (category === "trick") return "锦囊";
    return "其他";
}

function getMoveGroups(catalog) {
    const groups = {
        resource: [],
        attack_qi: [],
        attack_shield: [],
        defense: [],
        trick: []
    };

    for (const item of catalog) {
        if (item.name === "QI" || item.name === "SHIELD") {
            groups.resource.push(item);
        } else if (
            ["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"].includes(item.name)
        ) {
            groups.attack_qi.push(item);
        } else if (
            ["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"].includes(item.name)
        ) {
            groups.attack_shield.push(item);
        } else if (
            ["SHI_ZI", "BA_GUA"].includes(item.name)
        ) {
            groups.defense.push(item);
        } else {
            groups.trick.push(item);
        }
    }

    return groups;
}

function handleKeyboardMoveSelection(keyText) {
    if (!latestState || latestState.winner !== null) return;
    if (document.getElementById("help-modal-mask").classList.contains("show")) return;
    if (document.getElementById("settings-modal-mask").classList.contains("show")) return;
    if (document.getElementById("end-modal-mask").classList.contains("show")) return;

    const upperKey = keyText.toUpperCase();

    let matchedMove = null;
    for (const [moveName, hotkey] of Object.entries(fixedKeyMap)) {
        if (hotkey === upperKey) {
            matchedMove = moveName;
            break;
        }
    }

    if (!matchedMove) return;

    if (keyboardTarget === "p1") {
        const legal = latestState.legal_moves?.p1 || [];
        if (legal.includes(matchedMove)) {
            selectedP1Move = matchedMove;
            if (!selectedP2Move) {
                keyboardTarget = "p2";
            }
            renderState(latestState);
            document.getElementById("message").textContent =
                `已为 P1 选择 ${matchedMove}，现在请为 P2 选择。`;
        }
    } else {
        const legal = latestState.legal_moves?.p2 || [];
        if (legal.includes(matchedMove)) {
            selectedP2Move = matchedMove;
            renderState(latestState);
            document.getElementById("message").textContent =
                `已为 P2 选择 ${matchedMove}。可以提交本回合。`;
        }
    }
}

function renderMoveGroups(containerId, legalMoves, catalog, selectedMove, onSelect, targetSide) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    const groups = getMoveGroups(catalog);

    for (const [groupKey, items] of Object.entries(groups)) {
        if (items.length === 0) continue;

        const title = document.createElement("div");
        title.className = "move-group-title";
        title.textContent = moveCategoryTitle(groupKey);
        container.appendChild(title);

        const grid = document.createElement("div");
        grid.className = "move-grid";

        for (const item of items) {
            const wrap = document.createElement("div");
            wrap.className = "move-btn-wrap";

            const btn = document.createElement("button");
            btn.className = "move-btn";
            btn.type = "button";

            const legal = legalMoves.includes(item.name);
            if (!legal) {
                btn.classList.add("disabled");
            }
            if (selectedMove === item.name) {
                btn.classList.add("selected");
                btn.classList.add(targetSide === "p1" ? "p1-selected" : "p2-selected");
            }
            if (keyboardTarget === targetSide && legal) {
                btn.classList.add("keyboard-focus");
            }

            const hotkey = fixedKeyMap[item.name] || "";

            btn.innerHTML = `
                ${hotkey ? `<div class="move-hotkey">${hotkey}</div>` : ""}
                <div class="move-label">${item.label}</div>
                <div class="move-name">${item.name}</div>
            `;

            btn.addEventListener("click", () => {
                if (!legal) return;
                onSelect(item.name);
            });

            wrap.appendChild(btn);

            if (settings.showTooltips) {
                const tooltip = document.createElement("div");
                tooltip.className = "tooltip";
                tooltip.innerHTML = `
                    <div><strong>${item.label} (${item.name})</strong></div>
                    <div>类别：${moveCategoryTitle(groupKey)}</div>
                    <div>${moveDescriptions[item.name] || "暂无说明。"}</div>
                    ${hotkey ? `<div>快捷键：${hotkey}</div>` : ""}
                `;
                wrap.appendChild(tooltip);
            }

            grid.appendChild(wrap);
        }

        container.appendChild(grid);
    }
}

function updateSelectionBoxes(catalog) {
    function findLabel(moveName) {
        const item = catalog.find(x => x.name === moveName);
        if (!item) return moveName;
        return `${item.label} (${item.name})`;
    }

    document.getElementById("p1-selection-box").textContent =
        selectedP1Move ? `P1 当前选择：${findLabel(selectedP1Move)}` : "P1 当前未选择动作。";

    document.getElementById("p2-selection-box").textContent =
        selectedP2Move ? `P2 当前选择：${findLabel(selectedP2Move)}` : "P2 当前未选择动作。";
}

function updateTurnTips() {
    if (latestState && latestState.winner !== null) {
        document.getElementById("p1-turn-tip").textContent = "";
        document.getElementById("p2-turn-tip").textContent = "";
        return;
    }

    if (!selectedP1Move) {
        document.getElementById("p1-turn-tip").textContent = "正在输入";
        document.getElementById("p2-turn-tip").textContent = "";
        keyboardTarget = "p1";
    } else if (!selectedP2Move) {
        document.getElementById("p1-turn-tip").textContent = "";
        document.getElementById("p2-turn-tip").textContent = "正在输入";
        keyboardTarget = "p2";
    } else {
        document.getElementById("p1-turn-tip").textContent = "";
        document.getElementById("p2-turn-tip").textContent = "";
    }
}

function renderLatestRound(log) {
    if (!log) {
        return "<div class='muted'>当前还没有回合记录。</div>";
    }

    let finalResultLine = "";
    if (log.winner_after_round === 0) {
        finalResultLine = `<div><strong>本局结果：</strong><span class="danger-text">双败 / 平局</span></div>`;
    } else if (log.winner_after_round === 1) {
        finalResultLine = `<div><strong>本局结果：</strong><span class="good-text">P1 获胜</span></div>`;
    } else if (log.winner_after_round === 2) {
        finalResultLine = `<div><strong>本局结果：</strong><span class="good-text">P2 获胜</span></div>`;
    }

    return `
        <div class="round-box ${settings.emphasizeLatestRound ? "emphasized" : ""}">
            <div><strong>第 ${log.round_num} 回合</strong></div>
            <div>P1 动作：${log.p1_move_label} (${log.p1_move})</div>
            <div>P2 动作：${log.p2_move_label} (${log.p2_move})</div>
            <div>P1 受到伤害：<span class="${log.p1_damage_taken > 0 ? "danger-text" : "good-text"}">${log.p1_damage_taken}</span></div>
            <div>P2 受到伤害：<span class="${log.p2_damage_taken > 0 ? "danger-text" : "good-text"}">${log.p2_damage_taken}</span></div>
            <div>P1 说明：${log.p1_note || "无"}</div>
            <div>P2 说明：${log.p2_note || "无"}</div>
            <div><strong>总结：</strong>${log.summary}</div>
            ${finalResultLine}
        </div>
    `;
}

function renderHistory(logs) {
    const historyEl = document.getElementById("history");
    historyEl.innerHTML = "";

    if (!settings.showHistory) {
        historyEl.innerHTML = "<div class='muted'>历史记录已在设置中隐藏。</div>";
        return;
    }

    if (logs.length === 0) {
        historyEl.innerHTML = "<div class='muted'>当前还没有历史记录。</div>";
        return;
    }

    for (const log of logs.slice().reverse()) {
        const item = document.createElement("div");
        item.className = "history-item";
        item.innerHTML = `
            <div><strong>第 ${log.round_num} 回合</strong></div>
            <div>P1：${log.p1_move_label} (${log.p1_move}) | 合法：${log.p1_valid}</div>
            <div>P2：${log.p2_move_label} (${log.p2_move}) | 合法：${log.p2_valid}</div>
            <div>P1 伤害：${log.p1_damage_taken} | P2 伤害：${log.p2_damage_taken}</div>
            <div>P1 说明：${log.p1_note || "无"}</div>
            <div>P2 说明：${log.p2_note || "无"}</div>
            <div><strong>总结：</strong>${log.summary}</div>
        `;
        historyEl.appendChild(item);
    }
    historyEl.scrollTop = 0;
}

function applySettingsVisibility() {
    document.getElementById("latest-round-card").style.display =
        settings.showLatestRound ? "" : "none";

    document.getElementById("history-card").style.display =
        settings.showHistory ? "" : "none";

    applyCompactMode();
}

function maybeShowEndModal(state) {
    if (state.winner === null) {
        endModalShownForWinner = null;
        return;
    }

    if (endModalShownForWinner === state.winner) {
        return;
    }

    endModalShownForWinner = state.winner;
    document.getElementById("end-result-text").textContent = winnerText(state.winner);
    document.getElementById("end-result-detail").textContent =
        `最终回合数：${state.round_num}`;
    document.getElementById("end-modal-mask").classList.add("show");
}

function closeEndModal() {
    document.getElementById("end-modal-mask").classList.remove("show");
}

