function loadSettings() {
    try {
        const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
        if (!raw) {
            settings = { ...defaultSettings };
            return;
        }

        const parsed = JSON.parse(raw);
        settings = {
            ...defaultSettings,
            ...parsed
        };
    } catch (error) {
        settings = { ...defaultSettings };
    }
}

function saveSettings() {
    localStorage.setItem(
        SETTINGS_STORAGE_KEY,
        JSON.stringify(settings)
    );
}

function applyCompactMode() {
    if (settings.compactMode) {
        document.body.classList.add("compact-mode");
    } else {
        document.body.classList.remove("compact-mode");
    }
}

function renderState(state) {
    latestState = state;

    const catalog = state.move_catalog || [];
    const logs = state.history || [];

    updateTurnTips();

    document.getElementById("basic-info").innerHTML = `
        <span class="status-badge">回合：${state.round_num}</span>
        <span class="winner-badge">胜负：${winnerText(state.winner)}</span>
        <span class="turn-badge">当前输入：${keyboardTarget === "p1" ? "P1" : "P2"}</span>
    `;

    document.getElementById("p1-state").innerHTML = renderPlayerState(state.p1);
    document.getElementById("p2-state").innerHTML = renderPlayerState(state.p2);

    renderMoveGroups(
        "p1-move-groups",
        state.legal_moves?.p1 || [],
        catalog,
        selectedP1Move,
        (moveName) => {
            selectedP1Move = moveName;
            if (!selectedP2Move) keyboardTarget = "p2";
            renderState(latestState);
        },
        "p1"
    );

    renderMoveGroups(
        "p2-move-groups",
        state.legal_moves?.p2 || [],
        catalog,
        selectedP2Move,
        (moveName) => {
            selectedP2Move = moveName;
            renderState(latestState);
        },
        "p2"
    );

    updateSelectionBoxes(catalog);
    updateTurnTips();

    document.getElementById("latest-round").innerHTML =
        renderLatestRound(logs.length > 0 ? logs[logs.length - 1] : null);

    renderHistory(logs);
    applySettingsVisibility();

    const stepBtn = document.getElementById("step-btn");
    if (state.winner === null) {
        stepBtn.disabled = false;
        stepBtn.textContent = "提交本回合";
    } else {
        stepBtn.disabled = true;
        stepBtn.textContent = "游戏已结束";
    }

    maybeShowEndModal(state);
}

async function fetchState() {
    const result = await ApiUtils.apiGet("/v1/api/local/state");
    if (!result.ok) {
        document.getElementById("message").textContent =
            "获取状态失败：" + result.error;
        return;
    }
    renderState(result.data);
    document.getElementById("message").textContent = "状态已刷新。";
}

async function resetGame() {
    const result = await ApiUtils.apiPost("/v1/api/local/reset");

    if (!result.ok) {
        document.getElementById("message").textContent =
            "重置失败：" + result.error;
        return;
    }

    selectedP1Move = null;
    selectedP2Move = null;
    keyboardTarget = "p1";
    endModalShownForWinner = null;
    closeEndModal();

    renderState(result.data.state);
    document.getElementById("message").textContent =
        result.data.message || "游戏已重置。";
}

async function stepGame() {
    if (!selectedP1Move || !selectedP2Move) {
        document.getElementById("message").textContent =
            "请先为 P1 和 P2 都选择动作。";
        return;
    }

    const result = await ApiUtils.apiPost("/v1/api/local/step", {
        p1_move: selectedP1Move,
        p2_move: selectedP2Move
    });

    if (!result.ok) {
        document.getElementById("message").textContent =
            result.error || "提交失败。";
        return;
    }

    selectedP1Move = null;
    selectedP2Move = null;
    keyboardTarget = "p1";

    renderState(result.data.state);
    document.getElementById("message").textContent =
        result.data.message || "本回合已结算。";
}

function undoLastSelection() {
    if (selectedP2Move) {
        selectedP2Move = null;
        keyboardTarget = "p2";
        if (latestState) {
            renderState(latestState);
        }
        document.getElementById("message").textContent = "已撤销 P2 的选择。";
        return;
    }

    if (selectedP1Move) {
        selectedP1Move = null;
        keyboardTarget = "p1";
        if (latestState) {
            renderState(latestState);
        }
        document.getElementById("message").textContent = "已撤销 P1 的选择。";
    }
}

function clearSelection() {
    selectedP1Move = null;
    selectedP2Move = null;
    keyboardTarget = "p1";
    if (latestState) {
        renderState(latestState);
    }
    document.getElementById("message").textContent = "本回合选择已清空。";
}

