/**
 * ClapClap 2.0 房间身份存储。
 *
 * 管理 localStorage 中的 v2 房间身份信息。
 * 与 1.0 (room_identity.js) 使用不同 key 前缀，避免冲突。
 */
(function () {
    "use strict";

    var IDENTITY_PREFIX = "clapclap_v2_room_";

    window.V2RoomIdentity = {
        /** 保存 v2 房间身份 */
        save: function (roomId, playerToken, seatIndex) {
            try {
                localStorage.setItem(
                    IDENTITY_PREFIX + roomId,
                    JSON.stringify({
                        player_token: playerToken,
                        seat_index: seatIndex,
                        saved_at: new Date().toISOString(),
                    })
                );
            } catch (e) {
                // localStorage 不可用，忽略
            }
        },

        /** 加载 v2 房间身份，不存在则返回 null */
        load: function (roomId) {
            try {
                var raw = localStorage.getItem(IDENTITY_PREFIX + roomId);
                if (!raw) return null;
                return JSON.parse(raw);
            } catch (e) {
                return null;
            }
        },

        /** 删除单个 v2 房间身份 */
        remove: function (roomId) {
            try {
                localStorage.removeItem(IDENTITY_PREFIX + roomId);
            } catch (e) {
                // 忽略
            }
        },

        /** 清除所有 v2 房间身份 */
        clearAll: function () {
            try {
                var keysToRemove = [];
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    if (key && key.indexOf(IDENTITY_PREFIX) === 0) {
                        keysToRemove.push(key);
                    }
                }
                keysToRemove.forEach(function (k) { localStorage.removeItem(k); });
            } catch (e) {
                // 忽略
            }
        },
    };
})();
