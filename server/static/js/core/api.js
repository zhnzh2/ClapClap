(function () {
    async function parseJsonResponse(response) {
        var text = "";
        try {
            text = await response.text();
        } catch (error) {
            return null;
        }

        if (!text) {
            return null;
        }

        try {
            return JSON.parse(text);
        } catch (_ignored) {
            return { ok: false, error: text };
        }
    }

    function normalizeApiResult(response, data) {
        const body = data && typeof data === "object" ? data : {};
        const ok = response.ok && body.ok !== false;

        return {
            ok,
            status: response.status,
            data: body,
            error: body.error || body.message || response.statusText || "请求失败。"
        };
    }

    function _authHeaders() {
        var headers = {
            "Accept": "application/json"
        };
        if (window.SessionUtils) {
            var token = window.SessionUtils.getSessionToken();
            if (token) {
                headers["X-Session-Token"] = token;
            }
        }
        return headers;
    }

    function handleExpiredSession(response, data) {
        if (response.status !== 401 || !window.SessionUtils) {
            return;
        }
        var token = window.SessionUtils.getSessionToken();
        var redirect = data && data.redirect;
        if (!token || !redirect) {
            return;
        }
        window.SessionUtils.clearSession();
        var separator = redirect.indexOf("?") === -1 ? "?" : "&";
        window.location.href = redirect + separator + "expired=1";
    }

    async function apiGet(url) {
        var headers = _authHeaders();
        const response = await fetch(url, {
            method: "GET",
            headers: headers
        });
        const data = await parseJsonResponse(response);
        handleExpiredSession(response, data);
        return normalizeApiResult(response, data);
    }

    async function apiPost(url, payload = {}) {
        var headers = _authHeaders();
        headers["Content-Type"] = "application/json";
        const response = await fetch(url, {
            method: "POST",
            headers: headers,
            body: JSON.stringify(payload)
        });
        const data = await parseJsonResponse(response);
        handleExpiredSession(response, data);
        return normalizeApiResult(response, data);
    }

    window.ApiUtils = {
        apiGet,
        apiPost
    };
})();
