(function () {
    function createMatchStateController(options) {
        const {
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
            applyMatchStatus = null,
            setQueuedUi,
            setResumeUi,
            renderResumePanel = null,
            saveRoomIdentity,
            goToMatchedRoom,
            delayedGoToMatchedRoom,
            getOpponentNameFromMatchedData,
            getOpponentNameFromState
        } = options;

        async function joinMatchQueue() {
            const playerName = (getPlayerName() || "").trim();

            if (!playerName) {
                setMatchMessage("请先输入昵称。", "error");
                return;
            }

            const matchToken = ensureMatchIdentity(playerName);
            setPlayerToken(matchToken);

            const result = await ApiUtils.apiPost("/api/match/join", {
                player_name: playerName,
                player_token: matchToken
            });

            if (!result.ok) {
                setMatchMessage(result.error || "加入匹配失败。", "error");
                return;
            }

            const data = result.data;

            if (data.matched) {
                setJoinedQueue(false);
                setMatchedRoomId(data.room_id);
                setCurrentSeat(data.seat);
                setCurrentRoomPlayerToken(data.room_player_token || "");

                if (!data.room_player_token) {
                    setMatchMessage("匹配成功，但服务端没有返回 room_player_token。", "error");
                    return;
                }

                saveRoomIdentity(data.room_id, data.room_player_token, data.seat);

                const opponentName = getOpponentNameFromMatchedData(data);

                setMatchMessage(data.message || "匹配成功，正在进入房间……", "success");
                setSelfStatusText("你已匹配成功，正在准备进入房间。");
                setQueuedUi(false);
                setResumeUi(true);
                if (typeof renderResumePanel === "function") {
                    renderResumePanel(opponentName);
                }

                delayedGoToMatchedRoom(opponentName, data.seat);
                return;
            }

            setJoinedQueue(true);
            setMatchMessage(
                data.already_queued
                    ? "你已经在匹配队列中，请等待另一位玩家。"
                    : (data.message || "已进入匹配队列。"),
                "waiting"
            );
            setSelfStatusText("你已在匹配队列中，正在等待另一位玩家。");
            setQueuedUi(true);
            setResumeUi(false);
        }

        async function fetchMatchStatus() {
            if (getMatchedRoomId()) {
                return;
            }

            const result = await ApiUtils.apiGet("/api/match/status");
            if (!result.ok) {
                setQueueStatusText("匹配状态获取失败。");
                return;
            }

            const status = result.data.status;

            if (typeof applyMatchStatus === "function") {
                applyMatchStatus(status);
                return;
            }

            setQueueStatusText(
                status.has_waiting_player
                    ? `当前有玩家正在等待：${status.waiting_player}`
                    : "当前没有玩家在等待。"
            );
        }

        async function syncMyMatchState() {
            const playerToken = getPlayerToken();
            if (!playerToken) {
                return;
            }

            const result = await ApiUtils.apiGet(
                `/api/match/me?player_token=${encodeURIComponent(playerToken)}`
            );

            if (!result.ok) {
                return;
            }

            const state = result.data.state;

            if (state.status === "matched" && state.room_id && state.seat) {
                setJoinedQueue(false);
                setMatchedRoomId(state.room_id);
                setCurrentSeat(state.seat);
                setCurrentRoomPlayerToken(state.room_player_token || "");

                if (!state.room_player_token) {
                    setMatchMessage("你已匹配到房间，但缺少 room_player_token，暂时无法恢复。", "error");
                    return;
                }

                saveRoomIdentity(state.room_id, state.room_player_token, state.seat);

                setMatchMessage("你已经匹配到房间，正在为你恢复对局入口……", "info");
                setSelfStatusText(`你已匹配成功，座位为 ${state.seat.toUpperCase()}。`);
                setQueuedUi(false);
                setResumeUi(true);
                if (typeof renderResumePanel === "function") {
                    renderResumePanel(getOpponentNameFromState(state));
                }

                delayedGoToMatchedRoom(getOpponentNameFromState(state), state.seat);
                return;
            }

            if (state.status === "queued") {
                setJoinedQueue(true);
                setSelfStatusText("你已在匹配队列中，正在等待另一位玩家。");
                setQueuedUi(true);
                setResumeUi(false);
                return;
            }

            setJoinedQueue(false);
            setQueuedUi(false);
        }

        async function cancelMyMatch() {
            const playerToken = getPlayerToken();
            if (!playerToken) {
                return;
            }

            const result = await ApiUtils.apiPost("/api/match/cancel", {
                player_token: playerToken
            });

            if (!result.ok) {
                setMatchMessage(result.error || "取消匹配失败。", "error");
                return;
            }

            const data = result.data;

            setJoinedQueue(false);
            setMatchedRoomId(null);
            setCurrentSeat(null);
            setCurrentRoomPlayerToken("");

            setMatchMessage(data.message || "已取消匹配。", "info");
            setSelfStatusText("你当前尚未加入匹配队列。");
            setQueuedUi(false);
            setResumeUi(false);
        }

        async function fetchMyMatchResult() {
            const playerToken = getPlayerToken();
            const playerName = getPlayerName();

            if (!playerToken || !playerName || getMatchedRoomId()) {
                return;
            }

            const result = await ApiUtils.apiGet(
                `/api/match/result?player_token=${encodeURIComponent(playerToken)}`
            );

            if (!result.ok) {
                return;
            }

            const data = result.data;

            if (data.matched && data.room_id) {
                setMatchedRoomId(data.room_id);
                saveRoomIdentity(data.room_id, data.player_token, data.seat);
                setMatchMessage("匹配成功，正在跳转房间……", "success");
                window.location.href = `/room/${data.room_id}`;
            }
        }

        return {
            joinMatchQueue,
            fetchMatchStatus,
            syncMyMatchState,
            cancelMyMatch,
            fetchMyMatchResult
        };
    }

    window.createMatchStateController = createMatchStateController;
})();
