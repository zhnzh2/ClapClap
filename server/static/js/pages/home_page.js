window.initHomePage = function () {
    // 未登录则跳转到登录页
    if (!window.SessionUtils || !window.SessionUtils.isLoggedIn()) {
        window.location.href = "/login?expired=1";
        return;
    }

    const SERVER_BOOT_ID = window.SERVER_BOOT_ID || "";

    // 右上角账号按钮
    var accountBtn = document.getElementById("header-account-btn");
    if (accountBtn) {
        var sessionUser = window.SessionUtils.getSessionUser();
        if (sessionUser) {
            accountBtn.textContent = sessionUser.username;
            accountBtn.addEventListener("click", function () {
                window.location.href = "/user/" + sessionUser.uid;
            });
        }
    }

    BootUtils.handleServerBootChange(SERVER_BOOT_ID);
    ResumeRoomUtils.applyHomeResumeRoomEntry({
        buttonId: "match-mode-btn",
        descId: "match-mode-desc",
        badgeId: "match-mode-badge"
    });

    async function applyModeStatus() {
        if (!window.ApiUtils) {
            return;
        }

        const result = await ApiUtils.apiGet("/api/modes/status");
        if (!result.ok) {
            return;
        }

        const modes = result.data.modes || {};
        const mapping = {
            rooms: {
                badgeId: "rooms-mode-badge",
                descId: "rooms-mode-desc"
            },
            match: {
                badgeId: "match-mode-badge",
                descId: "match-mode-desc"
            },
            ai: {
                badgeId: "ai-mode-badge",
                descId: "ai-mode-desc"
            }
        };

        Object.keys(mapping).forEach((key) => {
            const mode = modes[key];
            if (!mode) {
                return;
            }

            const badge = document.getElementById(mapping[key].badgeId);
            const desc = document.getElementById(mapping[key].descId);

            if (badge) {
                badge.textContent = mode.label || badge.textContent;
                badge.classList.toggle("muted-badge", mode.status !== "available");
            }

            if (desc) {
                desc.textContent = mode.description || desc.textContent;
            }
        });
    }

    applyModeStatus();
};
