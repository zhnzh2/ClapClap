(() => {
    const roomId = window.CLAPCLAP_ROOM_ID || "";

    if (!roomId) {
        console.error("room_detail.js: 缺少房间号 CLAPCLAP_ROOM_ID");
        return;
    }

    function loadRoomIdentity(roomId) {
        const raw = localStorage.getItem(`clapclap_room_${roomId}`);
        if (!raw) {
            return {
                player_token: "",
                seat: null
            };
        }

        try {
            const parsed = JSON.parse(raw);
            return {
                player_token: parsed.player_token || "",
                seat: parsed.seat || null
            };
        } catch (error) {
            console.error("loadRoomIdentity error:", error);
            return {
                player_token: "",
                seat: null
            };
        }
    }

    const roomIdentity = loadRoomIdentity(roomId);
    let mySeat = roomIdentity.seat;
    let myPlayerToken = roomIdentity.player_token;

        console.log("roomId =", roomId);
        console.log("mySeat =", mySeat);
        console.log("myPlayerToken =", myPlayerToken);

        if (!myPlayerToken) {
            console.warn("当前没有找到本地房间身份，后续将按观战/未知身份处理。");
        }

        let currentSelectedMoveName = null;
        let currentSelectedSeat = null;
        let lastRenderedRoundCount = -1;

        if (typeof io !== "function") {
            console.error("room_detail.js: Socket.IO 未加载成功");
            return;
        }

        const socket = io();

        const DEFAULT_ROOM_UI_SETTINGS = {
            showRoomInfo: true,
            showRoomStatus: false,
            showInvite: false,
            showRoundResult: false,
            playerStateMode: "compact"
        };

        let roomUiSettings = { ...DEFAULT_ROOM_UI_SETTINGS };

        socket.on("connect", () => {
            socket.emit("join_room", { room_id: roomId });
        });

        socket.on("room_state", (data) => {
            if (!data || !data.ok) {
                return;
            }

            renderRoom(data.room);
            setRoomMessage("房间状态已实时同步。", "info");
        });

        socket.on("room_error", (data) => {
            setRoomMessage(data?.error || "房间实时连接出错。", "error");
        });

        const moveGroups = {
            resource: ["QI", "SHIELD"],
            attack_qi: ["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"],
            attack_shield: ["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"],
            defense: ["SHI_ZI", "BA_GUA"],
            trick: ["CHI", "SHUANG_CHI", "SHAN", "GAO"]
        };

        function seatDisplayText(seat) {
            if (seat === "p1") return "P1";
            if (seat === "p2") return "P2";
            return "观战 / 未知";
        }

        function roomStatusText(status) {
            if (status === "waiting") return "等待中";
            if (status === "playing") return "对战中";
            if (status === "finished") return "已结束";
            return status || "未知";
        }

        function getInviteLink() {
            return `${window.location.origin}/room/${roomId}`;
        }

        function getSeatLabel(seat) {
            if (seat === "p1") return "P1";
            if (seat === "p2") return "P2";
            return "观战";
        }

        function getOpponentSeat() {
            if (mySeat === "p1") return "p2";
            if (mySeat === "p2") return "p1";
            return null;
        }

        function isSpectatorMode() {
            return mySeat !== "p1" && mySeat !== "p2";
        }

        const MOVE_SHORTCUTS = {
            "qi": "1",
            "shield": "2",
            "spark": "3",
            "battery": "4",
            "pickaxe": "Q",
            "flash": "W",
            "blackhole": "E",
            "gi": "A",
            "cannon": "S",
            "crossbow": "D",
            "eight_trigrams": "F"
        };

        const KEY_TO_MOVE_NAME = {
            "1": "qi",
            "2": "shield",
            "3": "spark",
            "4": "battery",
            "q": "pickaxe",
            "w": "flash",
            "e": "blackhole",
            "a": "gi",
            "s": "cannon",
            "d": "crossbow",
            "f": "eight_trigrams"
        };

        function normalizeMoveName(moveName) {
            return String(moveName || "").trim().toLowerCase();
        }

        function getRoomSettingsStorageKey() {
            return `clapclap_room_ui_settings_${roomId}`;
        }

        function loadRoomUiSettings() {
            try {
                const raw = localStorage.getItem(getRoomSettingsStorageKey());
                if (!raw) {
                    roomUiSettings = { ...DEFAULT_ROOM_UI_SETTINGS };
                    return;
                }

                const parsed = JSON.parse(raw);
                roomUiSettings = {
                    ...DEFAULT_ROOM_UI_SETTINGS,
                    ...parsed
                };
            } catch (error) {
                console.error("loadRoomUiSettings error:", error);
                roomUiSettings = { ...DEFAULT_ROOM_UI_SETTINGS };
            }
        }

        function saveRoomUiSettings() {
            localStorage.setItem(
                getRoomSettingsStorageKey(),
                JSON.stringify(roomUiSettings)
            );
        }

        function syncSettingsControls() {
            document.getElementById("toggle-room-info").checked = !!roomUiSettings.showRoomInfo;
            document.getElementById("toggle-room-status").checked = !!roomUiSettings.showRoomStatus;
            document.getElementById("toggle-invite-section").checked = !!roomUiSettings.showInvite;
            document.getElementById("toggle-round-result").checked = !!roomUiSettings.showRoundResult;
            document.getElementById("player-state-mode-select").value = roomUiSettings.playerStateMode || "compact";
        }

        function applyRoomUiSettings() {
            const roomInfoSection = document.getElementById("room-info-section");
            const roomStatusSection = document.getElementById("room-status-section");
            const inviteSection = document.getElementById("invite-section");
            const roundResultSection = document.getElementById("round-result-section");
            const playerStateModeFull = document.getElementById("player-state-mode-full");
            const playerStateModeCompact = document.getElementById("player-state-mode-compact");

            if (roomInfoSection) {
                roomInfoSection.style.display = roomUiSettings.showRoomInfo ? "" : "none";
            }

            if (roomStatusSection) {
                roomStatusSection.style.display = roomUiSettings.showRoomStatus ? "" : "none";
            }

            if (inviteSection) {
                inviteSection.style.display = roomUiSettings.showInvite ? "" : "none";
            }

            if (roundResultSection) {
                roundResultSection.style.display = roomUiSettings.showRoundResult ? "" : "none";
            }

            if (playerStateModeFull && playerStateModeCompact) {
                if (roomUiSettings.playerStateMode === "full") {
                    playerStateModeFull.style.display = "";
                    playerStateModeCompact.style.display = "none";
                } else {
                    playerStateModeFull.style.display = "none";
                    playerStateModeCompact.style.display = "";
                }
            }
        }

        function openSettingsModal() {
            document.getElementById("settings-mask").classList.add("show");
        }

        function closeSettingsModal() {
            document.getElementById("settings-mask").classList.remove("show");
        }

        function getMyPendingMove(room) {
            if (mySeat === "p1") return room.pending_p1_move;
            if (mySeat === "p2") return room.pending_p2_move;
            return null;
        }

        function getOpponentPendingMove(room) {
            if (mySeat === "p1") return room.pending_p2_move;
            if (mySeat === "p2") return room.pending_p1_move;
            return null;
        }

        function isMyActionLocked(room) {
            if (!room) return true;
            if (isSpectatorMode()) return true;
            if (room.status !== "playing") return true;
            return !!getMyPendingMove(room);
        }

        function phaseTextForSelf(room) {
            if (isSpectatorMode()) {
                return "当前为观战中";
            }

            if (room.status === "waiting") {
                if (!room.p1_name || !room.p2_name) {
                    return "等待另一位玩家进入";
                }
                return "已就绪，等待开始";
            }

            if (room.status === "finished") {
                return "本局已结束";
            }

            const myPending = mySeat === "p1" ? room.pending_p1_move : room.pending_p2_move;
            const opponentPending = mySeat === "p1" ? room.pending_p2_move : room.pending_p1_move;

            if (myPending && opponentPending) {
                return "正在结算";
            }

            if (myPending && !opponentPending) {
                return "已选择动作，等待对方";
            }

            if (!myPending && opponentPending) {
                return "正在等待你选择";
            }

            return "正在等待你选择";
        }

        function phaseTextForOpponent(room) {
            const opponentSeat = getOpponentSeat();

            if (isSpectatorMode()) {
                if (!room.p1_name && !room.p2_name) {
                    return "房间暂无玩家";
                }
                if (room.p1_name && room.p2_name) {
                    if (room.pending_p1_move && room.pending_p2_move) {
                        return "双方都已选择动作";
                    }
                    if (room.pending_p1_move || room.pending_p2_move) {
                        return "其中一方已选择动作";
                    }
                    return "双方正在等待选择";
                }
                return "等待另一位玩家进入";
            }

            if (!opponentSeat) {
                return "未知";
            }

            const opponentPending = opponentSeat === "p1" ? room.pending_p1_move : room.pending_p2_move;

            if (room.status === "waiting") {
                return room[`${opponentSeat}_name`] ? "对方已进入房间" : "对方尚未进入房间";
            }

            if (room.status === "finished") {
                return "本局已结束";
            }

            if (room.pending_p1_move && room.pending_p2_move) {
                return "对方已选择动作";
            }

            if (opponentPending) {
                return "对方已选择动作";
            }

            return "对方正在选择动作";
        }

        function roundPhaseText(room) {
            if (room.status === "waiting") {
                return "准备阶段";
            }

            if (room.status === "finished") {
                return "本回合已结束";
            }

            if (room.pending_p1_move && room.pending_p2_move) {
                return "正在结算";
            }

            if (room.pending_p1_move || room.pending_p2_move) {
                return "等待另一方选择";
            }

            return "等待双方选择";
        }

        function opponentOnlineText(room) {
            const onlineStatus = room.online_status || {};
            const opponentSeat = getOpponentSeat();

            if (isSpectatorMode()) {
                const p1Online = !!onlineStatus.p1_online;
                const p2Online = !!onlineStatus.p2_online;

                if (p1Online && p2Online) {
                    return "两位玩家在线";
                }
                if (p1Online || p2Online) {
                    return "仅有一位玩家在线";
                }

                const joinedCount = (room.p1_name ? 1 : 0) + (room.p2_name ? 1 : 0);
                if (joinedCount === 2) {
                    return "两位玩家均已进入，但当前离线";
                }
                if (joinedCount === 1) {
                    return "仅有一位玩家进入";
                }
                return "房间暂无玩家";
            }

            if (!opponentSeat) {
                return "未知";
            }

            const opponentJoined = !!room[`${opponentSeat}_name`];
            const opponentOnline = opponentSeat === "p1"
                ? !!onlineStatus.p1_online
                : !!onlineStatus.p2_online;

            if (!opponentJoined) {
                return "未进入房间";
            }

            if (opponentOnline) {
                return "在线";
            }

            return "离线";
        }

        function renderInvitePanel() {
            const inviteLink = getInviteLink();
            document.getElementById("invite-link-preview").textContent = inviteLink;
        }

        function renderStatusSummary(room) {
            document.getElementById("self-phase-text").textContent = phaseTextForSelf(room);
            document.getElementById("opponent-phase-text").textContent = phaseTextForOpponent(room);
            document.getElementById("round-phase-text").textContent = roundPhaseText(room);

            const opponentText = opponentOnlineText(room);
            const opponentOnlineEl = document.getElementById("opponent-online-text");

            if (opponentText === "在线" || opponentText.includes("两位玩家在线")) {
                opponentOnlineEl.innerHTML = `<span class="online-dot online"></span>${opponentText}`;
            } else if (opponentText === "离线" || opponentText.includes("离线")) {
                opponentOnlineEl.innerHTML = `<span class="online-dot offline"></span>${opponentText}`;
            } else {
                opponentOnlineEl.textContent = opponentText;
            }
        }

        function renderTurnAlert(room) {
            const el = document.getElementById("turn-alert");
            el.className = "turn-alert";
            el.textContent = "";

            if (room.status === "waiting") {
                el.classList.add("show", "waiting-opponent");
                el.textContent = "当前处于准备阶段，等待双方进入并开始。";
                return;
            }

            if (room.status === "finished") {
                el.classList.add("show", "resolving");
                el.textContent = "本局已结束，可以查看结果并选择是否再来一局。";
                return;
            }

            const myPending = getMyPendingMove(room);
            const opponentPending = getOpponentPendingMove(room);

            if (myPending && opponentPending) {
                el.classList.add("show", "resolving");
                el.textContent = "双方都已提交动作，正在结算本回合……";
                return;
            }

            if (myPending && !opponentPending) {
                el.classList.add("show", "waiting-opponent");
                el.textContent = "你已提交动作，正在等待对方选择。";
                return;
            }

            if (!myPending && opponentPending) {
                el.classList.add("show", "waiting-self");
                el.textContent = "对方已提交动作，现在轮到你选择。";
                return;
            }

            el.classList.add("show", "waiting-self");
            el.textContent = "请先选择你的本回合动作。";
        }

        function renderRoundResultBanner(room) {
            const banner = document.getElementById("round-result-section");
            const titleEl = document.getElementById("round-result-title");
            const bodyEl = document.getElementById("round-result-body");
            const chipsEl = document.getElementById("round-result-chips");

            if (!banner || !titleEl || !bodyEl || !chipsEl) {
                return;
            }

            chipsEl.innerHTML = "";

            const history = room.game?.history || [];
            if (!Array.isArray(history) || history.length === 0) {
                banner.classList.remove("show");
                return;
            }

            const lastLog = history[history.length - 1];
            const roundIndex = history.length;

            if (lastRenderedRoundCount === roundIndex && room.status !== "finished") {
                return;
            }

            banner.classList.add("show");
            lastRenderedRoundCount = roundIndex;

            titleEl.textContent = `本回合结果 · 第 ${roundIndex} 回合`;

            const p1Move = lastLog.p1_move_label || lastLog.p1_move || "未知";
            const p2Move = lastLog.p2_move_label || lastLog.p2_move || "未知";
            const summaryText = lastLog.summary || "本回合已完成结算。";

            bodyEl.textContent = `P1：${p1Move}　|　P2：${p2Move}　|　${summaryText}`;

            const chips = [
                `P1 动作：${p1Move}`,
                `P2 动作：${p2Move}`
            ];

            if (room.game?.winner === 1) {
                chips.push("当前胜者：P1");
            } else if (room.game?.winner === 2) {
                chips.push("当前胜者：P2");
            }

            chips.forEach((text) => {
                const chip = document.createElement("span");
                chip.className = "result-chip";
                chip.textContent = text;
                chipsEl.appendChild(chip);
            });
        }

        function renderFinishModal(room) {
            const mask = document.getElementById("game-finish-mask");
            const titleEl = document.getElementById("game-finish-title");
            const subtitleEl = document.getElementById("game-finish-subtitle");
            const chipRow = document.getElementById("game-finish-chip-row");

            chipRow.innerHTML = "";

            if (room.status !== "finished") {
                mask.classList.remove("show");
                return;
            }

            let finishTitle = "对局结束";
            if (room.game?.winner === 1) {
                finishTitle = mySeat === "p1" ? "你赢了" : "P1 获胜";
            } else if (room.game?.winner === 2) {
                finishTitle = mySeat === "p2" ? "你赢了" : "P2 获胜";
            }else {
                finishTitle = "对局结束";
            }

            titleEl.textContent = finishTitle;
            subtitleEl.textContent = "本局已经结束。你可以选择重新开始一局，或返回大厅。";

            const chipTexts = [
                `P1：${room.p1_name || "暂无"}`,
                `P2：${room.p2_name || "暂无"}`
            ];

            chipTexts.forEach((text) => {
                const chip = document.createElement("span");
                chip.className = "result-chip";
                chip.textContent = text;
                chipRow.appendChild(chip);
            });

            mask.classList.add("show");
        }

        function closeFinishModal() {
            document.getElementById("game-finish-mask").classList.remove("show");
        }

        function renderResetHint(room) {
            if (!room.reset_requested_by) {
                return;
            }

            if (isSpectatorMode()) {
                setRoomMessage(`${room.reset_requested_by.toUpperCase()} 已发起重置请求，等待另一方确认。`, "waiting");
                return;
            }

            if (room.reset_requested_by === mySeat) {
                setRoomMessage("你已发起重置请求，等待对方确认。", "waiting");
            } else {
                setRoomMessage("对方已发起重置请求；你再点击一次“重置对局”即可确认。", "waiting");
            }
        }

        function renderSpectatorBanner() {
            const banner = document.getElementById("spectator-banner");
            banner.style.display = isSpectatorMode() ? "" : "none";
        }

        function setSettlingMask(show) {
            const mask = document.getElementById("settling-mask");
            if (show) {
                mask.classList.add("show");
            } else {
                mask.classList.remove("show");
            }
        }

        function applyRoomStatusBadge(status) {
            const el = document.getElementById("room-status");
            el.textContent = roomStatusText(status);
            el.className = "status-badge";

            if (status === "waiting") {
                el.classList.add("status-waiting");
            } else if (status === "playing") {
                el.classList.add("status-playing");
            } else if (status === "finished") {
                el.classList.add("status-finished");
            }
        }

        function applySeatHighlights() {
            const p1NameBox = document.getElementById("p1-name-box");
            const p2NameBox = document.getElementById("p2-name-box");
            const p1PlayerBox = document.getElementById("p1-player-box");
            const p2PlayerBox = document.getElementById("p2-player-box");
            const p1RowFull = document.getElementById("p1-row-full");
            const p2RowFull = document.getElementById("p2-row-full");

            p1NameBox.classList.remove("seat-p1");
            p2NameBox.classList.remove("seat-p2");
            p1PlayerBox.classList.remove("active-seat", "active-seat-p1");
            p2PlayerBox.classList.remove("active-seat", "active-seat-p2");
            p1RowFull.classList.remove("seat-p1", "seat-p2");
            p2RowFull.classList.remove("seat-p1", "seat-p2");

            if (mySeat === "p1") {
                p1NameBox.classList.add("seat-p1");
                p1PlayerBox.classList.add("active-seat", "active-seat-p1");
                document.getElementById("p1-seat-note").textContent = "这是你当前操作的一侧。";
                document.getElementById("p2-seat-note").textContent = "这是对方当前状态。";
                p1RowFull.classList.add("seat-p1");
            } else if (mySeat === "p2") {
                p2NameBox.classList.add("seat-p2");
                p2PlayerBox.classList.add("active-seat", "active-seat-p2");
                document.getElementById("p1-seat-note").textContent = "这是对方当前状态。";
                document.getElementById("p2-seat-note").textContent = "这是你当前操作的一侧。";
                p2RowFull.classList.add("seat-p2");
            } else {
                document.getElementById("p1-seat-note").textContent = "当前为观战或未知身份。";
                document.getElementById("p2-seat-note").textContent = "当前为观战或未知身份。";
            }
        }

        function applyPendingHighlights(room) {
            const p1Box = document.getElementById("pending-p1-box");
            const p2Box = document.getElementById("pending-p2-box");

            p1Box.classList.remove("pending-ready-p1");
            p2Box.classList.remove("pending-ready-p2");

            if (room.pending_p1_move) {
                p1Box.classList.add("pending-ready-p1");
            }

            if (room.pending_p2_move) {
                p2Box.classList.add("pending-ready-p2");
            }
        }

        function applySeatVisibility() {
            const actionSection = document.getElementById("action-section");
            const resetBtn = document.getElementById("reset-room-btn");

            if (mySeat === "p1" || mySeat === "p2") {
                if (actionSection) {
                    actionSection.style.display = "";
                }
                if (resetBtn) {
                    resetBtn.disabled = false;
                }
                return;
            }

            if (actionSection) {
                actionSection.style.display = "none";
            }
            if (resetBtn) {
                resetBtn.disabled = true;
            }
        }

        function moveCategoryTitle(key) {
            if (key === "resource") return "资源";
            if (key === "attack_qi") return "气系攻击";
            if (key === "attack_shield") return "盾系攻击";
            if (key === "defense") return "防御";
            if (key === "trick") return "锦囊";
            return "其他";
        }

        function resourceItem(label, value) {
            return `
                <div class="resource-item">
                    <div class="resource-label">${label}</div>
                    <div class="resource-value">${value}</div>
                </div>
            `;
        }

        function renderPlayerState(player) {
            return `
                ${resourceItem("生命", player.hp)}
                ${resourceItem("气", player.qi)}
                ${resourceItem("盾", player.shield)}
                ${resourceItem("火种", player.spark)}
                ${resourceItem("电池", player.battery)}
                ${resourceItem("镐", player.pickaxe)}
                ${resourceItem("闪次数", player.flash_used)}
            `;
        }

        function renderPlayerStateFull(player) {
            return `
                ${resourceItem("生命", player.hp)}
                ${resourceItem("气", player.qi)}
                ${resourceItem("盾", player.shield)}
                ${resourceItem("火种", player.spark)}
                ${resourceItem("电池", player.battery)}
                ${resourceItem("镐", player.pickaxe)}
                ${resourceItem("闪次数", player.flash_used)}
            `;
        }

        function renderPlayerStateCompact(player) {
            return `
                ${resourceItem("生命", player.hp)}
                ${resourceItem("镐", player.pickaxe)}
                ${resourceItem("气", player.qi)}
                ${resourceItem("盾", player.shield)}
            `;
        }

        function bindSettingsEvents() {
            document.getElementById("toggle-room-info").addEventListener("change", (event) => {
                roomUiSettings.showRoomInfo = event.target.checked;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });

            document.getElementById("toggle-room-status").addEventListener("change", (event) => {
                roomUiSettings.showRoomStatus = event.target.checked;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });

            document.getElementById("toggle-invite-section").addEventListener("change", (event) => {
                roomUiSettings.showInvite = event.target.checked;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });

            document.getElementById("toggle-round-result").addEventListener("change", (event) => {
                roomUiSettings.showRoundResult = event.target.checked;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });

            document.getElementById("player-state-mode-select").addEventListener("change", (event) => {
                roomUiSettings.playerStateMode = event.target.value;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });
        }

        function moveLabel(moveName, catalog) {
            const item = catalog.find(x => x.name === moveName);
            return item ? item.label : moveName;
        }

        function renderMoveGroups(containerId, legalMoves, catalog, seat) {
            const container = document.getElementById(containerId);
            container.innerHTML = "";

            for (const [groupKey, moveNames] of Object.entries(moveGroups)) {
                const title = document.createElement("div");
                title.className = "move-group-title";
                title.textContent = moveCategoryTitle(groupKey);
                container.appendChild(title);

                const grid = document.createElement("div");
                grid.className = "move-grid";

                for (const moveName of moveNames) {
                    const btn = document.createElement("button");
                    btn.className = "move-btn";
                    btn.type = "button";

                    const legal = legalMoves.includes(moveName);
                    if (!legal) {
                        btn.classList.add("disabled");
                    }

                    btn.innerHTML = `
                        <div class="move-label">${moveLabel(moveName, catalog)}</div>
                        <div class="move-name">${moveName}</div>
                    `;

                    const normalizedMoveName = normalizeMoveName(moveName);
                    const shortcutKey = MOVE_SHORTCUTS[normalizedMoveName];

                    if (shortcutKey) {
                        const shortcutEl = document.createElement("div");
                        shortcutEl.className = "move-shortcut";
                        shortcutEl.textContent = shortcutKey;
                        btn.appendChild(shortcutEl);
                    }

                    const actionLocked = isMyActionLocked(latestRoom);
                    if (!legal || actionLocked) {
                        btn.classList.add("locked");
                    }

                    btn.dataset.moveName = normalizedMoveName;
                    btn.dataset.seat = seat;

                    btn.addEventListener("click", () => {
                        if (!legal) return;
                        if (isMyActionLocked(latestRoom)) return;
                        if (isSpectatorMode()) return;

                        container.querySelectorAll(".move-btn").forEach((node) => {
                            node.classList.remove("selected-p1", "selected-p2", "keyboard-focus");
                        });

                        currentSelectedMoveName = normalizedMoveName;
                        currentSelectedSeat = seat;

                        if (seat === "p1") {
                            btn.classList.add("selected-p1");
                        } else if (seat === "p2") {
                            btn.classList.add("selected-p2");
                        }

                        submitMove(seat, moveName);
                    });

                    grid.appendChild(btn);
                }

                container.appendChild(grid);
            }
        }

        function renderHistory(logs) {
            const historyEl = document.getElementById("history");
            historyEl.innerHTML = "";

            if (!logs || logs.length === 0) {
                historyEl.innerHTML = "<div class='muted'>当前还没有历史记录。</div>";
                return;
            }

            for (const log of logs.slice().reverse()) {
                const item = document.createElement("div");
                item.className = "history-item";
                item.innerHTML = `
                    <div><strong>第 ${log.round_num} 回合</strong></div>
                    <div>P1：${log.p1_move_label} (${log.p1_move})</div>
                    <div>P2：${log.p2_move_label} (${log.p2_move})</div>
                    <div>P1 伤害：${log.p1_damage_taken} | P2 伤害：${log.p2_damage_taken}</div>
                    <div><strong>总结：</strong>${log.summary}</div>
                `;
                historyEl.appendChild(item);
            }
        }

        async function copyTextWithFeedback(text, successText) {
            try {
                await navigator.clipboard.writeText(text);
                setRoomMessage(successText, "success");
            } catch (error) {
                setRoomMessage("复制失败，请手动复制。", "error");
            }
        }

        async function copyRoomId() {
            await copyTextWithFeedback(roomId, "房间号已复制。");
        }

        async function copyRoomLink() {
            await copyTextWithFeedback(getInviteLink(), "邀请链接已复制。");
        }

        function findMoveButtonByMoveName(moveName) {
            const normalized = normalizeMoveName(moveName);
            return document.querySelector(`.move-btn[data-move-name="${normalized}"]`);
        }

        function handleMoveKeyboardSelect(event) {
            if (isSpectatorMode()) return;
            if (!latestRoom) return;
            if (isMyActionLocked(latestRoom)) return;
            if (latestRoom.status !== "playing") return;

            const key = String(event.key || "").toLowerCase();
            const moveName = KEY_TO_MOVE_NAME[key];

            if (!moveName) return;

            const btn = findMoveButtonByMoveName(moveName);
            if (!btn) return;
            if (btn.classList.contains("locked") || btn.classList.contains("disabled")) return;

            event.preventDefault();

            document.querySelectorAll(".move-btn").forEach((node) => {
                node.classList.remove("keyboard-focus");
            });

            btn.classList.add("keyboard-focus");
            btn.click();
        }

        function handleGlobalKeyboard(event) {
            if (event.key === "Escape") {
                closeFinishModal();
                return;
            }

            if (event.key === "Enter") {
                const finishMask = document.getElementById("game-finish-mask");
                if (finishMask.classList.contains("show")) {
                    event.preventDefault();
                    resetRoomGame();
                    return;
                }
            }

            handleMoveKeyboardSelect(event);
        }

        function setRoomMessage(text, type = "info") {
            const el = document.getElementById("room-message");
            el.textContent = text;
            el.className = `message ${type}`;
        }

        function renderRoom(room) {
            try {
                latestRoom = room;

                document.getElementById("room-id").textContent = room.room_id;
                applyRoomStatusBadge(room.status);
                document.getElementById("p1-name").textContent = room.p1_name || "暂无";
                document.getElementById("p2-name").textContent = room.p2_name || "暂无";

                applySeatVisibility();
                applySeatHighlights();

                document.getElementById("pending-p1").textContent = room.pending_p1_move || "暂无";
                document.getElementById("pending-p2").textContent = room.pending_p2_move || "暂无";
                applyPendingHighlights(room);

                const mySeatTextEl = document.getElementById("my-seat-text");
                if (mySeatTextEl) {
                    mySeatTextEl.textContent = getSeatLabel(mySeat);
                }

                renderSpectatorBanner();
                renderStatusSummary(room);
                renderTurnAlert(room);
                renderRoundResultBanner(room);
                renderInvitePanel();
                setSettlingMask(room.pending_p1_move && room.pending_p2_move && room.status === "playing");
                renderResetHint(room);
                renderFinishModal(room);

                document.getElementById("p1-state-full").innerHTML = renderPlayerStateFull(room.game.p1);
                document.getElementById("p2-state-full").innerHTML = renderPlayerStateFull(room.game.p2);

                document.getElementById("p1-state-compact").innerHTML = renderPlayerStateCompact(room.game.p1);
                document.getElementById("p2-state-compact").innerHTML = renderPlayerStateCompact(room.game.p2);

                renderMoveGroups(
                    "p1-move-groups",
                    mySeat === "p1" ? (room.game.legal_moves?.p1 || []) : [],
                    room.game.move_catalog || [],
                    "p1"
                );

                renderMoveGroups(
                    "p2-move-groups",
                    mySeat === "p2" ? (room.game.legal_moves?.p2 || []) : [],
                    room.game.move_catalog || [],
                    "p2"
                );

                renderHistory(room.game.history || []);
            } catch (error) {
                console.error("renderRoom error:", error, room);
                setRoomMessage("房间页面渲染失败：" + error, "error");
            }
        }

        async function fetchRoomState() {
            try {
                if (!myPlayerToken) {
                    setRoomMessage("当前未检测到本地房间身份，可能只能以观战或未知身份进入。", "waiting");
                }
                console.log("fetchRoomState player_token =", myPlayerToken);
                const queryPlayerToken = myPlayerToken || "";
                const res = await fetch(
                    `/api/rooms/${roomId}?player_token=${encodeURIComponent(queryPlayerToken)}`
                );
                const data = await res.json();

                if (!res.ok || !data.ok) {
                    setRoomMessage(data.error || "房间状态获取失败。", "error");
                    return;
                }

                if (data.room.requester_seat) {
                    mySeat = data.room.requester_seat;
                }

                renderRoom(data.room);
            } catch (error) {
                setRoomMessage("房间状态获取失败：" + error, "error");
            }
        }

        async function submitMove(seat, moveName) {
            if (isSpectatorMode()) {
                setRoomMessage("观战模式下不能提交动作。", "error");
                return;
            }

            try {
                console.log("submitMove:", seat, moveName, myPlayerToken);
                const res = await fetch(`/api/rooms/${roomId}/step`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        player_token: myPlayerToken,
                        move_name: moveName
                    })
                });

                const data = await res.json();

                if (!res.ok || !data.ok) {
                    setRoomMessage(data.error || "提交动作失败。", "error");
                    return;
                }

                renderRoom(data.room);

                if (data.resolved) {
                    setRoomMessage(data.message || "本回合已结算。", "success");
                } else {
                    setRoomMessage(data.message || "你已提交动作，当前操作已锁定，正在等待对方。", "waiting");
                }

                const msgEl = document.getElementById(`${seat}-submit-msg`);
                msgEl.textContent = `${seat.toUpperCase()} 已提交 ${moveName}`;
            } catch (error) {
                setRoomMessage("提交动作失败：" + error, "error");
            }
        }

        async function resetRoomGame() {
            if (isSpectatorMode()) {
                setRoomMessage("观战模式下不能重置对局。", "error");
                return;
            }

            try {
                const res = await fetch(`/api/rooms/${roomId}/reset`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        player_token: myPlayerToken
                    })
                });

                const data = await res.json();

                if (!res.ok || !data.ok) {
                    setRoomMessage(data.error || "重置失败。", "error");
                    return;
                }

                renderRoom(data.room);

                if (data.did_reset) {
                    setRoomMessage(data.message || "双方已确认，房间对局已重置。", "success");
                } else {
                    setRoomMessage(data.message || "已发起重置请求，等待另一方确认。", "waiting");
                }

                document.getElementById("p1-submit-msg").textContent = "";
                document.getElementById("p2-submit-msg").textContent = "";
            } catch (error) {
                setRoomMessage("重置失败：" + error, "error");
            }
        }

        window.addEventListener("load", () => {
            try {
                const resetRoomBtn = document.getElementById("reset-room-btn");
                if (resetRoomBtn) {
                    resetRoomBtn.addEventListener("click", resetRoomGame);
                }

                const openSettingsBtn = document.getElementById("open-settings-btn");
                if (openSettingsBtn) {
                    openSettingsBtn.addEventListener("click", openSettingsModal);
                }

                const closeSettingsBtn = document.getElementById("close-settings-btn");
                if (closeSettingsBtn) {
                    closeSettingsBtn.addEventListener("click", closeSettingsModal);
                }

                const settingsMask = document.getElementById("settings-mask");
                if (settingsMask) {
                    settingsMask.addEventListener("click", (event) => {
                        if (event.target.id === "settings-mask") {
                            closeSettingsModal();
                        }
                    });
                }

                const copyRoomIdBtn = document.getElementById("copy-room-id-btn");
                if (copyRoomIdBtn) {
                    copyRoomIdBtn.addEventListener("click", copyRoomId);
                }

                const copyRoomLinkBtn = document.getElementById("copy-room-link-btn");
                if (copyRoomLinkBtn) {
                    copyRoomLinkBtn.addEventListener("click", copyRoomLink);
                }

                const finishResetBtn = document.getElementById("finish-reset-btn");
                if (finishResetBtn) {
                    finishResetBtn.addEventListener("click", resetRoomGame);
                }

                const finishBackBtn = document.getElementById("finish-back-btn");
                if (finishBackBtn) {
                    finishBackBtn.addEventListener("click", () => {
                        window.location.href = "/rooms";
                    });
                }

                document.addEventListener("keydown", handleGlobalKeyboard);

                loadRoomUiSettings();
                syncSettingsControls();
                bindSettingsEvents();
                applyRoomUiSettings();

                applySeatVisibility();
                applySeatHighlights();
                renderInvitePanel();
                renderSpectatorBanner();
                setRoomMessage("正在连接房间并同步状态……", "info");
                fetchRoomState();
                setInterval(fetchRoomState, 15000);
            } catch (error) {
                console.error("room_detail.js init error:", error);
            }
        });
})();