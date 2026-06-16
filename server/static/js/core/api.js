(function () {
    async function parseJsonResponse(response) {
        try {
            return await response.json();
        } catch (error) {
            return null;
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

    async function apiGet(url) {
        var headers = _authHeaders();
        const response = await fetch(url, {
            method: "GET",
            headers: headers
        });
        const data = await parseJsonResponse(response);
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
        return normalizeApiResult(response, data);
    }

    window.ApiUtils = {
        apiGet,
        apiPost
    };
})();
