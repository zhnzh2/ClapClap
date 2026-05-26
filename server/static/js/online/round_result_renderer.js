(function () {
    function renderRoundResultBanner(room, lastRenderedRoundCount) {
        const banner = document.getElementById("round-result-section");
        const titleEl = document.getElementById("round-result-title");
        const bodyEl = document.getElementById("round-result-body");
        const chipsEl = document.getElementById("round-result-chips");

        if (!banner || !titleEl || !bodyEl || !chipsEl) {
            return lastRenderedRoundCount;
        }

        chipsEl.innerHTML = "";

        const history = room.game?.history || [];
        if (!Array.isArray(history) || history.length === 0) {
            banner.classList.remove("show");
            return lastRenderedRoundCount;
        }

        const lastLog = history[history.length - 1];
        const roundIndex = history.length;

        if (lastRenderedRoundCount === roundIndex && room.status !== "finished") {
            return lastRenderedRoundCount;
        }

        banner.classList.add("show");
        titleEl.textContent = `本回合结果 · 第 ${roundIndex} 回合`;

        const p1Move = lastLog.p1_move_label || lastLog.p1_move || "未知";
        const p2Move = lastLog.p2_move_label || lastLog.p2_move || "未知";
        const summaryText = lastLog.summary || "本回合已完成结算。";

        bodyEl.textContent = `P1：${p1Move}　|　P2：${p2Move}　|　${summaryText}`;

        const chips = [
            `P1 动作：${p1Move}`,
            `P2 动作：${p2Move}`
        ];

        if ((lastLog.p1_damage_taken ?? 0) > 0) {
            chips.push(`P1 受到 ${lastLog.p1_damage_taken} 点伤害`);
        }
        if ((lastLog.p2_damage_taken ?? 0) > 0) {
            chips.push(`P2 受到 ${lastLog.p2_damage_taken} 点伤害`);
        }
        if ((lastLog.p1_pickaxe_blocked ?? 0) > 0) {
            chips.push(`P1 镐抵挡 ${lastLog.p1_pickaxe_blocked} 点`);
        }
        if ((lastLog.p2_pickaxe_blocked ?? 0) > 0) {
            chips.push(`P2 镐抵挡 ${lastLog.p2_pickaxe_blocked} 点`);
        }

        if (room.game?.winner === 1) {
            chips.push("当前胜者：P1");
        } else if (room.game?.winner === 2) {
            chips.push("当前胜者：P2");
        }

        chips.forEach((text) => {
            const chip = document.createElement("span");
            chip.className = "result-chip";
            chip.textContent = text;
            chipsEl.appendChild(chip);
        });

        return roundIndex;
    }

    window.RoomRoundResultRenderer = {
        renderRoundResultBanner
    };
})();
