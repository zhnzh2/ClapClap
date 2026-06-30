from __future__ import annotations

from app.v1.constants import Move
from app.v1.game import GameEngine
from app.v1.models import GameState


MOVE_INPUT_MAP: dict[str, Move] = {
    "qi": Move.QI,
    "气": Move.QI,

    "shield": Move.SHIELD,
    "dun": Move.SHIELD,
    "盾": Move.SHIELD,

    "gi": Move.GI,
    "po": Move.PO,
    "破": Move.PO,
    "leng_feng": Move.LENG_FENG,
    "lengfeng": Move.LENG_FENG,
    "冷锋": Move.LENG_FENG,
    "rulai": Move.RU_LAI,
    "ru_lai": Move.RU_LAI,
    "如来": Move.RU_LAI,
    "heidong": Move.HEI_DONG,
    "hei_dong": Move.HEI_DONG,
    "黑洞": Move.HEI_DONG,

    "fire": Move.FIRE,
    "shandian": Move.SHAN_DIAN,
    "shan_dian": Move.SHAN_DIAN,
    "闪电": Move.SHAN_DIAN,
    "lieyan": Move.LIE_YAN,
    "lie_yan": Move.LIE_YAN,
    "烈焰": Move.LIE_YAN,
    "shining": Move.SHINING,

    "shizi": Move.SHI_ZI,
    "shi_zi": Move.SHI_ZI,
    "十字": Move.SHI_ZI,
    "bagua": Move.BA_GUA,
    "ba_gua": Move.BA_GUA,
    "八卦": Move.BA_GUA,

    "chi": Move.CHI,
    "你吃": Move.CHI,
    "shuangchi": Move.SHUANG_CHI,
    "shuang_chi": Move.SHUANG_CHI,
    "双吃": Move.SHUANG_CHI,
    "shan": Move.SHAN,
    "闪": Move.SHAN,
    "gao": Move.GAO,
    "镐": Move.GAO,
}


def print_help() -> None:
    print("=" * 60)
    print("拍拍 1.0 双人对战版（命令行测试）")
    print("=" * 60)
    print("可输入动作如下：")
    print("  气 / qi")
    print("  盾 / shield")
    print("  gi")
    print("  破 / po")
    print("  冷锋 / leng_feng")
    print("  如来 / rulai")
    print("  黑洞 / heidong")
    print("  Fire / fire")
    print("  闪电 / shandian")
    print("  烈焰 / lieyan")
    print("  Shining / shining")
    print("  十字 / shizi")
    print("  八卦 / bagua")
    print("  你吃 / chi")
    print("  双吃 / shuangchi")
    print("  闪 / shan")
    print("  镐 / gao")
    print()
    print("其它命令：")
    print("  help      查看帮助")
    print("  state     查看当前状态")
    print("  history   查看全部回合记录")
    print("  restart   重新开始")
    print("  quit      退出程序")
    print("=" * 60)


def format_player_state(name: str, player) -> str:
    return (
        f"{name}: "
        f"HP={player.hp}, "
        f"Qi={player.qi}, "
        f"Shield={player.shield}, "
        f"Spark={player.spark}, "
        f"Battery={player.battery}, "
        f"Pickaxe={player.pickaxe}, "
        f"FlashUsed={player.flash_used}"
    )

def print_state(state: GameState) -> None:
    print("-" * 60)
    print(f"当前回合数：{state.round_num}")
    print(format_player_state("P1", state.p1))
    print(format_player_state("P2", state.p2))
    if state.winner is None:
        print("当前胜负：未结束")
    elif state.winner == 0:
        print("当前胜负：双败 / 平局")
    elif state.winner == 1:
        print("当前胜负：P1 获胜")
    elif state.winner == 2:
        print("当前胜负：P2 获胜")
    print("-" * 60)


def parse_move(text: str) -> Move | None:
    key = text.strip().lower()
    return MOVE_INPUT_MAP.get(key)


def ask_player_move(player_name: str) -> Move | str:
    while True:
        raw = input(f"{player_name} 请输入动作：").strip()

        if raw.lower() in {"help", "state", "history", "restart", "quit"}:
            return raw.lower()

        move = parse_move(raw)
        if move is not None:
            return move

        print("无法识别该动作，请重新输入。输入 help 可查看帮助。")

