/**
 * 前端 Session 管理。
 * Session token 存储在 localStorage 的 clapclap_session 键中。
 */
(function () {
    const SESSION_KEY = "clapclap_session";

    function getSessionToken() {
        try {
            const parsed = JSON.parse(localStorage.getItem(SESSION_KEY));
            if (parsed && typeof parsed.token === "string") {
                return parsed.token;
            }
        } catch (e) {
            // ignore
        }
        return "";
    }

    function getSessionUser() {
        try {
            const parsed = JSON.parse(localStorage.getItem(SESSION_KEY));
            if (parsed && parsed.user && typeof parsed.user === "object") {
                return parsed.user;
            }
        } catch (e) {
            // ignore
        }
        return null;
    }

    function saveSession(token, user) {
        localStorage.setItem(SESSION_KEY, JSON.stringify({
            token: token || "",
            user: user || null
        }));
    }

    function clearSession() {
        localStorage.removeItem(SESSION_KEY);
    }

    function isLoggedIn() {
        return !!getSessionToken();
    }

    window.SessionUtils = {
        getSessionToken: getSessionToken,
        getSessionUser: getSessionUser,
        saveSession: saveSession,
        clearSession: clearSession,
        isLoggedIn: isLoggedIn,
        SESSION_KEY: SESSION_KEY
    };
})();
