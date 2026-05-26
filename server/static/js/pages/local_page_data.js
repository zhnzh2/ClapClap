var latestState = null;
var selectedP1Move = null;
var selectedP2Move = null;
var keyboardTarget = "p1";
var endModalShownForWinner = null;

const SETTINGS_STORAGE_KEY = "clapclap_ui_settings_v2";

const defaultSettings = {
    compactMode: false,
    showTooltips: true,
    showHistory: true,
    showLatestRound: true,
    coloredResources: false,
    emphasizeLatestRound: false
};

var settings = { ...defaultSettings };

const moveDescriptions = {
    QI: "资源动作。获得 1 气。",
    SHIELD: "资源动作。获得 1 盾。",
    GI: "气系攻击。消耗 1 气，攻击力 1。可抢对方本回合出的镐。",
    PO: "气系攻击。消耗 2 气，攻击力 2。会被你吃 / 双吃针对。",
    LENG_FENG: "气系攻击。消耗 3 气，攻击力 3。",
    RU_LAI: "气系攻击。消耗 5 气，攻击力 4，伤害 2。",
    HEI_DONG: "气系攻击。消耗 8 气，攻击力 5，伤害 3。当前版本不拆分。",
    FIRE: "盾系攻击。消耗 2 盾，攻击力 1.5，并获得 1 火种。",
    SHAN_DIAN: "盾系攻击。消耗 3 盾，攻击力 2，并获得 1 电池。会被你吃 / 双吃针对。",
    LIE_YAN: "盾系攻击。优先消耗 2 火种，否则消耗 4 盾。攻击力 3。",
    SHINING: "盾系攻击。优先消耗 2 电池，否则消耗 6 盾。攻击力 4，伤害 2。会被双吃针对。",
    SHI_ZI: "防御动作。消耗 2 气，防御力 3。",
    BA_GUA: "防御动作。消耗 3 气，防御力 4。",
    CHI: "锦囊动作。消耗 1 气。可针对破、闪电。",
    SHUANG_CHI: "锦囊动作。消耗 2 气。可针对破、闪电、Shining。当前版本不拆分。",
    SHAN: "锦囊动作。每局最多 2 次。使用后完全退出本回合结算。",
    GAO: "锦囊动作。消耗 2 气，获得 1 镐。镐可抵挡伤害，2 个及以上会爆镐。"
};

const fixedKeyMap = {
    CHI: "1",
    SHUANG_CHI: "2",
    SHAN: "3",
    GAO: "4",

    QI: "Q",
    SHIELD: "W",
    SHI_ZI: "E",
    BA_GUA: "R",

    GI: "A",
    PO: "S",
    LENG_FENG: "D",
    RU_LAI: "F",
    HEI_DONG: "G",

    FIRE: "Z",
    SHAN_DIAN: "X",
