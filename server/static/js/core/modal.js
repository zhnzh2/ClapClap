(function () {
    let currentActionHandlers = [];

    function getModalElements() {
        return {
            mask: document.getElementById("global-modal-mask"),
            card: document.getElementById("global-modal-card"),
            icon: document.getElementById("global-modal-icon"),
            title: document.getElementById("global-modal-title"),
            body: document.getElementById("global-modal-body"),
            actions: document.getElementById("global-modal-actions")
        };
    }

    function cleanupModalActions() {
        currentActionHandlers.forEach(({ button, handler }) => {
            if (button && handler) {
                button.removeEventListener("click", handler);
            }
        });
        currentActionHandlers = [];
    }

    function closeModal() {
        const { mask, actions } = getModalElements();
        if (!mask || !actions) {
            return;
        }

        cleanupModalActions();
        actions.innerHTML = "";
        mask.classList.remove("show");
    }

    function buildActionButton(action) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = action.text || "确定";
        button.className = action.className || "secondary";

        const handler = () => {
            if (action.closeOnClick !== false) {
                closeModal();
            }
            if (typeof action.onClick === "function") {
                action.onClick();
            }
        };

        button.addEventListener("click", handler);
        currentActionHandlers.push({ button, handler });

        return button;
    }

    function showModal({
        icon = "",
        iconClass = "",
        title = "",
        body = "",
        actions = []
    }) {
        const { mask, icon: iconEl, title: titleEl, body: bodyEl, actions: actionsEl } = getModalElements();

        if (!mask || !iconEl || !titleEl || !bodyEl || !actionsEl) {
            return;
        }

        cleanupModalActions();
        actionsEl.innerHTML = "";

        iconEl.textContent = icon || "";
        iconEl.className = `modal-icon ${iconClass || ""}`.trim();

        if (icon) {
            iconEl.style.display = "";
        } else {
            iconEl.style.display = "none";
        }

        titleEl.textContent = title || "";
        bodyEl.textContent = body || "";

        (actions || []).forEach((action) => {
            actionsEl.appendChild(buildActionButton(action));
        });

        mask.classList.add("show");
    }

    function showConfirmModal({
        title = "确认操作",
        body = "你确定要继续吗？",
        confirmText = "确认",
        cancelText = "取消",
        onConfirm = null,
        onCancel = null,
        confirmClassName = "danger",
        cancelClassName = "secondary"
    }) {
        showModal({
            icon: "!",
            iconClass: "warning",
            title,
            body,
            actions: [
                {
                    text: cancelText,
                    className: cancelClassName,
                    onClick: onCancel
                },
                {
                    text: confirmText,
                    className: confirmClassName,
                    onClick: onConfirm
                }
            ]
        });
    }

    function showInfoModal({
        title = "提示",
        body = "",
        buttonText = "知道了",
        onClose = null
    }) {
        showModal({
            icon: "i",
            iconClass: "info",
            title,
            body,
            actions: [
                {
                    text: buttonText,
                    className: "primary",
                    onClick: onClose
                }
            ]
        });
    }

    function showSuccessModal({
        title = "操作成功",
        body = "",
        buttonText = "确定",
        onClose = null
    }) {
        showModal({
            icon: "✓",
            iconClass: "success",
            title,
            body,
            actions: [
                {
                    text: buttonText,
                    className: "primary",
                    onClick: onClose
                }
            ]
        });
    }

    function bindGlobalModalEvents() {
        const { mask } = getModalElements();
        if (!mask) {
            return;
        }

        mask.addEventListener("click", (event) => {
            if (event.target === mask) {
                closeModal();
            }
        });
    }

    window.ModalUtils = {
        showModal,
        closeModal,
        showConfirmModal,
        showInfoModal,
        showSuccessModal,
        bindGlobalModalEvents
    };
})();