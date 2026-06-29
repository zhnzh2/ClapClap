(function () {
    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function buildEventTags(log) {
        const eventTags = [];

        if ((log.p1_damage_taken ?? 0) > 0) {
            eventTags.push({ text: `1号位-${log.p1_damage_taken}血`, type: "damage" });
        }
        if ((log.p2_damage_taken ?? 0) > 0) {
            eventTags.push({ text: `2号位-${log.p2_damage_taken}血`, type: "damage" });
        }
        if ((log.p1_pickaxe_blocked ?? 0) > 0) {
            eventTags.push({ text: `1号位镐挡${log.p1_pickaxe_blocked}`, type: "block" });
        }
        if ((log.p2_pickaxe_blocked ?? 0) > 0) {
            eventTags.push({ text: `2号位镐挡${log.p2_pickaxe_blocked}`, type: "block" });
        }

        const noteText = `${log.p1_note || ""} ${log.p2_note || ""}`;
        ["双吃", "你吃", "爆镐", "抢镐", "闪", "反噬"].forEach((keyword) => {
            if (noteText.includes(keyword)) {
                eventTags.push({ text: keyword, type: "special" });
            }
        });

        if (log.winner_after_round === 1) {
            eventTags.push({ text: "P1胜", type: "special" });
        } else if (log.winner_after_round === 2) {
            eventTags.push({ text: "P2胜", type: "special" });
        } else if (log.winner_after_round === 0) {
            eventTags.push({ text: "平局/双败", type: "special" });
        }

        return eventTags;
    }

    function renderHistory(elementId, logs) {
        const historyEl = document.getElementById(elementId);
        if (!historyEl) {
            return;
        }

        historyEl.innerHTML = "";

        if (!logs || logs.length === 0) {
            historyEl.innerHTML = "<div class='muted' style='padding: 12px;'>当前还没有历史记录。</div>";
            return;
        }

        const rowsHtml = logs.slice().reverse().map((log) => {
            const p1Move = log.p1_move_label || log.p1_move || "";
            const p2Move = log.p2_move_label || log.p2_move || "";
            const eventTags = buildEventTags(log);
            const tagHtml = eventTags.length > 0
                ? eventTags
                    .map((item) => `<span class="history-tag ${item.type}">${escapeHtml(item.text)}</span>`)
                    .join("")
                : "<span class='muted'>无伤害</span>";

            return `
                <tr>
                    <td class="history-table-col-round">${escapeHtml(log.round_num)}</td>
                    <td class="history-table-col-move">${escapeHtml(p1Move)}</td>
                    <td class="history-table-col-move">${escapeHtml(p2Move)}</td>
                    <td class="history-table-col-summary">
                        <div>${escapeHtml(log.summary)}</div>
                        <div class="history-event-row">${tagHtml}</div>
                    </td>
                </tr>
            `;
        }).join("");

        historyEl.innerHTML = `
            <table class="history-table">
                <thead>
                    <tr>
                        <th class="history-table-col-round">回合数</th>
                        <th class="history-table-col-move">1号位动作</th>
                        <th class="history-table-col-move">2号位动作</th>
                        <th class="history-table-col-summary">总结</th>
                    </tr>
                </thead>
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
        `;
    }

    window.RoomHistoryRenderer = {
        renderHistory
    };
})();
