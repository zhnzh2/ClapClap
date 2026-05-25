function saveRoomIdentity(roomId, playerToken, seat) {
    StorageUtils.setJsonStorage(
        STORAGE_KEYS.roomIdentity(roomId),
        {
            player_token: playerToken,
            seat: seat
        }
    );
}

function loadRoomIdentity(roomId) {
    return StorageUtils.getJsonStorage(STORAGE_KEYS.roomIdentity(roomId), null);
}

function removeRoomIdentity(roomId) {
    StorageUtils.removeStorage(STORAGE_KEYS.roomIdentity(roomId));
}

function removeAllRoomIdentity() {
    const keysToDelete = [];

    for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (!key) {
            continue;
        }

        if (
            key.startsWith("clapclap_room_") &&
            !key.startsWith("clapclap_room_ui_settings_")
        ) {
            keysToDelete.push(key);
        }
    }

    keysToDelete.forEach((key) => localStorage.removeItem(key));
}

window.RoomIdentityStorage = {
    saveRoomIdentity,
    loadRoomIdentity,
    removeRoomIdentity,
    removeAllRoomIdentity
};