(() => {
        let joinedQueue = false;
        let matchedRoomId = null;
        let currentPlayerName = "";
        let currentMatchToken = "";
        let currentRoomPlayerToken = "";
        let currentSeat = null;

        function ensureMatchIdentity(playerName) {
            const raw = localStorage.getItem("clapclap_match_identity");
            if (raw) {
                try {
                    const parsed = JSON.parse(raw);
                    if (parsed.player_name === playerName && parsed.player_token) {
                        return parsed.player_token;
                    }
                } catch (error) {
                    console.error(error);
                }
            }

            const token = crypto.randomUUID().replaceAll("-", "");
            localStorage.setItem(
                "clapclap_match_identity",
                JSON.stringify({
                    player_name: playerName,
                    player_token: token
                })
            );
            return token;
        }

        async function readJsonSafely(res) {
            const contentType = res.headers.get("content-type") || "";
            const text = await res.text();

            if (contentType.includes("application/json")) {
                try {
                    return {
                        ok: true,
                        data: JSON.parse(text),
                        rawText: text
                    };
                } catch (error) {
                    return {
                        ok: false,
                        error: `JSON 解析失败：${error}`,
                        rawText: text
                    };
                }
            }

            return {
                ok: false,
                error: `服务端返回的不是 JSON，而是：${contentType || "未知类型"}`,
                rawText: text
            };
        }

        function saveRoomIdentity(roomId, playerToken, seat) {
            localStorage.setItem(
                `clapclap_room_${roomId}`,
                JSON.stringify({
                    player_token: playerToken,
                    seat: seat
                })
            );
        }

        function clearRoomIdentity(roomId) {
            localStorage.removeItem(`clapclap_room_${roomId}`);
        }

        function setJoiningUi(isJoining) {
            document.getElementById("join-match-btn").disabled = isJoining;
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

            try {
                const res = await fetch(
                    `/api/rooms/${matchedRoomId}?player_token=${encodeURIComponent(currentRoomPlayerToken)}`
                );
                const parsed = await readJsonSafely(res);

                if (!parsed.ok || !res.ok || !parsed.data.ok) {
                    clearRoomIdentity(matchedRoomId);
                    matchedRoomId = null;
                    currentSeat = null;
                    currentRoomPlayerToken = "";
                    joinedQueue = false;

                    setMatchMessage(data.error || "检测到旧房间已失效，已清除无效恢复状态，请重新匹配。", "error");
                    document.getElementById("self-status").textContent =
                        "你当前尚未加入匹配队列。";

                    setQueuedUi(false);
                    setResumeUi(false);
                    hideMatchedTransition();
                    return;
                }

                saveRoomIdentity(matchedRoomId, currentRoomPlayerToken, currentSeat);
                window.location.href = `/room/${matchedRoomId}`;
            } catch (error) {
                setMatchMessage("恢复房间失败：" + error, "error");
            }
        }

        function clearFrontendCacheForNewBoot() {
            const savedBootId = localStorage.getItem("clapclap_server_boot_id");

            if (savedBootId === SERVER_BOOT_ID) {
                return false;
            }

            localStorage.clear();
            sessionStorage.clear();
            localStorage.setItem("clapclap_server_boot_id", SERVER_BOOT_ID);
            return true;
        }

        function showMatchedTransition(opponentName, seat) {
            document.getElementById("matched-opponent-chip").textContent =
                `对手：${opponentName || "已匹配玩家"}`;
            document.getElementById("matched-seat-chip").textContent =
                `座位：${(seat || "").toUpperCase()}`;
            document.getElementById("matched-room-chip").textContent =
                `房间：${matchedRoomId || "加载中"}`;
            document.getElementById("match-success-subtitle").textContent =
                "已完成匹配，正在同步房间身份、恢复座位并准备进入对战房间……";
            document.getElementById("match-success-countdown").textContent =
                "正在进入房间……";
            document.getElementById("match-success-mask").classList.add("show");
        }

        function hideMatchedTransition() {
            document.getElementById("match-success-mask").classList.remove("show");
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

        function delayedGoToMatchedRoom(opponentName, seat) {
            showMatchedTransition(opponentName, seat);

            window.setTimeout(async () => {
                await goToMatchedRoom();
            }, 300);
        }

        function setMatchMessage(text, type = "info") {
            const el = document.getElementById("match-message");
            if (!el) return;
            el.className = `message ${type}`;
            el.textContent = text || "";
        }

        function setQueueStatusMessage(text, type = "info") {
            const el = document.getElementById("queue-status");
            if (!el) return;
            el.textContent = text || "";
        }

        async function joinMatchQueue() {
            const playerName = document.getElementById("player-name").value.trim();
            const msg = document.getElementById("match-message");
            const selfStatus = document.getElementById("self-status");

            if (!playerName) {
                msg.textContent = "请先输入昵称。";
                return;
            }
            currentMatchToken = ensureMatchIdentity(playerName);

            try {
                const res = await fetch("/api/match/join", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        player_name: playerName,
                        player_token: currentMatchToken
                    })
                });

                const parsed = await readJsonSafely(res);

                if (!parsed.ok) {
                    console.error("join /api/match/join 非 JSON 响应：", parsed.rawText);
                    msg.textContent =
                        `加入匹配失败：${parsed.error}；HTTP ${res.status}`;
                    return;
                }

                const data = parsed.data;

                if (!res.ok || !data.ok) {
                    msg.textContent = data.error || "加入匹配失败。";
                    return;
                }

                if (data.matched) {
                    matchedRoomId = data.room_id;
                    currentSeat = data.seat;
                    currentRoomPlayerToken = data.room_player_token || "";

                    if (!currentRoomPlayerToken) {
                        msg.textContent = "匹配成功，但服务端没有返回 room_player_token。";
                        return;
                    }

                    saveRoomIdentity(data.room_id, currentRoomPlayerToken, currentSeat);

                    const opponentName = getOpponentNameFromMatchedData(data);

                    msg.textContent = data.message || "匹配成功，正在进入房间……";
                    selfStatus.textContent = "你已匹配成功，正在准备进入房间。";
                    setQueuedUi(false);
                    setResumeUi(true);

                    delayedGoToMatchedRoom(opponentName, currentSeat);
                    return;
                }

                joinedQueue = true;
                msg.textContent = data.already_queued
                    ? "你已经在匹配队列中，请等待另一位玩家。"
                    : (data.message || "已进入匹配队列。");
                selfStatus.textContent = "你已在匹配队列中，正在等待另一位玩家。";
                setQueuedUi(true);
                setResumeUi(false);
            } catch (error) {
                msg.textContent = "加入匹配失败：" + error;
            }
        }

        async function fetchMatchStatus() {
            if (matchedRoomId) {
                return;
            }

            try {
                const res = await fetch("/api/match/status");
                const parsed = await readJsonSafely(res);
                if (!parsed.ok) {
                    // 按各自函数场景处理
                    return;
                }
                const data = parsed.data;

                if (!res.ok || !data.ok) {
                    document.getElementById("queue-status").textContent = "匹配状态获取失败。";
                    return;
                }

                const status = data.status;

                if (status.has_waiting_player) {
                    document.getElementById("queue-status").textContent =
                        `当前有玩家正在等待：${status.waiting_player}`;
                } else {
                    document.getElementById("queue-status").textContent =
                        "当前没有玩家在等待。";
                }
            } catch (error) {
                document.getElementById("queue-status").textContent =
                    "匹配状态获取失败：" + error;
            }
        }

        async function syncMyMatchState() {
            if (!currentMatchToken) {
                return;
            }

            try {
                const res = await fetch(
                    `/api/match/me?player_token=${encodeURIComponent(currentMatchToken)}`
                );
                const parsed = await readJsonSafely(res);
                if (!parsed.ok) {
                    // 按各自函数场景处理
                    return;
                }
                const data = parsed.data;

                if (!res.ok || !data.ok) {
                    return;
                }

                const state = data.state;

                if (state.status === "matched" && state.room_id && state.seat) {
                    joinedQueue = false;
                    matchedRoomId = state.room_id;
                    currentSeat = state.seat;
                    currentRoomPlayerToken = state.room_player_token || "";

                    if (!currentRoomPlayerToken) {
                        setMatchMessage("你已匹配到房间，但缺少 room_player_token，暂时无法恢复。", "error");
                        return;
                    }

                    saveRoomIdentity(state.room_id, currentRoomPlayerToken, state.seat);

                    setMatchMessage("你已经匹配到房间，正在为你恢复对局入口……", "success");
                    document.getElementById("self-status").textContent =
                        `你已匹配成功，座位为 ${state.seat.toUpperCase()}。`;

                    setQueuedUi(false);
                    setResumeUi(true);

                    delayedGoToMatchedRoom(getOpponentNameFromState(state), state.seat);
                    return;
                }

                if (state.status === "queued") {
                    joinedQueue = true;
                    document.getElementById("self-status").textContent =
                        "你已在匹配队列中，正在等待另一位玩家。";
                    setQueuedUi(true);
                    setResumeUi(false);
                    return;
                }

                joinedQueue = false;
                setQueuedUi(false);
            } catch (error) {
                console.error("syncMyMatchState error:", error);
            }
        }

        async function cancelMyMatch() {
            if (!currentMatchToken) {
                return;
            }

            try {
                const res = await fetch("/api/match/cancel", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        player_token: currentMatchToken
                    })
                });

                const parsed = await readJsonSafely(res);
                if (!parsed.ok) {
                    // 按各自函数场景处理
                    return;
                }
                const data = parsed.data;

                if (!res.ok || !data.ok) {
                    setMatchMessage(data.error || "取消匹配失败。", "error");
                    return;
                }

                joinedQueue = false;
                matchedRoomId = null;
                currentSeat = null;

                setMatchMessage(data.message || "已取消匹配。", "success");
                document.getElementById("self-status").textContent =
                    "你当前尚未加入匹配队列。";

                setQueuedUi(false);
                setResumeUi(false);
            } catch (error) {
                setMatchMessage("取消匹配失败：" + error, "error");
            }
        }

        async function fetchMyMatchResult() {
            if (!joinedQueue || matchedRoomId || !currentPlayerName) {
                return;
            }

            try {
                const res = await fetch(
                    `/api/match/result?player_token=${encodeURIComponent(currentMatchToken)}`
                );
                const parsed = await readJsonSafely(res);
                if (!parsed.ok) {
                    // 按各自函数场景处理
                    return;
                }
                const data = parsed.data;

                if (!res.ok || !data.ok) {
                    return;
                }

                if (data.matched && data.room_id) {
                    matchedRoomId = data.room_id;
                    saveRoomIdentity(data.room_id, data.player_token, data.seat);
                    setMatchMessage("匹配成功，正在跳转房间……", "waiting");
                    window.location.href = `/room/${data.room_id}`;
                }
            } catch (error) {
                console.error("fetchMyMatchResult error:", error);
            }
        }

        document.getElementById("join-match-btn").addEventListener("click", joinMatchQueue);
        document.getElementById("cancel-match-btn").addEventListener("click", cancelMyMatch);
        document.getElementById("resume-room-btn").addEventListener("click", async () => {
            await goToMatchedRoom();
        });

        const savedIdentityRaw = localStorage.getItem("clapclap_match_identity");
        if (savedIdentityRaw) {
            try {
                const savedIdentity = JSON.parse(savedIdentityRaw);
                currentPlayerName = savedIdentity.player_name || "";
                currentMatchToken = savedIdentity.player_token || "";
                if (currentPlayerName) {
                    document.getElementById("player-name").value = currentPlayerName;
                }
            } catch (error) {
                console.error(error);
            }
        }

        fetchMatchStatus();
        syncMyMatchState();

        setInterval(() => {
            fetchMatchStatus();
            syncMyMatchState();
        }, 1000);
})();