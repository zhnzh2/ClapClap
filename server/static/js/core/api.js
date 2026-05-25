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

    async function apiGet(url) {
        const response = await fetch(url, {
            method: "GET",
            headers: {
                "Accept": "application/json"
            }
        });
        const data = await parseJsonResponse(response);
        return normalizeApiResult(response, data);
    }

    async function apiPost(url, payload = {}) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
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
