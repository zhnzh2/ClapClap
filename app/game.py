from __future__ import annotations

from app.constants import (
    ATTACK_MOVES,
    ATTACK_POWER,
    DAMAGE_VALUE,
    DEFENSE_POWER,
    MOVE_COSTS,
    Move,
    Resource,
)
from app.models import GameState, PlayerState, RoundLog


class GameEngine:
    @staticmethod
    def can_afford(player: PlayerState, move: Move) -> bool:
        if move == Move.LIE_YAN:
            return player.spark >= 2 or player.shield >= 4

        if move == Move.SHINING:
            return player.battery >= 2 or player.shield >= 6

        if move == Move.SHAN:
            return player.can_use_flash()

        cost = MOVE_COSTS[move]

        for resource, amount in cost.items():
            if not GameEngine._get_resource_value(player, resource) >= amount:
                return False

        return True

    @staticmethod
    def consume_cost(player: PlayerState, move: Move) -> None:
        if move == Move.LIE_YAN:
            if player.spark >= 2:
                player.spark -= 2
            else:
                player.shield -= 4
            return

        if move == Move.SHINING:
            if player.battery >= 2:
                player.battery -= 2
            else:
                player.shield -= 6
            return

        if move == Move.SHAN:
            player.flash_used += 1
            return

        cost = MOVE_COSTS[move]
        for resource, amount in cost.items():
            GameEngine._add_resource(player, resource, -amount)

    @staticmethod
    def get_defense_power(move: Move) -> float:
        return DEFENSE_POWER[move]

    @staticmethod
    def _chi_hits(chi_move: Move, target_move: Move) -> bool:
        if chi_move == Move.CHI:
            return target_move in {Move.PO, Move.SHAN_DIAN}

        if chi_move == Move.SHUANG_CHI:
            return target_move in {Move.PO, Move.SHAN_DIAN, Move.SHINING}

        return False

    @staticmethod
    def _attack_is_canceled_by_trick(attack_move: Move, trick_move: Move) -> bool:
        if trick_move == Move.CHI:
            return attack_move in {Move.PO, Move.SHAN_DIAN}

        if trick_move == Move.SHUANG_CHI:
            return attack_move in {Move.PO, Move.SHAN_DIAN, Move.SHINING}

        return False

    @staticmethod
    def resolve_round(state: GameState, p1_move: Move, p2_move: Move) -> GameState:
        if state.winner is not None:
            return state

        state.round_num += 1
        log = RoundLog(
            round_num=state.round_num,
            p1_move=p1_move,
            p2_move=p2_move,
        )

        p1 = state.p1
        p2 = state.p2

        # -------------------------
        # 1. 合法性检查
        # -------------------------
        p1_valid = GameEngine.can_afford(p1, p1_move)
        p2_valid = GameEngine.can_afford(p2, p2_move)
        log.p1_valid = p1_valid
        log.p2_valid = p2_valid

        if not p1_valid and not p2_valid:
            state.winner = 0
            log.summary = "双方动作均非法，双败。"
            GameEngine._fill_log_after(log, state)
            state.history.append(log)
            return state

        if not p1_valid:
            state.winner = 2
            log.summary = "P1 动作非法，P2 获胜。"
            GameEngine._fill_log_after(log, state)
            state.history.append(log)
            return state

        if not p2_valid:
            state.winner = 1
            log.summary = "P2 动作非法，P1 获胜。"
            GameEngine._fill_log_after(log, state)
            state.history.append(log)
            return state

        # -------------------------
        # 2. 扣除消耗
        # -------------------------
        GameEngine.consume_cost(p1, p1_move)
        GameEngine.consume_cost(p2, p2_move)

        # -------------------------
        # 3. 闪：完全退出本回合
        # -------------------------
        p1_flash = p1_move == Move.SHAN
        p2_flash = p2_move == Move.SHAN

        if p1_flash:
            log.p1_note = GameEngine._append_note(log.p1_note, "本回合使用闪，退出结算。")
        if p2_flash:
            log.p2_note = GameEngine._append_note(log.p2_note, "本回合使用闪，退出结算。")

        # -------------------------
        # 4. 基础资源获得 / 特殊资源获得前置标记
        # -------------------------
        p1_lightning_eaten = False
        p2_lightning_eaten = False

        p1_gi_steal_got = False
        p2_gi_steal_got = False

        p1_gain_pickaxe = False
        p2_gain_pickaxe = False

        # 先处理最基础的资源动作
        if not p1_flash and p1_move == Move.QI:
            p1.qi += 1
        if not p2_flash and p2_move == Move.QI:
            p2.qi += 1

        if not p1_flash and p1_move == Move.SHIELD:
            p1.shield += 1
        if not p2_flash and p2_move == Move.SHIELD:
            p2.shield += 1

        # -------------------------
        # 5. 处理锦囊特判
        # -------------------------
        # 吃 / 双吃：第一版不拆分
        # 闪状态下已退出，不参与任何结算

        # 你吃 / 双吃
        if not p1_flash and p1_move in {Move.CHI, Move.SHUANG_CHI} and not p2_flash:
            if GameEngine._chi_hits(p1_move, p2_move):
                if p2_move == Move.PO:
                    log.p1_note += f"{p1_move.value}命中破，对方反噬 1 点伤害。"
                    log.p2_note += f"破被{p1_move.value}命中，反噬 1 点伤害。"
                    log.p2_damage_taken += 1
                elif p2_move == Move.SHAN_DIAN:
                    p2_lightning_eaten = True
                    log.p1_note += f"{p1_move.value}命中闪电。"
                    log.p2_note += f"闪电被{p1_move.value}命中，失效且不获得电池。"
                elif p2_move == Move.SHINING:
                    log.p1_note += "双吃命中 Shining，使其失效。"
                    log.p2_note += "Shining 被双吃命中，失效。"

        if not p2_flash and p2_move in {Move.CHI, Move.SHUANG_CHI} and not p1_flash:
            if GameEngine._chi_hits(p2_move, p1_move):
                if p1_move == Move.PO:
                    log.p2_note += f"{p2_move.value}命中破，对方反噬 1 点伤害。"
                    log.p1_note += f"破被{p2_move.value}命中，反噬 1 点伤害。"
                    log.p1_damage_taken += 1
                elif p1_move == Move.SHAN_DIAN:
                    p1_lightning_eaten = True
                    log.p2_note += f"{p2_move.value}命中闪电。"
                    log.p1_note += f"闪电被{p2_move.value}命中，失效且不获得电池。"
                elif p1_move == Move.SHINING:
                    log.p2_note += "双吃命中 Shining，使其失效。"
                    log.p1_note += "Shining 被双吃命中，失效。"

        # gi 抢镐：只限对方本回合出镐
        if not p1_flash and not p2_flash:
            if p1_move == Move.GI and p2_move == Move.GAO:
                p1_gi_steal_got = True
                log.p1_note += "gi 抢镐成功，自己获得 1 个镐。"
                log.p2_note += "镐被 gi 抢走，本回合无法获得镐。"

            elif p2_move == Move.GI and p1_move == Move.GAO:
                p2_gi_steal_got = True
                log.p2_note += "gi 抢镐成功，自己获得 1 个镐。"
                log.p1_note += "镐被 gi 抢走，本回合无法获得镐。"

        # 正常获得镐
        if not p1_flash and p1_move == Move.GAO and p2_move != Move.GI:
            p1_gain_pickaxe = True

        if not p2_flash and p2_move == Move.GAO and p1_move != Move.GI:
            p2_gain_pickaxe = True

        # -------------------------
        # 6. 处理攻击是否被锦囊直接化解
        # -------------------------
        p1_attack_canceled = False
        p2_attack_canceled = False

        if not p1_flash and not p2_flash:
            if GameEngine._attack_is_canceled_by_trick(p1_move, p2_move):
                p1_attack_canceled = True

            if GameEngine._attack_is_canceled_by_trick(p2_move, p1_move):
                p2_attack_canceled = True

        # -------------------------
        # 7. 资源型副产物
        # -------------------------
        if not p1_flash and p1_move == Move.FIRE:
            p1.spark += 1
        if not p2_flash and p2_move == Move.FIRE:
            p2.spark += 1

        if not p1_flash and p1_move == Move.SHAN_DIAN and not p1_lightning_eaten:
            p1.battery += 1
        if not p2_flash and p2_move == Move.SHAN_DIAN and not p2_lightning_eaten:
            p2.battery += 1

        if p1_gi_steal_got:
            p1.pickaxe += 1
        elif p1_gain_pickaxe:
            p1.pickaxe += 1

        if p2_gi_steal_got:
            p2.pickaxe += 1
        elif p2_gain_pickaxe:
            p2.pickaxe += 1

        # -------------------------
        # 8. 爆镐
        # -------------------------
        if p1.pickaxe >= 2:
            p1.hp = 0
            log.p1_note += "触发爆镐。"
        if p2.pickaxe >= 2:
            p2.hp = 0
            log.p2_note += "触发爆镐。"

        # -------------------------
        # 9. 普通攻防结算
        # -------------------------
        # 只要没闪、没被直接取消，且本身是攻击动作，才参与攻防
        if (
            not p1_flash
            and p1_move in ATTACK_MOVES
            and not p1_attack_canceled
            and not p2_flash
        ):
            p1_power = ATTACK_POWER[p1_move]
            p2_def = GameEngine.get_defense_power(p2_move)

            if p1_power > p2_def:
                log.p2_damage_taken += DAMAGE_VALUE[p1_move]
                log.p1_note = GameEngine._append_note(
                    log.p1_note,
                    f"攻击成立，对 P2 造成 {DAMAGE_VALUE[p1_move]} 点伤害。"
                )
            elif p1_power == p2_def and p2_move in ATTACK_MOVES:
                log.p1_note += "与对方攻击对掉。"

        if (
            not p2_flash
            and p2_move in ATTACK_MOVES
            and not p2_attack_canceled
            and not p1_flash
        ):
            p2_power = ATTACK_POWER[p2_move]
            p1_def = GameEngine.get_defense_power(p1_move)

            if p2_power > p1_def:
                log.p1_damage_taken += DAMAGE_VALUE[p2_move]
                log.p2_note = GameEngine._append_note(
                    log.p2_note,
                    f"攻击成立，对 P1 造成 {DAMAGE_VALUE[p2_move]} 点伤害。"
                )
            elif p2_power == p1_def and p1_move in ATTACK_MOVES:
                log.p2_note += "与对方攻击对掉。"

        # -------------------------
        # 10. 镐挡伤
        # -------------------------
        if log.p1_damage_taken > 0 and p1.pickaxe > 0:
            blocked = min(log.p1_damage_taken, p1.pickaxe)
            log.p1_damage_taken -= blocked
            p1.pickaxe -= blocked
            log.p1_pickaxe_blocked = blocked
            log.p1_note = GameEngine._append_note(
                log.p1_note,
                f"镐抵挡了 {blocked} 点伤害。"
            )

        if log.p2_damage_taken > 0 and p2.pickaxe > 0:
            blocked = min(log.p2_damage_taken, p2.pickaxe)
            log.p2_damage_taken -= blocked
            p2.pickaxe -= blocked
            log.p2_pickaxe_blocked = blocked
            log.p2_note = GameEngine._append_note(
                log.p2_note,
                f"镐抵挡了 {blocked} 点伤害。"
            )

        # -------------------------
        # 11. 扣血
        # -------------------------
        if log.p1_damage_taken > 0 and p1.hp > 0:
            p1.hp -= log.p1_damage_taken

        if log.p2_damage_taken > 0 and p2.hp > 0:
            p2.hp -= log.p2_damage_taken

        # -------------------------
        # 12. 胜负判定
        # -------------------------
        p1_dead = p1.hp <= 0
        p2_dead = p2.hp <= 0

        if p1_dead and p2_dead:
            state.winner = 0
        elif p1_dead:
            state.winner = 2
        elif p2_dead:
            state.winner = 1
        else:
            state.winner = None

        # -------------------------
        # 13. 回合总结
        # -------------------------
        if state.winner == 0:
            if log.summary == "":
                log.summary = "本回合结束，双方死亡，双败。"
        elif state.winner == 1:
            if log.summary == "":
                log.summary = "本回合结束，P1 获胜。"
        elif state.winner == 2:
            if log.summary == "":
                log.summary = "本回合结束，P2 获胜。"
        else:
            if log.summary == "":
                log.summary = "本回合结束，游戏继续。"

        GameEngine._fill_log_after(log, state)
        state.history.append(log)
        return state

    @staticmethod
    def _append_note(old_text: str, new_text: str) -> str:
        if not old_text:
            return new_text
        return old_text + " " + new_text

    @staticmethod
    def _fill_log_after(log: RoundLog, state: GameState) -> None:
        log.p1_hp_after = state.p1.hp
        log.p2_hp_after = state.p2.hp
        log.p1_qi_after = state.p1.qi
        log.p2_qi_after = state.p2.qi
        log.p1_shield_after = state.p1.shield
        log.p2_shield_after = state.p2.shield
        log.p1_spark_after = state.p1.spark
        log.p2_spark_after = state.p2.spark
        log.p1_battery_after = state.p1.battery
        log.p2_battery_after = state.p2.battery
        log.p1_pickaxe_after = state.p1.pickaxe
        log.p2_pickaxe_after = state.p2.pickaxe
        log.winner_after_round = state.winner

    @staticmethod
    def _get_resource_value(player: PlayerState, resource: Resource) -> int:
        if resource == Resource.HP:
            return player.hp
        if resource == Resource.QI:
            return player.qi
        if resource == Resource.SHIELD:
            return player.shield
        if resource == Resource.SPARK:
            return player.spark
        if resource == Resource.BATTERY:
            return player.battery
        if resource == Resource.PICKAXE:
            return player.pickaxe
        raise ValueError(f"未知资源: {resource}")

    @staticmethod
    def _add_resource(player: PlayerState, resource: Resource, amount: int) -> None:
        if resource == Resource.HP:
            player.hp += amount
            return
        if resource == Resource.QI:
            player.qi += amount
            return
        if resource == Resource.SHIELD:
            player.shield += amount
            return
        if resource == Resource.SPARK:
            player.spark += amount
            return
        if resource == Resource.BATTERY:
            player.battery += amount
            return
        if resource == Resource.PICKAXE:
            player.pickaxe += amount
            return
        raise ValueError(f"未知资源: {resource}")