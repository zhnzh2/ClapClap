(function () {

    async function createRoom() {
        const playerName = document.getElementById("create-name").value.trim();

        if (!playerName) {
            MessageUtils.setMessage("create-message", "请先输入昵称。", "error");
            return;
        }

        try {
            const result = await ApiUtils.apiPost("/api/rooms", {
                player_name: playerName
            });

            if (!result.ok) {
                MessageUtils.setMessage("create-message", result.error || "创建房间失败。", "error");
                return;
            }

            const data = result.data;

            if (!data.player_token) {
                MessageUtils.setMessage("create-message", "创建房间失败：服务端没有返回 player_token。", "error");
                return;
            }

            RoomIdentityStorage.saveRoomIdentity(data.room.room_id, data.player_token, data.seat);
            MessageUtils.setMessage("create-message", `房间创建成功，房间号：${data.room.room_id}`, "success");
            window.location.href = `/room/${data.room.room_id}`;
        } catch (error) {
            MessageUtils.setMessage("create-message", "创建房间失败：" + error, "error");
        }
    }

    async function joinRoom() {
        const playerName = document.getElementById("join-name").value.trim();
        const roomId = document.getElementById("join-room-id").value.trim().toUpperCase();

        if (!playerName || !roomId) {
            MessageUtils.setMessage("join-message", "请先输入昵称和房间号。", "error");
            return;
        }

        try {
            const result = await ApiUtils.apiPost(`/api/rooms/${roomId}/join`, {
                player_name: playerName
            });

            if (!result.ok) {
                MessageUtils.setMessage("join-message", result.error || "加入房间失败。", "error");
                return;
            }

            const data = result.data;

            RoomIdentityStorage.saveRoomIdentity(roomId, data.player_token, data.seat);
            MessageUtils.setMessage("join-message", `加入成功，你的位置是 ${data.seat}`, "success");
            window.location.href = `/room/${roomId}`;
        } catch (error) {
            MessageUtils.setMessage("join-message", "加入房间失败：" + error, "error");
        }
    }

    document.getElementById("create-room-btn").addEventListener("click", createRoom);
    document.getElementById("join-room-btn").addEventListener("click", joinRoom);
})();