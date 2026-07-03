/**
 * ClapClap 2.0 本地模拟对战 —— 数据层
 *
 * 全局状态变量、常量定义、快捷键映射。
 */

/* ── 全局状态 ────────────────────────────────────────── */
var v2LatestState = null;            // GameStateV2 payload
var v2SettlementResult = null;       // 当前 SettlementStepResult
var v2SelectedMoves = {};            // {player_id: move_name}
var v2FocusedPlayer = null;          // 当前键盘焦点 player_id
var v2PlayerCount = 2;              // 准备阶段的玩家数量
var v2PlayerNames = [];             // 准备阶段的玩家名称
var v2PlayerTypes = [];             // 准备阶段的玩家类型 ["human"|"ai", ...]
var v2AiDifficulty = "normal";      // AI 难度 "random" | "normal"
var v2IsSetupPhase = true;          // 是否在准备阶段
var v2EndShown = false;             // 结束卡片是否已显示
var v2RoundSummaryShown = false;    // 回合总结是否已显示
var v2HumanPlayerIds = [];          // 对局中的人类玩家 ID
var v2AiPlayerIds = [];             // 对局中的 AI 玩家 ID

/* ── 玩家颜色 ────────────────────────────────────────── */
var V2_PLAYER_COLORS = [
    "#2563eb", "#dc2626", "#16a34a",
    "#f59e0b", "#8b5cf6", "#06b6d4"
];

/* ── 设置 ────────────────────────────────────────────── */
var V2_SETTINGS_KEY = "clapclap_v2_ui_settings";
var v2Settings = {
    autoResolve: false,         // 自动决策（默认关闭）
    showHistory: true,
    collapseSettlementLog: true, // 结算日志默认折叠
    compactMode: false,         // 紧凑出招区
};

/* ── 动作快捷键映射 ──────────────────────────────────── */
var V2_KEY_TO_MOVE = {
    /* 锦囊 */
    "1": "CHI", "2": "SHUANG_CHI", "3": "HEI_DONG", "4": "RU_LAI",
    /* 资源与防御 */
    "q": "QI", "w": "SHIELD", "e": "GAO", "r": "SHI_ZI",
    /* 气系攻击 */
    "a": "GI", "s": "PO", "d": "SHAN_DIAN", "f": "LENG_FENG", "g": "SHINING",
    /* 盾系攻击 */
    "z": "LIE_YAN", "x": "FIRE", "c": "SHAN", "v": "BA_GUA",
};

/* ── 动作类别（用于分组显示） ────────────────────────── */
var V2_MOVE_CATEGORIES = [
    { key: "resource", label: "资源", moves: ["QI", "SHIELD", "GAO"] },
    { key: "trick", label: "锦囊", moves: ["CHI", "SHUANG_CHI", "HEI_DONG", "RU_LAI"] },
    { key: "attack_qi", label: "气系攻击", moves: ["GI", "PO", "SHAN_DIAN", "LENG_FENG", "SHINING"] },
    { key: "attack_shield", label: "盾系攻击", moves: ["LIE_YAN", "FIRE"] },
    { key: "defense", label: "防御", moves: ["SHI_ZI", "BA_GUA"] },
    { key: "special", label: "特殊", moves: ["SHAN"] },
];

/* ── 动作中文名 ──────────────────────────────────────── */
var V2_MOVE_LABELS = {
    "GI": "gi", "PO": "破", "SHAN_DIAN": "闪电", "LENG_FENG": "冷锋", "SHINING": "Shining",
    "LIE_YAN": "烈焰", "FIRE": "Fire", "SHAN": "闪",
    "QI": "气", "SHIELD": "盾", "GAO": "加镐",
    "CHI": "你吃", "SHUANG_CHI": "双吃", "HEI_DONG": "黑洞", "RU_LAI": "如来",
    "SHI_ZI": "十字", "BA_GUA": "八卦",
};

/* ── 速度层名称 ──────────────────────────────────────── */
var V2_SPEED_LAYER_NAMES = {
    1: "闪", 2: "三连", 3: "你吃/双吃", 4: "gi攻黑洞",
    5: "黑洞", 6: "如来/Shining", 7: "冷锋/烈焰",
    8: "gi攻击/抢镐", 9: "破/闪电", 10: "Fire",
    11: "gi无目标", 12: "气/盾/加镐",
};

/* ── 死亡原因中文 ───────────────────────────────────── */
var V2_DEATH_LABELS = {
    "normal": "HP归零",
    "boom": "爆镐",
    "ant": "爆气/爆盾",
    "toad": "蛤蟆",
    "fake_toad": "蟆蛤",
    "surrender": "投降",
};

/* ── 设置读写 ────────────────────────────────────────── */
function v2LoadSettings() {
    try {
        var raw = localStorage.getItem(V2_SETTINGS_KEY);
        if (raw) {
            var parsed = JSON.parse(raw);
            v2Settings = Object.assign(v2Settings, parsed);
        }
    } catch (e) {}
}

function v2SaveSettings() {
    try {
        localStorage.setItem(V2_SETTINGS_KEY, JSON.stringify(v2Settings));
    } catch (e) {}
}
