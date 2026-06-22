window.initMatchPage = function () {
        let joinedQueue = false;
        let matchedRoomId = null;
        let currentPlayerName = "";
        let currentMatchToken = "";
        let currentRoomPlayerToken = "";
        let currentSeat = null;
        let matchStateController = null;
        let matchSocket = null;
        let matchPollTimer = null;

        function startMatchFallbackPolling() {
            if (matchPollTimer) return;
            matchPollTimer = window.setInterval(() => {
                matchStateController.fetchMatchStatus();
                matchStateController.syncMyMatchState();
            }, 5000);
        }

        function stopMatchFallbackPolling() {
            if (!matchPollTimer) return;
            window.clearInterval(matchPollTimer);
            matchPollTimer = null;
        }

        if (window.SERVER_BOOT_ID) {
            const bootResult = BootUtils.handleServerBootChange(window.SERVER_BOOT_ID);

            if (bootResult.changed) {
                setMatchMessage("检测到服务已重启，正在尝试恢复匹配或房间入口。", "info");
            }
        }

        function getPlayerName() {
            return currentPlayerName;
        }

        function setPlayerName(value) {
            currentPlayerName = value || "";
        }

        function getPlayerToken() {
            return currentMatchToken;
        }

        function setPlayerToken(value) {
            currentMatchToken = value || "";
        }

        function getMatchedRoomId() {
            return matchedRoomId;
        }

        function setMatchedRoomId(value) {
            matchedRoomId = value || null;
        }

        function getCurrentSeat() {
            return currentSeat;
        }

        function setCurrentSeat(value) {
            currentSeat = value || null;
        }

        function getCurrentRoomPlayerToken() {
            return currentRoomPlayerToken;
        }

        function setCurrentRoomPlayerToken(value) {
            currentRoomPlayerToken = value || "";
        }

        function setJoinedQueue(value) {
            joinedQueue = !!value;
        }

        function setQueueStatusText(text) {
            document.getElementById("queue-status").textContent = text || "";
        }

        function setSelfStatusText(text) {
            document.getElementById("self-status").textContent = text || "";
        }

        function setMatchMessage(text, type = "info") {
            MessageUtils.setMessage("match-message", text, type);
        }

        function applyMatchStatus(status) {
            if (!status) {
                return;
            }

            if (status.has_waiting_player) {
                setQueueStatusText(`当前有玩家正在等待：${status.waiting_player}`);
            } else {
                setQueueStatusText("当前没有玩家在等待。");
            }
        }

        function ensureMatchIdentity(playerName) {
            const parsed = StorageUtils.getJsonStorage(STORAGE_KEYS.MATCH_IDENTITY, null);

            if (parsed) {
                try {
                    if (parsed.player_name === playerName && parsed.player_token) {
                        return parsed.player_token;
                    }
                } catch (error) {
                    console.error(error);
                }
            }

            const token = crypto.randomUUID().replaceAll("-", "");
            StorageUtils.setJsonStorage(
                STORAGE_KEYS.MATCH_IDENTITY,
                {
                    player_name: playerName,
                    player_token: token
                }
            );
            return token;
        }

        function setQueuedUi(isQueued) {
            document.getElementById("cancel-match-btn").style.display = isQueued ? "" : "none";
        }

        function setResumeUi(showResume) {
            document.getElementById("resume-room-btn").style.display = showResume ? "" : "none";
            const panel = document.getElementById("resume-panel");
            if (panel) {
                panel.classList.toggle("show", !!showResume);
            }
            renderResumePanel();
        }

        function renderResumePanel(opponentName = "") {
            const roomEl = document.getElementById("resume-room-id");
            const seatEl = document.getElementById("resume-seat");
            const opponentEl = document.getElementById("resume-opponent");

            if (roomEl) {
                roomEl.textContent = matchedRoomId || "-";
            }
            if (seatEl) {
                seatEl.textContent = currentSeat ? currentSeat.toUpperCase() : "-";
            }
            if (opponentEl) {
                opponentEl.textContent = opponentName || opponentEl.textContent || "-";
            }
        }

        function clearResumeState() {
            if (matchedRoomId) {
                RoomIdentityStorage.removeRoomIdentity(matchedRoomId);
            }
            setMatchedRoomId(null);
            setCurrentSeat(null);
            setCurrentRoomPlayerToken("");
            setJoinedQueue(false);
            setResumeUi(false);
            setSelfStatusText("你当前尚未加入匹配队列。");
        }

        async function goToMatchedRoom() {
            if (!matchedRoomId || !currentSeat || !currentRoomPlayerToken) {
                return;
            }

            const result = await ApiUtils.apiGet(
                `/api/rooms/${matchedRoomId}?player_token=${encodeURIComponent(currentRoomPlayerToken)}`
            );

            if (!result.ok) {
                clearResumeState();

                setMatchMessage(
                    result.error || "检测到旧房间已失效，已清除无效恢复状态，请重新匹配。",
                    "error"
                );
                setSelfStatusText("你当前尚未加入匹配队列。");

                setQueuedUi(false);
                setResumeUi(false);
                return;
            }

            RoomIdentityStorage.saveRoomIdentity(matchedRoomId, currentRoomPlayerToken, currentSeat);
            window.location.href = `/room/${matchedRoomId}`;
        }

        function showMatchedTransition(opponentName) {
            ModalUtils.showSuccessModal({
                title: "匹配成功",
                body: `已为你匹配到对手 ${opponentName || "未知对手"}，正在为你进入房间……`,
                buttonText: "立即进入",
                onClose: async () => {
                    await goToMatchedRoom();
                }
            });
        }

        function getOpponentNameFromMatchedData(data) {
            if (data.seat === "p1") {
                return data.p2_name || "";
            }
            if (data.seat === "p2") {
                return data.p1_name || "";
            }
            return "";
        }

        function getOpponentNameFromState(state) {
            return state.opponent_name || "";
        }

        function delayedGoToMatchedRoom(opponentName) {
            showMatchedTransition(opponentName);

            window.setTimeout(async () => {
                await goToMatchedRoom();
            }, 1000);
        }

        document.getElementById("join-match-btn").addEventListener("click", () => {
            // 从 session 获取用户名
            var sessionUser = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
            var name = sessionUser ? sessionUser.username : "";
            if (!name) {
                setMatchMessage("登录信息丢失，请重新登录。", "error");
                window.location.href = "/login";
                return;
            }
            setPlayerName(name);
            matchStateController.joinMatchQueue();
        });

        document.getElementById("cancel-match-btn").addEventListener("click", () => {
            matchStateController.cancelMyMatch();
        });
        document.getElementById("resume-room-btn").addEventListener("click", async () => {
            await goToMatchedRoom();
        });

        document.getElementById("resume-continue-btn").addEventListener("click", async () => {
            await goToMatchedRoom();
        });

        document.getElementById("resume-forget-btn").addEventListener("click", () => {
            ModalUtils.showConfirmModal({
                title: "放弃房间入口",
                body: "这只会清除当前浏览器里的恢复入口，不会替你退出服务端房间。确认继续吗？",
                confirmText: "放弃入口",
                cancelText: "取消",
                confirmClassName: "danger",
                onConfirm: () => {
                    clearResumeState();
                    StorageUtils.removeStorage(STORAGE_KEYS.MATCH_IDENTITY);
                    setMatchMessage("已清除本地恢复入口。", "info");
                }
            });
        });

        // 从 session 恢复玩家名称
        var sessionUser = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
        if (sessionUser && sessionUser.username) {
            setPlayerName(sessionUser.username);
        }

        const savedIdentity = StorageUtils.getJsonStorage(STORAGE_KEYS.MATCH_IDENTITY, null);
        if (savedIdentity) {
            try {
                setPlayerToken(savedIdentity.player_token || "");
            } catch (error) {
                console.error(error);
            }
        }

        matchStateController = createMatchStateController({
            ensureMatchIdentity,
            getPlayerName,
            setPlayerName,
            getPlayerToken,
            setPlayerToken,
            getMatchedRoomId,
            setMatchedRoomId,
            getCurrentSeat,
            setCurrentSeat,
            getCurrentRoomPlayerToken,
            setCurrentRoomPlayerToken,
            setJoinedQueue,
            setQueueStatusText,
            setSelfStatusText,
            setMatchMessage,
            applyMatchStatus,
            setQueuedUi,
            setResumeUi,
            renderResumePanel,
            saveRoomIdentity: RoomIdentityStorage.saveRoomIdentity,
            goToMatchedRoom,
            delayedGoToMatchedRoom,
            getOpponentNameFromMatchedData,
            getOpponentNameFromState
        });

        ModalUtils.bindGlobalModalEvents();

        if (typeof io === "function") {
            matchSocket = io();
            matchSocket.on("connect", () => {
                stopMatchFallbackPolling();
                matchSocket.emit("join_match_lobby");
            });
            matchSocket.on("disconnect", startMatchFallbackPolling);
            matchSocket.on("connect_error", startMatchFallbackPolling);
            matchSocket.on("match_status", (data) => {
                if (data && data.ok) {
                    applyMatchStatus(data.status);
                }
            });
        }

        matchStateController.fetchMatchStatus();
        matchStateController.syncMyMatchState();
        if (!matchSocket || !matchSocket.connected) {
            startMatchFallbackPolling();
        }
        ResumeRoomUtils.applyMatchResumeRoomEntry(setResumeUi);
}