function openHelp() {
    document.getElementById("help-modal-mask").classList.add("show");
}

function closeHelp() {
    document.getElementById("help-modal-mask").classList.remove("show");
}

function openSettings() {
    syncSettingsUI();
    document.getElementById("settings-modal-mask").classList.add("show");
}

function closeSettings() {
    document.getElementById("settings-modal-mask").classList.remove("show");
}

function syncSettingsUI() {
    document.getElementById("setting-compact-mode").checked = settings.compactMode;
    document.getElementById("setting-show-tooltips").checked = settings.showTooltips;
    document.getElementById("setting-show-history").checked = settings.showHistory;
    document.getElementById("setting-show-latest-round").checked = settings.showLatestRound;
    document.getElementById("setting-colored-resources").checked = settings.coloredResources;
    document.getElementById("setting-emphasize-latest-round").checked = settings.emphasizeLatestRound;
}

function applySettingAndRerender(key, value) {
    settings[key] = value;
    saveSettings();
    if (latestState) {
        renderState(latestState);
    } else {
        applySettingsVisibility();
    }
}

function bindSettings() {
    document.getElementById("setting-compact-mode").addEventListener("change", (event) => {
        applySettingAndRerender("compactMode", event.target.checked);
    });

    document.getElementById("setting-show-tooltips").addEventListener("change", (event) => {
        applySettingAndRerender("showTooltips", event.target.checked);
    });

    document.getElementById("setting-show-history").addEventListener("change", (event) => {
        applySettingAndRerender("showHistory", event.target.checked);
    });

    document.getElementById("setting-show-latest-round").addEventListener("change", (event) => {
        applySettingAndRerender("showLatestRound", event.target.checked);
    });

    document.getElementById("setting-colored-resources").addEventListener("change", (event) => {
        applySettingAndRerender("coloredResources", event.target.checked);
    });

    document.getElementById("setting-emphasize-latest-round").addEventListener("change", (event) => {
        applySettingAndRerender("emphasizeLatestRound", event.target.checked);
    });
}

function initLocalPage() {
    document.addEventListener("keydown", (event) => {
        if (event.target && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) {
            return;
        }

        const key = event.key;

        if (/^[1-4]$/.test(key) || /^[qwerasdfgzxcv]$/i.test(key)) {
            event.preventDefault();
            handleKeyboardMoveSelection(key);
            return;
        }

        if (key === "Enter") {
            if (document.getElementById("end-modal-mask").classList.contains("show")) {
                closeEndModal();
                resetGame();
                return;
            }

            if (selectedP1Move && selectedP2Move && latestState && latestState.winner === null) {
                stepGame();
            }
            return;
        }

        if (key === "Backspace") {
            event.preventDefault();

            if (document.getElementById("help-modal-mask").classList.contains("show") ||
                document.getElementById("settings-modal-mask").classList.contains("show") ||
                document.getElementById("end-modal-mask").classList.contains("show")) {
                closeHelp();
                closeSettings();
                closeEndModal();
                return;
            }

            undoLastSelection();
            return;
        }

        if (key === "Escape") {
            closeHelp();
            closeSettings();
            closeEndModal();
        }
    });

    document.getElementById("refresh-btn").addEventListener("click", fetchState);
    document.getElementById("reset-btn").addEventListener("click", resetGame);
    document.getElementById("step-btn").addEventListener("click", stepGame);
    document.getElementById("clear-selection-btn").addEventListener("click", clearSelection);

    document.getElementById("help-open-btn").addEventListener("click", openHelp);
    document.getElementById("help-close-btn").addEventListener("click", closeHelp);

    document.getElementById("settings-open-btn").addEventListener("click", openSettings);
    document.getElementById("settings-close-btn").addEventListener("click", closeSettings);

    document.getElementById("end-close-btn").addEventListener("click", closeEndModal);
    document.getElementById("end-reset-btn").addEventListener("click", async () => {
        closeEndModal();
        await resetGame();
    });

    document.getElementById("help-modal-mask").addEventListener("click", (event) => {
        if (event.target.id === "help-modal-mask") {
            closeHelp();
        }
    });

    document.getElementById("settings-modal-mask").addEventListener("click", (event) => {
        if (event.target.id === "settings-modal-mask") {
            closeSettings();
        }
    });

    document.getElementById("end-modal-mask").addEventListener("click", (event) => {
        if (event.target.id === "end-modal-mask") {
            closeEndModal();
        }
    });

    loadSettings();
    applyCompactMode();
    syncSettingsUI();
    bindSettings();
    fetchState();
}

if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
    window.location.href = "/v1/login";
} else {
    initLocalPage();
}
