window.initMatchPage = function () {
        let joinedQueue = false;
        let matchedRoomId = null;
        let currentPlayerName = "";
        let currentMatchToken = "";
        let currentRoomPlayerToken = "";
        let currentSeat = null;
        let matchStateController = null;

        if (window.SERVER_BOOT_ID) {
            const bootResult = BootUtils.handleServerBootChange(window.SERVER_BOOT_ID);

            if (bootResult.changed) {
                setMatchMessage("检测到服务已重启，之前保存的匹配与房间缓存已自动清除。", "info");
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
        }

        async function goToMatchedRoom() {
            if (!matchedRoomId || !currentSeat || !currentRoomPlayerToken) {
                return;
            }

            const result = await ApiUtils.apiGet(
                `/api/rooms/${matchedRoomId}?player_token=${encodeURIComponent(currentRoomPlayerToken)}`
            );

            if (!result.ok) {
                RoomIdentityStorage.removeRoomIdentity(matchedRoomId);
                setMatchedRoomId(null);
                setCurrentSeat(null);
                setCurrentRoomPlayerToken("");
                setJoinedQueue(false);

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
            setPlayerName(document.getElementById("player-name").value.trim());
            matchStateController.joinMatchQueue();
        });

        document.getElementById("cancel-match-btn").addEventListener("click", () => {
            matchStateController.cancelMyMatch();
        });
        document.getElementById("resume-room-btn").addEventListener("click", async () => {
            await goToMatchedRoom();
        });

        const savedIdentity = StorageUtils.getJsonStorage(STORAGE_KEYS.MATCH_IDENTITY, null);
        if (savedIdentity) {
            try {
                setPlayerName(savedIdentity.player_name || "");
                setPlayerToken(savedIdentity.player_token || "");
                if (currentPlayerName) {
                    document.getElementById("player-name").value = getPlayerName();
                }
            } catch (error) {
                console.error(error);
            }
        }

        matchStateController.fetchMatchStatus();
        matchStateController.syncMyMatchState();
        ResumeRoomUtils.applyMatchResumeRoomEntry(setResumeUi);

        setInterval(() => {
            matchStateController.fetchMatchStatus();
            matchStateController.syncMyMatchState();
        }, 1000);

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
            setQueuedUi,
            setResumeUi,
            saveRoomIdentity: RoomIdentityStorage.saveRoomIdentity,
            goToMatchedRoom,
            delayedGoToMatchedRoom,
            getOpponentNameFromMatchedData,
            getOpponentNameFromState
        });
}