(function () {
    function getSettingsStorageKey(roomId) {
        return STORAGE_KEYS.roomUiSettings(roomId);
    }

    function loadSettings(roomId) {
        var settings;
        try {
            var parsed = StorageUtils.getJsonStorage(getSettingsStorageKey(roomId), null);
            if (!parsed) {
                settings = { ...window.CLAPCLAP_DEFAULT_ROOM_UI_SETTINGS };
            } else {
                settings = {
                    ...window.CLAPCLAP_DEFAULT_ROOM_UI_SETTINGS,
                    ...parsed
                };
            }
        } catch (error) {
            console.error("loadRoomUiSettings error:", error);
            settings = { ...window.CLAPCLAP_DEFAULT_ROOM_UI_SETTINGS };
        }
        return settings;
    }

    function saveSettings(roomId, settings) {
        StorageUtils.setJsonStorage(getSettingsStorageKey(roomId), settings);
    }

    function syncSettingsControls(settings) {
        var el;
        el = document.getElementById("toggle-room-info");
        if (el) el.checked = !!settings.showRoomInfo;
        el = document.getElementById("toggle-room-status");
        if (el) el.checked = !!settings.showRoomStatus;
        el = document.getElementById("toggle-invite-section");
        if (el) el.checked = !!settings.showInvite;
        el = document.getElementById("toggle-round-result");
        if (el) el.checked = !!settings.showRoundResult;
        el = document.getElementById("toggle-history-section");
        if (el) el.checked = !!settings.showHistory;
        el = document.getElementById("toggle-move-subtitles");
        if (el) el.checked = !!settings.showMoveSubtitles;
        el = document.getElementById("player-state-mode-select");
        if (el) el.value = settings.playerStateMode || "compact";
        el = document.getElementById("reveal-advance-mode-select");
        if (el) el.value = settings.revealAdvanceMode || "auto";
    }

    function updateOverviewCardVisibility(settings) {
        var overviewCard = document.getElementById("overview-card");
        var spectatorBanner = document.getElementById("spectator-banner");

        if (!overviewCard) {
            return;
        }

        var showAnything =
            !!settings.showRoomInfo ||
            !!settings.showRoomStatus ||
            !!settings.showInvite ||
            (spectatorBanner && spectatorBanner.style.display !== "none");

        overviewCard.style.display = showAnything ? "" : "none";
    }

    function applySettings(settings) {
        var sections = {
            "room-info-section": settings.showRoomInfo,
            "room-status-section": settings.showRoomStatus,
            "invite-section": settings.showInvite,
            "round-result-section": settings.showRoundResult,
            "history-section": settings.showHistory
        };

        Object.keys(sections).forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.style.display = sections[id] ? "" : "none";
            }
        });

        var fullEl = document.getElementById("player-state-mode-full");
        var compactEl = document.getElementById("player-state-mode-compact");

        if (fullEl && compactEl) {
            if (settings.playerStateMode === "full") {
                fullEl.style.display = "";
                compactEl.style.display = "none";
            } else {
                fullEl.style.display = "none";
                compactEl.style.display = "";
            }
        }

        updateOverviewCardVisibility(settings);
    }

    window.RoomDetailSettings = {
        loadSettings: loadSettings,
        saveSettings: saveSettings,
        syncSettingsControls: syncSettingsControls,
        applySettings: applySettings,
        updateOverviewCardVisibility: updateOverviewCardVisibility
    };
})();
