(function () {
    function handleServerBootChange(serverBootId) {
        const savedBootId = localStorage.getItem(STORAGE_KEYS.SERVER_BOOT_ID);

        if (savedBootId === serverBootId) {
            return {
                changed: false
            };
        }

        StorageUtils.clearAllClapClapStorage();
        sessionStorage.clear();
        localStorage.setItem(STORAGE_KEYS.SERVER_BOOT_ID, serverBootId);

        return {
            changed: true
        };
    }

    window.BootUtils = {
        handleServerBootChange
    };
})();