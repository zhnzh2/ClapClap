/**
 * ClapClap 2.0 房间列表页逻辑。
 *
 * 创建/加入 v2 多人房间。
 */
(function () {
    "use strict";

    // ── 创建房间参数 ──
    var createMax = 4;
    var createMin = 2;

    // ── 人数步进器 ──
    document.getElementById("create-max-inc").addEventListener("click", function () {
        if (createMax < 6) { createMax++; syncSteppers(); }
    });
    document.getElementById("create-max-dec").addEventListener("click", function () {
        if (createMax > 2 && createMax > createMin) { createMax--; syncSteppers(); }
    });
    document.getElementById("create-min-inc").addEventListener("click", function () {
        if (createMin < createMax) { createMin++; syncSteppers(); }
    });
    document.getElementById("create-min-dec").addEventListener("click", function () {
        if (createMin > 2) { createMin--; syncSteppers(); }
    });

    function syncSteppers() {
        document.getElementById("create-max").textContent = createMax;
        document.getElementById("create-min").textContent = createMin;
    }

    // ── 创建房间 ──
    document.getElementById("create-room-btn").addEventListener("click", async function () {
        var payload = {
            max_players: createMax,
            min_players: createMin,
            start_condition: document.getElementById("create-start-condition").value,
            allow_spectate: document.getElementById("create-allow-spectate").checked,
        };

        try {
            var result = await ApiUtils.apiPost("/api/v2/rooms", payload);

            if (!result.ok) {
                MessageUtils.setMessage("create-message", result.error || "创建房间失败。", "error");
                return;
            }

            var data = result.data;
            if (!data.player_token) {
                MessageUtils.setMessage("create-message", "创建失败：服务端未返回 player_token。", "error");
                return;
            }

            window.V2RoomIdentity.save(data.room.room_id, data.player_token, data.seat_index);
            window.location.href = "/v2/room/" + data.room.room_id;
        } catch (e) {
            MessageUtils.setMessage("create-message", "创建房间失败：" + e, "error");
        }
    });

    // ── 加入房间 ──
    document.getElementById("join-room-btn").addEventListener("click", async function () {
        var roomId = document.getElementById("join-room-id").value.trim().toUpperCase();
        if (!roomId) {
            MessageUtils.setMessage("join-message", "请先输入房间号。", "error");
            return;
        }

        try {
            var result = await ApiUtils.apiPost("/api/v2/rooms/" + roomId + "/join", {});

            if (!result.ok) {
                MessageUtils.setMessage("join-message", result.error || "加入房间失败。", "error");
                return;
            }

            var data = result.data;
            window.V2RoomIdentity.save(roomId, data.player_token, data.seat_index);
            window.location.href = "/v2/room/" + roomId;
        } catch (e) {
            MessageUtils.setMessage("join-message", "加入房间失败：" + e, "error");
        }
    });

    // ── 回车加入 ──
    document.getElementById("join-room-id").addEventListener("keydown", function (e) {
        if (e.key === "Enter") document.getElementById("join-room-btn").click();
    });
})();
