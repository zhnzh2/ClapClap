// ClapClap 房间对战 — 共享数据常量
(function () {
    window.CLAPCLAP_MOVE_GROUPS = {
        resource_defense: ["QI", "SHIELD", "SHI_ZI", "BA_GUA"],
        attack_qi: ["GI", "PO", "LENG_FENG", "RU_LAI", "HEI_DONG"],
        attack_shield: ["FIRE", "SHAN_DIAN", "LIE_YAN", "SHINING"],
        trick: ["CHI", "SHUANG_CHI", "SHAN", "GAO"]
    };

    window.CLAPCLAP_MOVE_SHORTCUTS = {
        "chi": "1", "shuang_chi": "2", "shan": "3", "gao": "4",
        "qi": "Q", "shield": "W", "shi_zi": "E", "ba_gua": "R",
        "gi": "A", "po": "S", "leng_feng": "D", "ru_lai": "F", "hei_dong": "G",
        "fire": "Z", "shan_dian": "X", "lie_yan": "C", "shining": "V"
    };

    window.CLAPCLAP_KEY_TO_MOVE_NAME = {
        "1": "chi", "2": "shuang_chi", "3": "shan", "4": "gao",
        "q": "qi", "w": "shield", "e": "shi_zi", "r": "ba_gua",
        "a": "gi", "s": "po", "d": "leng_feng", "f": "ru_lai", "g": "hei_dong",
        "z": "fire", "x": "shan_dian", "c": "lie_yan", "v": "shining"
    };

    window.CLAPCLAP_DEFAULT_ROOM_UI_SETTINGS = {
        showRoomInfo: false,
        showRoomStatus: false,
        showInvite: false,
        showRoundResult: false,
        showHistory: true,
        showMoveSubtitles: false,
        playerStateMode: "compact",
        revealAdvanceMode: "auto"
    };
})();
