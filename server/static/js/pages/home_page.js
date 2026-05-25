window.initHomePage = function () {
    const SERVER_BOOT_ID = window.SERVER_BOOT_ID || "";

    BootUtils.handleServerBootChange(SERVER_BOOT_ID);
    ResumeRoomUtils.applyHomeResumeRoomEntry({
        buttonId: "match-mode-btn",
        descId: "match-mode-desc",
        badgeId: "match-mode-badge"
    });
};