def print_round_result(state: GameState) -> None:
    log = state.history[-1]

    print("\n" + "=" * 60)
    print(f"第 {log.round_num} 回合结算")
    print("=" * 60)
    print(f"P1 动作：{log.p1_move.value} | 合法：{log.p1_valid}")
    print(f"P2 动作：{log.p2_move.value} | 合法：{log.p2_valid}")
    print()

    if log.p1_note:
        print(f"P1 说明：{log.p1_note}")
    if log.p2_note:
        print(f"P2 说明：{log.p2_note}")

    print()
    print(f"P1 本回合受到伤害：{log.p1_damage_taken}")
    print(f"P2 本回合受到伤害：{log.p2_damage_taken}")

    if log.p1_pickaxe_blocked > 0:
        print(f"P1 的镐抵挡伤害：{log.p1_pickaxe_blocked}")
    if log.p2_pickaxe_blocked > 0:
        print(f"P2 的镐抵挡伤害：{log.p2_pickaxe_blocked}")

    print()
    print(f"回合总结：{log.summary}")
    print()
    print("回合后状态：")
    print(
        f"P1: HP={log.p1_hp_after}, Qi={log.p1_qi_after}, Shield={log.p1_shield_after}, "
        f"Spark={log.p1_spark_after}, Battery={log.p1_battery_after}, "
        f"Pickaxe={log.p1_pickaxe_after}"
    )
    print(
        f"P2: HP={log.p2_hp_after}, Qi={log.p2_qi_after}, Shield={log.p2_shield_after}, "
        f"Spark={log.p2_spark_after}, Battery={log.p2_battery_after}, "
        f"Pickaxe={log.p2_pickaxe_after}"
    )

    print()
    if state.winner is None:
        print("游戏状态：继续")
    elif state.winner == 0:
        print("游戏状态：双败 / 平局")
    elif state.winner == 1:
        print("游戏状态：P1 获胜")
    elif state.winner == 2:
        print("游戏状态：P2 获胜")

    print("=" * 60 + "\n")

def print_history(state: GameState) -> None:
    if not state.history:
        print("当前还没有回合记录。")
        return

    print("\n" + "=" * 60)
    print("全部回合记录")
    print("=" * 60)
    for log in state.history:
        print(f"R{log.round_num}: P1[{log.p1_move.value}] vs P2[{log.p2_move.value}]")
        print(f"  合法性：P1={log.p1_valid}, P2={log.p2_valid}")
        print(f"  伤害：P1={log.p1_damage_taken}, P2={log.p2_damage_taken}")
        if log.p1_note:
            print(f"  P1说明：{log.p1_note}")
        if log.p2_note:
            print(f"  P2说明：{log.p2_note}")
        print(f"  总结：{log.summary}")
        print(
            f"  回合后："
            f"P1(HP={log.p1_hp_after}, Qi={log.p1_qi_after}, Shield={log.p1_shield_after}, "
            f"Spark={log.p1_spark_after}, Battery={log.p1_battery_after}, Pickaxe={log.p1_pickaxe_after}) | "
            f"P2(HP={log.p2_hp_after}, Qi={log.p2_qi_after}, Shield={log.p2_shield_after}, "
            f"Spark={log.p2_spark_after}, Battery={log.p2_battery_after}, Pickaxe={log.p2_pickaxe_after})"
        )
        print("-" * 60)
    print("=" * 60 + "\n")

def print_final_result(state: GameState) -> None:
    print("\n" + "#" * 60)
    print("游戏结束")
    print("#" * 60)

    if state.winner == 0:
        print("最终结果：双败 / 平局")
    elif state.winner == 1:
        print("最终结果：P1 获胜")
    elif state.winner == 2:
        print("最终结果：P2 获胜")
    else:
        print("最终结果：未结束")

    print()
    print("最终状态：")
    print(format_player_state("P1", state.p1))
    print(format_player_state("P2", state.p2))
    print("#" * 60 + "\n")

def main() -> None:
    state = GameState()
    print_help()
    print_state(state)

    command_set = {"help", "state", "history", "restart", "quit"}

    while state.winner is None:
        p1_input = ask_player_move("P1")
        if p1_input in command_set:
            if p1_input == "help":
                print_help()
            elif p1_input == "state":
                print_state(state)
            elif p1_input == "history":
                print_history(state)
            elif p1_input == "restart":
                state = GameState()
                print("已重新开始游戏。")
                print_state(state)
            elif p1_input == "quit":
                print("已退出程序。")
                return
            continue

        p2_input = ask_player_move("P2")
        if p2_input in command_set:
            if p2_input == "help":
                print_help()
            elif p2_input == "state":
                print_state(state)
            elif p2_input == "history":
                print_history(state)
            elif p2_input == "restart":
                state = GameState()
                print("已重新开始游戏。")
                print_state(state)
            elif p2_input == "quit":
                print("已退出程序。")
                return
            continue

        state = GameEngine.resolve_round(state, p1_input, p2_input)
        print_round_result(state)

    print_final_result(state)
    print_history(state)

if __name__ == "__main__":
    main()
