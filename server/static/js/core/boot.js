(function () {
    function handleServerBootChange(serverBootId, options = {}) {
        const shouldClearStorage = options.clearStorage === true;
        const savedBootId = localStorage.getItem(STORAGE_KEYS.SERVER_BOOT_ID);

        if (savedBootId === serverBootId) {
            return {
                changed: false
            };
        }

        if (shouldClearStorage) {
            StorageUtils.clearAllClapClapStorage();
        }
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
