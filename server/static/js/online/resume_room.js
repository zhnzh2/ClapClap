(function () {
    function getLatestResumeRoom() {
        return StorageUtils.getLatestRoomIdentityFromStorage();
    }

    function hasResumeRoom() {
        const latestRoom = getLatestResumeRoom();
        return !!(latestRoom && latestRoom.roomId);
    }

    function clearAllRoomRuntimeCache() {
        RoomIdentityStorage.removeAllRoomIdentity();
        StorageUtils.clearStorageByPrefix("clapclap_room_ui_settings_");
        StorageUtils.removeStorage(STORAGE_KEYS.MATCH_IDENTITY);
        StorageUtils.removeStorage(STORAGE_KEYS.MATCH_STATE);
    }

    function applyHomeResumeRoomEntry(config = {}) {
        const {
            buttonId = "match-mode-btn",
            descId = "match-mode-desc",
            badgeId = "match-mode-badge"
        } = config;

        const latestRoom = getLatestResumeRoom();
        if (!latestRoom || !latestRoom.roomId) {
            return;
        }

        const btnEl = document.getElementById(buttonId);
        const descEl = document.getElementById(descId);
        const badgeEl = document.getElementById(badgeId);

        if (descEl) {
            descEl.textContent = "检测到你仍有一个未退出的房间，可以直接回到该房间继续游戏。";
        }

        if (btnEl) {
            btnEl.textContent = "返回房间";
            btnEl.href = `/room/${latestRoom.roomId}`;
        }

        if (badgeEl) {
            badgeEl.textContent = "可继续";
            badgeEl.classList.remove("muted-badge");
        }
    }

    function applyMatchResumeRoomEntry(setResumeUi) {
        const latestRoom = getLatestResumeRoom();
        if (!latestRoom || !latestRoom.roomId) {
            return;
        }

        if (typeof setResumeUi === "function") {
            setResumeUi(true);
        }
    }

    window.ResumeRoomUtils = {
        getLatestResumeRoom,
        hasResumeRoom,
        clearAllRoomRuntimeCache,
        applyHomeResumeRoomEntry,
        applyMatchResumeRoomEntry
    };
})();