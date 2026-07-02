/**
 * ClapClap 2.0 决策 UI 组件。
 *
 * 管理决策弹窗（目标选择、三连选人、冲突协商）和回合总结弹窗。
 */
(function () {
    "use strict";

    var decisionTimer = null;
    var decisionDeadline = 0;
    var currentDecision = null;
    var selectedOptions = [];

    // ═══════════════════════════════════════════════════════
    // 决策弹窗
    // ═══════════════════════════════════════════════════════

    window.showDecisionModal = function (request) {
        if (!request) return;
        currentDecision = request;
        selectedOptions = [];

        var typeNames = {
            target_select: "选择目标",
            three_chain_select: "三连人选",
            conflict_resolve: "冲突协商",
        };

        document.getElementById("decision-title").textContent = typeNames[request.decision_type] || "决策";
        document.getElementById("decision-prompt").textContent = request.prompt || "";

        // 倒计时
        if (decisionTimer) { clearInterval(decisionTimer); decisionTimer = null; }
        if (request.timeout_seconds) {
            decisionDeadline = Date.now() + request.timeout_seconds * 1000;
            window.updateDecisionTimer();
            decisionTimer = setInterval(window.updateDecisionTimer, 1000);
        } else {
            decisionDeadline = 0;
            document.getElementById("decision-timer").textContent = "";
        }

        // 选项渲染
        var options = request.options || [];
        var splitCount = request.split_count || 1;
        var optionsHtml = "";

        if (splitCount > 1) {
            optionsHtml += '<div class="split-counter">请选择 ' + splitCount + ' 个目标（可重复）</div>';
        }

        for (var i = 0; i < options.length; i++) {
            var opt = options[i];
            var cls = "decision-option";
            if (!opt.is_valid) cls += " invalid";
            optionsHtml += '<div class="' + cls + '" ' +
                'data-option-id="' + _escAttr(opt.option_id) + '" ' +
                'data-is-valid="' + opt.is_valid + '" ' +
                'onclick="window.__v2_clickOption(this)">' +
                '<span>' + _esc(opt.label) + '</span>' +
                (opt.reason ? '<span class="opt-reason">' + _esc(opt.reason) + '</span>' : "") +
                '</div>';
        }

        document.getElementById("decision-options").innerHTML = optionsHtml;
        document.getElementById("decision-submit-btn").disabled = true;

        if (splitCount > 1) {
            // 拆分技能需要先选了再启用提交
            document.getElementById("decision-submit-btn").disabled = true;
        } else {
            // 单选情况下，预选第一个合法选项
            var firstValid = null;
            for (var j = 0; j < options.length; j++) {
                if (options[j].is_valid) { firstValid = options[j]; break; }
            }
            if (firstValid) {
                window.__v2_clickOption(
                    document.querySelector('.decision-option[data-option-id="' + _escAttr(firstValid.option_id) + '"]')
                );
            }
        }

        document.getElementById("decision-modal-mask").classList.add("show");
    };

    window.hideDecisionModal = function () {
        document.getElementById("decision-modal-mask").classList.remove("show");
        if (decisionTimer) { clearInterval(decisionTimer); decisionTimer = null; }
        currentDecision = null;
        selectedOptions = [];
    };

    window.updateDecisionTimer = function () {
        var timerEl = document.getElementById("decision-timer");
        if (!decisionDeadline) { timerEl.textContent = ""; return; }
        var remaining = Math.max(0, Math.ceil((decisionDeadline - Date.now()) / 1000));
        timerEl.textContent = remaining + "s";
        if (remaining <= 5) timerEl.style.color = "#dc2626";
        else timerEl.style.color = "#d97706";

        if (remaining <= 0) {
            // 超时自动提交
            window.__v2_autoSubmitDecision();
        }
    };

    window.__v2_clickOption = function (el) {
        if (!el || el.getAttribute("data-is-valid") !== "true") return;

        var optId = el.getAttribute("data-option-id");
        var splitCount = currentDecision ? currentDecision.split_count || 1 : 1;

        // 单选模式
        if (splitCount <= 1) {
            // 取消所有选中
            var all = document.querySelectorAll(".decision-option.selected");
            all.forEach(function (a) { a.classList.remove("selected"); });
            el.classList.add("selected");
            selectedOptions = [optId];
            document.getElementById("decision-submit-btn").disabled = false;
            return;
        }

        // 多选模式（拆分技能）
        var already = selectedOptions.indexOf(optId);
        if (already >= 0) {
            // 取消选中
            selectedOptions.splice(already, 1);
            el.classList.remove("selected");
        } else if (selectedOptions.length < splitCount) {
            selectedOptions.push(optId);
            el.classList.add("selected");
        }
        document.getElementById("decision-submit-btn").disabled = (selectedOptions.length < splitCount);
    };

    window.__v2_autoSubmitDecision = function () {
        if (!currentDecision) return;

        var options = currentDecision.options || [];
        var valid = options.filter(function (o) { return o.is_valid; });
        var splitCount = currentDecision.split_count || 1;

        if (valid.length === 0) {
            selectedOptions = [];
        } else if (splitCount <= 1) {
            selectedOptions = [valid[0].option_id];
        } else {
            selectedOptions = [];
            for (var i = 0; i < splitCount; i++) {
                selectedOptions.push(valid[i % valid.length].option_id);
            }
        }

        window.__v2_submitDecisionCallback(selectedOptions);
        window.hideDecisionModal();
    };

    window.__v2_submitCurrentDecision = function () {
        if (!currentDecision) return;
        if (selectedOptions.length === 0) return;
        window.__v2_submitDecisionCallback(selectedOptions);
        window.hideDecisionModal();
    };

    // ═══════════════════════════════════════════════════════
    // 决策提交回调（由主控制器设置）
    // ═══════════════════════════════════════════════════════

    window.__v2_submitDecisionCallback = function (selected) {
        // 由 v2_room_page.js 覆盖
        return selected;
    };

    // ═══════════════════════════════════════════════════════
    // 决策摘要（公开广播）
    // ═══════════════════════════════════════════════════════

    window.showDecisionSummary = function (data) {
        var requests = data.decision_requests || [];
        if (requests.length === 0) return;

        var parts = [];
        for (var i = 0; i < requests.length; i++) {
            var r = requests[i];
            var typeName = r.decision_type === "target_select" ? "选择目标" :
                r.decision_type === "three_chain_select" ? "三连选人" : "协商中";
            parts.push(r.player_id + " " + typeName);
        }
        setMessage("等待决策：" + parts.join("、"), "waiting");
    };

    // ═══════════════════════════════════════════════════════
    // 回合总结弹窗
    // ═══════════════════════════════════════════════════════

    window.showRoundSummary = function (summary) {
        if (!summary) return;
        if (typeof window.__v2_shouldShowRoundSummary === "function" &&
                !window.__v2_shouldShowRoundSummary()) {
            return;
        }

        var body = document.getElementById("round-summary-body");
        var MOVE_LABELS = window.MOVE_LABELS || {};
        var SPEED_LAYER_NAMES = window.SPEED_LAYER_NAMES || {};

        var html = '<div class="summary-round-num">第 ' + summary.round_num + ' 回合总结</div>';

        // ── 1. 本回合动作 ──
        var moves = summary.moves || {};
        if (Object.keys(moves).length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title">🎯 本回合动作</div>' +
                '<div class="summary-moves">';
            for (var pid in moves) {
                var moveLabel = MOVE_LABELS[moves[pid]] || moves[pid];
                html += '<span class="summary-move-tag">' + _esc(pid) + ': ' + _esc(moveLabel) + '</span>';
            }
            html += '</div></div>';
        }

        // ── 2. 资源检查 ──
        var resCheck = summary.resource_check || {};
        var illegal = resCheck.illegal || [];
        if (illegal.length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title">⚠️ 资源不足</div>' +
                '<div class="summary-text">' + illegal.map(function (pid) { return _esc(pid); }).join('、') +
                ' 资源不足导致动作无效</div></div>';
        }

        // ── 3. 闪 ──
        var flashed = summary.flashed_players || [];
        if (flashed.length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title">✨ 闪避</div>' +
                '<div class="summary-text">' + flashed.map(function (f) { return _esc(f); }).join('、') +
                ' 本回合使用了闪</div></div>';
        }

        // ── 4. 三连 ──
        var threeChain = summary.three_chain || {};
        var groups = threeChain.groups || [];
        if (groups.length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title">🔗 三连</div>';
            for (var g = 0; g < groups.length; g++) {
                var group = groups[g];
                html += '<div class="summary-text">类型: ' + _esc(group.type || '未知') +
                    '，参与: ' + (group.players || []).map(function (p) { return _esc(p); }).join(' → ') + '</div>';
            }
            html += '</div>';
        }

        // ── 5. 速度层事件（可折叠，默认折叠） ──
        var eventsByLayer = summary.events_by_layer || {};
        var layers = Object.keys(eventsByLayer).sort(function (a, b) { return parseInt(a) - parseInt(b); });
        if (layers.length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title summary-collapsible" onclick="window.__v2_toggleSpeedLayers()">' +
                '⚡ 速度层事件（' + layers.length + ' 层）<span class="collapse-arrow">▶</span></div>' +
                '<div id="speed-layers-detail" class="summary-speed-layers" style="display:none;">';
            for (var li = 0; li < layers.length; li++) {
                var layerNum = layers[li];
                var layerName = SPEED_LAYER_NAMES[layerNum] || ('层' + layerNum);
                var events = eventsByLayer[layerNum] || [];
                html += '<div class="speed-layer-group">' +
                    '<div class="speed-layer-label">层 ' + layerNum + ' · ' + _esc(layerName) + '</div>';
                for (var ei = 0; ei < events.length; ei++) {
                    var ev = events[ei];
                    var srcHtml = ev.source_player_id ?
                        '<span class="ev-source">' + _esc(ev.source_player_id) + '</span>' : '';
                    var tgtHtml = ev.target_player_id ?
                        '<span class="ev-arrow"> → </span><span class="ev-target">' + _esc(ev.target_player_id) + '</span>' : '';
                    html += '<div class="speed-layer-event">' +
                        srcHtml + tgtHtml +
                        '<span class="ev-detail">' + _esc(ev.detail || ev.event_type || '') + '</span>' +
                        '</div>';
                }
                html += '</div>';
            }
            html += '</div></div>';
        }

        // ── 6. 资源变化 ──
        var changes = summary.resource_changes || {};
        if (Object.keys(changes).length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title">📊 资源变化</div>' +
                '<div class="summary-changes"><table>' +
                '<tr><th>玩家</th><th>HP</th><th>气</th><th>盾</th><th>火种</th><th>电池</th><th>镐</th></tr>';
            for (var pid2 in changes) {
                var c = changes[pid2];
                html += '<tr><td>' + _esc(pid2) + '</td>' +
                    _changeTd(c.hp) + _changeTd(c.qi) + _changeTd(c.shield) +
                    _changeTd(c.spark) + _changeTd(c.battery) + _changeTd(c.pickaxe) +
                    '</tr>';
            }
            html += '</table></div></div>';
        }

        // ── 7. 淘汰 ──
        var deaths = summary.deaths || [];
        if (deaths.length > 0) {
            html += '<div class="summary-section">' +
                '<div class="summary-section-title">💀 淘汰</div>';
            for (var j = 0; j < deaths.length; j++) {
                var d = deaths[j];
                html += '<div class="summary-text">💀 ' + _esc(d.player_id || '?') +
                    ' 死亡（' + _esc(d.cause || '未知') + '）</div>';
            }
            html += '</div>';
        }

        // ── 8. 状态 ──
        html += '<div class="summary-section"><div class="summary-text">' +
            '存活: ' + (summary.alive_count != null ? summary.alive_count : '?') + ' 人';
        if (summary.game_ended) {
            html += ' · 对局已结束';
        }
        html += '</div></div>';

        // ── 9. 胜者 ──
        if (summary.winner) {
            html += '<div class="summary-section"><div class="summary-winner">🏆 ' +
                _esc(summary.winner) + ' 获胜！</div></div>';
        }

        body.innerHTML = html;
        document.getElementById("round-summary-mask").classList.add("show");
    };

    // 切换速度层事件展开/折叠
    window.__v2_toggleSpeedLayers = function () {
        var el = document.getElementById("speed-layers-detail");
        if (!el) return;
        var isVisible = el.style.display !== "none";
        el.style.display = isVisible ? "none" : "block";
        // 更新箭头
        var title = el.parentElement.querySelector(".collapse-arrow");
        if (title) {
            title.textContent = isVisible ? "▶" : "▼";
        }
    };

    window.hideRoundSummary = function () {
        document.getElementById("round-summary-mask").classList.remove("show");
    };

    // ═══════════════════════════════════════════════════════
    // 辅助函数
    // ═══════════════════════════════════════════════════════

    function _changeTd(val) {
        if (val === undefined || val === null || val === 0) return '<td>0</td>';
        var cls = val > 0 ? "change-positive" : "change-negative";
        var sign = val > 0 ? "+" : "";
        return '<td class="' + cls + '">' + sign + val + '</td>';
    }

    function _esc(s) {
        if (!s) return "";
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function _escAttr(s) {
        if (!s) return "";
        return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
})();
