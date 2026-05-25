function getJsonStorage(key, fallback = null) {
    try {
        const raw = localStorage.getItem(key);
        if (!raw) {
            return fallback;
        }
        return JSON.parse(raw);
    } catch (error) {
        console.error("getJsonStorage error:", key, error);
        return fallback;
    }
}

function setJsonStorage(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
}

function removeStorage(key) {
    localStorage.removeItem(key);
}

function clearStorageByPrefix(prefix) {
    const keysToDelete = [];

    for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (!key) {
            continue;
        }
        if (key.startsWith(prefix)) {
            keysToDelete.push(key);
        }
    }

    keysToDelete.forEach((key) => localStorage.removeItem(key));
}

function clearAllClapClapStorage() {
    const keysToDelete = [];

    for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (!key) {
            continue;
        }

        if (
            key === STORAGE_KEYS.SERVER_BOOT_ID ||
            key === STORAGE_KEYS.MATCH_IDENTITY ||
            key === STORAGE_KEYS.MATCH_STATE ||
            key.startsWith("clapclap_room_") ||
            key.startsWith("clapclap_room_ui_settings_")
        ) {
            keysToDelete.push(key);
        }
    }

    keysToDelete.forEach((key) => localStorage.removeItem(key));
}

function getLatestRoomIdentityFromStorage() {
    let latestRoom = null;

    for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (!key) {
            continue;
        }

        if (!key.startsWith("clapclap_room_")) {
            continue;
        }

        if (key.startsWith("clapclap_room_ui_settings_")) {
            continue;
        }

        const roomId = key.slice("clapclap_room_".length);
        const parsed = getJsonStorage(key, null);

        if (!parsed || !parsed.player_token) {
            continue;
        }

        latestRoom = {
            roomId,
            player_token: parsed.player_token,
            seat: parsed.seat || null
        };
    }

    return latestRoom;
}

window.StorageUtils = {
    getJsonStorage,
    setJsonStorage,
    removeStorage,
    clearStorageByPrefix,
    clearAllClapClapStorage,
    getLatestRoomIdentityFromStorage
};