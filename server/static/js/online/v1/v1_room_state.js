(function () {
    function createRoomStateController(options) {
        const {
            getMySeat,
            getRoomUiSettings,
            moveLabel,
            showResolvedPreview,
            highlightResolvedPreviewButtons,
            clearMoveSelection,
            renderRoom,
            setRoomMessage
        } = options;

        let latestRoom = null;
        let roundResolvePreview = null;
        let resolvePreviewTimer = null;
        let waitingManualRevealAdvance = false;
        let resolvePreviewRoundNumber = null;
        let lastResolvedHistoryLength = 0;
        let latestRoomUpdatedAt = "";

        function getLatestRoom() {
            return latestRoom;
        }

        function getRoundResolvePreview() {
            return roundResolvePreview;
        }

        function isWaitingManualRevealAdvance() {
            return waitingManualRevealAdvance;
        }

        function getResolvePreviewRoundNumber() {
            return resolvePreviewRoundNumber;
        }

        function buildResolvedPreviewFromRoom(room) {
            const history = room?.game?.history || [];
            if (!Array.isArray(history) || history.length === 0) {
                return null;
            }

            const lastLog = history[history.length - 1];
            if (!lastLog) {
                return null;
            }

            return {
                p1_move: lastLog.p1_move || null,
                p2_move: lastLog.p2_move || null
            };
        }

        function setLatestRoom(room) {
            latestRoomUpdatedAt = room?.updated_at || latestRoomUpdatedAt;
            latestRoom = room;
        }

        function clearResolvePreviewTimer() {
            if (resolvePreviewTimer) {
                window.clearTimeout(resolvePreviewTimer);
                resolvePreviewTimer = null;
            }
        }

        function startResolvedPreview(room, preview = null) {
            roundResolvePreview = preview || buildResolvedPreviewFromRoom(room);
            resolvePreviewRoundNumber = Array.isArray(room?.game?.history)
                ? room.game.history.length
                : null;

            renderRoom(room);

            if (roundResolvePreview) {
                showResolvedPreview(roundResolvePreview, room);
                highlightResolvedPreviewButtons(roundResolvePreview);
            }

            clearResolvePreviewTimer();

            if ((getRoomUiSettings()?.revealAdvanceMode || "auto") === "manual") {
                waitingManualRevealAdvance = true;
                setRoomMessage("本回合动作已展示。按任意键或点击任意位置进入下一回合。", "waiting");
            } else {
                waitingManualRevealAdvance = false;
                resolvePreviewTimer = window.setTimeout(() => {
                    finishResolvedPreview(room);
                }, 1000);
            }
        }

        function finishResolvedPreview(room) {
            roundResolvePreview = null;
            waitingManualRevealAdvance = false;
            resolvePreviewRoundNumber = null;

            const history = room?.game?.history || [];
            lastResolvedHistoryLength = Array.isArray(history) ? history.length : 0;

            clearMoveSelection();
            renderRoom(room);
        }

        function handleResolvedSubmitResult(room, preview = null, successMessage = "本回合已结算。") {
            startResolvedPreview(room, preview);
            setRoomMessage(successMessage, "success");
        }

        function applyIncomingRoomState(room) {
            const incomingUpdatedAt = room?.updated_at || "";
            if (latestRoomUpdatedAt && incomingUpdatedAt && incomingUpdatedAt < latestRoomUpdatedAt) {
                return {
                    handledResolvedPreview: false,
                    ignoredStale: true
                };
            }
            latestRoomUpdatedAt = incomingUpdatedAt || latestRoomUpdatedAt;
            latestRoom = room;

            const historyLength = Array.isArray(room?.game?.history) ? room.game.history.length : 0;
            const bothPendingCleared = !room?.pending_p1_move && !room?.pending_p2_move;
            const hasNewResolvedRound =
                bothPendingCleared &&
                historyLength > 0 &&
                historyLength > lastResolvedHistoryLength;

            if (hasNewResolvedRound) {
                startResolvedPreview(room);
                return {
                    handledResolvedPreview: true
                };
            }

            renderRoom(room);
            return {
                handledResolvedPreview: false
            };
        }

        function handleManualAdvanceIfNeeded() {
            if (!waitingManualRevealAdvance || !latestRoom) {
                return false;
            }

            finishResolvedPreview(latestRoom);
            return true;
        }

        function markResolvedHistoryAsRendered(room) {
            const history = room?.game?.history || [];
            lastResolvedHistoryLength = Array.isArray(history) ? history.length : 0;
        }

        return {
            getLatestRoom,
            getRoundResolvePreview,
            isWaitingManualRevealAdvance,
            getResolvePreviewRoundNumber,
            setLatestRoom,
            buildResolvedPreviewFromRoom,
            clearResolvePreviewTimer,
            startResolvedPreview,
            finishResolvedPreview,
            handleResolvedSubmitResult,
            applyIncomingRoomState,
            handleManualAdvanceIfNeeded,
            markResolvedHistoryAsRendered
        };
    }

    window.createRoomStateController = createRoomStateController;
})();
