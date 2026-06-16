/**
 * 登录页面逻辑。
 */
window.initLoginPage = function () {

    var loginUsername = document.getElementById("login-username");
    var loginPassword = document.getElementById("login-password");
    var loginBtn = document.getElementById("login-btn");
    var loginMessage = document.getElementById("login-message");

    var regUsername = document.getElementById("reg-username");
    var regPassword = document.getElementById("reg-password");
    var regConfirmPw = document.getElementById("reg-confirm-password");
    var regIntro = document.getElementById("reg-intro");
    var registerBtn = document.getElementById("register-btn");
    var registerMessage = document.getElementById("register-message");

    var loginFormDiv = document.getElementById("login-form");
    var registerFormDiv = document.getElementById("register-form");

    var successMask = document.getElementById("success-mask");
    var successTitle = document.getElementById("success-title");
    var successBody = document.getElementById("success-body");
    var successOkBtn = document.getElementById("success-ok-btn");

    function setMessage(el, text, type) {
        if (el) {
            el.textContent = text || "";
            el.className = "message " + (type || "info");
        }
    }

    // ── 登录 ──────────────────────────────────────

    async function doLogin() {
        var username = (loginUsername.value || "").trim();
        var password = loginPassword.value || "";

        if (!username || !password) {
            setMessage(loginMessage, "请输入用户名和密码。", "error");
            return;
        }

        loginBtn.disabled = true;
        setMessage(loginMessage, "正在登录……", "info");

        var result = await ApiUtils.apiPost("/api/auth/login", {
            username: username,
            password: password
        });

        loginBtn.disabled = false;

        if (!result.ok) {
            setMessage(loginMessage, result.error || "登录失败。", "error");
            return;
        }

        SessionUtils.saveSession(result.data.session_token, result.data.user);
        window.location.href = "/";
    }

    loginBtn.addEventListener("click", doLogin);
    loginPassword.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { doLogin(); }
    });

    // ── 注册 ──────────────────────────────────────

    document.getElementById("show-register-btn").addEventListener("click", function () {
        loginFormDiv.style.display = "none";
        registerFormDiv.style.display = "";
        setMessage(registerMessage, "", "");
    });

    document.getElementById("back-to-login-btn").addEventListener("click", function () {
        registerFormDiv.style.display = "none";
        loginFormDiv.style.display = "";
        setMessage(registerMessage, "", "");
    });

    async function doRegister() {
        var username = (regUsername.value || "").trim();
        var password = regPassword.value || "";
        var confirmPw = regConfirmPw.value || "";
        var intro = (regIntro.value || "").trim();

        if (!username) {
            setMessage(registerMessage, "用户名不能为空。", "error");
            return;
        }
        if (!password) {
            setMessage(registerMessage, "密码不能为空。", "error");
            return;
        }
        if (password !== confirmPw) {
            setMessage(registerMessage, "两次输入的密码不一致。", "error");
            return;
        }

        registerBtn.disabled = true;
        setMessage(registerMessage, "正在注册……", "info");

        var result = await ApiUtils.apiPost("/api/auth/register", {
            username: username,
            password: password,
            confirm_password: confirmPw,
            intro: intro
        });

        registerBtn.disabled = false;

        if (!result.ok) {
            setMessage(registerMessage, result.error || "注册失败。", "error");
            return;
        }

        SessionUtils.saveSession(result.data.session_token, result.data.user);
        showSuccessPopup(username, password, false);
    }

    registerBtn.addEventListener("click", doRegister);

    // ── 访客登录 ──────────────────────────────────

    document.getElementById("guest-login-btn").addEventListener("click", async function () {
        var btn = document.getElementById("guest-login-btn");
        btn.disabled = true;
        setMessage(loginMessage, "正在创建访客账号……", "info");

        var result = await ApiUtils.apiPost("/api/auth/guest", {});

        btn.disabled = false;

        if (!result.ok) {
            setMessage(loginMessage, result.error || "访客登录失败。", "error");
            return;
        }

        SessionUtils.saveSession(result.data.session_token, result.data.user);
        showSuccessPopup(
            result.data.user.username,
            result.data.default_password || "ClapClap",
            true
        );
    });

    // ── 成功弹窗 ──────────────────────────────────

    function showSuccessPopup(username, password, isGuest) {
        var maskedPw = "";
        if (isGuest) {
            // 访客显示明文密码
            maskedPw = password;
        } else {
            // 正常注册显示 *
            maskedPw = "";
            for (var i = 0; i < password.length; i++) {
                maskedPw += "*";
            }
        }

        successTitle.textContent = "注册成功";
        successBody.textContent =
            "用户名：" + username + "\n" +
            "密码：" + maskedPw + "\n" +
            (isGuest ? "这是默认密码，请尽快修改。" : "请妥善保管你的账号信息。");

        successMask.classList.add("show");
    }

    successOkBtn.addEventListener("click", function () {
        window.location.href = "/";
    });

    successMask.addEventListener("click", function (e) {
        if (e.target === successMask) {
            window.location.href = "/";
        }
    });

    // 如果已经登录，直接跳转
    if (SessionUtils.isLoggedIn()) {
        window.location.href = "/";
        return;
    }
};
