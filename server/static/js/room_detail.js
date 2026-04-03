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
        let currentSelectedOriginalMoveName = null;
        let currentSelectedSeat = null;
        let lastRenderedRoundCount = -1;
        let roundResolvePreview = null;
        let resolvePreviewTimer = null;
        let waitingManualRevealAdvance = false;
        let confirmAction = null;

        if (typeof io !== "function") {
            console.error("room_detail.js: Socket.IO 未加载成功");
            return;
        }

        const socket = io();

        const DEFAULT_ROOM_UI_SETTINGS = {
            showRoomInfo: false,
            showRoomStatus: false,
            showInvite: false,
            showRoundResult: false,
            showHistory: true,
            showMoveSubtitles: false,
            playerStateMode: "compact",
            revealAdvanceMode: "auto"
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

        socket.on("opponent_left", (data) => {
            if (!data || !data.ok) {
                return;
            }

            if (data.left_seat === mySeat) {
                return;
            }

            openOpponentLeftModal();
        });

        const moveGroups = {
            resource_defense: ["QI", "SHIELD", "SHI_ZI", "BA_GUA"],
            attack_qi: ["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"],
            attack_shield: ["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"],
            trick: ["CHI", "SHUANG_CHI", "SHAN", "GAO"]
        };

        function seatDisplayText(seat) {
            if (seat === "p1") return "1号位";
            if (seat === "p2") return "2号位";
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
            if (seat === "p1") return "1号位";
            if (seat === "p2") return "2号位";
            return "观战";
        }

        function getOpponentSeat() {
            if (mySeat === "p1") return "p2";
            if (mySeat === "p2") return "p1";
            return null;
        }

        function getSeatDisplayName(room, seat) {
            const playerName = seat === "p1" ? (room.p1_name || "暂无") : (room.p2_name || "暂无");
            const seatLabel = seat === "p1" ? "1号位" : "2号位";
            return `${playerName} · ${seatLabel}`;
        }

        function getOrderedSeatsForDisplay() {
            return ["p1", "p2"];
        }

        function isSpectatorMode() {
            return mySeat !== "p1" && mySeat !== "p2";
        }

        const MOVE_SHORTCUTS = {
            "chi": "1",
            "shuang_chi": "2",
            "shan": "3",
            "gao": "4",

            "qi": "Q",
            "shield": "W",
            "shi_zi": "E",
            "ba_gua": "R",

            "gi": "A",
            "po": "S",
            "leng_feng": "D",
            "ru_lai": "F",
            "hei_dong": "G",

            "fire": "Z",
            "shan_dian": "X",
            "lie_yan": "C",
            "shining": "V"
        };

        const KEY_TO_MOVE_NAME = {
            "1": "chi",
            "2": "shuang_chi",
            "3": "shan",
            "4": "gao",

            "q": "qi",
            "w": "shield",
            "e": "shi_zi",
            "r": "ba_gua",

            "a": "gi",
            "s": "po",
            "d": "leng_feng",
            "f": "ru_lai",
            "g": "hei_dong",

            "z": "fire",
            "x": "shan_dian",
            "c": "lie_yan",
            "v": "shining"
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
            document.getElementById("toggle-history-section").checked = !!roomUiSettings.showHistory;
            document.getElementById("toggle-move-subtitles").checked = !!roomUiSettings.showMoveSubtitles;
            document.getElementById("player-state-mode-select").value = roomUiSettings.playerStateMode || "compact";
            document.getElementById("reveal-advance-mode-select").value = roomUiSettings.revealAdvanceMode || "auto";
        }

        function applyRoomUiSettings() {
            const roomInfoSection = document.getElementById("room-info-section");
            const roomStatusSection = document.getElementById("room-status-section");
            const inviteSection = document.getElementById("invite-section");
            const roundResultSection = document.getElementById("round-result-section");
            const historySection = document.getElementById("history-section");
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

            if (historySection) {
                historySection.style.display = roomUiSettings.showHistory ? "" : "none";
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
            updateOverviewCardVisibility();
        }

        function updateOverviewCardVisibility() {
            const overviewCard = document.getElementById("overview-card");
            const spectatorBanner = document.getElementById("spectator-banner");

            if (!overviewCard) {
                return;
            }

            const showAnything =
                !!roomUiSettings.showRoomInfo ||
                !!roomUiSettings.showRoomStatus ||
                !!roomUiSettings.showInvite ||
                (spectatorBanner && spectatorBanner.style.display !== "none");

            overviewCard.style.display = showAnything ? "" : "none";
        }

        function openHelpModal() {
            document.getElementById("help-mask").classList.add("show");
        }

        function closeHelpModal() {
            document.getElementById("help-mask").classList.remove("show");
        }

        function openSettingsModal() {
            document.getElementById("settings-mask").classList.add("show");
        }

        function closeSettingsModal() {
            document.getElementById("settings-mask").classList.remove("show");
        }

        function clearCurrentRoomIdentity() {
            localStorage.removeItem(`clapclap_room_${roomId}`);
        }

        function clearAllRoomIdentity() {
            const keysToDelete = [];

            for (let i = 0; i < localStorage.length; i += 1) {
                const key = localStorage.key(i);
                if (!key) {
                    continue;
                }

                if (
                    key.startsWith("clapclap_room_") ||
                    key.startsWith("clapclap_room_ui_settings_") ||
                    key === "clapclap_match_player_token" ||
                    key === "clapclap_match_player_name" ||
                    key === "clapclap_match_state"
                ) {
                    keysToDelete.push(key);
                }
            }

            keysToDelete.forEach((key) => localStorage.removeItem(key));
        }

        function goHome() {
            window.location.href = "/";
        }

        function goHomeKeepRoom() {
            goHome();
        }

        function openConfirmModal(title, message, onConfirm) {
            const mask = document.getElementById("confirm-mask");
            const titleEl = document.getElementById("confirm-title");
            const messageEl = document.getElementById("confirm-message");

            titleEl.textContent = title;
            messageEl.textContent = message;
            confirmAction = onConfirm;
            mask.classList.add("show");
        }

        function closeConfirmModal() {
            const mask = document.getElementById("confirm-mask");
            mask.classList.remove("show");
            confirmAction = null;
        }

        function openOpponentLeftModal() {
            document.getElementById("opponent-left-mask").classList.add("show");
        }

        function closeOpponentLeftModal() {
            document.getElementById("opponent-left-mask").classList.remove("show");
        }

        async function leaveRoomAndGoHome() {
            try {
                const res = await fetch(`/api/rooms/${roomId}/leave`, {
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
                    setRoomMessage(data.error || "退出房间失败。", "error");
                    return;
                }

                clearAllRoomIdentity();
                goHome();
            } catch (error) {
                setRoomMessage("退出房间失败：" + error, "error");
            }
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

        function updatePendingChoicePreview() {
            if (!latestRoom) {
                return;
            }

            const pendingSelfEl = document.getElementById("pending-self");
            const pendingSelfLabelEl = document.getElementById("pending-self-label");
            const pendingOpponentEl = document.getElementById("pending-opponent");
            const pendingOpponentLabelEl = document.getElementById("pending-opponent-label");

            const myPending = getMyPendingMove(latestRoom);
            const opponentPending = getOpponentPendingMove(latestRoom);

            const myPreviewMove =
                !myPending &&
                currentSelectedSeat === mySeat &&
                currentSelectedOriginalMoveName
                    ? currentSelectedOriginalMoveName
                    : null;

            if (pendingSelfEl) {
                if (myPending) {
                    pendingSelfEl.textContent = moveLabel(myPending, latestRoom.game.move_catalog || []);
                } else if (myPreviewMove) {
                    pendingSelfEl.textContent = moveLabel(myPreviewMove, latestRoom.game.move_catalog || []);
                } else {
                    pendingSelfEl.textContent = "暂无";
                }
            }

            if (pendingSelfLabelEl) {
                pendingSelfLabelEl.textContent =
                    myPending ? "我方已选择" : "我方待选择";
            }

            if (pendingOpponentEl) {
                pendingOpponentEl.textContent =
                    opponentPending ? "对方已选择" : "";
            }

            if (pendingOpponentLabelEl) {
                pendingOpponentLabelEl.textContent =
                    opponentPending ? "对方已选择" : "对方选择中";
            }
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
            updateOverviewCardVisibility();
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

            if (p1NameBox) {
                p1NameBox.classList.remove("seat-p1");
            }
            if (p2NameBox) {
                p2NameBox.classList.remove("seat-p2");
            }
            if (p1PlayerBox) {
                p1PlayerBox.classList.remove("active-seat", "active-seat-p1", "active-seat-p2");
            }
            if (p2PlayerBox) {
                p2PlayerBox.classList.remove("active-seat", "active-seat-p1", "active-seat-p2");
            }
            if (p1RowFull) {
                p1RowFull.classList.remove("seat-p1", "seat-p2");
            }
            if (p2RowFull) {
                p2RowFull.classList.remove("seat-p1", "seat-p2");
            }

            if (mySeat === "p1") {
                if (p1NameBox) {
                    p1NameBox.classList.add("seat-p1");
                }
            } else if (mySeat === "p2") {
                if (p2NameBox) {
                    p2NameBox.classList.add("seat-p2");
                }
            }
        }

        function applyPendingHighlights(room) {
            const selfBox = document.getElementById("pending-self-box");
            const opponentBox = document.getElementById("pending-opponent-box");

            if (!selfBox || !opponentBox) {
                return;
            }

            selfBox.classList.remove("pending-self-ready");
            opponentBox.classList.remove("pending-opponent-ready");

            const myPending = getMyPendingMove(room);
            const opponentPending = getOpponentPendingMove(room);

            if (myPending) {
                selfBox.classList.add("pending-self-ready");
            }

            if (opponentPending) {
                opponentBox.classList.add("pending-opponent-ready");
            }
        }

        function applySeatVisibility() {
            const actionSection = document.getElementById("action-section");
            const resetBtn = document.getElementById("reset-room-btn");
            const p1SubmitBox = document.getElementById("p1-submit-box");
            const p2SubmitBox = document.getElementById("p2-submit-box");

            if (mySeat === "p1") {
                if (actionSection) {
                    actionSection.style.display = "";
                }
                if (resetBtn) {
                    resetBtn.disabled = false;
                }
                if (p1SubmitBox) {
                    p1SubmitBox.style.display = "";
                }
                if (p2SubmitBox) {
                    p2SubmitBox.style.display = "none";
                }
                return;
            }

            if (mySeat === "p2") {
                if (actionSection) {
                    actionSection.style.display = "";
                }
                if (resetBtn) {
                    resetBtn.disabled = false;
                }
                if (p1SubmitBox) {
                    p1SubmitBox.style.display = "none";
                }
                if (p2SubmitBox) {
                    p2SubmitBox.style.display = "";
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

        function renderPlayerStateFull(player, side = "self") {
            const sideClass = side === "self" ? "state-side-self" : "state-side-opponent";

            return `
                <div class="status-table-row full ${sideClass}">
                    <div class="status-table-full-top">
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">生命</span>
                            <span class="status-table-value">${player.hp ?? 0}</span>
                        </div>
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">镐</span>
                            <span class="status-table-value">${player.pickaxe ?? 0}</span>
                        </div>
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">气</span>
                            <span class="status-table-value">${player.qi ?? 0}</span>
                        </div>
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">盾</span>
                            <span class="status-table-value">${player.shield ?? 0}</span>
                        </div>
                    </div>

                    <div class="status-table-full-bottom">
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">火种</span>
                            <span class="status-table-value">${player.spark ?? 0}</span>
                        </div>
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">电池</span>
                            <span class="status-table-value">${player.battery ?? 0}</span>
                        </div>
                        <div class="status-table-cell status-table-cell-stat">
                            <span class="status-table-key">闪次数</span>
                            <span class="status-table-value">${player.flash_used ?? 0}</span>
                        </div>
                    </div>
                </div>
            `;
        }

        function renderPlayerStateCompact(player, side = "self") {
            const sideClass = side === "self" ? "state-side-self" : "state-side-opponent";

            return `
                <div class="status-table-row ${sideClass}">
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">生命</span>
                        <span class="status-table-value">${player.hp ?? 0}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">镐</span>
                        <span class="status-table-value">${player.pickaxe ?? 0}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">气</span>
                        <span class="status-table-value">${player.qi ?? 0}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">盾</span>
                        <span class="status-table-value">${player.shield ?? 0}</span>
                    </div>
                </div>
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

            document.getElementById("toggle-history-section").addEventListener("change", (event) => {
                roomUiSettings.showHistory = event.target.checked;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });

            document.getElementById("toggle-move-subtitles").addEventListener("change", (event) => {
                roomUiSettings.showMoveSubtitles = event.target.checked;
                saveRoomUiSettings();
                renderRoom(latestRoom);
            });

            document.getElementById("player-state-mode-select").addEventListener("change", (event) => {
                roomUiSettings.playerStateMode = event.target.value;
                saveRoomUiSettings();
                applyRoomUiSettings();
            });

            document.getElementById("reveal-advance-mode-select").addEventListener("change", (event) => {
                roomUiSettings.revealAdvanceMode = event.target.value;
                saveRoomUiSettings();
            });
        }

        function moveLabel(moveName, catalog) {
            const item = catalog.find(x => x.name === moveName);
            return item ? item.label : moveName;
        }

        function renderMoveGroups(containerId, legalMoves, catalog, seat) {
            const container = document.getElementById(containerId);
            if (!container) {
                return;
            }

            container.innerHTML = "";

            const layout = document.createElement("div");
            layout.className = "move-layout";

            const rows = [
                {
                    title: "资源 / 防御",
                    className: "move-grid resource-defense-grid",
                    moveNames: moveGroups.resource_defense
                },
                {
                    title: "气系攻击",
                    className: "move-grid qi-attack-grid",
                    moveNames: moveGroups.attack_qi
                },
                {
                    title: "盾系攻击",
                    className: "move-grid shield-attack-grid",
                    moveNames: moveGroups.attack_shield
                },
                {
                    title: "锦囊",
                    className: "move-grid trick-grid",
                    moveNames: moveGroups.trick
                }
            ];

            function appendMoveButton(grid, moveName) {
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
                btn.dataset.originalMoveName = moveName;
                btn.dataset.seat = seat;

                if (
                    seat === mySeat &&
                    currentSelectedMoveName === normalizedMoveName &&
                    currentSelectedSeat === seat &&
                    !isMyActionLocked(latestRoom)
                ) {
                    btn.classList.add("pending-confirm-p1");
                }

                btn.addEventListener("click", async () => {
                    if (!legal) return;
                    if (isMyActionLocked(latestRoom)) return;
                    if (isSpectatorMode()) return;
                    if (seat !== mySeat) return;

                    const normalizedCurrent = normalizeMoveName(moveName);

                    if (
                        currentSelectedSeat === seat &&
                        currentSelectedMoveName === normalizedCurrent
                    ) {
                        await confirmSelectedMove();
                        return;
                    }

                    selectMoveForConfirm(seat, moveName);
                });

                grid.appendChild(btn);
            }

            for (const rowConfig of rows) {
                const row = document.createElement("div");
                row.className = "move-row single-move-row";

                const title = document.createElement("div");
                title.className = "move-group-title";
                title.textContent = rowConfig.title;
                title.style.display = roomUiSettings.showMoveSubtitles ? "" : "none";

                const grid = document.createElement("div");
                grid.className = rowConfig.className;

                for (const moveName of rowConfig.moveNames) {
                    appendMoveButton(grid, moveName);
                }

                row.appendChild(title);
                row.appendChild(grid);
                layout.appendChild(row);
            }

            container.appendChild(layout);

        }

        function renderHistory(logs) {
            const historyEl = document.getElementById("history");
            if (!historyEl) {
                return;
            }

            historyEl.innerHTML = "";

            if (!logs || logs.length === 0) {
                historyEl.innerHTML = "<div class='muted' style='padding: 12px;'>当前还没有历史记录。</div>";
                return;
            }

            const rowsHtml = logs.slice().reverse().map((log) => {
                const p1Move = log.p1_move_label || log.p1_move || "";
                const p2Move = log.p2_move_label || log.p2_move || "";

                const damageParts = [];
                if ((log.p1_damage_taken ?? 0) > 0) {
                    damageParts.push(`1号位受到${log.p1_damage_taken}点伤害`);
                }
                if ((log.p2_damage_taken ?? 0) > 0) {
                    damageParts.push(`2号位受到${log.p2_damage_taken}点伤害`);
                }

                const summaryText = damageParts.length > 0
                    ? damageParts.join("，")
                    : "";

                return `
                    <tr>
                        <td class="history-table-col-round">${log.round_num}</td>
                        <td class="history-table-col-move">${p1Move}</td>
                        <td class="history-table-col-move">${p2Move}</td>
                        <td class="history-table-col-summary">${summaryText}</td>
                    </tr>
                `;
            }).join("");

            historyEl.innerHTML = `
                <table class="history-table">
                    <thead>
                        <tr>
                            <th class="history-table-col-round">回合数</th>
                            <th class="history-table-col-move">1号位动作</th>
                            <th class="history-table-col-move">2号位动作</th>
                            <th class="history-table-col-summary">总结</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rowsHtml}
                    </tbody>
                </table>
            `;
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

        function clearMoveSelection() {
            currentSelectedMoveName = null;
            currentSelectedOriginalMoveName = null;
            currentSelectedSeat = null;

            document.querySelectorAll(".move-btn").forEach((node) => {
                node.classList.remove(
                    "selected-p1",
                    "selected-p2",
                    "keyboard-focus",
                    "pending-confirm-p1",
                    "pending-confirm-p2"
                );
            });

            updatePendingChoicePreview();
        }

        function selectMoveForConfirm(seat, moveName) {
            const normalizedMoveName = normalizeMoveName(moveName);

            clearMoveSelection();

            currentSelectedMoveName = normalizedMoveName;
            currentSelectedOriginalMoveName = moveName;
            currentSelectedSeat = seat;

            const btn = document.querySelector(
                `.move-btn[data-seat="${seat}"][data-move-name="${normalizedMoveName}"]`
            );

            if (!btn) {
                updatePendingChoicePreview();
                return;
            }

            btn.classList.add("pending-confirm-p1");
            btn.classList.add("keyboard-focus");

            updatePendingChoicePreview();

            setRoomMessage(
                `已选择 ${moveLabel(btn.dataset.originalMoveName, latestRoom?.game?.move_catalog || [])}，按 Enter 确认提交，按 Backspace 取消。`,
                "waiting"
            );
        }

        function findMoveButtonByMoveName(moveName) {
            const normalized = normalizeMoveName(moveName);
            return document.querySelector(
                `.move-btn[data-seat="${mySeat}"][data-move-name="${normalized}"]`
            );
        }

        function highlightResolvedPreviewButtons(preview) {
            if (!preview || !latestRoom) {
                return;
            }

            document.querySelectorAll(".move-btn").forEach((node) => {
                node.classList.remove("pending-confirm-p1", "pending-confirm-p2");
            });

            const myMove = mySeat === "p1" ? preview.p1_move : preview.p2_move;
            const opponentMove = mySeat === "p1" ? preview.p2_move : preview.p1_move;

            if (myMove) {
                const myBtn = findMoveButtonByMoveName(myMove);
                if (myBtn) {
                    myBtn.classList.add("pending-confirm-p1");
                }
            }

            if (opponentMove) {
                const opponentBtn = findMoveButtonByMoveName(opponentMove);
                if (opponentBtn) {
                    opponentBtn.classList.add("pending-confirm-p2");
                }
            }
        }

        async function confirmSelectedMove() {
            if (isSpectatorMode()) return;
            if (!latestRoom) return;
            if (!currentSelectedMoveName || !currentSelectedSeat) return;
            if (currentSelectedSeat !== mySeat) return;
            if (isMyActionLocked(latestRoom)) return;

            const btn = document.querySelector(
                `.move-btn[data-seat="${currentSelectedSeat}"][data-move-name="${currentSelectedMoveName}"]`
            );
            if (!btn) {
                return;
            }

            const originalMoveName = btn.dataset.originalMoveName;
            await submitMove(currentSelectedSeat, originalMoveName);
        }

        async function cancelSubmittedMove() {
            if (isSpectatorMode()) {
                return;
            }
            if (!latestRoom) {
                return;
            }
            if (!isMyActionLocked(latestRoom)) {
                return;
            }

            const myPending = getMyPendingMove(latestRoom);
            const opponentPending = getOpponentPendingMove(latestRoom);

            if (!myPending) {
                return;
            }

            if (opponentPending) {
                setRoomMessage("对方也已提交，当前回合正在进入结算，不能撤回。", "error");
                return;
            }

            try {
                const res = await fetch(`/api/rooms/${roomId}/cancel-step`, {
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
                    setRoomMessage(data.error || "撤回提交失败。", "error");
                    return;
                }

                renderRoom(data.room);
                clearMoveSelection();
                updatePendingChoicePreview();
                setRoomMessage(data.message || "已撤回本回合提交动作。", "waiting");

                const myMsgEl = document.getElementById(`${mySeat}-submit-msg`);
                if (myMsgEl) {
                    myMsgEl.textContent = "";
                }
            } catch (error) {
                setRoomMessage("撤回提交失败：" + error, "error");
            }
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
            selectMoveForConfirm(mySeat, btn.dataset.originalMoveName || moveName);
        }

        async function handleGlobalKeyboard(event) {
            if (waitingManualRevealAdvance && latestRoom) {
                event.preventDefault();
                finishResolvedPreview(latestRoom);
                return;
            }

            if (event.target && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) {
                return;
            }

            if (event.key === "Escape") {
                closeHelpModal();
                closeSettingsModal();
                closeFinishModal();
                closeConfirmModal();
                closeOpponentLeftModal();
                return;
            }

            if (event.key === "Enter") {
                const finishMask = document.getElementById("game-finish-mask");
                if (finishMask.classList.contains("show")) {
                    event.preventDefault();
                    resetRoomGame();
                    return;
                }

                if (currentSelectedMoveName && currentSelectedSeat === mySeat) {
                    event.preventDefault();
                    await confirmSelectedMove();
                    return;
                }
            }

            if (event.key === "Backspace") {
                event.preventDefault();

                const finishMask = document.getElementById("game-finish-mask");
                const settingsMask = document.getElementById("settings-mask");
                const helpMask = document.getElementById("help-mask");

                if (finishMask.classList.contains("show")) {
                    closeFinishModal();
                    return;
                }

                if (helpMask.classList.contains("show")) {
                    closeHelpModal();
                    return;
                }

                if (settingsMask.classList.contains("show")) {
                    closeSettingsModal();
                    return;
                }

                if (currentSelectedMoveName && currentSelectedSeat === mySeat) {
                    clearMoveSelection();
                    setRoomMessage("已取消当前选择。", "info");
                    return;
                }

                await cancelSubmittedMove();
                return;
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

                const currentRound = Array.isArray(room.game?.history) ? room.game.history.length + 1 : 1;

                const currentRoundEl = document.getElementById("current-round");
                const pendingSelfEl = document.getElementById("pending-self");
                const pendingOpponentEl = document.getElementById("pending-opponent");
                const pendingSelfLabelEl = document.getElementById("pending-self-label");
                const pendingOpponentLabelEl = document.getElementById("pending-opponent-label");

                if (currentRoundEl) {
                    currentRoundEl.textContent = currentRound;
                }

                const myPending = getMyPendingMove(room);
                const opponentPending = getOpponentPendingMove(room);

                const myPreviewMove =
                    !myPending &&
                    currentSelectedSeat === mySeat &&
                    currentSelectedOriginalMoveName
                        ? currentSelectedOriginalMoveName
                        : null;

                if (pendingSelfEl) {
                    if (myPending) {
                        pendingSelfEl.textContent = moveLabel(myPending, room.game.move_catalog || []);
                    } else if (myPreviewMove) {
                        pendingSelfEl.textContent = moveLabel(myPreviewMove, room.game.move_catalog || []);
                    } else {
                        pendingSelfEl.textContent = "暂无";
                    }
                }

                if (pendingOpponentEl) {
                    pendingOpponentEl.textContent =
                        opponentPending ? "对方已选择" : "";
                }

                if (pendingSelfLabelEl) {
                    pendingSelfLabelEl.textContent =
                        myPending ? "我方已选择" : "我方待选择";
                }

                if (pendingOpponentLabelEl) {
                    pendingOpponentLabelEl.textContent =
                        opponentPending ? "对方已选择" : "对方选择中";
                }

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

                const [leftSeat, rightSeat] = getOrderedSeatsForDisplay();
                const leftPlayer = leftSeat === "p1" ? room.game.p1 : room.game.p2;
                const rightPlayer = rightSeat === "p1" ? room.game.p1 : room.game.p2;

                document.getElementById("left-row-title").textContent = `${getSeatDisplayName(room, leftSeat)} `;
                document.getElementById("right-row-title").textContent = `${getSeatDisplayName(room, rightSeat)} `;
                document.getElementById("left-compact-title").textContent = `${getSeatDisplayName(room, leftSeat)} `;
                document.getElementById("right-compact-title").textContent = `${getSeatDisplayName(room, rightSeat)} `;

                const leftSideType = leftSeat === mySeat ? "self" : "opponent";
                const rightSideType = rightSeat === mySeat ? "self" : "opponent";

                document.getElementById("p1-player-box").classList.toggle("status-table-line-self", leftSideType === "self");
                document.getElementById("p1-player-box").classList.toggle("status-table-line-opponent", leftSideType !== "self");

                document.getElementById("p2-player-box").classList.toggle("status-table-line-self", rightSideType === "self");
                document.getElementById("p2-player-box").classList.toggle("status-table-line-opponent", rightSideType !== "self");

                document.getElementById("p1-row-full").classList.toggle("status-table-line-self", leftSideType === "self");
                document.getElementById("p1-row-full").classList.toggle("status-table-line-opponent", leftSideType !== "self");

                document.getElementById("p2-row-full").classList.toggle("status-table-line-self", rightSideType === "self");
                document.getElementById("p2-row-full").classList.toggle("status-table-line-opponent", rightSideType !== "self");

                document.getElementById("p1-state-full").innerHTML = renderPlayerStateFull(leftPlayer, leftSideType);
                document.getElementById("p2-state-full").innerHTML = renderPlayerStateFull(rightPlayer, rightSideType);

                document.getElementById("p1-state-compact").innerHTML = renderPlayerStateCompact(leftPlayer, leftSideType);
                document.getElementById("p2-state-compact").innerHTML = renderPlayerStateCompact(rightPlayer, rightSideType);

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

                if (roundResolvePreview) {
                    showResolvedPreview(roundResolvePreview, room);
                    highlightResolvedPreviewButtons(roundResolvePreview);
                }

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

        function showResolvedPreview(preview, room) {
            waitingManualRevealAdvance = false;

            const pendingSelfEl = document.getElementById("pending-self");
            const pendingOpponentEl = document.getElementById("pending-opponent");
            const pendingSelfLabelEl = document.getElementById("pending-self-label");
            const pendingOpponentLabelEl = document.getElementById("pending-opponent-label");

            if (!preview || !room) {
                return;
            }

            const myMove = mySeat === "p1" ? preview.p1_move : preview.p2_move;
            const opponentMove = mySeat === "p1" ? preview.p2_move : preview.p1_move;

            if (pendingSelfLabelEl) {
                pendingSelfLabelEl.textContent = "我方本回合动作";
            }
            if (pendingOpponentLabelEl) {
                pendingOpponentLabelEl.textContent = "对方本回合动作";
            }
            if (pendingSelfEl) {
                pendingSelfEl.textContent = myMove
                    ? moveLabel(myMove, room.game.move_catalog || [])
                    : "暂无";
            }
            if (pendingOpponentEl) {
                pendingOpponentEl.textContent = opponentMove
                    ? moveLabel(opponentMove, room.game.move_catalog || [])
                    : "暂无";
            }
        }

        function finishResolvedPreview(room) {
            roundResolvePreview = null;
            waitingManualRevealAdvance = false;
            clearMoveSelection();
            renderRoom(room);
        }

        function getLatestRoomIdentity() {
            let latestRoom = null;

            for (let i = 0; i < localStorage.length; i += 1) {
                const key = localStorage.key(i);
                if (!key || !key.startsWith("clapclap_room_")) {
                    continue;
                }

                if (key.startsWith("clapclap_room_ui_settings_")) {
                    continue;
                }

                const roomId = key.slice("clapclap_room_".length);
                const raw = localStorage.getItem(key);
                if (!raw) {
                    continue;
                }

                try {
                    const parsed = JSON.parse(raw);
                    if (!parsed || !parsed.player_token) {
                        continue;
                    }

                    latestRoom = {
                        roomId,
                        player_token: parsed.player_token,
                        seat: parsed.seat || null
                    };
                } catch (error) {
                    continue;
                }
            }

            return latestRoom;
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

                clearMoveSelection();

                if (data.resolved) {
                    roundResolvePreview = data.resolved_preview || null;

                    renderRoom(data.room);

                    if (roundResolvePreview) {
                        showResolvedPreview(roundResolvePreview, data.room);
                        highlightResolvedPreviewButtons(roundResolvePreview);
                    }

                    setRoomMessage(data.message || "本回合已结算。", "success");

                    if (resolvePreviewTimer) {
                        window.clearTimeout(resolvePreviewTimer);
                        resolvePreviewTimer = null;
                    }

                    if ((roomUiSettings.revealAdvanceMode || "auto") === "manual") {
                        waitingManualRevealAdvance = true;
                        setRoomMessage("本回合动作已展示。按任意键或点击任意位置进入下一回合。", "waiting");
                    } else {
                        waitingManualRevealAdvance = false;
                        resolvePreviewTimer = window.setTimeout(() => {
                            finishResolvedPreview(data.room);
                        }, 1000);
                    }
                } else {
                    renderRoom(data.room);
                    setRoomMessage(data.message || "你已提交动作，当前操作已锁定，正在等待对方。", "waiting");
                }

                const msgEl = document.getElementById(`${seat}-submit-msg`);
                if (msgEl) {
                    msgEl.textContent = `你已提交 ${moveLabel(moveName, data.room?.game?.move_catalog || [])}`;
                }
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

                const p1SubmitMsg = document.getElementById("p1-submit-msg");
                const p2SubmitMsg = document.getElementById("p2-submit-msg");

                if (p1SubmitMsg) {
                    p1SubmitMsg.textContent = "";
                }
                if (p2SubmitMsg) {
                    p2SubmitMsg.textContent = "";
                }

                clearMoveSelection();
            } catch (error) {
                setRoomMessage("重置失败：" + error, "error");
            }
        }

        window.addEventListener("load", () => {
            try {
                const confirmMask = document.getElementById("confirm-mask");
                if (confirmMask) {
                    confirmMask.addEventListener("click", (event) => {
                        if (event.target.id === "confirm-mask") {
                            closeConfirmModal();
                        }
                    });
                }
                
                const backHomeBtn = document.getElementById("back-home-btn");
                if (backHomeBtn) {
                    backHomeBtn.addEventListener("click", () => {
                        openConfirmModal(
                            "确认返回主页",
                            "返回主页后你将暂时离开当前页面，但房间会保留，你之后仍可继续返回该房间。",
                            () => {
                                closeConfirmModal();
                                goHomeKeepRoom();
                            }
                        );
                    });
                }

                const leaveRoomBtn = document.getElementById("leave-room-btn");
                if (leaveRoomBtn) {
                    leaveRoomBtn.addEventListener("click", () => {
                        openConfirmModal(
                            "确认退出房间",
                            "退出房间后当前房间会关闭，确认继续吗？",
                            async () => {
                                closeConfirmModal();
                                await leaveRoomAndGoHome();
                            }
                        );
                    });
                }

                const finishBackBtn = document.getElementById("finish-back-btn");
                if (finishBackBtn) {
                    finishBackBtn.addEventListener("click", () => {
                        openConfirmModal(
                            "确认返回主页",
                            "返回主页后你将暂时离开当前页面，但房间会保留。",
                            () => {
                                closeConfirmModal();
                                goHomeKeepRoom();
                            }
                        );
                    });
                }

                const confirmCancelBtn = document.getElementById("confirm-cancel-btn");
                if (confirmCancelBtn) {
                    confirmCancelBtn.addEventListener("click", closeConfirmModal);
                }

                const confirmOkBtn = document.getElementById("confirm-ok-btn");
                if (confirmOkBtn) {
                    confirmOkBtn.addEventListener("click", async () => {
                        if (typeof confirmAction === "function") {
                            await confirmAction();
                        }
                    });
                }

                const opponentLeftOkBtn = document.getElementById("opponent-left-ok-btn");
                if (opponentLeftOkBtn) {
                    opponentLeftOkBtn.addEventListener("click", () => {
                        closeOpponentLeftModal();
                        clearAllRoomIdentity();
                        goHome();
                    });
                }
                const openHelpBtn = document.getElementById("open-help-btn");
                if (openHelpBtn) {
                    openHelpBtn.addEventListener("click", openHelpModal);
                }

                const closeHelpBtn = document.getElementById("close-help-btn");
                if (closeHelpBtn) {
                    closeHelpBtn.addEventListener("click", closeHelpModal);
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

                const helpMask = document.getElementById("help-mask");
                if (helpMask) {
                    helpMask.addEventListener("click", (event) => {
                        if (event.target.id === "help-mask") {
                            closeHelpModal();
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

                document.addEventListener("keydown", handleGlobalKeyboard);
                document.addEventListener("click", (event) => {
                    if (!waitingManualRevealAdvance || !latestRoom) {
                        return;
                    }

                    const settingsMask = document.getElementById("settings-mask");
                    const helpMask = document.getElementById("help-mask");
                    const finishMask = document.getElementById("game-finish-mask");

                    if (settingsMask.classList.contains("show")) {
                        return;
                    }
                    if (helpMask.classList.contains("show")) {
                        return;
                    }
                    if (finishMask.classList.contains("show")) {
                        return;
                    }

                    finishResolvedPreview(latestRoom);
                });

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