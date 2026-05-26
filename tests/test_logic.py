from __future__ import annotations

import unittest

from app.constants import Move
from app.game import GameEngine
from app.matchmaking import PLAYER_MATCH_STATE, pop_player_match_result
from app.models import GameState


class TestClapClapLogic(unittest.TestCase):
    def test_qi_vs_qi(self):
        state = GameState()
        state = GameEngine.resolve_round(state, Move.QI, Move.QI)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.qi, 1)
        self.assertEqual(state.p2.qi, 1)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p2.hp, 1)

    def test_gi_vs_qi(self):
        state = GameState()
        state.p1.qi = 1

        state = GameEngine.resolve_round(state, Move.GI, Move.QI)

        self.assertEqual(state.winner, 1)
        self.assertEqual(state.p1.qi, 0)
        self.assertLessEqual(state.p2.hp, 0)

    def test_double_illegal_moves(self):
        state = GameState()

        state = GameEngine.resolve_round(state, Move.GI, Move.PO)

        self.assertEqual(state.winner, 0)

    def test_single_illegal_move_p1_loses(self):
        state = GameState()
        state.p2.qi = 1

        state = GameEngine.resolve_round(state, Move.GI, Move.GI)

        self.assertEqual(state.winner, 2)

    def test_single_illegal_move_p2_loses(self):
        state = GameState()
        state.p1.qi = 1

        state = GameEngine.resolve_round(state, Move.GI, Move.GI)

        self.assertEqual(state.winner, 1)

    def test_shield_blocks_gi(self):
        state = GameState()
        state.p2.qi = 1

        state = GameEngine.resolve_round(state, Move.SHIELD, Move.GI)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p2.hp, 1)
        self.assertEqual(state.p1.shield, 1)

    def test_po_breaks_shield(self):
        state = GameState()
        state.p2.qi = 2

        state = GameEngine.resolve_round(state, Move.SHIELD, Move.PO)

        self.assertEqual(state.winner, 2)

    def test_chi_hits_po(self):
        state = GameState()
        state.p1.qi = 1
        state.p2.qi = 2

        state = GameEngine.resolve_round(state, Move.CHI, Move.PO)

        self.assertEqual(state.winner, 1)

    def test_chi_hits_lightning(self):
        state = GameState()
        state.p1.qi = 1
        state.p2.shield = 3

        state = GameEngine.resolve_round(state, Move.CHI, Move.SHAN_DIAN)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p2.battery, 0)

    def test_shuang_chi_hits_shining(self):
        state = GameState()
        state.p1.qi = 2
        state.p2.shield = 6

        state = GameEngine.resolve_round(state, Move.SHUANG_CHI, Move.SHINING)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p2.hp, 1)

    def test_flash_escapes_attack(self):
        state = GameState()
        state.p2.qi = 5

        state = GameEngine.resolve_round(state, Move.SHAN, Move.RU_LAI)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p1.flash_used, 1)

    def test_gi_steals_pickaxe(self):
        state = GameState()
        state.p1.qi = 1
        state.p2.qi = 2

        state = GameEngine.resolve_round(state, Move.GI, Move.GAO)

        self.assertEqual(state.winner, 1)
        self.assertEqual(state.p1.pickaxe_after if False else state.p1.pickaxe, 1)
        self.assertEqual(state.p2.pickaxe, 0)

    def test_pickaxe_blocks_damage(self):
        state = GameState()
        state.p1.pickaxe = 1
        state.p2.qi = 1

        state = GameEngine.resolve_round(state, Move.QI, Move.GI)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p1.pickaxe, 0)

    def test_pickaxe_explodes_at_two(self):
        state = GameState()
        state.p1.qi = 2
        state.p1.pickaxe = 1

        state = GameEngine.resolve_round(state, Move.GAO, Move.QI)

        self.assertEqual(state.winner, 2)

    def test_lie_yan_prefers_spark(self):
        state = GameState()
        state.p1.spark = 2

        state = GameEngine.resolve_round(state, Move.LIE_YAN, Move.QI)

        self.assertEqual(state.p1.spark, 0)
        self.assertEqual(state.p1.shield, 0)
        self.assertEqual(state.winner, 1)

    def test_shining_prefers_battery(self):
        state = GameState()
        state.p1.battery = 2

        state = GameEngine.resolve_round(state, Move.SHINING, Move.QI)

        self.assertEqual(state.p1.battery, 0)
        self.assertEqual(state.p1.shield, 0)
        self.assertEqual(state.winner, 1)

    def test_flash_cannot_be_used_more_than_twice(self):
        state = GameState()
        state.p1.flash_used = 2

        state = GameEngine.resolve_round(state, Move.SHAN, Move.QI)

        self.assertEqual(state.winner, 2)

    def test_history_is_recorded(self):
        state = GameState()
        state = GameEngine.resolve_round(state, Move.QI, Move.QI)

        self.assertEqual(len(state.history), 1)
        self.assertEqual(state.history[0].round_num, 1)
        self.assertEqual(state.history[0].p1_move, Move.QI)
        self.assertEqual(state.history[0].p2_move, Move.QI)

    def test_fire_gains_spark(self):
        state = GameState()
        state.p1.shield = 2

        state = GameEngine.resolve_round(state, Move.FIRE, Move.QI)

        self.assertEqual(state.p1.spark, 1)
        self.assertEqual(state.winner, 1)

    def test_lightning_gains_battery_when_not_eaten(self):
        state = GameState()
        state.p1.shield = 3

        state = GameEngine.resolve_round(state, Move.SHAN_DIAN, Move.QI)

        self.assertEqual(state.p1.battery, 1)
        self.assertEqual(state.winner, 1)

    def test_lightning_no_battery_when_eaten(self):
        state = GameState()
        state.p1.shield = 3
        state.p2.qi = 1

        state = GameEngine.resolve_round(state, Move.SHAN_DIAN, Move.CHI)

        self.assertEqual(state.p1.battery, 0)
        self.assertIsNone(state.winner)

    def test_shi_zi_blocks_leng_feng(self):
        state = GameState()
        state.p1.qi = 2
        state.p2.qi = 3

        state = GameEngine.resolve_round(state, Move.SHI_ZI, Move.LENG_FENG)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p2.hp, 1)

    def test_ru_lai_breaks_shi_zi(self):
        state = GameState()
        state.p1.qi = 2
        state.p2.qi = 5

        state = GameEngine.resolve_round(state, Move.SHI_ZI, Move.RU_LAI)

        self.assertEqual(state.winner, 2)

    def test_ba_gua_blocks_ru_lai(self):
        state = GameState()
        state.p1.qi = 3
        state.p2.qi = 5

        state = GameEngine.resolve_round(state, Move.BA_GUA, Move.RU_LAI)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)

    def test_hei_dong_kills_target(self):
        state = GameState()
        state.p1.qi = 8

        state = GameEngine.resolve_round(state, Move.HEI_DONG, Move.QI)

        self.assertEqual(state.winner, 1)

    def test_attack_equal_power_do_not_damage(self):
        state = GameState()
        state.p1.qi = 2
        state.p2.shield = 3

        state = GameEngine.resolve_round(state, Move.PO, Move.SHAN_DIAN)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.hp, 1)
        self.assertEqual(state.p2.hp, 1)

    def test_shining_hits_for_two_damage(self):
        state = GameState()
        state.p1.battery = 2
        state.p2.hp = 2

        state = GameEngine.resolve_round(state, Move.SHINING, Move.QI)

        self.assertEqual(state.winner, 1)
        self.assertLessEqual(state.p2.hp, 0)

    def test_ru_lai_hits_for_two_damage(self):
        state = GameState()
        state.p1.qi = 5
        state.p2.hp = 2

        state = GameEngine.resolve_round(state, Move.RU_LAI, Move.QI)

        self.assertEqual(state.winner, 1)
        self.assertLessEqual(state.p2.hp, 0)

    def test_state_does_not_change_after_game_over(self):
        state = GameState()
        state.p1.qi = 1

        state = GameEngine.resolve_round(state, Move.GI, Move.QI)
        self.assertEqual(state.winner, 1)

        round_num_before = state.round_num
        p1_hp_before = state.p1.hp
        p2_hp_before = state.p2.hp
        history_len_before = len(state.history)

        state = GameEngine.resolve_round(state, Move.QI, Move.QI)

        self.assertEqual(state.round_num, round_num_before)
        self.assertEqual(state.p1.hp, p1_hp_before)
        self.assertEqual(state.p2.hp, p2_hp_before)
        self.assertEqual(len(state.history), history_len_before)

    def test_flash_second_time_is_still_valid(self):
        state = GameState()
        state.p1.flash_used = 1
        state.p2.qi = 1

        state = GameEngine.resolve_round(state, Move.SHAN, Move.GI)

        self.assertIsNone(state.winner)
        self.assertEqual(state.p1.flash_used, 2)
        self.assertEqual(state.p1.hp, 1)

    def test_game_state_from_empty_dict_starts_at_round_zero(self):
        state = GameState.from_dict({})

        self.assertEqual(state.round_num, 0)

    def test_match_result_returns_room_player_token(self):
        PLAYER_MATCH_STATE["test_match_token"] = {
            "status": "matched",
            "player_name": "Tester",
            "room_id": "ROOM42",
            "seat": "p1",
            "room_player_token": "room-token-42",
            "updated_at": "2026-05-25T00:00:00",
        }

        try:
            result = pop_player_match_result("test_match_token")
        finally:
            PLAYER_MATCH_STATE.pop("test_match_token", None)

        self.assertTrue(result["matched"])
        self.assertEqual(result["room_player_token"], "room-token-42")
        self.assertNotIn("player_token", result)

if __name__ == "__main__":
    unittest.main()
