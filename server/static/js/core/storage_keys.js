window.STORAGE_KEYS = {
    SERVER_BOOT_ID: "clapclap_server_boot_id",
    MATCH_IDENTITY: "clapclap_match_identity",
    MATCH_STATE: "clapclap_match_state",

    roomIdentity(roomId) {
        return `clapclap_room_${roomId}`;
    },

    roomUiSettings(roomId) {
        return `clapclap_room_ui_settings_${roomId}`;
    }
};