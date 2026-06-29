(function () {
    function valueOf(player, key) {
        return player?.[key] ?? 0;
    }

    function renderPlayerStateFull(player, side = "self") {
        const sideClass = side === "self" ? "state-side-self" : "state-side-opponent";

        return `
            <div class="status-table-row full ${sideClass}">
                <div class="status-table-full-top">
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">生命</span>
                        <span class="status-table-value">${valueOf(player, "hp")}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">镐</span>
                        <span class="status-table-value">${valueOf(player, "pickaxe")}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">气</span>
                        <span class="status-table-value">${valueOf(player, "qi")}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">盾</span>
                        <span class="status-table-value">${valueOf(player, "shield")}</span>
                    </div>
                </div>

                <div class="status-table-full-bottom">
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">火种</span>
                        <span class="status-table-value">${valueOf(player, "spark")}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">电池</span>
                        <span class="status-table-value">${valueOf(player, "battery")}</span>
                    </div>
                    <div class="status-table-cell status-table-cell-stat">
                        <span class="status-table-key">闪次数</span>
                        <span class="status-table-value">${valueOf(player, "flash_used")}</span>
                    </div>
                </div>
            </div>
        `;
    }

    function renderPlayerStateCompact(player, side = "self") {
        const sideClass = side === "self" ? "state-side-self" : "state-side-opponent";

        return `
            <div class="status-table-row ${sideClass}">
                <div class="status-table-cell status-table-cell-stat">
                    <span class="status-table-key">生命</span>
                    <span class="status-table-value">${valueOf(player, "hp")}</span>
                </div>
                <div class="status-table-cell status-table-cell-stat">
                    <span class="status-table-key">镐</span>
                    <span class="status-table-value">${valueOf(player, "pickaxe")}</span>
                </div>
                <div class="status-table-cell status-table-cell-stat">
                    <span class="status-table-key">气</span>
                    <span class="status-table-value">${valueOf(player, "qi")}</span>
                </div>
                <div class="status-table-cell status-table-cell-stat">
                    <span class="status-table-key">盾</span>
                    <span class="status-table-value">${valueOf(player, "shield")}</span>
                </div>
            </div>
        `;
    }

    window.RoomPlayerStateRenderer = {
        renderPlayerStateFull,
        renderPlayerStateCompact
    };
})();
