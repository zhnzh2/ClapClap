/**
 * 管理员「查看用户」弹窗。
 * 调用 window.AdminUsersModal.open() 打开。
 */
(function () {
    function _apiUrl(path) {
        var versionPrefix = window.location.pathname.indexOf("/v2") === 0 ? "/v2" : "/v1";
        return versionPrefix + "/api" + path;
    }

    function open() {
        var user = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;
        if (!user || user.role !== "admin") {
            return;
        }

        ApiUtils.apiGet(_apiUrl("/admin/users")).then(function (result) {
            if (!result.ok) {
                if (typeof ModalUtils !== "undefined") {
                    ModalUtils.showInfoModal({
                        title: "错误",
                        body: result.error || "获取用户列表失败。",
                        buttonText: "关闭"
                    });
                }
                return;
            }
            _renderModal(result.data.users || []);
        }).catch(function () {
            if (typeof ModalUtils !== "undefined") {
                ModalUtils.showInfoModal({
                    title: "错误",
                    body: "获取用户列表失败。",
                    buttonText: "关闭"
                });
            }
        });
    }

    function _renderModal(users) {
        var existing = document.getElementById("admin-users-mask");
        if (existing) { existing.remove(); }

        var mask = document.createElement("div");
        mask.id = "admin-users-mask";
        mask.className = "modal-mask show";
        mask.style.zIndex = "1000";

        var card = document.createElement("div");
        card.className = "modal-card large";
        card.style.width = "min(900px, calc(100vw - 32px))";
        card.style.maxHeight = "calc(100vh - 64px)";
        card.style.overflowY = "auto";

        var title = document.createElement("div");
        title.className = "modal-title";
        title.textContent = "用户管理（共 " + users.length + " 人）";

        var toolbar = document.createElement("div");
        toolbar.className = "admin-bulk-toolbar";
        toolbar.innerHTML =
            '<label class="admin-select-all"><input type="checkbox" id="admin-select-all-users" /> 全选可操作用户</label>' +
            '<span class="admin-selected-count" id="admin-selected-count">已选 0 人</span>' +
            '<button class="admin-bulk-btn verify" id="admin-bulk-verify" disabled>批量验证</button>' +
            '<button class="admin-bulk-btn delete" id="admin-bulk-delete" disabled>批量注销</button>';

        // 表格容器
        var tableWrap = document.createElement("div");
        tableWrap.style.overflowX = "auto";
        tableWrap.style.marginTop = "12px";

        var table = document.createElement("table");
        table.className = "admin-users-table";

        var thead = document.createElement("thead");
        var headerRow = document.createElement("tr");
        var headers = [
            { text: "", width: "38px" },
            { text: "UID", width: "52px" },
            { text: "用户名", width: "auto" },
            { text: "创建时间", width: "150px" },
            { text: "已验证", width: "68px" },
            { text: "权限", width: "60px" },
            { text: "介绍信", width: "auto" },
            { text: "操作", width: "120px" }
        ];
        headers.forEach(function (h) {
            var th = document.createElement("th");
            th.textContent = h.text;
            if (h.width !== "auto") {
                th.style.width = h.width;
                th.style.minWidth = h.width;
            }
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        var tbody = document.createElement("tbody");
        users.forEach(function (u) {
            var tr = document.createElement("tr");
            tr.setAttribute("data-uid", String(u.uid));
            if (u.uid === 0) {
                tr.style.background = "#fefce8";
            }

            var verifiedLabel = u.verified === "1"
                ? '<span style="color:#16a34a;white-space:nowrap;">已验证</span>'
                : '<span style="color:#d97706;white-space:nowrap;">未验证</span>';

            var roleLabel = u.role === "admin"
                ? '<span style="color:#2563eb;font-weight:bold;">管理员</span>'
                : '用户';

            var introText = u.intro || "-";
            var introDisplay = introText.length > 15
                ? _esc(introText.substring(0, 15)) + "..."
                : _esc(introText);

            tr.innerHTML =
                '<td style="text-align:center;">' + _buildSelectCell(u) + '</td>' +
                '<td style="text-align:center;">' + u.uid + '</td>' +
                '<td>' + _esc(u.username) + '</td>' +
                '<td style="font-size:12px;color:#6b7280;white-space:nowrap;">' + _esc(u.created_at || "-") + '</td>' +
                '<td>' + verifiedLabel + '</td>' +
                '<td>' + roleLabel + '</td>' +
                '<td style="font-size:12px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + _esc(introText) + '">' + introDisplay + '</td>' +
                '<td>' + _buildActionCell(u) + '</td>';

            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        tableWrap.appendChild(table);

        // 关闭（点击遮罩区域即可关闭，不设关闭按钮）
        card.appendChild(title);
        card.appendChild(toolbar);
        card.appendChild(tableWrap);
        mask.appendChild(card);
        document.body.appendChild(mask);

        mask.addEventListener("click", function (e) {
            if (e.target === mask) { mask.remove(); }
        });

        _applyTableStyles();
        _bindActionEvents(mask, users);
        _bindBulkEvents(mask, users);
    }

    function _buildSelectCell(u) {
        if (u.uid === 0) {
            return '<span style="color:#9ca3af;">-</span>';
        }
        return '<input class="admin-user-check" type="checkbox" data-uid="' + u.uid + '" />';
    }

    function _buildActionCell(u) {
        var html = '<div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;">';

        if (u.uid !== 0) {
            if (u.verified !== "1") {
                html += '<button class="admin-action-btn verify-btn" data-uid="' + u.uid + '" data-action="verify">验证</button>';
            }
            html += '<button class="admin-action-btn delete-btn" data-uid="' + u.uid + '" data-action="delete">注销</button>';
        } else {
            html += '<span style="color:#6b7280;font-size:12px;">-</span>';
        }

        html += '</div>';
        return html;
    }

    function _bindActionEvents(mask, users) {
        mask.querySelectorAll(".admin-action-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var uid = parseInt(btn.getAttribute("data-uid"), 10);
                var action = btn.getAttribute("data-action");
                var user = _findUser(users, uid);
                var name = user ? user.username : ("UID " + uid);

                if (action === "verify") {
                    _confirmVerify(uid, name, btn, mask);
                } else if (action === "delete") {
                    _confirmDelete(uid, name, mask);
                }
            });
        });
    }

    function _bindBulkEvents(mask, users) {
        var selectAll = mask.querySelector("#admin-select-all-users");
        var bulkVerify = mask.querySelector("#admin-bulk-verify");
        var bulkDelete = mask.querySelector("#admin-bulk-delete");

        mask.querySelectorAll(".admin-user-check").forEach(function (checkbox) {
            checkbox.addEventListener("change", function () {
                _updateBulkToolbar(mask);
            });
        });

        if (selectAll) {
            selectAll.addEventListener("change", function () {
                var checked = !!selectAll.checked;
                mask.querySelectorAll(".admin-user-check").forEach(function (checkbox) {
                    checkbox.checked = checked;
                });
                _updateBulkToolbar(mask);
            });
        }

        if (bulkVerify) {
            bulkVerify.addEventListener("click", function () {
                var uids = _selectedUids(mask);
                if (uids.length === 0) return;
                _confirmBulk("verify", uids, mask);
            });
        }

        if (bulkDelete) {
            bulkDelete.addEventListener("click", function () {
                var uids = _selectedUids(mask);
                if (uids.length === 0) return;
                _confirmBulk("delete", uids, mask);
            });
        }

        _updateBulkToolbar(mask);
    }

    function _selectedUids(mask) {
        var uids = [];
        mask.querySelectorAll(".admin-user-check:checked").forEach(function (checkbox) {
            var uid = parseInt(checkbox.getAttribute("data-uid"), 10);
            if (!isNaN(uid)) uids.push(uid);
        });
        return uids;
    }

    function _updateBulkToolbar(mask) {
        var selected = _selectedUids(mask);
        var count = mask.querySelector("#admin-selected-count");
        var bulkVerify = mask.querySelector("#admin-bulk-verify");
        var bulkDelete = mask.querySelector("#admin-bulk-delete");
        var selectAll = mask.querySelector("#admin-select-all-users");
        var allChecks = mask.querySelectorAll(".admin-user-check");
        var checkedChecks = mask.querySelectorAll(".admin-user-check:checked");

        if (count) count.textContent = "已选 " + selected.length + " 人";
        if (bulkVerify) bulkVerify.disabled = selected.length === 0;
        if (bulkDelete) bulkDelete.disabled = selected.length === 0;
        if (selectAll) {
            selectAll.checked = allChecks.length > 0 && checkedChecks.length === allChecks.length;
            selectAll.indeterminate = checkedChecks.length > 0 && checkedChecks.length < allChecks.length;
        }
    }

    function _confirmBulk(action, uids, mask) {
        var isDelete = action === "delete";
        var title = isDelete ? "批量注销用户" : "批量验证用户";
        var body = isDelete
            ? "确认注销选中的 " + uids.length + " 个用户吗？此操作不可撤销，会清理关联房间、匹配状态并标记历史对局。"
            : "确认验证选中的 " + uids.length + " 个用户吗？";

        if (typeof ModalUtils !== "undefined" && ModalUtils.showConfirmModal) {
            ModalUtils.showConfirmModal({
                title: title,
                body: body,
                confirmText: isDelete ? "批量注销" : "批量验证",
                cancelText: "取消",
                confirmClassName: isDelete ? "danger" : "primary",
                onConfirm: function () {
                    _doBulk(action, uids, mask);
                }
            });
        } else if (confirm(body)) {
            _doBulk(action, uids, mask);
        }
    }

    function _doBulk(action, uids, mask) {
        _setBulkBusy(mask, true);
        ApiUtils.apiPost(_apiUrl("/admin/users/bulk"), {
            action: action,
            uids: uids
        }).then(function (result) {
            if (!result.ok) {
                _showError(result.error || "批量操作失败。");
                return;
            }
            var okUids = (result.data.results || [])
                .filter(function (item) { return item.ok; })
                .map(function (item) { return item.uid; });

            if (action === "verify") {
                okUids.forEach(function (uid) {
                    _updateVerifiedCell(mask, uid);
                });
            } else {
                okUids.forEach(function (uid) {
                    _removeTableRow(mask, uid, false);
                });
                _updateUserCountTitle(mask);
            }
            _clearSelected(mask);
            _updateBulkToolbar(mask);
        }).catch(function () {
            _showError("批量操作失败。");
        }).finally(function () {
            _setBulkBusy(mask, false);
        });
    }

    function _setBulkBusy(mask, busy) {
        mask.querySelectorAll(".admin-bulk-btn").forEach(function (btn) {
            btn.disabled = busy || _selectedUids(mask).length === 0;
        });
        mask.querySelectorAll(".admin-user-check, #admin-select-all-users").forEach(function (input) {
            input.disabled = busy;
        });
    }

    function _clearSelected(mask) {
        mask.querySelectorAll(".admin-user-check").forEach(function (checkbox) {
            checkbox.checked = false;
        });
    }

    function _showError(message) {
        if (typeof ModalUtils !== "undefined") {
            ModalUtils.showInfoModal({ title: "错误", body: message, buttonText: "关闭" });
        } else {
            alert(message);
        }
    }

    function _confirmVerify(uid, name, btn, mask) {
        if (typeof ModalUtils !== "undefined" && ModalUtils.showConfirmModal) {
            ModalUtils.showConfirmModal({
                title: "验证用户",
                body: "确认验证用户 " + name + "（UID: " + uid + "）吗？",
                confirmText: "确认验证",
                cancelText: "取消",
                confirmClassName: "primary",
                onConfirm: function () {
                    _doVerify(uid, btn, mask);
                }
            });
        } else {
            if (confirm("确认验证用户 " + name + "（UID: " + uid + "）吗？")) {
                _doVerify(uid, btn, mask);
            }
        }
    }

    function _confirmDelete(uid, name, mask) {
        if (typeof ModalUtils !== "undefined" && ModalUtils.showConfirmModal) {
            ModalUtils.showConfirmModal({
                title: "注销用户",
                body: "确认注销用户 " + name + "（UID: " + uid + "）吗？\n\n此操作不可撤销，该用户的所有数据将被永久删除。",
                confirmText: "确认注销",
                cancelText: "取消",
                confirmClassName: "danger",
                onConfirm: function () {
                    _doDelete(uid, mask);
                }
            });
        } else {
            if (confirm("确认注销用户 " + name + "（UID: " + uid + "）吗？\n\n此操作不可撤销，该用户的所有数据将被永久删除。")) {
                if (confirm("请再次确认：永久注销 " + name + "？")) {
                    _doDelete(uid, mask);
                }
            }
        }
    }

    function _doVerify(uid, btn, mask) {
        ApiUtils.apiPost(_apiUrl("/admin/verify/" + uid), {}).then(function (result) {
            if (result.ok) {
                btn.remove();
                _updateVerifiedCell(mask, uid);
            } else {
                _showError(result.error || "验证失败。");
            }
        });
    }

    function _doDelete(uid, mask) {
        ApiUtils.apiPost(_apiUrl("/admin/delete/" + uid), {}).then(function (result) {
            if (result.ok) {
                _removeTableRow(mask, uid, true);
            } else {
                _showError(result.error || "注销失败。");
            }
        });
    }

    function _updateVerifiedCell(mask, uid) {
        var rows = mask.querySelectorAll("tbody tr");
        rows.forEach(function (tr) {
            if (tr.getAttribute("data-uid") === String(uid)) {
                var cells = tr.querySelectorAll("td");
                if (cells[4]) {
                    cells[4].innerHTML = '<span style="color:#16a34a;">已验证</span>';
                }
                var verifyBtn = tr.querySelector('.verify-btn[data-uid="' + uid + '"]');
                if (verifyBtn) verifyBtn.remove();
            }
        });
    }

    function _removeTableRow(mask, uid, updateTitle) {
        var rows = mask.querySelectorAll("tbody tr");
        rows.forEach(function (tr) {
            if (tr.getAttribute("data-uid") === String(uid)) {
                tr.remove();
            }
        });
        if (updateTitle) {
            _updateUserCountTitle(mask);
        }
    }

    function _updateUserCountTitle(mask) {
        var titleEl = mask.querySelector(".modal-title");
        if (titleEl) {
            var remaining = mask.querySelectorAll("tbody tr").length;
            titleEl.textContent = "用户管理（共 " + remaining + " 人）";
        }
    }

    function _findUser(users, uid) {
        for (var i = 0; i < users.length; i++) {
            if (users[i].uid === uid) return users[i];
        }
        return null;
    }

    function _applyTableStyles() {
        var styleId = "admin-table-style";
        if (!document.getElementById(styleId)) {
            var style = document.createElement("style");
            style.id = styleId;
            style.textContent =
                ".admin-users-table {" +
                "  width: 100%;" +
                "  border-collapse: collapse;" +
                "  font-size: 14px;" +
                "  table-layout: auto;" +
                "}" +
                ".admin-users-table th {" +
                "  background: #f9fafb;" +
                "  padding: 10px 8px;" +
                "  text-align: left;" +
                "  font-size: 13px;" +
                "  font-weight: bold;" +
                "  color: #374151;" +
                "  border-bottom: 2px solid #e5e7eb;" +
                "  white-space: nowrap;" +
                "  position: sticky;" +
                "  top: 0;" +
                "  z-index: 1;" +
                "}" +
                ".admin-users-table td {" +
                "  padding: 8px;" +
                "  border-bottom: 1px solid #f3f4f6;" +
                "  vertical-align: middle;" +
                "  line-height: 1.5;" +
                "}" +
                ".admin-bulk-toolbar {" +
                "  display:flex;" +
                "  align-items:center;" +
                "  gap:8px;" +
                "  flex-wrap:wrap;" +
                "  margin-top:12px;" +
                "  padding:10px;" +
                "  border:1px solid #e5e7eb;" +
                "  border-radius:10px;" +
                "  background:#f9fafb;" +
                "}" +
                ".admin-select-all {" +
                "  display:inline-flex;" +
                "  align-items:center;" +
                "  gap:6px;" +
                "  font-size:13px;" +
                "  font-weight:700;" +
                "  color:#374151;" +
                "}" +
                ".admin-selected-count {" +
                "  color:#6b7280;" +
                "  font-size:12px;" +
                "  margin-right:auto;" +
                "}" +
                ".admin-bulk-btn {" +
                "  padding:6px 12px;" +
                "  border:1px solid #d1d5db;" +
                "  border-radius:8px;" +
                "  font-size:12px;" +
                "  font-weight:800;" +
                "  background:white;" +
                "  cursor:pointer;" +
                "}" +
                ".admin-bulk-btn.verify { color:#15803d; border-color:#86efac; }" +
                ".admin-bulk-btn.delete { color:#dc2626; border-color:#fca5a5; }" +
                ".admin-bulk-btn:disabled { opacity:0.45; cursor:not-allowed; }" +
                ".admin-users-table tbody tr:hover {" +
                "  background: #f9fafb !important;" +
                "}" +
                ".admin-action-btn {" +
                "  padding: 4px 10px;" +
                "  border: 1px solid #d1d5db;" +
                "  border-radius: 8px;" +
                "  font-size: 12px;" +
                "  font-weight: bold;" +
                "  cursor: pointer;" +
                "  background: white;" +
                "  white-space: nowrap;" +
                "  transition: background 0.12s;" +
                "}" +
                ".admin-action-btn.verify-btn {" +
                "  color: #16a34a;" +
                "  border-color: #86efac;" +
                "}" +
                ".admin-action-btn.verify-btn:hover {" +
                "  background: #f0fdf4;" +
                "}" +
                ".admin-action-btn.delete-btn {" +
                "  color: #ef4444;" +
                "  border-color: #fca5a5;" +
                "}" +
                ".admin-action-btn.delete-btn:hover {" +
                "  background: #fef2f2;" +
                "}";
            document.head.appendChild(style);
        }
    }

    // 修复：正确处理 0
    function _esc(text) {
        if (text === undefined || text === null) { return ""; }
        return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    window.AdminUsersModal = {
        open: open
    };

    // 自动初始化：页面加载后检查 admin 权限，显示/隐藏 admin 按钮
    function autoInit() {
        var btn = document.getElementById("header-admin-btn");
        if (!btn) return;

        var user = window.SessionUtils ? window.SessionUtils.getSessionUser() : null;

        function showIfAdmin(u) {
            if (u && u.role === "admin") {
                btn.style.display = "";
                btn.addEventListener("click", function () { open(); });
            }
        }

        if (user) {
            if (user.role) {
                showIfAdmin(user);
            } else {
                if (window.ApiUtils) {
                    ApiUtils.apiGet(_apiUrl("/auth/me")).then(function (result) {
                        if (result.ok && result.data.user) {
                            var token = SessionUtils.getSessionToken();
                            SessionUtils.saveSession(token, result.data.user);
                            showIfAdmin(result.data.user);
                        }
                    }).catch(function () {});
                }
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", autoInit);
    } else {
        autoInit();
    }
})();
