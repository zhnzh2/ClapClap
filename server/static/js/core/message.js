function setMessage(elementId, text, type = "info") {
    const el = document.getElementById(elementId);
    if (!el) {
        return;
    }

    el.textContent = text || "";
    el.className = `message ${type}`;
}

function clearMessage(elementId) {
    const el = document.getElementById(elementId);
    if (!el) {
        return;
    }

    el.textContent = "";
    el.className = "message";
}

function createMessageController(elementId) {
    return {
        set(text, type = "info") {
            setMessage(elementId, text, type);
        },
        clear() {
            clearMessage(elementId);
        }
    };
}

window.MessageUtils = {
    setMessage,
    clearMessage,
    createMessageController
};